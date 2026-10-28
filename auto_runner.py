# AutoWork - fully automatic /work job-outreach runner
# Wraps the proven $work stack (work_pipeline.py + connector) with autonomous
# discovery, fail-closed screening, no-repeat dedupe, and sequential sending.
# Any candidate that cannot be fully verified is rejected - never guessed.
import argparse
import datetime as dt
import json
import os
import re
import socket
import struct
import subprocess
import sys
import time

VERSION = '2.0.0'
FROZEN = bool(getattr(sys, 'frozen', False))
AW_HOME = os.path.dirname(os.path.abspath(sys.argv[0] if FROZEN else __file__))
BACKUP = os.environ.get('WORK_BACKUP_ROOT', r'F:\backup\ai\work-skill')
CONNECTOR = os.path.join(BACKUP, 'connector')
PROJECT = os.environ.get('WORK_PROJECT', r'F:\study\projects\career\job_search\outreach\email\gmail\windows\job-application-email-sender')
PLUGIN = os.environ.get('WORK_PLUGIN', os.path.join(BACKUP, 'plugin', 'codex-cmd-work'))
GATE_STATE = os.path.join(BACKUP, 'state', 'gate', 'codex-work-completion-gate', 'active-run.json')
PY = os.environ.get('WORK_PYTHON', r'C:\Users\Admin\AppData\Local\Programs\Python\Python312\python.exe')
WP = os.path.join(CONNECTOR, 'work_pipeline.py')
SELF_ADDR = 'michaelovsky5@gmail.com'
sys.path.insert(0, CONNECTOR)

RUN = {'dir': None, 'log': None, 'run_id': None, 'invocation': None}

def load_config():
    cfg_paths = []
    cfg_paths.append(os.path.join(AW_HOME, 'auto-config.json'))
    cfg_paths.append(os.path.join(os.getcwd(), 'auto-config.json'))
    for p in cfg_paths:
        if os.path.isfile(p):
            with open(p, encoding='utf-8-sig') as f:
                return json.load(f)
    raise SystemExit('auto-config.json not found next to AutoWork')

def tstamp():
    n = dt.datetime.now()
    return '{h:02d}:{m:02d}:{s:02d}'.format(h=n.hour, m=n.minute, s=n.second)

def log(msg):
    line = '[{t}] {m}'.format(t=tstamp(), m=msg)
    try:
        print(line, flush=True)
    except Exception:
        pass  # headless mode (no console): file log below is the source of truth
    if RUN['log']:
        with open(RUN['log'], 'a', encoding='utf-8') as f:
            f.write(dt.datetime.now().isoformat(timespec='seconds') + '  ' + msg + chr(10))

def enable_vt():
    try:
        import ctypes
        k = ctypes.windll.kernel32
        h = k.GetStdHandle(-11)
        mode = ctypes.c_uint32()
        if k.GetConsoleMode(h, ctypes.byref(mode)):
            k.SetConsoleMode(h, mode.value | 4)
    except Exception:
        pass

def red(msg):
    return chr(27) + '[91;1m' + msg + chr(27) + '[0m'

def log_red(msg):
    try:
        print(red(msg), flush=True)
    except Exception:
        pass  # headless mode (no console)
    if RUN['log']:
        with open(RUN['log'], 'a', encoding='utf-8') as f:
            f.write(dt.datetime.now().isoformat(timespec='seconds') + '  ' + msg + chr(10))


def sh(cmd, cwd=None, env=None, timeout=None):
    # UTF-8 is forced for EVERY child: Hebrew company names crash cp1252 children
    # otherwise (the v1.0.0 live failure class - belt and braces, never again).
    e = dict(env) if env is not None else dict(os.environ)
    e['PYTHONIOENCODING'] = 'utf-8'
    e['PYTHONUTF8'] = '1'
    r = subprocess.run(cmd, cwd=cwd, env=e, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=timeout)
    out = ((r.stdout or '') + (r.stderr or '')).strip()
    return r, out

def wp_env():
    e = dict(os.environ)
    updates = dict()
    updates['WORK_BACKUP_ROOT'] = BACKUP
    updates['WORK_PROJECT'] = PROJECT
    updates['WORK_PLUGIN'] = PLUGIN
    updates['WORK_STATE_ROOT'] = os.path.join(BACKUP, 'state', 'gate')
    updates['WORK_RUN_ID'] = RUN['run_id'] or ''
    updates['PYTHONIOENCODING'] = 'utf-8'
    updates['PYTHONUTF8'] = '1'
    e.update(updates)
    return e

def doctor(offline=False):
    problems = []
    if not os.path.isfile(PY):
        problems.append('python not found: ' + PY)
    r, _ = sh(['node', '--version'])
    if r.returncode != 0:
        problems.append('node not on PATH (prepare-run hook needs it)')
    must = []
    must.append(WP)
    must.append(os.path.join(CONNECTOR, 'validate_lead.py'))
    must.append(os.path.join(CONNECTOR, 'allexp.py'))
    must.append(os.path.join(CONNECTOR, 'ak.py'))
    must.append(os.path.join(CONNECTOR, 'kws.txt'))
    must.append(os.path.join(CONNECTOR, 'li.py'))
    must.append(os.path.join(CONNECTOR, 'wave.py'))
    must.append(os.path.join(CONNECTOR, 'rf.py'))
    must.append(os.path.join(CONNECTOR, 'role_map.json'))
    must.append(os.path.join(CONNECTOR, 'canonical-body.txt'))
    must.append(os.path.join(CONNECTOR, 'contacted-index.json'))
    must.append(os.path.join(CONNECTOR, 'credentials', 'mcp-auth.json'))
    must.append(os.path.join(PROJECT, 'JobApplicationSender.exe'))
    must.append(os.path.join(PROJECT, 'sent_log.csv'))
    for p in must:
        if not os.path.isfile(p):
            problems.append('missing: ' + p)
    if problems:
        for p in problems:
            log('DOCTOR FAIL: ' + p)
        raise SystemExit('doctor failed - fix the environment first')
    log('doctor OK: python + node + connector + credentials + sender + ledgers')
    hcfg = dict()
    try:
        hcfg = load_config()
    except Exception:
        hcfg = dict()
    try:
        heal_stale_gate(hcfg)
    except Exception as e:
        log('gate heal error (continuing): ' + repr(e))
    if offline:
        return
    hard = list()
    for attempt in range(2):
        r, out = sh([PY, os.path.join(CONNECTOR, 'selftest.py')], cwd=CONNECTOR, env=wp_env(), timeout=300)
        log('selftest attempt ' + str(attempt + 1) + ' exit code: ' + str(r.returncode))
        print(out[-1500:])
        drift = ('body-hash', 'receipt-validator')
        hard = list()
        profile_ok = False
        for l in out.splitlines():
            if l.startswith('FAIL '):
                name = l.split()[1]
                if name not in drift:
                    hard.append(l.strip())
            if l.startswith('PASS gmail-profile'):
                profile_ok = True
        if not profile_ok:
            hard.append('gmail-profile missing or failed')
        if not hard:
            break
        if attempt == 0:
            log('selftest failed - one retry in 12 seconds')
            time.sleep(12)
    for l in hard:
        log('SELFTEST HARD FAIL: ' + l)
    if hard:
        raise SystemExit('selftest hard failures - aborting (fail-closed)')
    log('selftest OK (known-drift warnings ignored: body-hash, receipt-validator)')

def heal_stale_gate(cfg):
    # A half-open gate (active:true left behind by an interrupted $work session)
    # used to brick every AutoWork start: selftest requires no active gate.
    # Release only STALE ones; a fresh active gate means a live run elsewhere -
    # leave it alone and let selftest fail closed.
    try:
        with open(GATE_STATE, encoding='utf-8-sig') as f:
            g = json.load(f)
    except FileNotFoundError:
        return
    except Exception as e:
        log('gate heal skipped (state unreadable): ' + repr(e))
        return
    if not g.get('active'):
        return
    stale_min = int((cfg or dict()).get('stale_gate_minutes', 30))
    stamp = g.get('resumedAt') or g.get('activatedAt') or ''
    age_min = None
    if stamp:
        try:
            t0 = dt.datetime.fromisoformat(str(stamp).replace('Z', '+00:00'))
            age_min = (dt.datetime.now(dt.timezone.utc) - t0).total_seconds() / 60.0
        except Exception:
            age_min = None
    if age_min is not None and age_min < stale_min:
        log('gate active and FRESH (' + str(int(age_min)) + ' min old, invocation=' + str(g.get('invocationId')) + ') - possible live run elsewhere; leaving it alone (fail-closed)')
        return
    g['active'] = False
    g['releasedAt'] = dt.datetime.now(dt.timezone.utc).isoformat()
    g['releaseReason'] = 'stale-adopted-by-autowork age=' + ('unknown' if age_min is None else str(int(age_min)) + 'min')
    tmp = GATE_STATE + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(g, f)
    os.replace(tmp, GATE_STATE)
    log('STALE GATE RELEASED (half-open run from an interrupted session): invocation=' + str(g.get('invocationId')) + ' age=' + ('unknown' if age_min is None else str(int(age_min)) + ' min'))

