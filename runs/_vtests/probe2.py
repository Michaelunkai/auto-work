# Sitemap + job-page probe for drushim lane tuning.
import re
import sys

sys.path.insert(0, r'F:\backup\ai\work-skill\connector')
import rf  # noqa: E402

# 1. sitemap index
try:
    s, f, h = rf.get('https://www.drushim.co.il/sitemap.xml', timeout=25)
except Exception as e:
    print('sitemap fetch error', repr(e)[:120])
    sys.exit(0)
h = h or ''
print('sitemap status', s, 'len', len(h))
locs = re.findall(r'<loc>\s*([^<\s]+)', h)
print('locs:', len(locs))
for u in locs[:25]:
    print('  ', u[:120])

# 2. try one job page if a job URL exists in any sub-sitemap
jobs = [u for u in locs if '/job' in u][:3]
if not jobs and locs:
    try:
        s2, f2, h2 = rf.get(locs[0], timeout=25)
        h2 = h2 or ''
        sub = re.findall(r'<loc>\s*([^<\s]+)', h2)
        print('sub-sitemap', locs[0], 'locs:', len(sub))
        for u in sub[:15]:
            print('  ', u[:120])
        jobs = [u for u in sub if '/job' in u][:3]
    except Exception as e:
        print('sub fetch error', repr(e)[:120])
for u in jobs:
    try:
        s3, f3, h3 = rf.get(u, timeout=25)
    except Exception as e:
        print('job fetch error', u, repr(e)[:120])
        continue
    h3 = h3 or ''
    txt = re.sub(r'<[^>]+>', ' ', re.sub(r'<(script|style)[^>]*>.*?</\1>', ' ', h3, flags=re.S | re.I))
    txt = re.sub(r'\s+', ' ', txt)
    mails = re.findall(r'[A-Za-z0-9._+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}', txt)
    cf = re.findall(r'data-cfemail=["\']([0-9a-f]+)', h3)
    print('JOB', u[:100], 'status', s3, 'len', len(h3), 'mails', sorted(set(m.lower() for m in mails))[:5], 'cf', len(cf))
    print('  text[:300]:', txt[:300])
