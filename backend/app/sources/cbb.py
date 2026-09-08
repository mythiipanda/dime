"""Keyless college stats via BartTorvik (draft modeling).

Endpoint that worked: GET https://barttorvik.com/getadvstats.php?year=YYYY
-> HTTP 200 JSON array-of-arrays, no header, 67 cols (content-type text/html
but body is JSON). Browser UA required; no fallback needed.
Column map verified 2026-09-08 vs known 2025 freshmen (Flagg/Harper/Bailey/
Edgecombe PPG all match). Idx: 0 name, 1 team, 3 GP, 6 USG, 8 TS (0-100),
13-14 FTM/FTA, 16-17 2PM/2PA, 19-20 3PM/3PA, 59 REB/G, 60 AST/G, 63 PTS/G.
FGA total = 2PA + 3PA. PTS/REB/AST are per-game.
"""

import polars as pl

from .base import FetchResult, safe

SOURCE = "barttorvik"
URL = "https://barttorvik.com/getadvstats.php"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "application/json,text/plain,*/*",
    "Referer": "https://barttorvik.com/",
}


def _f(v):
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def get_player_stats(season_year: int = 2025) -> FetchResult:
    def run() -> pl.DataFrame:
        import httpx

        r = httpx.get(URL, params={"year": season_year}, headers=HEADERS, timeout=30)
        r.raise_for_status()
        out = []
        for x in r.json():
            if not x or len(x) < 64:
                continue
            gp, ppg = _f(x[3]), _f(x[63])
            fga = (_f(x[17]) or 0) + (_f(x[20]) or 0)
            fta = _f(x[14]) or 0
            ts = (_f(x[8]) / 100) if _f(x[8]) is not None else None
            if ts is None and gp and ppg and (fga + 0.44 * fta):
                ts = (ppg * gp) / (2 * (fga + 0.44 * fta))
            out.append({"PLAYER_NAME": x[0], "TEAM": x[1], "GP": gp,
                        "PTS": ppg, "REB": _f(x[59]), "AST": _f(x[60]),
                        "TS_PCT": ts, "USG": _f(x[6])})
        return pl.DataFrame(out) if out else pl.DataFrame()

    return safe(SOURCE, str(season_year), run)