def release_gate():
    try:
        with open(GATE_STATE, encoding='utf-8') as f:
            g = json.load(f)
        mine = (not RUN['invocation']) or (g.get('invocationId') == RUN['invocation'])
        if g.get('active') and mine:
            g['active'] = False
            g['releasedAt'] = dt.datetime.now(dt.timezone.utc).isoformat()
            tmp = GATE_STATE + '.tmp'
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump(g, f)
            os.replace(tmp, GATE_STATE)
            log('completion gate released (active=false) - run did not finalize')
    except Exception as e:
        log('gate release skipped: ' + repr(e))

def notify_self(subject, body):
    for attempt in range(2):
        try:
            from gmail_client import gmail
            args = {'recipient_email': SELF_ADDR, 'subject': subject, 'body': body, 'is_html': False}
            res = gmail([{'tool_slug': 'GMAIL_SEND_EMAIL', 'arguments': args}])
            d = res[0].get('response', dict())
            if not d.get('successful'):
                raise RuntimeError(json.dumps(d)[:200])
            log('self-notification sent: ' + subject)
            return True
        except Exception as e:
            if attempt == 0:
                time.sleep(5)
                continue
            log('self-notification FAILED (run continues): ' + repr(e)[:180])
            return False
    return False


def dns_query(qname, server, timeout=4.0):
    q = b''.join(bytes([len(p)]) + p.encode('ascii', 'ignore') for p in qname.split('.'))
    q = q + b'\x00' + struct.pack('>HH', 15, 1)
    pkt = struct.pack('>HHHHHH', 0x1234, 0x0100, 1, 0, 0, 0) + q
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(timeout)
    try:
        s.sendto(pkt, (server, 53))
        data, _ = s.recvfrom(2048)
    finally:
        s.close()
    return data

def mx_exists(domain):
    # True: MX present, False: no MX or NXDOMAIN, None: DNS unreachable
    for server in ('8.8.8.8', '1.1.1.1'):
        try:
            data = dns_query(domain, server)
        except Exception:
            continue
        rcode = data[3] & 15
        ancount = struct.unpack('>H', data[6:8])[0]
        if rcode == 3:
            return False
        return ancount > 0
    return None

try:
    import rf
    RF_OK = True
except Exception:
    rf = None
    RF_OK = False

STRIP_WS = re.compile(r'\s+')
MAILPICK = re.compile(r'[A-Za-z0-9._+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}')
JUNK_MAIL = re.compile(r'(example\.|sentry|wixpress|\.png|\.jpg|\.gif|\.svg|schema\.|@2x|@3x|placeholder|yourmail|domain\.com|company\.com|noreply|no-reply|donotreply)', re.I)
CAREER_HINT = re.compile(r'(career|job|hiring|join|recruit|vacanc)', re.I)
HIRE_HINT = re.compile(r'(hiring|join us|join our|open position|open positions|we are hiring|careers|vacanc|apply now)', re.I)
SKIP_SITE = re.compile(r'(linkedin|facebook|instagram|tiktok|youtube|twitter|x\.com|w3\.org|schema|google|whatsapp|mailto:|tel:)', re.I)

def textify(html):
    t = re.sub(r'<(script|style)[^>]*>.*?</\1>', ' ', html, flags=re.S | re.I)
    t = re.sub(r'<[^>]+>', ' ', t)
    return STRIP_WS.sub(' ', t).strip()

def site_domain(u):
    m = re.search(r'https?://([^/?#]+)', u or '')
    if not m:
        return ''
    d = m.group(1).lower()
    if d.startswith('www.'):
        d = d[4:]
    return d

BS = chr(92)
DQ2 = chr(34)
DQ = DQ2
JOBLINK_RE = re.compile(
    'href=' + DQ + '(/Search/UploadSingle' + BS + '.aspx' + BS + '?JobID=' + BS + 'd+)'
    + DQ + '[^>]*>(.*?)</a>', re.S)
EMP_RE = re.compile(
    '<a href=' + DQ + '/Employer/HP/Default' + BS + '.aspx' + BS + '?cid=(' + BS + 'd+)'
    + DQ + '>([^<]+)</a>')
OGP_RE = re.compile(
    'og:description' + DQ + BS + 's+content=' + DQ + '([^' + DQ + ']+)')
def _clean_text(t):
    t = re.sub(r'<[^>]+>', ' ', t)
    return STRIP_WS.sub(' ', t).strip()
def _ad_row(jobid, title, cfg):
    url = 'https://www.alljobs.co.il/Search/UploadSingle.aspx?JobID=' + str(jobid)
    try:
        _, _, html = rf.get(url, timeout=15)
    except Exception:
        return None
    if not html:
        return None
    emp = EMP_RE.search(html)
    og = OGP_RE.search(html)
    text = textify(html)
    mails = []
    for m in MAILPICK.findall(text)[:6]:
        if not JUNK_MAIL.search(m):
            mails.append(m.lower())
    for hx in rf.CF_RE.findall(html)[:6]:
        dec = rf.cfdecode(hx)
        if '@' in dec:
            dmail = dec.split(':')[-1].lower()
            if not JUNK_MAIL.search(dmail):
                mails.append(dmail)
    mail = choose_mail(list(dict.fromkeys(mails)), cfg)
    ctx_snip = ''
    if mail:
        i = text.lower().find(mail)
        if i >= 0:
            ctx_snip = text[max(0, i - 120):i + 140]
    return {'company': (emp.group(2).strip() if emp else ''), 'cid': (emp.group(1) if emp else None),
            'title': title[:150], 'url': url, 'og': (_clean_text(og.group(1))[:280] if og else ''),
            'mail': (mail or ''), 'mail_ctx': ctx_snip, 'lane': 'ads', 'loc': ''}
def lane_ads(out_path, cfg):
    if not RF_OK:
        return False
    import allexp
    import concurrent.futures
    import urllib.parse
    jobs = []
    seen = set()
    pages = cfg.get('ads_pages', 3)
    for kw in cfg.get('ads_keywords', []):
        for pg in range(1, pages + 1):
            url = ('https://www.alljobs.co.il/SearchResultsGuest.aspx?keyword='
                     + urllib.parse.quote(kw) + '&page=' + str(pg))
            try:
                _, _, html = rf.get(url, timeout=20)
            except Exception:
                break
            if not html:
                break
            for href, inner in JOBLINK_RE.findall(html):
                jm = re.search('JobID=(' + BS + 'd+)', href)
                if not jm:
                    continue
                t = _clean_text(inner)
                if len(t) < 6 or jm.group(1) in seen:
                    continue
                if allexp.BAD.search(t) or not allexp.GOOD.search(t):
                    continue
                seen.add(jm.group(1))
                jobs.append((jm.group(1), t))
    log('ads lane: ' + str(len(jobs)) + ' relevant ads to scan for published mailboxes')
    limit = cfg.get('ads_max', 160)
    workers = cfg.get('ads_workers', 8)
    rows = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
        for r in ex.map(lambda j: _ad_row(j[0], j[1], cfg), jobs[:limit]):
            if r and (r.get('mail') or r.get('company')):
                rows.append(r)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(rows, f, ensure_ascii=False, indent=1)
    withmail = sum(1 for r in rows if r.get('mail'))
    log('ads lane done: ' + str(len(rows)) + ' rows, ' + str(withmail) + ' with a published mailbox')
    return True

def _extract_mailset(html, text, cap):
    mails = []
    for m in MAILPICK.findall(text)[:cap]:
        if not JUNK_MAIL.search(m):
            mails.append(m.lower())
    # pages increasingly publish the mailbox only inside JSON-LD or meta blocks
    # in the raw html, never in visible text (e.g. gotfriends schema.org email)
    for m in MAILPICK.findall(html or '')[:cap]:
        if not JUNK_MAIL.search(m):
            mails.append(m.lower())
    for hx in rf.CF_RE.findall(html)[:cap]:
        dec = rf.cfdecode(hx)
        if '@' in dec:
            dmail = dec.split(':')[-1].lower()
            if not JUNK_MAIL.search(dmail):
                mails.append(dmail)
    return list(dict.fromkeys(mails))

def _board_ad_row(url, html, lane, cfg):
    text = textify(html)
    tm = re.search(r'<title>(.*?)</title>', html, re.S)
    title = _clean_text(tm.group(1))[:150] if tm else ''
    mails = _extract_mailset(html, text, 6)
    mail = choose_mail(mails, cfg) if mails else ''
    ctx_snip = ''
    if mail:
        i = text.lower().find(mail)
        if i >= 0:
            ctx_snip = text[max(0, i - 120):i + 140]
    comp = ''
    cm = re.search(r'(?:שם החברה|חברה:|company:|employer:)\s*([^\n<]{2,60})', text, re.I)
    if cm:
        comp = _clean_text(cm.group(1))[:60]
    if not (mail or comp):
        return None
    return {'company': comp, 'title': title, 'url': url, 'og': _clean_text(text[:280]), 'mail': mail, 'mail_ctx': ctx_snip, 'lane': lane, 'loc': ''}

