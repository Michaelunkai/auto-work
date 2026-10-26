# AutoWork v2.0.0 offline verification battery - no network, no sends, no ledger edits.
# Run: python runs\_vtests\test_v2.py  (exit 0 = all green)
import json
import os
import sys
import tempfile

AW_HOME = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, AW_HOME)

import auto_runner as ar  # noqa: E402

ok = 0
fail = 0


def check(name, cond, detail=''):
    global ok, fail
    if cond:
        ok += 1
        print('PASS ' + name)
    else:
        fail += 1
        print('FAIL ' + name + ' ' + str(detail))


PY = ar.PY

# 1. UTF-8 hardening: Hebrew through sh() child (the v1.0.0/02:17 crash class)
r, out = ar.sh([PY, '-c', 'print("טלזר 019")'])
check('hebrew-print', r.returncode == 0 and 'טלזר 019' in out, out[-200:])
# and with an explicitly empty-ish env (grandchild belt-and-braces)
r, out = ar.sh([PY, '-c', 'print("טלזר 019")'], env={'SystemRoot': os.environ.get('SystemRoot', '')})
check('hebrew-print-clean-env', r.returncode == 0 and 'טלזר 019' in out, out[-200:])

# 2. heal_stale_gate unit test on a temp state file
with tempfile.TemporaryDirectory() as td:
    st = os.path.join(td, 'active-run.json')
    real_gate = ar.GATE_STATE
    try:
        ar.GATE_STATE = st
        import datetime as dtm
        stale = {'active': True, 'activatedAt': (dtm.datetime.now(dtm.timezone.utc) - dtm.timedelta(hours=3)).isoformat(), 'invocationId': 'unit-stale'}
        with open(st, 'w', encoding='utf-8') as f:
            json.dump(stale, f)
        ar.heal_stale_gate({'stale_gate_minutes': 30})
        g = json.load(open(st, encoding='utf-8'))
        check('heal-stale-released', g.get('active') is False and 'stale-adopted' in g.get('releaseReason', ''), g)
        fresh = {'active': True, 'activatedAt': dtm.datetime.now(dtm.timezone.utc).isoformat(), 'invocationId': 'unit-fresh'}
        with open(st, 'w', encoding='utf-8') as f:
            json.dump(fresh, f)
        ar.heal_stale_gate({'stale_gate_minutes': 30})
        g = json.load(open(st, encoding='utf-8'))
        check('heal-fresh-untouched', g.get('active') is True, g)
    finally:
        ar.GATE_STATE = real_gate

# 3. accuracy v2 fixtures
check('seniority-3y-reject', bool(ar.SENIORITY_RE.search('requires 3 years of experience')))
check('seniority-3-5y-reject', bool(ar.SENIORITY_RE.search('3-5 years')))
check('seniority-he-reject', bool(ar.SENIORITY_RE.search('5 שנות ניסיון')))
check('seniority-junior-ok', not ar.SENIORITY_RE.search('0-2 years experience') and not ar.SENIORITY_RE.search('1 year'))
check('mgr-en-reject', bool(ar.MGR_EN_RE.search('IT Team Leader')))
check('mgr-he-sysadmin-ok', not ar.MGR_HE_RE.search('מנהל מערכות ורשתות Windows'))
check('mgr-he-lead-reject', bool(ar.MGR_HE_RE.search('מנהל צוות תפעול')))
check('team-he-reject', bool(ar.TEAM_HE_RE.search('ראש צוות תשתיות')))
check('macos-reject', bool(ar.TECH_EXCLUDE_RE.search('macOS administrator')))
check('filled-reject', ar.filled_marker('המשרה מלאה'))
check('fulltime-ok', not ar.filled_marker('משרה מלאה בתל אביב'))
check('junior-he-hint', bool(ar.JUNIOR_HINT.search('משרת ג' + chr(39) + 'וניור')))
check('prefer-hybrid', bool(ar.PREFER_RE.search('עבודה היברידית')))
check('fresh-today', bool(ar.FRESH_RE.search('פורסם היום')) or bool(ar.FRESH_RE.search('היום')))
check('stale-old', bool(ar.STALE_RE.search('לפני 90 ימים')))
check('hire-ctx-he', bool(ar.HIRE_CTX_HE_RE.search('לשלוח קורות חיים למייל')))

