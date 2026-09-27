"""Real NBA salaries off Basketball-Reference contracts (keyless).
Index + 30 team pages, 4s gaps; y1 is the current season observed at
scrape time (2026-27 on 2026-09-08 and 2026-09-11 probes).

Frozen spec column SALARY_2025_26 holds the observed y1 money for
whatever vintage was scraped. The column name never changes. The
vintage lives in _season plus the fetch_log season, both set from the
observed y1 header, never from a hardcoded default. ESPN roster API:
403 on 2026-09-08, no salary fields. SOURCE bref_contracts."""
import re
import time
import unicodedata

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

# Basketball-Reference franchise abbreviations differ from the nba_api scheme
# used everywhere else in this app (silver_leaders_pts, silver_cap_players,
# get_trade_check team args). Normalize at ingestion so TEAM joins match.
# Without this, _payroll("BKN") matches zero salary rows and trade checks
# silently fall back to estimated cap figures for Brooklyn/Charlotte/Phoenix.
TEAM_ABBR = {"BRK": "BKN", "CHO": "CHA", "PHO": "PHX"}


def _fold(name: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", str(name or ""))
        if not unicodedata.combining(c)
    ).strip()


def _get(url: str) -> str:
    import httpx
    last: Exception | None = None
    for attempt in range(4):
        r = httpx.get(url, headers=HEADERS, timeout=30, follow_redirects=True)
        if r.status_code == 429:
            last = RuntimeError(f"429 for {url}")
            time.sleep(8 * (attempt + 1))
            continue
        r.raise_for_status()
        return r.text
    raise last or RuntimeError(f"failed fetching {url}")

def _csk(row: str, stat: str) -> int:
    m = re.search(r'data-stat="%s"[^>]*csk="(\d+)"' % stat, row)
    return int(m.group(1)) if m else 0

def _run(season: list) -> pl.DataFrame:
    html = _get(URL)
    m = re.search(r'data-stat="y1"[^>]*>([\d-]+)', html)
    observed = (m.group(1).strip() if m else "")
    season.append(observed)
    rows = []
    consecutive_failures = 0
    for a in sorted(set(re.findall(r"/contracts/([A-Z]{2,3})\.html", html))):
        time.sleep(4)
        try:
            page = _get(URL + a + ".html")
        except Exception:
            consecutive_failures += 1
            if consecutive_failures >= 3:
                break
            continue
        consecutive_failures = 0
        t = re.search(r'id="contracts".*?</thead>(.*?)</table>', page, re.S)
        if not t:
            continue
        for row in re.findall(r"<tr[^>]*>(.*?)</tr>", t.group(1), re.S):
            p = re.search(r'data-stat="player"[^>]*csk=[^>]*>(?:<a[^>]*>)?([^<]+)', row)
            s = _csk(row, "y1")
            if not p or not s:
                continue
            g = _csk(row, "remain_gtd")
            rows.append({"PLAYER_NAME": _fold(p.group(1)),
                         "TEAM": TEAM_ABBR.get(a, a),
                         "SALARY_2025_26": s, "GUARANTEED": g or s})
    return pl.DataFrame(rows)

def get_contracts() -> FetchResult:
    season: list = []
    res = safe(SOURCE, "unknown", lambda: _run(season))
    observed = season[0] if season and season[0] else ""
    if observed:
        res.meta.season = observed
    else:
        res.meta.season = "unknown"
        res.ok = False
        res.error = (res.error or "y1 header not observed")[:300]
    return res