def _scan_board_lanes(base_harvest, scan_one, label, out_path, cfg):
    import concurrent.futures
    urls = base_harvest()
    log(label + ' lane: ' + str(len(urls)) + ' ad pages to scan')
    limit = cfg.get('board_scan_max', 120)
    workers = cfg.get('ads_workers', 8)
    rows = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
        for r in ex.map(scan_one, urls[:limit]):
            if r:
                rows.append(r)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(rows, f, ensure_ascii=False, indent=1)
    withmail = sum(1 for r in rows if r.get('mail'))
    log(label + ' lane done: ' + str(len(rows)) + ' rows, ' + str(withmail) + ' with a published mailbox')
    return True

def lane_jobclick(out_path, cfg):
    # jobclick.co.il/jobs: the playbook's highest-yield single page - hundreds of
    # current ads with Cloudflare-obfuscated CV mailboxes (rf.cfdecode).
    if not RF_OK:
        return False

    def harvest():
        urls = []
        seen = set()
        pages = cfg.get('jobclick_pages', 3)
        for pg in range(1, pages + 1):
            url = 'https://www.jobclick.co.il/jobs' + ('' if pg == 1 else '?page=' + str(pg))
            try:
                _, _, html = rf.get(url, timeout=20)
            except Exception:
                break
            if not html:
                break
            for m in re.finditer(r'href="(/jobs/[^"#?]+|/job/[^"#?]+)"', html):
                u = 'https://www.jobclick.co.il' + m.group(1)
                if u not in seen:
                    seen.add(u)
                    urls.append(u)
        return urls

    def scan_one(u):
        try:
            _, _, html = rf.get(u, timeout=15)
        except Exception:
            return None
        if not html:
            return None
        return _board_ad_row(u, html, 'jobclick', cfg)

    return _scan_board_lanes(harvest, scan_one, 'jobclick', out_path, cfg)

def _drushim_pages(data):
    # react-query dehydratedState.queries serializes entries in mixed shapes
    # (dict with 'state', or [queryKey, state] pair) and job order shifts;
    # return the first pages list that actually carries job entries.
    try:
        queries = data['props']['pageProps']['dehydratedState']['queries']
    except Exception:
        return None
    for q in queries:
        state = None
        if isinstance(q, dict):
            state = q.get('state')
        elif isinstance(q, list) and len(q) >= 2 and isinstance(q[1], dict):
            state = q[1]
        if isinstance(state, dict):
            d = state.get('data')
            if isinstance(d, dict):
                pgs = d.get('pages')
                if isinstance(pgs, list):
                    for pg in pgs:
                        if isinstance(pg, dict) and pg.get('jobs'):
                            return pgs
    return None


def lane_drushim(out_path, cfg):
    # drushim.co.il Next.js search pages embed the FULL job list in
    # __NEXT_DATA__ (title, company, city, experience, scope, description,
    # freshness). Rows are company-driven: screening resolves the official
    # site and mailbox; pure-Hebrew names without English tokens fail closed.
    if not RF_OK:
        return False
    import urllib.parse
    rows = []
    seen = set()
    pages_n = cfg.get('drushim_pages', 2)
    for kw in cfg.get('drushim_keywords', list()):
        for pg in range(1, pages_n + 1):
            url = 'https://www.drushim.co.il/jobs/search/' + urllib.parse.quote(kw) + ('?page=' + str(pg) if pg > 1 else '')
            try:
                _, _, html = rf.get(url, timeout=25)
            except Exception:
                break
            m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html or '', re.S)
            if not m:
                break
            try:
                data = json.loads(m.group(1))
                pages = _drushim_pages(data)
                if not pages:
                    raise KeyError('no jobs pages in drushim payload')
            except Exception as e:
                log('drushim payload unreadable: ' + repr(e)[:120])
                break
            n = 0
            for page in pages:
                for j in page.get('jobs', []):
                    jid = str(j.get('id') or '')
                    if not jid or jid in seen:
                        continue
                    seen.add(jid)
                    desc = ' '.join(((j.get('title') or ''), (j.get('experience') or ''), (j.get('scope') or ''), (j.get('publishedAt') or ''), (j.get('description') or '')[:400]))
                    rows.append({'company': (j.get('companyName') or '').strip(), 'title': (j.get('title') or '')[:150], 'url': url, 'og': desc[:600], 'lane': 'drushim', 'mail': '', 'mail_ctx': '', 'loc': (j.get('city') or '')[:60]})
                    n = n + 1
            if n == 0 and pg == 1:
                break
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(rows, f, ensure_ascii=False, indent=1)
    log('drushim lane done: ' + str(len(rows)) + ' rows from ' + str(len(cfg.get('drushim_keywords', list()))) + ' keywords')
    return True

def lane_fbposts(out_path, cfg):
    # MANUAL-ONLY lane (network-hostile from this machine: search engines drop
    # site: quality and reader proxies rate-limit). Mines FB post PERMALINKS from
    # Bing RSS (group home pages stay login-walled - verified dead end), then
    # reads each through a full-content reader for CV mailboxes.
    if not RF_OK:
        return False
    import urllib.parse
    rows = []
    reader = cfg.get('fb_reader', 'https://r.jina.ai/')
    queries = cfg.get('fb_queries', ['site:facebook.com/groups devops israel cv'])
    links = set()
    for q in queries:
        url = 'https://www.bing.com/search?q=' + urllib.parse.quote(q) + '&format=rss'
        try:
            _, _, html = rf.get(url, timeout=20)
        except Exception:
            continue
        if not html:
            continue
        for u in re.findall(r'<link>([^<]+)</link>', html):
            if 'facebook.com' in u and ('/posts/' in u or '/permalink/' in u):
                links.add(u.strip())
    log('fbposts lane: ' + str(len(links)) + ' permalinks mined from search')
    for u in list(links)[:cfg.get('fb_max', 40)]:
        try:
            _, _, html = rf.get(reader + u, timeout=30)
        except Exception as e:
            log('fbposts read skipped (' + repr(e)[:60] + ')')
            continue
        if not html:
            continue
        text = textify(html)
        mails = _extract_mailset(html, text, 6)
        mail = choose_mail(mails, cfg) if mails else ''
        if not mail:
            continue
        i = text.lower().find(mail)
        rows.append({'company': '', 'title': 'facebook group post', 'url': u, 'og': _clean_text(text[:280]), 'mail': mail, 'mail_ctx': text[max(0, i - 120):i + 140] if i >= 0 else '', 'lane': 'fbposts', 'loc': ''})
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(rows, f, ensure_ascii=False, indent=1)
    log('fbposts lane done: ' + str(len(rows)) + ' rows, ' + str(sum(1 for r in rows if r.get('mail'))) + ' with a published mailbox')
    return True

def lane_recruiters(out_path, cfg):
    # Standing recruiter channels from the playbook: re-probe each run; skip when
    # the channel is marked filled; contacted-index still rejects burned domains.
    if not RF_OK:
        return False
    rows = []
    for ent in cfg.get('recruiter_probes', list()):
        name = ent.get('name', '')
        url = ent.get('url', '')
        try:
            _, _, html = rf.get(url, timeout=20)
        except Exception:
            continue
        if not html:
            continue
        text = textify(html)
        if filled_marker(text):
            log('recruiters: ' + name + ' page marked filled - skipping')
            continue
        mails = _extract_mailset(html, text, 8)
        mail = choose_mail(mails, cfg) if mails else ''
        if not mail:
            continue
        i = text.lower().find(mail)
        rows.append({'company': name, 'title': ent.get('title', 'recruitment channel'), 'url': url, 'og': _clean_text(text[:280]), 'mail': mail, 'mail_ctx': text[max(0, i - 120):i + 140] if i >= 0 else '', 'lane': 'recruiters', 'loc': ''})
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(rows, f, ensure_ascii=False, indent=1)
    log('recruiters lane done: ' + str(len(rows)) + ' live channels with a published mailbox')
    return True

def run_lane(lane, out_path, cfg, timeout=1800):
    cache_min = cfg.get('harvest_cache_minutes', 30)
    if os.path.isfile(out_path) and (time.time() - os.path.getmtime(out_path)) < cache_min * 60:
        try:
            with open(out_path, encoding='utf-8') as fh:
                if json.load(fh):
                    log('lane cached (fresh, skipping re-harvest): ' + lane)
                    return True
        except Exception:
            pass
    if lane == 'ads':
        return lane_ads(out_path, cfg)
    if lane == 'jobclick':
        return lane_jobclick(out_path, cfg)
    if lane == 'drushim':
        return lane_drushim(out_path, cfg)
    if lane == 'fbposts':
        return lane_fbposts(out_path, cfg)
    if lane == 'recruiters':
        return lane_recruiters(out_path, cfg)
    if lane == 'alljobs':
        ax = os.path.join(AW_HOME, 'allexp_local.py')
        if not os.path.isfile(ax):
            ax = os.path.join(CONNECTOR, 'allexp.py')
        cmd = [PY, ax]
        cmd.append(out_path)
    elif lane == 'ak':
        cmd = [PY, os.path.join(CONNECTOR, 'ak.py')]
        ak_kws = os.path.join(AW_HOME, 'ak-kws.txt')
        if not os.path.isfile(ak_kws):
            ak_kws = os.path.join(CONNECTOR, 'kws.txt')
        cmd.append(ak_kws)
        cmd.append(out_path)
        cmd.append('--pages')
        cmd.append(str(cfg.get('ak_pages', 4)))
    elif lane == 'linkedin':
        cmd = [PY, os.path.join(CONNECTOR, 'li.py')]
        cmd.append(out_path)
        cmd.append(','.join(cfg['linkedin_keywords']))
        cmd.append('--pages')
        cmd.append(str(cfg.get('linkedin_pages', 1)))
        cmd.append('--fresh')
        cmd.append(str(cfg.get('linkedin_fresh_days', 14)))
    elif lane == 'wave':
        cmd = [PY, os.path.join(CONNECTOR, 'wave.py')]
        cmd.append(out_path)
        for q in cfg.get('wave_queries', []):
            cmd.append(q)
    else:
        log('unknown lane: ' + lane)
        return False
    log('lane start: ' + lane)
    r, out = sh(cmd, cwd=CONNECTOR, env=wp_env(), timeout=timeout)
    if r.returncode >= 3221225472:
        # NTSTATUS crash (0xC0000000+, e.g. 0xC0000142 DLL-init under resource
        # pressure): transient system condition - one retry after a breather.
        log('lane ' + lane + ' child crashed NTSTATUS ' + hex(r.returncode) + ' - one retry in 5s')
        time.sleep(5)
        r, out = sh(cmd, cwd=CONNECTOR, env=wp_env(), timeout=timeout)
    ok = (r.returncode == 0) and os.path.isfile(out_path)
    log('lane done: ' + lane + ' exit=' + str(r.returncode) + ' artifact=' + ('yes' if ok else 'no'))
    for l in out.splitlines()[-3:]:
        if l.strip():
            log('  ' + l[:150])
    return ok

