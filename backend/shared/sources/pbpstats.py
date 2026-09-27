"""PBP Stats REST source. Possession-level splits without computing them.

Base: https://api.pbpstats.com. No key. Season like 2025-26.
SeasonType is Regular Season, Playoffs, or All.
"""

import polars as pl

from .base import FetchResult, empty, safe

SOURCE = "pbpstats"
BASE = "https://api.pbpstats.com"


def _get(path: str, params: dict) -> pl.DataFrame:
    import httpx

    r = httpx.get(BASE + path, params=params, timeout=30)
    r.raise_for_status()
    payload = r.json()
    rows = payload.get("results", payload)
    if isinstance(rows, dict):
        rows = [rows]
    return pl.DataFrame(rows) if rows else pl.DataFrame()


def on_off(
    player_id: int, team_id: int, season: str, stat_type: str = "team",
) -> FetchResult:
    def run() -> pl.DataFrame:
        return _get(
            f"/get-on-off/nba/{stat_type}",
            {"PlayerId": player_id, "TeamId": team_id,
             "Season": season, "SeasonType": "Regular Season"},
        )

    return safe(SOURCE, season, run)


def wowy(
    player_ids: list[int], team_id: int, season: str, only_with: bool = True,
) -> FetchResult:
    def run() -> pl.DataFrame:
        return _get(
            "/get-wowy-stats/nba",
            {"PlayerIds": ",".join(str(i) for i in player_ids),
             "TeamId": team_id, "Season": season,
             "SeasonType": "Regular Season",
             "OnlyWithPlayers": str(only_with).lower()},
        )

    return safe(SOURCE, season, run)


def four_factors(player_id: int, team_id: int, season: str) -> FetchResult:
    def run() -> pl.DataFrame:
        return _get(
            "/get-four-factor-on-off/nba",
            {"PlayerId": player_id, "TeamId": team_id,
             "Season": season, "SeasonType": "Regular Season"},
        )

    return safe(SOURCE, season, run)


def lineup_player_stats(team_id: int, season: str) -> FetchResult:
    def run() -> pl.DataFrame:
        return _get(
            "/get-lineup-player-stats/nba",
            {"TeamId": team_id, "Season": season,
             "SeasonType": "Regular Season"},
        )

    return safe(SOURCE, season, run)
