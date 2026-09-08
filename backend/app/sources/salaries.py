"""Real NBA salaries off Basketball-Reference contracts (keyless).
Index + 30 team pages, 4s gaps; y1 is current season (2026-27 on 2026-09-08,
kept under spec column SALARY_2025_26). ESPN roster API: 403 on 2026-09-08,
no salary fields. SOURCE bref_contracts."""
import re
import time

import polars as pl

from .base import FetchResult, safe

SOURCE = "bref_contracts"
URL = "https://www.basketball-reference.com/contracts/"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "text/html,*/*",
    "Referer": "https://www.basketball-reference.com/",
}

def _get(url: str) -> str:
    import httpx
    r = httpx.get(url, headers=HEADERS, timeout=30, follow_redirects=True)
    r.raise_for_status()
    return r.text

def _csk(row: str, stat: str) -> int:
    m = re.search(r'data-stat="%s"[^>]*csk="(\d+)"' % stat, row)
    return int(m.group(1)) if m else 0

def _run(season: list) -> pl.DataFrame:
    html = _get(URL)
    m = re.search(r'data-stat="y1"[^>]*>([\d-]+)', html)
    season.append(m.group(1) if m else "")
    rows = []
    for a in sorted(set(re.findall(r"/contracts/([A-Z]{2,3})\.html", html))):
        time.sleep(4)
        try:
            page = _get(URL + a + ".html")
        except Exception:
            continue
        t = re.search(r'id="contracts".*?</thead>(.*?)</table>', page, re.S)
        if not t:
            continue
        for row in re.findall(r"<tr[^>]*>(.*?)</tr>", t.group(1), re.S):
            p = re.search(r'data-stat="player"[^>]*csk=[^>]*>(?:<a[^>]*>)?([^<]+)', row)
            s = _csk(row, "y1")
            if not p or not s:
                continue
            g = _csk(row, "remain_gtd")
            rows.append({"PLAYER_NAME": p.group(1).strip(), "TEAM": a, "SALARY_2025_26": s, "GUARANTEED": g or s})
    return pl.DataFrame(rows)

def get_contracts() -> FetchResult:
    season: list = []
    res = safe(SOURCE, "2026-27", lambda: _run(season))
    if season and season[0]:
        res.meta.season = season[0]
    return res