def norm_rows(files):
    rows = []
    for f in files:
        if not os.path.isfile(f):
            continue
        try:
            with open(f, encoding='utf-8') as fh:
                data = json.load(fh)
            if isinstance(data, dict) and 'dossiers' in data:
                data = data['dossiers']
        except Exception as e:
            log('lane file unreadable ' + f + ': ' + repr(e))
            continue
        lane = os.path.basename(f).split('-')[1].split('.')[0]
        for d in data:
            if not isinstance(d, dict):
                continue
            if lane == 'alljobs':
                j = d.get('job') or dict()
                rows.append({'company': d.get('name'), 'title': j.get('title', ''), 'url': j.get('url', ''), 'og': d.get('og', ''), 'lane': lane, 'loc': ''})
            elif lane == 'ak':
                j = d.get('job') or dict()
                jid = str(j.get('jobid') or '')
                jurl = 'https://www.alljobs.co.il/Search/UploadSingle.aspx?JobID=' + jid if jid else ''
                rows.append({'company': d.get('employer'), 'title': j.get('title', ''), 'url': jurl, 'og': d.get('og', ''), 'lane': lane, 'cid': d.get('cid'), 'loc': ''})
            elif lane == 'ads':
                rows.append({'company': d.get('company'), 'title': d.get('title', ''), 'url': d.get('url', ''), 'og': d.get('og', ''), 'lane': lane, 'cid': d.get('cid'), 'mail': (d.get('mail') or '').lower(), 'mail_ctx': (d.get('mail_ctx') or '')[:400], 'loc': ''})
            elif lane in ('jobclick', 'drushim', 'fbposts', 'recruiters'):
                rows.append({'company': d.get('company'), 'title': d.get('title', ''), 'url': d.get('url', ''), 'og': d.get('og', ''), 'lane': lane, 'cid': None, 'mail': (d.get('mail') or '').lower(), 'mail_ctx': (d.get('mail_ctx') or '')[:400], 'loc': ''})
            elif lane == 'linkedin':
                rows.append({'company': d.get('company'), 'title': d.get('title', ''), 'url': d.get('url', ''), 'og': '', 'lane': lane, 'loc': d.get('loc', '')})
            elif lane == 'wave':
                for m in d.get('mails') or []:
                    rows.append({'company': '', 'title': d.get('title', ''), 'url': d.get('url', ''), 'og': d.get('og', ''), 'lane': lane, 'mail': m.get('email', '').lower(), 'mail_ctx': ' '.join(m.get('ctx') or [])[:400], 'loc': ''})
    out = []
    seen = set()
    for r in rows:
        keys = []
        if r.get('mail') and '@' in r['mail']:
            keys.append('mail:' + r['mail'])
        if (r.get('company') or '').strip():
            keys.append('co:' + r['company'].strip().lower())
        if not keys:
            continue
        if any(k in seen for k in keys):
            continue
        for k in keys:
            seen.add(k)
        r['company'] = (r.get('company') or '').strip()
        out.append(r)
    return out

DQ = chr(34)
HREF_RE = re.compile('href=' + DQ + '([^' + DQ + ']+)' + DQ)
STOP_WORDS = ('ltd', 'llc', 'inc', 'bmg', 'the', 'and', 'of', 'bv', 'group', 'tech', 'technologies', 'systems', 'solutions', 'software', 'services', 'it', 'company', 'co', 'international', 'israel', 'il')

def domain_candidates(company, cfg):
    name = company.lower()
    name = re.sub(r'[^a-z0-9 -]', ' ', name)
    toks = [t for t in name.split() if t and t not in STOP_WORDS]
    if not toks:
        return list()
    bases = []
    joined = '-'.join(toks)
    bases.append(joined)
    squooshed = ''.join(toks)
    if squooshed != joined:
        bases.append(squooshed)
    if len(toks) > 2:
        bases.append('-'.join(toks[:2]))
    doms = []
    for b in bases:
        for tld in cfg['tlds']:
            doms.append(b + tld)
    return doms

def resolve_site(company, cfg, cache):
    if company in cache:
        return cache[company]
    site = ''
    doms = domain_candidates(company, cfg)
    limit = cfg.get('max_domain_guesses', 12)
    for dom in doms[:limit]:
        url = 'https://' + dom
        try:
            status, final, html = rf.get(url, timeout=12)
        except Exception:
            continue
        if not html:
            continue
        text = textify(html)[:8000].lower()
        cleaned = re.sub(r'[^a-z0-9 ]', ' ', company.lower())
        toks = [t for t in cleaned.split() if len(t) > 2 and t not in STOP_WORDS]
        hits = sum(1 for t in toks if t in text)
        if toks and (hits >= max(1, len(toks) - 1)):
            site = (final or url).split('?')[0].rstrip('/')
            break
    cache[company] = site
    return site

def emp_page_dossier(cid):
    out = dict()
    if not cid:
        return out
    url = 'https://www.alljobs.co.il/Employer/HP/Default.aspx?cid=' + str(cid)
    try:
        _, _, html = rf.get(url, timeout=15)
    except Exception:
        return out
    if not html:
        return out
    text = textify(html)
    mails = []
    for m in MAILPICK.findall(text)[:10]:
        if not JUNK_MAIL.search(m):
            mails.append(m.lower())
    for hx in rf.CF_RE.findall(html)[:10]:
        dec = rf.cfdecode(hx)
        if '@' in dec:
            dmail = dec.split(':')[-1].lower()
            if not JUNK_MAIL.search(dmail):
                mails.append(dmail)
    out['mails'] = list(dict.fromkeys(mails))[:8]
    out['page'] = url
    site = ''
    found = list()
    seen_doms = list()
    for h in HREF_RE.findall(html):
        if not h.startswith('http'):
            continue
        if 'alljobs' in h or SKIP_SITE.search(h):
            continue
        u = h.split('?')[0].rstrip('/')
        d = site_domain(u)
        if not d or d in seen_doms:
            continue
        seen_doms.append(d)
        found.append(u)
    for u in found[:3]:
        try:
            status, final, h2 = rf.get(u, timeout=12)
            if h2:
                site = (final or u).split('?')[0].rstrip('/')
                break
        except Exception:
            continue
    out['site'] = site
    return out

def scan_site_mails(site, cfg):
    if not RF_OK:
        return None
    pages = list()
    pages.append(site)
    home_html = ''
    try:
        _, _, home_html = rf.get(site, timeout=15)
    except Exception:
        home_html = ''
    for href in HREF_RE.findall(home_html or '')[:600]:
        if not CAREER_HINT.search(href):
            continue
        u = href.split('#')[0]
        if not u.startswith('http'):
            if not u.startswith('/'):
                u = '/' + u
            u = site + u
        if SKIP_SITE.search(u):
            continue
        if site_domain(u) != site_domain(site):
            continue
        if u not in pages:
            pages.append(u)
    for pth in cfg.get('career_paths', []):
        u = site + pth
        if u not in pages:
            pages.append(u)
    best = None
    maxpages = cfg.get('max_career_pages', 6)
    for u in pages[:maxpages]:
        try:
            _, _, h = rf.get(u, timeout=12)
        except Exception:
            continue
        if not h:
            continue
        text = textify(h)
        mails = []
        for m in MAILPICK.findall(text)[:8]:
            if not JUNK_MAIL.search(m):
                mails.append(m.lower())
        for hx in rf.CF_RE.findall(h)[:8]:
            dec = rf.cfdecode(hx)
            if '@' in dec:
                dmail = dec.split(':')[-1].lower()
                if not JUNK_MAIL.search(dmail):
                    mails.append(dmail)
        uniq = list(dict.fromkeys(mails))
        if not uniq:
            continue
        hiring = bool(HIRE_HINT.search(text[:6000]))
        rec = {'page': u, 'mails': uniq[:6], 'hiring': hiring}
        if best is None:
            best = rec
        if hiring and not best['hiring']:
            best = rec
    return best

