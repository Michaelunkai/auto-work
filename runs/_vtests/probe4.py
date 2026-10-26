# Probe drushim __NEXT_DATA__ payload for embedded job listings.
import json
import re
import sys
import urllib.parse

sys.path.insert(0, r'F:\backup\ai\work-skill\connector')
import rf  # noqa: E402

url = 'https://www.drushim.co.il/jobs/search/index.aspx?searchword=' + urllib.parse.quote('devops')
s, f, h = rf.get(url, timeout=30)
h = h or ''
print('status', s, 'len', len(h))
m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', h, re.S)
print('has __NEXT_DATA__:', bool(m))
if m:
    data = json.loads(m.group(1))
    txt = m.group(1)
    # find job-like url fragments inside the payload
    urls = sorted(set(re.findall(r'(?:https://www\.drushim\.co\.il)?/jobs?/[a-z0-9\-]+/?', txt)))
    print('job-like urls in payload:', len(urls))
    for u in urls[:15]:
        print('  ', u[:110])
    # look for job ids / titles
    ids = sorted(set(re.findall(r'"jobId"\s*:\s*(\d+)', txt)))[:10]
    print('jobIds:', ids)
    titles = re.findall(r'"jobTitle"\s*:\s*"([^"]{5,60})"', txt)[:10]
    print('jobTitles sample:', titles)
    # dump keys structure
    def walk(d, depth=0, prefix=''):
        if depth > 3:
            return
        if isinstance(d, dict):
            for k in list(d.keys())[:12]:
                print('  ' * depth + prefix + str(k))
                walk(d[k], depth + 1)
    walk(data.get('props', {}).get('pageProps', {}), 0)
