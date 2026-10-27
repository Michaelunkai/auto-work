# Campaign watcher: sleep, then print only NEW progress lines since last call.
import os
import sys
import time

RUNS = r'F:\study\projects\career\job_search\outreach\email\gmail\windows\auto-work\runs'
STATE = os.path.join(os.environ.get('TEMP', '.'), 'aw_watch_state.txt')
KEYS = ('SENDING', 'SENT AND RECONCILED', 'self-notification', 'accepted', 'FINALIZED', 'SHORTFALL', 'ABORTED', 'FOREVER', 'no new verified', 'STALE GATE', 'selftest HARD', 'RUN ABORTED')

wait_s = int(sys.argv[1]) if len(sys.argv) > 1 else 150
mode = sys.argv[2] if len(sys.argv) > 2 else 'any'
HOT = ('SENT AND RECONCILED', 'RUN ABORTED', 'STALE GATE', 'guard', 'exited with')
deadline = time.time() + min(wait_s, 170)

last_len = 0
if os.path.isfile(STATE):
    try:
        last_len = int(open(STATE).read().strip() or 0)
    except Exception:
        last_len = 0


def snapshot():
    dirs = sorted(d for d in os.listdir(RUNS) if d.startswith('auto-'))
    out = []
    for d in dirs:
        lp = os.path.join(RUNS, d, 'auto-run.log')
        if os.path.isfile(lp):
            for ln in open(lp, encoding='utf-8', errors='replace').read().splitlines():
                if any(k in ln for k in KEYS):
                    out.append(d[-6:] + ' ' + ln)
        gp = os.path.join(RUNS, 'guard.log')
    gp = os.path.join(RUNS, 'guard.log')
    if os.path.isfile(gp):
        for ln in open(gp, encoding='utf-8', errors='replace').read().splitlines():
            if any(k in ln for k in HOT):
                out.append('guard ' + ln)
    return out


new = []
while time.time() < deadline:
    out = snapshot()
    new = out[last_len:] if last_len <= len(out) else out
    hot = [l for l in new if any(k in l for k in HOT)]
    if mode == 'sent' and hot:
        break
    if mode == 'any' and new:
        break
    time.sleep(10)

open(STATE, 'w').write(str(len(out)))
print('total:', len(out), '| new:', len(new), '| mode:', mode)
for ln in new[-20:]:
    print(ln[:170])