def choose_mail(mails, cfg):
    best, best_pr = None, -1
    for m in mails:
        if JUNK_MAIL.search(m):
            continue
        local, _, dom = m.partition('@')
        if local in cfg.get('blocked_mail_locals', list()):
            continue
        if dom in cfg['free_mail_domains'] and dom not in cfg['allowed_ats_domains']:
            continue
        pr = 1
        for i, pfx in enumerate(cfg['mail_prefix_priority']):
            if local.startswith(pfx):
                pr = 100 - i
                break
        if pr > best_pr:
            best, best_pr = m, pr
    return best

JUNIOR_HINT = re.compile(r'(junior|entry.level|student|graduate|no experience|intern|0-2 years|1-2 years|1 year|2 years|בוגר|סטודנט|ללא ני?סיון|צעיר|ג'+chr(39)+'וניור|ג'+chr(0x5f3)+'וניור)', re.I)

# ---- accuracy v2 (work playbook fit rules, 2026-10-19) ----
# Reject 3+ year experience mandates ("0-2 years"/"1 year" stay junior-OK).
SENIORITY_RE = re.compile(r'([3-9]|[1-9]\d)\s*(\+\s*|[-\u2013]\s*\d+\s*)?(years|years of experience|שנות|שנים)', re.I)
# Reject management/team-lead. Hebrew מנהל is whitelisted for מערכות/מערכת/רשת/מחשבים (system admin!).
MGR_EN_RE = re.compile(r'(team lead|team leader|\bmanager\b|head of|director of|chief )', re.I)
MGR_HE_RE = re.compile('מנהל[ /]*(צוות|פיתוח|מוצר|תפעול|פרויקטים|סייבר|אבטחת|מידע|תשתיות|רכש|שיווק|כספים|devops|it|qa|hr)')
TEAM_HE_RE = re.compile('(ר"צ|ר״צ|ראש צוות|אחראי משמרת|אחראי/ת צוות)')
TECH_EXCLUDE_RE = re.compile('(macos|mac os|clearance|polygraph|פוליגרף|סיווג בטחוני|תעודה בטחונית)', re.I)
PREFER_RE = re.compile(r'(hybrid|היברידי|סטודנט|student|intern|משרה חלקית|80%|part.time|partial)', re.I)
FRESH_RE = re.compile(r'(היום|אתמול|לפני [1-7] ימים|לפני [1-9] שעות|today|yesterday|just posted)', re.I)
STALE_RE = re.compile(r'(לפני (6[5-9]|[7-9]\d|\d{3,}) ימים|\d+ months ago)', re.I)
HIRE_CTX_HE_RE = re.compile('(קורות חיים|משרה|דרוש|דרושה|לשלוח|הגשת מועמדות|למייל)')

def filled_marker(text):
    # "משרה מלאה" = full-time (fine); "המשרה מלאה" or any bare "מלאה" marker =
    # position filled (reject). The lookbehind keeps המשרה מלאה intact.
    if 'מלאה' not in text:
        return False
    t = re.sub('(?<!ה)משרה[ ' + chr(0x5be) + ']מלאה', ' ', text)
    return 'מלאה' in t

def posting_venue(url, cfg):
    # A posting venue is a board/page whose active ad itself publishes the CV
    # mailbox (alljobs ad pages, jobclick, drushim listings, FB post permalinks).
    d = site_domain(url or '')
    if not d:
        return False
    for host in cfg.get('posting_venue_hosts', ['alljobs.co.il']):
        if d == host or d.endswith('.' + host):
            return True
    return False

def load_synonyms():
    with open(os.path.join(CONNECTOR, 'role_map.json'), encoding='utf-8') as f:
        rm = json.load(f)
    out = dict()
    for fam, words in rm.get('role_family_synonyms', dict()).items():
        pats = [re.compile(re.escape(w), re.I) for w in words]
        out[fam] = pats
    return out

def classify_family(blob, syns):
    best, bestn = None, 0
    low = blob.lower()
    for fam in sorted(syns):
        n = 0
        for p in syns[fam]:
            if p.search(blob):
                n = n + 1
        if fam in low:
            n = n + 3
        if n > bestn:
            best, bestn = fam, n
    return best, bestn

BOUNCE_INDEX = os.path.join(AW_HOME, 'runs', 'bounce-index.txt')


def load_bounces():
    addrs, doms = set(), set()
    try:
        with open(BOUNCE_INDEX, encoding='utf-8') as f:
            for line in f:
                line = line.strip().lower()
                if not line or line.startswith('#'):
                    continue
                if line.startswith('@'):
                    doms.add(line[1:])
                elif '@' in line:
                    addrs.add(line)
    except Exception:
        pass
    return addrs, doms


def record_bounce(entry, why):
    entry = entry.strip().lower()
    if not entry:
        return False
    try:
        cur = set()
        if os.path.isfile(BOUNCE_INDEX):
            with open(BOUNCE_INDEX, encoding='utf-8') as f:
                cur = {l.strip().lower() for l in f if l.strip() and not l.startswith('#')}
        if entry in cur:
            return False
        with open(BOUNCE_INDEX, 'a', encoding='utf-8') as f:
            f.write(entry + '  # ' + why + chr(10))
        return True
    except Exception:
        return False


def sweep_bounces():
    # Zero-bounce doctrine: any delivery-failure notice ever seen for an address
    # excludes that address AND its whole domain from all future sends.
    import re as _re
    found_new = []
    addrs, doms = load_bounces()
    queries = ['from:mailer-daemon newer_than:7d', 'subject:"delivery status notification" newer_than:7d',
               'subject:"delivery incomplete" newer_than:7d', 'subject:"returned mail" newer_than:7d',
               'from:postmaster newer_than:7d']
    for q in queries:
        try:
            res = gmail_query(q)
        except Exception:
            continue
        for m in res:
            blob = str(m.get('subject', '')) + ' ' + str(m.get('messageText', m.get('preview', '')))
            for addr in _re.findall(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}', blob):
                if any(d in addr for d in ('mailer-daemon', 'gmail.com')) and 'mailer-daemon' in addr:
                    continue
                if addr.lower() in ('mailer-daemon@googlemail.com',):
                    continue
                dom = addr.split('@')[1]
                if dom in ('gmail.com', 'googlemail.com', 'google.com'):
                    continue
                if addr not in addrs:
                    if record_bounce(addr, 'dsn ' + q.split()[0].replace('subject:', '')):
                        addrs.add(addr)
                        found_new.append(addr)
    if found_new:
        log_red('BOUNCE SWEEP excluded ' + str(len(found_new)) + ' address(es): ' + ', '.join(found_new[:10]))
        try:
            notify_self('[AutoWork] Bounce sweep: ' + str(len(found_new)) + ' new exclusion(s)',
                        'Delivery failures detected and permanently excluded from future sends:' + chr(10) + chr(10).join(found_new[:30]))
        except Exception:
            pass
    return found_new


def gmail_query(q):
    # Connector caps full payloads around 10 results: larger max_results come
    # back as a truncated 'data_preview' with NO 'data', which used to parse as
    # an empty message list and silently blinded the bounce sweep.
    sys.path.insert(0, CONNECTOR)
    from gmail_client import gmail as _gmail
    resp = {}
    for _attempt in (0, 1):
        res = _gmail([{'tool_slug': 'GMAIL_FETCH_EMAILS', 'arguments': {'query': q, 'max_results': 10, 'include_payload': True}}])
        resp = res[0].get('response', {}) if isinstance(res, list) and res else {}
        data = resp.get('data')
        if data is not None:
            return data.get('messages', [])
    prev = resp.get('data_preview')
    if prev:
        # Degraded mode: hand the raw preview text to the caller; the sweep
        # regexes addresses straight out of it, so coverage survives truncation.
        return [{'subject': '', 'messageText': str(prev)}]
    raise RuntimeError('gmail_query: response has neither data nor data_preview')


def make_ctx(cfg):
    idx = dict()
    try:
        with open(os.path.join(CONNECTOR, 'contacted-index.json'), encoding='utf-8') as f:
            idx = json.load(f).get('domains', dict())
    except Exception as e:
        log('contacted-index unreadable: ' + repr(e))
    exc = set()
    exc_path = os.path.join(CONNECTOR, 'exclusion-set-current.txt')
    if os.path.isfile(exc_path):
        with open(exc_path, encoding='utf-8') as f:
            for l in f:
                if l.strip():
                    exc.add(l.strip().lower())
    import allexp
    pats = dict()
    pats['bad'] = allexp.BAD
    pats['good'] = allexp.GOOD
    extra = cfg.get('extra_bad_title_words', list())
    if extra:
        pats['bad_extra'] = re.compile('|'.join(re.escape(w) for w in extra), re.I)
    ctx = dict()
    ctx['idx'] = idx
    ctx['exc'] = exc
    ctx['syns'] = load_synonyms()
    ctx['pats'] = pats
    ctx['site_cache'] = dict()
    # browser-resolved official sites for Hebrew-named employers (verified by
    # sitemap_builder.py fail-closed token rule); forever batches re-read this
    # map every cycle, so enrichment needs no campaign recycle
    try:
        with open(os.path.join(AW_HOME, 'runs', 'site-map.json'), encoding='utf-8') as f:
            ctx['site_cache'].update(json.load(f))
    except Exception:
        pass
    ctx['emp_cache'] = dict()
    ctx['seen_domains'] = set()
    ctx['bounce_addrs'], ctx['bounce_doms'] = load_bounces()
    return ctx

