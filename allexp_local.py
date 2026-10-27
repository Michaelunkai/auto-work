"""AllJobs mass harvest chain (auto-work local widened copy; output contract identical).

Usage:
    python allexp.py OUT.json
Steps: fetch listing pages (keywords + position codes), extract relevant job
URLs, fetch each ad page, resolve employer+cid, write unique employer rows.
"""
import json
import re
import sys
import os, sys
sys.path.insert(0, os.environ.get('AUTOWORK_CONNECTOR', 'F:/backup/ai/work-skill/connector'))
from rf import get

BAD = re.compile(r"(senior|מנוס|ראש צוות|team lead|manager|מנהל|VP|director|architect|ארכיטקט|סמנכ|reg|Legal|marketing|שיווק|sales|מכירות|finance|כספים|accountant|הנהלת|ספורט)", re.I)
GOOD = re.compile(r"(devops|help ?desk|תומכ|תמיכה|טכני|sysadmin|מערכות|network|רשת|noc|תפעול|support|IT|infrastructure|תשתיות|cloud|ענן|cyber|אבטח|security|פנטרסט|implementation|הטמעה|field|שטח|technician|computer|מחשבים|student|סטודנט|junior|זוטר|ג'וניור)", re.I)
NAV = re.compile(r"(VIP|הרשמה|שאלות|ליווי|הכוון|מדריך|כתיבת|בדיקת|שכר|מכתב|איך|פני|תנאי|מדיניות|סוכן|לכל|כתיבה)", re.I)
JOBLINK = re.compile(r'href="(/Search/UploadSingle\.aspx\?JobID=\d+)"[^>]*>(.*?)</a>', re.S)


def clean(t):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", t)).strip()


def listings():
    urls = []
    kws = ["devops", "helpdesk", "תמיכה טכנית", "sysadmin", "noc", "אבטחת מידע", "מערכות מידע", "ענן",
           "linux", "cloud", "junior it", "network", "help desk", "it support", "devops junior",
           "windows admin", "טכנאי מחשבים", "תמיכת IT", "מרכז נתונים", "טכנאי רשתות"]
    for kw in kws:
        for pg in range(1, 5):
            urls.append(f"https://www.alljobs.co.il/SearchResultsGuest.aspx?keyword={kw}&page={pg}")
    for pos in (840, 823):
        for pg in range(1, 7):
            urls.append(f"https://www.alljobs.co.il/SearchResultsGuest.aspx?page={pg}&position={pos}")
    return urls


def main():
    outp = sys.argv[1]
    ads, seen = [], set()
    for u in listings():
        try:
            _, _, html = get(u, timeout=20)
        except Exception:  # noqa: BLE001
            continue
        for href, inner in JOBLINK.findall(html):
            t = clean(inner)
            if href in seen or not t or BAD.search(t) or not GOOD.search(t) or NAV.search(t):
                continue
            seen.add(href)
            ads.append({"url": href, "title": t[:150]})
    print(json.dumps({"relevant_ads": len(ads)}, ensure_ascii=False))
    emps, cseen = {}, set()
    for a in ads:
        full = "https://www.alljobs.co.il" + a["url"]
        try:
            _, _, html = get(full, timeout=20)
        except Exception:  # noqa: BLE001
            continue
        m = re.search(r'<a href="/Employer/HP/Default\.aspx\?cid=(\d+)">([^<]+)</a>', html)
        og = re.search(r'og:description"\s+content="([^"]+)"', html)
        if not m or m.group(1) in cseen:
            continue
        cseen.add(m.group(1))
        emps[m.group(1)] = {"cid": m.group(1), "name": m.group(2).strip(),
                            "slug": None,
                            "job": {"title": a["title"], "url": full},
                            "og": re.sub(r"\s+", " ", og.group(1)).strip()[:400] if og else ""}
    rows = list(emps.values())
    json.dump(rows, open(outp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps({"unique_employers": len(rows), "out": outp}, ensure_ascii=False))


if __name__ == "__main__":
    main()
