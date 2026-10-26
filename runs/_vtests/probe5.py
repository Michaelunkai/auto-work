# Dig into drushim dehydratedState.queries for job listings.
import json
import re
import sys
import urllib.parse

sys.path.insert(0, r'F:\backup\ai\work-skill\connector')
import rf  # noqa: E402

url = sys.argv[1] if len(sys.argv) > 1 else 'https://www.drushim.co.il/jobs/search/index.aspx?searchword=' + urllib.parse.quote('devops')
s, f, h = rf.get(url, timeout=30)
m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', h or '', re.S)
data = json.loads(m.group(1))
qs = data.get('props', {}).get('pageProps', {}).get('dehydratedState', {}).get('queries', [])
print('queries:', len(qs))
for i, q in enumerate(qs):
    key = str(q.get('queryKey'))[:120]
    st = q.get('state', {})
    d = st.get('data')
    print(i, 'key=', key, 'data-type=', type(d).__name__, 'len=', (len(d) if hasattr(d, '__len__') else '-'))
    if isinstance(d, dict):
        for k, v in list(d.items())[:10]:
            print('    .', k, type(v).__name__, (len(v) if hasattr(v, '__len__') else ''))
            if isinstance(v, list) and v:
                first = v[0]
                if isinstance(first, dict):
                    print('      first keys:', list(first.keys())[:15])
                    print('      first sample:', json.dumps(first, ensure_ascii=False)[:400])
    if isinstance(d, list) and d and isinstance(d[0], dict):
        print('    first keys:', list(d[0].keys())[:15])
        print('    first sample:', json.dumps(d[0], ensure_ascii=False)[:400])