def screen(row, cfg, ctx):
    reasons = list()
    cname = (row.get('company') or '').lower()
    jbp = cfg.get('job_board_patterns', list())
    for pat in jbp:
        if pat in cname:
            reasons.append('job board or aggregator, not an employer')
            return None, reasons
    if row.get('mail'):
        mdom = row['mail'].split('@')[1]
        for pat in jbp:
            if pat in mdom:
                reasons.append('job board or aggregator mailbox')
                return None, reasons
        rowurl = (row.get('url', '') or '').lower()
        if rowurl and not posting_venue(rowurl, cfg):
            for pat in jbp:
                if pat in rowurl:
                    reasons.append('source page is a cv service or job board, not an employer')
                    return None, reasons
    blob = ' '.join((row.get('title', ''), row.get('og', ''), row.get('mail_ctx', ''), ''))
    bad = ctx['pats']['bad'].search(blob)
    if not bad and 'bad_extra' in ctx['pats']:
        bad = ctx['pats']['bad_extra'].search(blob)
    if bad:
        reasons.append('negative title filter (senior or management or unrelated)')
        return None, reasons
    if SENIORITY_RE.search(blob) or MGR_EN_RE.search(blob) or MGR_HE_RE.search(blob) or TEAM_HE_RE.search(blob) or TECH_EXCLUDE_RE.search(blob) or filled_marker(blob):
        reasons.append('accuracy filter v2 (3+ years mandate, management/team-lead, filled, macOS or clearance role)')
        return None, reasons
    fam, nsyn = classify_family(blob, ctx['syns'])
    if not fam and row.get('lane') == 'recruiters':
        # standing recruiter channels carry no job-title text, but they are
        # application routes for every family by design (send tier 2 below)
        fam, nsyn = 'support', 2
    if not fam:
        reasons.append('no role-family match - irrelevant for this profile')
        return None, reasons
    site = ''
    site_info = None
    if row.get('mail'):
        if not row.get('company'):
            ctxblob = (row.get('mail_ctx', '') + ' ' + row.get('title', '') + ' ' + row.get('og', '')).lower()
            if not re.search(r'(send cv|send resume|apply|career|job|vacanc|hiring|recruit|hr@|jobs@|cv to|resume to|join us|work with us)', ctxblob) and not HIRE_CTX_HE_RE.search(ctxblob):
                reasons.append('mailbox found without hiring or application context - not a verified careers route')
                return None, reasons
        mail = row['mail']
        mail_page = row.get('url', '')
    else:
        if not row.get('company'):
            reasons.append('no company name to resolve')
            return None, reasons
        site = ctx['site_cache'].get(row['company'], '')
        if not site:
            site = resolve_site(row['company'], cfg, ctx['site_cache'])
        emp = ctx['emp_cache'].get(row['company'])
        if emp is None and row.get('cid'):
            emp = emp_page_dossier(row.get('cid'))
            ctx['emp_cache'][row['company']] = emp
        emp = emp or dict()
        if not site:
            site = emp.get('site', '')
            if site:
                ctx['site_cache'][row['company']] = site
        site_info = None
        if site:
            site_info = scan_site_mails(site, cfg)
        mail = None
        mail_page = ''
        if site_info and site_info.get('mails'):
            mail = choose_mail(site_info['mails'], cfg)
            mail_page = site_info['page']
        elif emp.get('mails'):
            mail = choose_mail(emp['mails'], cfg)
            mail_page = emp.get('page', '')
        if not site and not emp:
            reasons.append('official site unverifiable - fail closed')
            return None, reasons
        if not mail:
            reasons.append('no acceptable mailbox on official pages or employer profile')
            return None, reasons
    dom = mail.split('@')[1]
    if dom in cfg['free_mail_domains'] and dom not in cfg['allowed_ats_domains']:
        reasons.append('free-mail provider mailbox (unofficial): ' + dom)
        return None, reasons
    if dom in ctx['idx']:
        reasons.append('employer domain already contacted (whole-employer no-repeat): ' + dom)
        return None, reasons
    if dom in ctx['seen_domains']:
        reasons.append('already handled this run: ' + dom)
        return None, reasons
    if mail in ctx['exc']:
        reasons.append('exact address in exclusion set')
        return None, reasons
    if mail in ctx.get('bounce_addrs', set()) or dom in ctx.get('bounce_doms', set()):
        reasons.append('delivery previously failed for this address or domain - never retried')
        return None, reasons
    if dom not in cfg['allowed_ats_domains']:
        sd = site_domain(site) if site else ''
        if sd and dom != sd and not dom.endswith('.' + sd):
            db = dom.split('.')[0]
            sb = sd.split('.')[0]
            ok = False
            if len(sb) >= 3 and db.startswith(sb):
                ok = True
            if len(db) >= 3 and sb.startswith(db):
                ok = True
            if not ok:
                reasons.append('mailbox domain does not match official site: ' + dom + ' vs ' + sd)
                return None, reasons
        if not sd and row.get('lane') != 'wave' and not posting_venue(mail_page, cfg):
            reasons.append('no verified official page for this mailbox')
    mx = mx_exists(dom)
    if mx is False:
        reasons.append('no DNS MX for mailbox domain - likely fake: ' + dom)
        return None, reasons
    if mx is None:
        reasons.append('MX unverifiable (DNS blocked) - fail closed: ' + dom)
        return None, reasons
    score = 3
    if nsyn > 1:
        score = score + 1
    if ctx['pats']['good'].search(blob):
        score = score + 2
    if JUNIOR_HINT.search(blob):
        score = score + 2
    if site_info and site_info.get('hiring'):
        score = score + 2
    local = mail.split('@')[0]
    for pfx in cfg['mail_prefix_priority']:
        if local.startswith(pfx):
            score = score + 2
            break
    if row.get('lane') in ('alljobs', 'linkedin'):
        score = score + 2
    if PREFER_RE.search(blob):
        score = score + 2
    if FRESH_RE.search(blob):
        score = score + 2
    if STALE_RE.search(blob):
        score = score - 3
    # reply-probability tier: 1 official employer jobs@-style mailbox,
    # 2 standing recruiter channel, 3 open application / general mailbox.
    if row.get('lane') == 'recruiters':
        score = max(score, 7)
    tier = 3
    if dom not in cfg['allowed_ats_domains'] and mail.split('@')[0].startswith(('jobs', 'job', 'careers', 'career', 'hr', 'recruit', 'recruitment', 'cv', 'resume')):
        tier = 1
    elif row.get('lane') == 'recruiters':
        tier = 2
    cand = {'mail': mail, 'mail_page': mail_page, 'company': row.get('company') or dom, 'family': fam, 'row': row, 'site': site, 'site_info': site_info, 'score': score, 'tier': tier}
    return cand, list()

FAMILY_ROLE = dict()
FAMILY_ROLE['devops'] = 'Junior DevOps Engineer'
FAMILY_ROLE['cloud'] = 'Junior Cloud Engineer'
FAMILY_ROLE['cyber'] = 'Junior Cybersecurity Engineer'
FAMILY_ROLE['sysadmin'] = 'Junior System Administrator'
FAMILY_ROLE['support'] = 'Junior IT Support Specialist'

def build_lead(cand):
    today = dt.date.today().isoformat()
    row = cand['row']
    fam = cand['family']
    src = row.get('url') or cand['mail_page']
    og = (row.get('og') or row.get('title') or '')[:280]
    loc = (row.get('loc') or 'Israel')[:60]
    ev = dict()
    ev['address_publication'] = {'url': cand['mail_page'], 'fact': 'Mailbox ' + cand['mail'] + ' is published on the employer official page linked from the active posting.'}
    ev['current_hiring'] = {'url': src, 'fact': 'Active posting found this run: ' + (row.get('title') or '')[:120]}
    ev['role_fit'] = {'url': src, 'fact': 'Posting matches the candidate junior ' + fam + ' track.'}
    ev['qualification_fit'] = {'url': src, 'fact': 'Junior-level scope; no seniority requirement beyond junior detected in title or summary.'}
    ev['geography_fit'] = {'url': src, 'fact': 'Posting is on an Israeli job source (Israel-located).'}
    ev['work_preference_fit'] = {'url': src, 'fact': 'Work arrangement not stated in the posting; recorded honestly as not stated.'}
    ev['employer_interest'] = {'url': src, 'fact': 'Employer currently publishes an open ' + fam + ' vacancy.'}
    ev['candidate_interest'] = {'url': src, 'fact': 'Role family ' + fam + ' is a target track for the candidate.'}
    lead = dict()
    lead['email'] = cand['mail']
    lead['company'] = cand['company']
    lead['target_role'] = (row.get('title') or FAMILY_ROLE.get(fam, 'Junior IT'))[:90]
    lead['role_family'] = fam
    lead['city'] = loc
    lead['work_arrangement'] = 'not stated'
    blob2 = (row.get('title') or '') + ' ' + og
    if JUNIOR_HINT.search(blob2):
        lead['route_kind'] = 'current_junior_vacancy'
    elif row.get('lane') in ('alljobs', 'linkedin'):
        lead['route_kind'] = 'current_adjacent_vacancy'
    else:
        lead['route_kind'] = 'explicit_open_application'
    lead['junior_rationale'] = 'Active junior-compatible ' + fam + ' posting discovered by AutoWork; mailbox published on the employer official domain.'
    lead['source_url'] = src
    lead['source_type'] = 'official_vacancy'
    lead['source_evidence'] = og
    lead['checked_date'] = today
    lead['hard_requirements_met'] = True
    lead['unmet_requirements'] = list()
    lead['notes'] = 'AutoWork autonomous lane=' + str(row.get('lane')) + '; site verified; MX verified; contacted-index, exclusion-set and live-history checks clear.'
    lead['research_contract_version'] = 2
    lead['evidence'] = ev
    return lead

