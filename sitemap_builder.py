"""Verify browser-harvested company-site candidates and build runs/site-map.json.

Fail-closed rules (mirror resolve_site): a candidate site is accepted only if
fetching it succeeds and its page text contains the company's own name tokens
(Hebrew words >=2 chars or Latin words, minus legal suffixes and stop words).
Directory/job-board/duplicate hosts are never accepted as an official site.
auto_runner.make_ctx() preloads runs/site-map.json into ctx['site_cache'].
"""
import io
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import auto_runner as ar

SKIP_HOSTS = re.compile(r'(drushim\.co\.il|alljobs\.co\.il|jobmaster\.co\.il|jobclick\.co\.il|checkid\.co\.il|dunsguide\.co\.il|(?<![a-z0-9])d\.co\.il|wikipedia\.org|google\.|facebook\.com|linkedin\.com|ksp\.co\.il|dugit\.co\.il|saf\.co\.il|shesek\.co\.il)', re.I)
HEB_STOP = {'בעמ', 'בע"מ', 'בע״מ', 'רואה', 'חשבון', 'קבוצת', 'חברת', 'טכנולוגיות', 'מערכות', 'תעשיות', 'בית', 'השקעות', 'לישראל', 'ישראל'}


def name_tokens(name):
    toks = []
    # scraped Hebrew names often carry invisible direction marks (\u200f etc)
    # which would poison every token comparison - strip before splitting
    name = re.sub(r'[\u200e\u200f\u202a-\u202e\u2066-\u2069]', '', name)
    for t in re.split(r'[\s/\-()&,.]+', name):
        t = t.strip('"\'״')
        if len(t) < 2:
            continue
        if re.search(r'[\u05d0-\u05ea]', t):
            if t not in HEB_STOP and len(t) >= 3:
                toks.append(t)
        elif re.match(r'[A-Za-z]{3,}$', t):
            toks.append(t.lower())
    return toks


def verify(name, urls):
    toks = name_tokens(name)
    if not toks:
        return ''
    for u in urls[:4]:
        if SKIP_HOSTS.search(u):
            continue
        try:
            _, final, html = ar.rf.get(u, timeout=12)
        except Exception:
            continue
        if not html:
            continue
        text = ar.textify(html)[:60000].lower()
        hits = sum(1 for t in toks if t.lower() in text)
        if hits >= max(1, len(toks) - 1):
            return (final or u).split('?')[0].rstrip('/')
    return ''


def main():
    cand_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join('runs', '_cache', 'sitemap-cands.json')
    out_path = os.path.join('runs', 'site-map.json')
    cands = json.load(io.open(cand_path, encoding='utf-8'))
    smap = {}
    if os.path.isfile(out_path):
        try:
            smap = json.load(io.open(out_path, encoding='utf-8'))
        except Exception:
            smap = {}
    ok = 0
    for name, urls in cands.items():
        if name in smap and smap[name]:
            ok += 1
            continue
        site = verify(name, urls)
        if site:
            smap[name] = site
            ok += 1
            print('OK   ' + name + ' -> ' + site)
        else:
            print('FAIL ' + name)
    json.dump(smap, io.open(out_path, 'w', encoding='utf-8', newline=''), ensure_ascii=False, indent=1)
    print('verified ' + str(ok) + '/' + str(len(cands)) + '; site-map size ' + str(len(smap)))


if __name__ == '__main__':
    main()
