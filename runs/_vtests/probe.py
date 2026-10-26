# Lane structure probe: fetch a URL and dump status, length, href sample, mail sample.
# Usage: python probe.py <url> [href_regex]
import re
import sys

sys.path.insert(0, r'F:\backup\ai\work-skill\connector')
import rf  # noqa: E402

url = sys.argv[1]
pat = sys.argv[2] if len(sys.argv) > 2 else r'href=["\']([^"\']+)["\']'
try:
    s, f, h = rf.get(url, timeout=30)
except Exception as e:
    print('FETCH ERROR', repr(e)[:200])
    sys.exit(0)
h = h or ''
print('status', s, 'final', (f or '')[:100], 'len', len(h))
hrefs = re.findall(pat, h)
uniq = []
for x in hrefs:
    if x not in uniq:
        uniq.append(x)
print('matches', len(hrefs), 'unique', len(uniq))
for u in uniq[:35]:
    print('  ', u[:130])
mails = re.findall(r'[A-Za-z0-9._+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}', re.sub(r'<[^>]+>', ' ', h))
print('plain mails:', sorted(set(m.lower() for m in mails))[:10])
cf = re.findall(r'data-cfemail=["\']([0-9a-f]+)["\']', h)
print('cfemail count:', len(cf))