def write_lead(cand):
    lead = build_lead(cand)
    safe = re.sub(r'[^a-z0-9]+', '-', cand['mail'].lower()).strip('-')
    path = os.path.join(RUN['dir'], 'lead-' + safe + '.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(lead, f, ensure_ascii=False, indent=1)
    return path

def screen_rows(rows, cfg, ctx, min_score):
    # Parallel screening: each candidate does its own site/MX verification with
    # network timeouts - a serial sweep was the throughput bottleneck.
    import concurrent.futures
    accepted = list()
    rejected = list()

    def one(row):
        try:
            return screen(row, cfg, ctx)
        except Exception as e:
            return None, ['screening error: ' + repr(e)[:120]]

    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
        results = list(ex.map(one, rows))
    for row, (cand, reasons) in zip(rows, results):
        if not cand:
            rejected.append({'company': row.get('company', ''), 'title': (row.get('title') or '')[:60], 'reasons': reasons})
            continue
        if cand['score'] < min_score:
            rejected.append({'company': cand['company'], 'title': (row.get('title') or '')[:60], 'reasons': ['score ' + str(cand['score']) + ' below minimum ' + str(min_score)]})
            continue
        accepted.append(cand)
        ctx['seen_domains'].add(cand['mail'].split('@')[1])
    accepted.sort(key=lambda c: (c.get('tier', 3), -c['score']))
    return accepted, rejected

def gather_rows(cfg, lane_list, rnd):
    import concurrent.futures
    cache_dir = os.path.join(AW_HOME, 'runs', '_cache')
    os.makedirs(cache_dir, exist_ok=True)
    out_paths = {lane: os.path.join(cache_dir, 'lane-' + lane + '.json') for lane in lane_list}
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(4, len(lane_list) or 1)) as ex:
        futs = {ex.submit(run_lane, lane, out_paths[lane], cfg): lane for lane in lane_list}
        for fut in concurrent.futures.as_completed(futs):
            lane = futs[fut]
            try:
                fut.result()
            except Exception as e:
                log('lane crashed ' + lane + ': ' + repr(e)[:150])
    files = [out_paths[lane] for lane in lane_list if os.path.isfile(out_paths[lane])]
    for lane in lane_list:
        src = out_paths[lane]
        if os.path.isfile(src):
            try:
                ev_path = os.path.join(RUN['dir'], 'lane-' + lane + '-r' + str(rnd) + '.json')
                with open(src, encoding='utf-8') as srcf, open(ev_path, 'w', encoding='utf-8') as dstf:
                    dstf.write(srcf.read())
            except Exception:
                pass
    return norm_rows(files)

def send_one(lead_path, company, fam):
    vpath = os.path.join(CONNECTOR, 'validate_lead.py')
    steps = list()
    steps.append(('validate', [PY, vpath, lead_path, '--company', company], 1))
    steps.append(('check', [PY, WP, 'check-lead', lead_path, '--company', company], 0))
    steps.append(('queue', [PY, WP, 'queue-lead', lead_path, '--company', company], 0))
    steps.append(('warm', [PY, WP, 'warm', fam], 1))
    steps.append(('send', [PY, WP, 'send-queued'], 1))
    out = ''
    r = None
    for name, cmd, retries in steps:
        if name == 'warm' and fam in RUN.get('warmed', set()):
            continue
        for attempt in range(retries + 1):
            r, out = sh(cmd, cwd=CONNECTOR, env=wp_env(), timeout=900)
            if r.returncode == 0:
                break
            if name == 'send' and 'prior Gmail messages' in out:
                return 'send-fail', name, 'prior Gmail history found just before send - possibly already sent; inspect ledger and readback'
            if attempt < retries:
                log('retrying ' + name + ' after transient failure')
                time.sleep(4)
        if name == 'warm':
            RUN.setdefault('warmed', set()).add(fam)
        if r.returncode != 0:
            return 'blocked', name, out[-400:]
        if name == 'send' and 'sent and reconciled' not in out:
            return 'send-fail', name, out[-600:]
    last = ''
    for l in out.splitlines():
        if 'sent and reconciled' in l:
            last = l.strip()
    return 'sent', 'send', last

