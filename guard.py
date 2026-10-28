# AutoWork campaign guard v2 - headless supervisor.
# Owns the forever campaign with zero console footprint (CREATE_NO_WINDOW),
# kills hung runs by log staleness, restarts crashes with exponential backoff,
# and releases half-open completion gates between restarts.
# Launch: pythonw guard.py   (stop: create runs\guard.stop file)
import datetime as dt
import json
import os
import subprocess
import sys
import time
import traceback

AW = os.path.dirname(os.path.abspath(__file__))
RUNS = os.path.join(AW, 'runs')
EXE = os.path.join(AW, 'AutoWork.exe')
PY = r'C:\Users\Admin\AppData\Local\Programs\Python\Python312\python.exe'
GATE = r'F:\backup\ai\work-skill\state\gate\codex-work-completion-gate\active-run.json'
LOG = os.path.join(RUNS, 'guard.log')
CREATE_NO_WINDOW = 0x08000000
STALE_MIN = 15          # no log line for this long while alive = hung -> kill
BACKOFF_S = [20, 60, 180, 600, 1800]


def glog(msg):
    with open(LOG, 'a', encoding='utf-8') as f:
        f.write('[{t}] {m}{n}'.format(t=dt.datetime.now().strftime('%m-%d %H:%M:%S'), m=msg, n='\n'))


def release_gate():
    try:
        with open(GATE, encoding='utf-8-sig') as f:
            g = json.load(f)
        if g.get('active'):
            g['active'] = False
            g['releasedAt'] = dt.datetime.now(dt.timezone.utc).isoformat()
            g['releaseReason'] = 'guard-restart-between-cycles'
            with open(GATE, 'w', encoding='utf-8') as f:
                json.dump(g, f)
            glog('gate released (was half-open)')
    except Exception as e:
        glog('gate release skipped: ' + repr(e)[:100])


def newest_log_mtime():
    newest = 0.0
    try:
        for d in os.listdir(RUNS):
            p = os.path.join(RUNS, d, 'auto-run.log')
            if d.startswith('auto-') and os.path.isfile(p):
                newest = max(newest, os.path.getmtime(p))
    except Exception:
        pass
    return newest


def main():
    glog('guard v2 starting (headless)')
    fails = 0
    while not os.path.isfile(os.path.join(RUNS, 'guard.stop')):
        # The guard owns every campaign process: any gate still active just
        # before a launch is by definition half-open from a dead run.
        release_gate()
        try:
            out = open(os.path.join(RUNS, 'guard-console.log'), 'a', encoding='utf-8', errors='replace')
            proc = subprocess.Popen([EXE, 'forever'], cwd=AW, stdout=out, stderr=subprocess.STDOUT,
                                    creationflags=CREATE_NO_WINDOW)
            glog('campaign started pid=' + str(proc.pid))
        except Exception:
            glog('launch failed: ' + traceback.format_exc()[-300:])
            time.sleep(120)
            continue
        start = time.time()
        while proc.poll() is None:
            time.sleep(30)
            if os.path.isfile(os.path.join(RUNS, 'guard.stop')):
                # Tree-kill while the launcher is alive: proc.kill() alone
                # orphans the onefile app child, which keeps running rounds.
                subprocess.run(['taskkill', '/F', '/T', '/PID', str(proc.pid)], capture_output=True)
                proc.kill()
                glog('guard.stop seen - campaign killed, guard exiting')
                release_gate()
                return
            idle_min = (time.time() - max(newest_log_mtime(), start)) / 60.0
            if idle_min > STALE_MIN:
                glog('campaign HUNG (no log line for ' + str(int(idle_min)) + ' min) - killing for restart')
                # Same rule: tree-kill FIRST - taskkill /T on an already-dead
                # launcher pid finds no children (orphan seen live on 10-28).
                subprocess.run(['taskkill', '/F', '/T', '/PID', str(proc.pid)], capture_output=True)
                try:
                    proc.kill()
                except Exception:
                    pass
                break
        code = proc.returncode
        stable_min = (time.time() - start) / 60.0
        if stable_min > 15:
            fails = 0
        wait = BACKOFF_S[min(fails, len(BACKOFF_S) - 1)]
        fails += 1
        glog('campaign exited code=' + str(code) + ' after ' + str(int(stable_min)) + ' min; restart in ' + str(wait) + 's (fail streak ' + str(fails) + ')')
        release_gate()
        time.sleep(wait)
    glog('guard.stop seen - exiting')


if __name__ == '__main__':
    try:
        main()
    except Exception:
        glog('guard crashed: ' + traceback.format_exc()[-500:])
        sys.exit(1)