# 4. posting_venue allowlist
cfg = {'posting_venue_hosts': ['alljobs.co.il', 'jobclick.co.il', 'drushim.co.il', 'facebook.com', 'fb.com']}
check('venue-alljobs', ar.posting_venue('https://www.alljobs.co.il/Search/UploadSingle.aspx?JobID=1', cfg))
check('venue-jobclick', ar.posting_venue('https://www.jobclick.co.il/jobs/xyz', cfg))
check('venue-fb', ar.posting_venue('https://www.facebook.com/groups/123/permalink/456', cfg))
check('venue-random-reject', not ar.posting_venue('https://www.some-employer.co.il/careers', cfg))

# 5. choose_mail rules (blocked local, free-mail, prefix priority)
cm_cfg = {'blocked_mail_locals': ['sales', 'webmaster'], 'free_mail_domains': ['gmail.com'], 'allowed_ats_domains': [], 'mail_prefix_priority': ['jobs', 'hr', 'info']}
check('choose-mail-prefix', ar.choose_mail(['info@acme.co.il', 'jobs@acme.co.il'], cm_cfg) == 'jobs@acme.co.il')
check('choose-mail-freemail', ar.choose_mail(['jobs@gmail.com'], cm_cfg) is None)
check('choose-mail-blocked-local', ar.choose_mail(['sales@acme.co.il'], cm_cfg) is None)

# 6. norm_rows dedupe + new-lane row shapes
with tempfile.TemporaryDirectory() as td:
    f1 = os.path.join(td, 'lane-jobclick.json')
    with open(f1, 'w', encoding='utf-8') as f:
        json.dump([{'company': 'Acme', 'title': 'Junior DevOps', 'url': 'https://www.jobclick.co.il/jobs/1', 'og': 'hiring junior', 'mail': 'jobs@acme.co.il', 'mail_ctx': 'send cv to jobs@', 'lane': 'jobclick', 'loc': ''}], f)
    rows = ar.norm_rows([f1])
    check('normrows-jobclick', len(rows) == 1 and rows[0]['mail'] == 'jobs@acme.co.il' and rows[0]['lane'] == 'jobclick', rows)

# 7. tier ordering contract
accepted = [{'mail': 'info@b.co.il', 'score': 9, 'tier': 3}, {'mail': 'jobs@a.co.il', 'score': 7, 'tier': 1}, {'mail': 'hr@r.co.il', 'score': 8, 'tier': 2}]
accepted.sort(key=lambda c: (c.get('tier', 3), -c['score']))
check('tier-order', [c['mail'] for c in accepted] == ['jobs@a.co.il', 'hr@r.co.il', 'info@b.co.il'], accepted)

# 8. config sanity for v2 keys
cfgf = json.load(open(os.path.join(AW_HOME, 'auto-config.json'), encoding='utf-8'))
check('cfg-min-score-6', cfgf['defaults']['min_score'] == 6)
check('cfg-stale-gate', cfgf['defaults']['stale_gate_minutes'] == 30)
check('cfg-cap-100', cfgf['forever']['daily_send_cap'] == 100)
check('cfg-rounds-new-lanes', all(any(l in rnd for l in ('jobclick', 'drushim', 'fbposts')) for rnd in cfgf['rounds']))
check('cfg-no-linkedin-wave-defaults', all('linkedin' not in rnd and 'wave' not in rnd for rnd in cfgf['rounds']))
check('cfg-venues', 'jobclick.co.il' in cfgf['posting_venue_hosts'])

print()
print(str(ok) + ' passed, ' + str(fail) + ' failed')
sys.exit(1 if fail else 0)
