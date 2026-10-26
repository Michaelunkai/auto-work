# Full drushim job object + pagination + job-page mailbox probe.
import json
import re
import sys
import urllib.parse

sys.path.insert(0, r'F:\backup\ai\work-skill\connector')
import rf  # noqa: E402

BASE = 'https://www.drushim.co.il/jobs/search/' + urllib.parse.quote(sys.argv[1] if len(sys.argv) > 1 else 'devops')
s, f, h = rf.get(BASE, timeout=30)
m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', h or '', re.S)
data = json.loads(m.group(1))
pages = data['props']['pageProps']['dehydratedState']['queries'][1]['state']['data']['pages']
pg0 = pages[0]
print('count:', pg0.get('count'), 'totalPages:', pg0.get('totalPages'), 'jobs in page:', len(pg0.get('jobs', [])))
j0 = pg0['jobs'][0]
print('FULL JOB:', json.dumps(j0, ensure_ascii=False, indent=1)[:1200])
for j in pg0.get('jobs', [])[:8]:
    print('-', j.get('id'), '|', j.get('title'), '|', j.get('companyName'), '|', j.get('city'), '| exp', j.get('experienceId'))

# job page probe: try common URL shapes for the first job id
jid = j0.get('id')
for shape in ('https://www.drushim.co.il/job/' + str(jid) + '/',
              'https://www.drushim.co.il/jobs/' + str(jid) + '/',
              'https://www.drushim.co.il/job/' + str(jid)):
    try:
        s2, f2, h2 = rf.get(shape, timeout=20)
    except Exception as e:
        print('shape', shape[-25:], 'error', repr(e)[:80])
        continue
    h2 = h2 or ''
    print('shape', shape[-25:], 'status', s2, 'final', (f2 or '')[:80], 'len', len(h2))
    if len(h2) > 20000:
        txt = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', re.sub(r'<(script|style)[^>]*>.*?</\1>', ' ', h2, flags=re.S | re.I)))
        mails = re.findall(r'[A-Za-z0-9._+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}', txt)
        print('   mails:', sorted(set(x.lower() for x in mails))[:6])
        print('   text[:300]:', txt[:300])
        break
