# DDG html endpoint probe: mine drushim job URLs + FB permalinks, fetch samples.
import re
import sys
import urllib.parse

sys.path.insert(0, r'F:\backup\ai\work-skill\connector')
import rf  # noqa: E402


def ddg(q):
    url = 'https://html.duckduckgo.com/html/?q=' + urllib.parse.quote(q)
    s, f, h = rf.get(url, timeout=25)
    h = h or ''
    print('DDG', q[:50], 'status', s, 'len', len(h))
    # ddg wraps urls in uddg= param
    raw = re.findall(r'uddg=([^&"]+)', h)
    dec = [urllib.parse.unquote(x) for x in raw]
    seen = []
    for u in dec:
        if u not in seen:
            seen.append(u)
    return seen


links = ddg('site:drushim.co.il/job devops')
for u in links[:10]:
    print('  drushim:', u[:110])
jobs = [u for u in links if 'drushim.co.il/job' in u][:2]
for u in jobs:
    try:
        s, f, h = rf.get(u, timeout=25)
    except Exception as e:
        print('job fetch error', repr(e)[:120])
        continue
    h = h or ''
    txt = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', re.sub(r'<(script|style)[^>]*>.*?</\1>', ' ', h, flags=re.S | re.I)))
    mails = re.findall(r'[A-Za-z0-9._+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}', txt)
    cf = re.findall(r'data-cfemail=["\']([0-9a-f]+)', h)
    print('JOB', u[:100], 'status', s, 'len', len(h), 'mails', sorted(set(m.lower() for m in mails))[:5], 'cf', len(cf))
    print('  text[:250]:', txt[:250])

fb = ddg('site:facebook.com/groups devops israel cv')
for u in fb[:10]:
    print('  fb:', u[:120])