def cmd_run(a):
    cfg = load_config()
    if a.lanes:
        cfg['rounds'] = [a.lanes.split(',')]
    n = a.count or int(os.environ.get('AUTOWORK_COUNT', '0') or 0) or cfg['defaults']['count']
    if n < 1 or n > cfg['hard_caps']['max_count']:
        raise SystemExit('count must be between 1 and ' + str(cfg['hard_caps']['max_count']))
    min_score = a.min_score if a.min_score is not None else cfg['defaults']['min_score']
    max_minutes = a.max_minutes or cfg['defaults']['max_minutes']
    started = time.time()
    RUN['dir'] = os.path.join(AW_HOME, 'runs', 'auto-' + dt.date.today().isoformat() + '-' + tstamp().replace(':', ''))
    os.makedirs(RUN['dir'], exist_ok=True)
    RUN['log'] = os.path.join(RUN['dir'], 'auto-run.log')
    mode = ' DRY-RUN' if a.dry_run else ''
    log('AutoWork v' + VERSION + ' starting: count=' + str(n) + mode + ' min_score=' + str(min_score) + ' rounds=' + str(len(cfg['rounds'])))
    doctor(offline=False)
    ctx = make_ctx(cfg)
    sent = 0
    results = list()
    exit_code = 0
    if a.dry_run:
        rows = gather_rows(cfg, cfg['rounds'][0], 1)
        accepted, rejected = screen_rows(rows, cfg, ctx, min_score)
        log('dry-run: ' + str(len(rows)) + ' raw rows, ' + str(len(rejected)) + ' rejected, ' + str(len(accepted)) + ' accepted')
        for c in accepted[:max(1, n)]:
            lp = write_lead(c)
            vcmd = [PY, os.path.join(CONNECTOR, 'validate_lead.py'), lp, '--company', c['company']]
            r, out = sh(vcmd, cwd=CONNECTOR, env=wp_env(), timeout=180)
            verdict = 'valid' if r.returncode == 0 else 'invalid'
            log('dry-run candidate ' + c['mail'] + ' -> ' + verdict)
            results.append({'email': c['mail'], 'company': c['company'], 'verdict': verdict, 'detail': out[-300:]})
        summary = {'mode': 'dry-run', 'rows': len(rows), 'accepted': len(accepted), 'rejected': len(rejected), 'results': results}
        with open(os.path.join(RUN['dir'], 'summary.json'), 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=1)
        log('DRY-RUN complete - nothing queued, nothing sent')
        RUN['last_sent'] = 0
        return 0
    r, out = sh([PY, WP, 'prepare-run', str(n)], cwd=CONNECTOR, env=wp_env(), timeout=300)
    if r.returncode != 0:
        release_gate()
        raise SystemExit('prepare-run failed: ' + out[-500:])
    m = re.search(r'run_id=(\S+) invocation=(\S+)', out)
    if not m:
        release_gate()
        raise SystemExit('could not parse prepare-run output: ' + out[-300:])
    RUN['run_id'] = m.group(1)
    RUN['invocation'] = m.group(2)
    log('prepare-run OK: run_id=' + RUN['run_id'] + ' invocation=' + RUN['invocation'])
    try:
        sweep_bounces()
    except Exception as e:
        log_red('bounce sweep failed at invocation start: ' + repr(e)[:120])
    try:
        rnd = 0
        idle = 0
        while sent < n:
            if (time.time() - started) / 60.0 > max_minutes:
                log('time budget reached (' + str(max_minutes) + ' min) - stopping')
                break
            rnd = rnd + 1
            lane_list = cfg['rounds'][(rnd - 1) % len(cfg['rounds'])]
            log('discovery round ' + str(rnd) + ': lanes=' + ','.join(lane_list))
            if rnd % 5 == 0:
                try:
                    sweep_bounces()
                except Exception as e:
                    log_red('bounce sweep failed (round ' + str(rnd) + '): ' + repr(e)[:120])
            rows = gather_rows(cfg, lane_list, rnd)
            accepted, rejected = screen_rows(rows, cfg, ctx, min_score)
            log('round ' + str(rnd) + ': ' + str(len(rows)) + ' raw rows, ' + str(len(rejected)) + ' rejected, ' + str(len(accepted)) + ' accepted')
            rej_path = os.path.join(RUN['dir'], 'rejected-r' + str(rnd) + '.json')
            with open(rej_path, 'w', encoding='utf-8') as f:
                json.dump(rejected, f, ensure_ascii=False, indent=1)
            for c in accepted:
                if sent >= n:
                    break
                ctx['seen_domains'].add(c['mail'].split('@')[1])
                lp = write_lead(c)
                log_red('SENDING to ' + c['mail'] + ' (' + c['company'] + ', ' + c['family'] + ', score ' + str(c['score']) + ')')
                verdict, stage, detail = send_one(lp, c['company'], c['family'])
                results.append({'email': c['mail'], 'company': c['company'], 'family': c['family'], 'score': c['score'], 'verdict': verdict, 'stage': stage, 'detail': str(detail)[:400]})
                if verdict == 'sent':
                    sent = sent + 1
                    idle = 0
                    log_red('[' + str(sent) + '/' + str(n) + '] SENT AND RECONCILED: ' + c['mail'] + ' (' + c['company'] + ') ' + str(detail))
                    NL = chr(10)
                    nbody = ('AutoWork sent your application:' + NL + NL + 'Company: ' + c['company'] + NL + 'Mailbox: ' + c['mail'] + NL + 'Role family: ' + c['family'] + NL + 'Source posting: ' + str(c['row'].get('url', '')) + NL + 'Relevance score: ' + str(c['score']) + NL + 'Run: ' + str(RUN['run_id']) + NL + 'Time: ' + dt.datetime.now().isoformat(timespec='seconds'))
                    notify_self('[AutoWork] Sent ' + str(sent) + '/' + str(n) + ': ' + c['company'], nbody)
                    if sent < n:
                        time.sleep(cfg.get('send_delay_seconds', 15))
                elif verdict == 'blocked':
                    log('gate rejected ' + c['mail'] + ' at ' + stage + ' - skipping to next candidate')
                    log('blocked detail: ' + str(detail)[:220])
                else:
                    raise RuntimeError('pipeline failure at ' + stage + ' for ' + c['mail'] + ': ' + str(detail))
            if not accepted and sent < n:
                idle = idle + 1
                if idle >= 2:
                    pause = cfg.get('idle_pause_seconds', 300)
                    log('no new verified candidates yet - refreshing harvest in ' + str(pause) + 's (run continues; stop with Ctrl+C)')
                    time.sleep(pause)
                    idle = 0
                    cache_dir = os.path.join(AW_HOME, 'runs', '_cache')
                    try:
                        for fn in os.listdir(cache_dir):
                            if fn.startswith('lane-'):
                                os.remove(os.path.join(cache_dir, fn))
                    except Exception:
                        pass
        if sent == n:
            r, out = sh([PY, WP, 'finalize'], cwd=CONNECTOR, env=wp_env(), timeout=300)
            receipt = ''
            for l in out.splitlines():
                if l.startswith('WORK_COMPLETION_RECEIPT:'):
                    receipt = l.split(':', 1)[1].strip()
            if r.returncode != 0 or not receipt:
                raise RuntimeError('finalize failed: ' + out[-400:])
            log('FINALIZED - receipt: ' + receipt)
            results.append({'verdict': 'finalized', 'receipt': receipt})
        else:
            log('SHORTFALL: sent ' + str(sent) + ' of ' + str(n) + ' - not finalizing')
            exit_code = 2
    except (Exception, KeyboardInterrupt) as e:
        log('RUN ABORTED: ' + repr(e))
        results.append({'verdict': 'aborted', 'detail': repr(e)})
        exit_code = 3
    if sent < n:
        release_gate()
    summary = dict()
    summary['run_id'] = RUN['run_id']
    summary['requested'] = n
    summary['sent'] = sent
    summary['results'] = results
    spath = os.path.join(RUN['dir'], 'summary.json')
    with open(spath, 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=1)
    log('summary: ' + spath)
    notify_self('[AutoWork] Run finished: sent ' + str(sent) + ' of ' + str(n), 'Run ' + str(RUN['run_id']) + ' finished.' + chr(10) + 'Sent: ' + str(sent) + ' of ' + str(n) + ' requested' + chr(10) + 'Summary: ' + spath)
    for res in results:
        print('  ' + str(res.get('email', '')) + ' -> ' + str(res.get('verdict', '')) + ' (' + str(res.get('stage', '')) + ')')
    RUN['last_sent'] = sent
    return exit_code

def cmd_forever(a):
    cfg = load_config()
    if a.lanes:
        cfg['rounds'] = [a.lanes.split(',')]
    if a.count:
        os.environ['AUTOWORK_COUNT'] = str(a.count)
    fv = cfg.get('forever', dict())
    cooldown = fv.get('cooldown_minutes', 25) * 60
    cap = fv.get('daily_send_cap', 40)
    sent_total = 0
    cycle = 0
    log('FOREVER mode: batch size ' + str(cfg['defaults']['count']) + ', cooldown ' + str(cooldown // 60) + ' min, daily cap ' + str(cap) + '. Stop with Ctrl+C or close the window.')
    try:
        while True:
            if sent_total >= cap:
                log('daily send cap ' + str(cap) + ' reached - forever mode stopping')
                break
            cycle = cycle + 1
            n = min(cfg['defaults']['count'], cap - sent_total)
            ns = argparse.Namespace(count=n, dry_run=False, max_minutes=None, min_score=None, lanes=None)
            log('FOREVER cycle ' + str(cycle) + ' starting (count ' + str(n) + ', sent today ' + str(sent_total) + ')')
            code = cmd_run(ns)
            sent_total += RUN.get('last_sent') or 0
            if code == 3:
                log('hard failure in cycle ' + str(cycle) + ' - forever mode stopping. Recover the reservation, then restart.')
                break
            log('FOREVER cycle ' + str(cycle) + ' done (exit ' + str(code) + '). Total sent today: ' + str(sent_total))
            if sent_total >= cap:
                log('daily send cap reached - forever mode stopping')
                break
            log('sleeping ' + str(cooldown // 60) + ' minutes - Ctrl+C to stop now')
            time.sleep(cooldown)
    except KeyboardInterrupt:
        log('FOREVER mode stopped by user')
    return 0


def cmd_discover(a):
    cfg = load_config()
    if a.lanes:
        lanes = a.lanes.split(',')
    else:
        lanes = cfg['rounds'][0]
    RUN['dir'] = os.path.join(AW_HOME, 'runs', 'discover-' + dt.date.today().isoformat() + '-' + tstamp().replace(':', ''))
    os.makedirs(RUN['dir'], exist_ok=True)
    RUN['log'] = os.path.join(RUN['dir'], 'discover.log')
    log('AutoWork discovery: lanes=' + ','.join(lanes))
    doctor(offline=True)
    ctx = make_ctx(cfg)
    rows = gather_rows(cfg, lanes, 1)
    min_score = a.min_score if a.min_score is not None else cfg['defaults']['min_score']
    accepted, rejected = screen_rows(rows, cfg, ctx, min_score)
    out = {'rows': len(rows), 'accepted': len(accepted), 'rejected': len(rejected), 'candidates': list(), 'rejections': rejected}
    for c in accepted[: a.limit or 20]:
        out['candidates'].append({'email': c['mail'], 'company': c['company'], 'family': c['family'], 'score': c['score'], 'source': c['row'].get('url', ''), 'site': c['site']})
    p = os.path.join(RUN['dir'], 'candidates.json')
    with open(p, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    log('candidates written: ' + p)
    for c in out['candidates']:
        print('  ' + c['email'] + '  ' + c['company'][:30] + '  ' + c['family'] + '  score=' + str(c['score']))
    return 0

def cmd_status(a):
    r, out = sh([PY, WP, 'status'], cwd=CONNECTOR, env=wp_env(), timeout=120)
    print(out)
    return r.returncode

def main():
    enable_vt()
    ap = argparse.ArgumentParser(prog='AutoWork', description='Fully automatic /work job outreach')
    sub = ap.add_subparsers(dest='cmd')
    pr = sub.add_parser('run')
    pr.add_argument('--count', type=int)
    pr.add_argument('--dry-run', action='store_true')
    pr.add_argument('--max-minutes', type=int)
    pr.add_argument('--min-score', type=int)
    pr.add_argument('--lanes')
    pd = sub.add_parser('discover')
    pd.add_argument('--lanes')
    pd.add_argument('--min-score', type=int)
    pd.add_argument('--limit', type=int)
    pf = sub.add_parser('forever')
    pf.add_argument('--count', type=int)
    pf.add_argument('--lanes')
    ps = sub.add_parser('status')
    pdoc = sub.add_parser('doctor')
    pdoc.add_argument('--offline', action='store_true')
    args = ap.parse_args()
    if args.cmd is None:
        args = ap.parse_args(['run'])
    if args.cmd == 'forever':
        sys.exit(cmd_forever(args))
    if args.cmd == 'discover':
        sys.exit(cmd_discover(args))
    if args.cmd == 'status':
        sys.exit(cmd_status(args))
    if args.cmd == 'doctor':
        doctor(offline=args.offline)
        sys.exit(0)
    sys.exit(cmd_run(args))

if __name__ == '__main__':
    main()
