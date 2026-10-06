
import html as _html
import re
import time

import polars as pl

from .base import FetchResult, safe

SOURCE = "tankathon"
MOCK_URL = "https://www.tankathon.com/mock-draft"
BIG_BOARD_URL = "https://www.tankathon.com/big-board"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "text/html,*/*",
    "Referer": "https://www.tankathon.com/",
}

_ROW = re.compile(r'<div class="mock-row"(.*?)</div>\s*</div>\s*</div>',
                   re.S)
_PICK = re.compile(r'mock-row-pick-number">(\d+)')
_NAME = re.compile(r'mock-row-name">([^<]+)')
_SLUG = re.compile(r'href="/players/([a-z0-9\-]+)"')
_POS_SCHOOL = re.compile(r'mock-row-school-position">([^<]+)')
_TEAM = re.compile(r'<img class="nba-30" alt="([A-Z]{2,3})"')
_HEIGHT = re.compile(r'section height-weight"><div>([^<]+)</div>'
                     r'<div>([\d]+)')
_YEAR_AGE = re.compile(r'section year-age desktop"><div>([^<]+)</div>'
                       r'<div>([\d.]+)')
_TITLE_YEAR = re.compile(r"<title>(\d{4}) NBA (?:Mock Draft|Draft Big Board)")

def _get(url: str) -> str:
    import httpx

    last: Exception | None = None
    for attempt in range(3):
        r = httpx.get(url, headers=HEADERS, timeout=30,
                      follow_redirects=True)
        if r.status_code == 429:
            last = RuntimeError(f"429 for {url}")
            time.sleep(10 * (attempt + 1))
            continue
        r.raise_for_status()
        return r.text
    raise last or RuntimeError(f"failed fetching {url}")

def _clean(s: str) -> str:
    return _html.unescape(s or "").replace("\xa0", " ").strip()

def _parse(html_text: str, board: str) -> tuple[pl.DataFrame, str]:
    m = _TITLE_YEAR.search(html_text)
    year = m.group(1) if m else ""
    rows: list[dict] = []
    seen: set[int] = set()
    for rm in _ROW.finditer(html_text):
        body = rm.group(1)
        name_m = _NAME.search(body)
        pick_m = _PICK.search(body)
        if not name_m or not pick_m:
            continue
        rank = int(pick_m.group(1))
        if rank in seen:
            continue
        seen.add(rank)
        slug_m = _SLUG.search(body)
        ps_m = _POS_SCHOOL.search(body)
        pos, school = "", ""
        if ps_m:
            parts = [p.strip() for p in _clean(ps_m.group(1)).split("|")]
            pos = parts[0] if parts else ""
            school = parts[1] if len(parts) > 1 else ""
        team_m = _TEAM.search(body)
        h_m = _HEIGHT.search(body)
        ya_m = _YEAR_AGE.search(body)
        rows.append({
            "RANK" if board == "big_board" else "PICK": rank,
            "PLAYER_NAME": _clean(name_m.group(1)),
            "PLAYER_SLUG": slug_m.group(1) if slug_m else "",
            "POSITION": pos,
            "SCHOOL": school,
            "TEAM_ABBREVIATION":
                team_m.group(1) if team_m and board == "mock_draft" else "",
            "HEIGHT": _clean(h_m.group(1)) if h_m else "",
            "WEIGHT_LBS": int(h_m.group(2)) if h_m else None,
            "CLASS_YEAR": _clean(ya_m.group(1)) if ya_m else "",
            "AGE": float(ya_m.group(2)) if ya_m else None,
            "BOARD": board,
        })
    return pl.DataFrame(rows), year

def _fetch(board: str, url: str) -> FetchResult:
    holder: dict = {}

    def run() -> pl.DataFrame:
        frame, year = _parse(_get(url), board)
        holder["year"] = year
        return frame

    res = safe(SOURCE, "unknown", run)
    year = holder.get("year", "")
    if res.ok:
        if year:
            res.meta.season = year
        else:
            res.ok = False
            res.error = "draft year not observed in page title"
    return res

def mock_draft() -> FetchResult:
    return _fetch("mock_draft", MOCK_URL)

def big_board() -> FetchResult:
    return _fetch("big_board", BIG_BOARD_URL)
