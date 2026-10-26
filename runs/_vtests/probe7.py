# Bing + FB permalink rendering probe for the fbposts lane.
import re
import sys
import urllib.parse

sys.path.insert(0, r'F:\backup\ai\work-skill\connector')
import rf  # noqa: E402

q = 'site:facebook.com/groups devops israel cv'
url = 'https://www.bing.com/search?q=' + urllib.parse.quote(q) + '&format=rss'
s, f, h = rf.get(url, timeout=30)
h = h or ''
print('bing-rss status', s, 'len', len(h), 'is-rss', '<rss' in h[:200] or '<channel' in h[:400])
links = re.findall(r'<link>([^<]+)</link>', h)
print('rss links:', len(links))
for u in links[:10]:
    print('  ', u[:120])
fb = [u for u in links if 'facebook.com' in u]
if not fb:
    # fall back to html parse of regular bing
    url2 = 'https://www.bing.com/search?q=' + urllib.parse.quote(q)
    s, f, h = rf.get(url2, timeout=30)
    h = h or ''
    print('bing-html status', s, 'len', len(h), 'fb-mentions', h.count('facebook.com'))
    for m in re.finditer(r'https?://(?:www\.|m\.|mbasic\.)?facebook\.com/[^"\'<>\s\\]+', h):
        u = m.group(0).split('&')[0]
        if u not in fb:
            fb.append(u)
    print('fb urls:', len(fb))
    for u in fb[:8]:
        print('  ', u[:120])

# try rendering one permalink through r.jina.ai if found
if fb:
    post = [u for u in fb if '/posts/' in u or '/permalink/' in u][:1]
    targets = post or fb[:1]
    for u in targets:
        try:
            s2, f2, h2 = rf.get('https://r.jina.ai/' + u, timeout=40)
        except Exception as e:
            print('jina error', repr(e)[:140])
            continue
        h2 = h2 or ''
        txt = re.sub(r'<[^>]+>', ' ', h2)
        mails = re.findall(r'[A-Za-z0-9._+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}', txt)
        print('jina render', u[:80], 'status', s2, 'len', len(h2), 'mails', sorted(set(x.lower() for x in mails))[:6])
        print('  text[:250]:', re.sub(r'\s+', ' ', txt)[:250])
