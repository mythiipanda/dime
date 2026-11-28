import time

import polars as pl

from .base import FetchResult, safe

SOURCE = "thedraftday:picks"
PICKS_URL = "https://thedraftday.com/api/picks"
HEADERS = {
    "User-Agent": "DimeAnalytics/1.0 (NBA research)",
    "Accept": "application/json",
}

_ABBR_TO_WAREHOUSE = {
    "GS": "GSW", "SA": "SAS", "NO": "NOP", "NY": "NYK",
    "UTAH": "UTA", "WSH": "WAS",
}

def _abbr(code: str) -> str:
    return _ABBR_TO_WAREHOUSE.get(str(code or "").strip().upper(),
                                  str(code or "").strip().upper())

def _get(url: str) -> dict:
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
        return r.json()
    raise last or RuntimeError(f"failed fetching {url}")

def _season_label(draft_years: list[int]) -> str:
    start = min(draft_years) - 1
    return f"{start}-{str(start + 1)[2:]}"

CHAIN_VERIFIED_SWAPS = {
    ("MIL", 2028, 1): "realgm:mil-outgoing-2028 — Portland receives the more favorable of its pick and Milwaukee's, Milwaukee receives the less favorable back through the Washington swap chain, so Milwaukee retains a first in all scenarios",
    ("MIN", 2030, 1): "realgm:min-outgoing-2030 — San Antonio's swap right and Charlotte's swap right both return a first to Minnesota in all scenarios, outright conveyance never occurs",
}


def _parse(payload: dict) -> pl.DataFrame:
    rows: list[dict] = []
    for team in payload.get("teams") or []:
        orig = _abbr(team.get("team"))
        for pick in team.get("picks") or []:
            holders = [_abbr(h) for h in (pick.get("held_by") or [])]
            status = pick.get("status") or ""
            override = CHAIN_VERIFIED_SWAPS.get(
                (orig, int(pick["draft_year"]), int(pick["round"])))
            if override and status == "traded":
                status = "swap"
            rows.append({
                "DRAFT_YEAR": int(pick["draft_year"]),
                "ROUND": int(pick["round"]),
                "ORIG_TEAM": orig,
                "STATUS": status,
                "HELD_BY": ";".join(holders),
                "PROTECTION": pick.get("protection"),
                "POOLED": bool(pick.get("pooled")),
                "CONDITIONAL": bool(pick.get("conditional")),
                "SUMMARY": pick.get("summary") or "",
                "LAST_EDITED": payload.get("last_edited") or "",
            })
    return pl.DataFrame(rows)

def future_picks() -> FetchResult:
    holder: dict = {}

    def run() -> pl.DataFrame:
        payload = _get(PICKS_URL)
        frame = _parse(payload)
        years = [int(y) for y in frame["DRAFT_YEAR"].unique().to_list()]
        holder["season"] = _season_label(years)
        return frame

    res = safe(SOURCE, "unknown", run)
    season = holder.get("season", "")
    if res.ok:
        if season:
            res.meta.season = season
        else:
            res.ok = False
            res.error = "no draft years observed in picks payload"
    return res
