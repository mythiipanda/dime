import json
from typing import Any

import polars as pl

from ..config import settings
from .base import FetchResult, safe

SOURCE = "nba_api"
TABLE = "silver_award_winners"

DESCRIPTION_AWARD = {
    "NBA Most Valuable Player": "MVP",
    "NBA Defensive Player of the Year": "DPOY",
    "NBA Rookie of the Year": "ROY",
    "NBA Sixth Man of the Year": "6MOY",
    "NBA Most Improved Player": "MIP",
    "All-NBA": "ALL_NBA",
    "All-Defensive Team": "ALL_DEFENSE",
    "All-Rookie Team": "ALL_ROOKIE",
}

SCHEMA = {
    "SEASON": pl.String,
    "AWARD": pl.String,
    "RANK": pl.Int64,
    "RANK_LABEL": pl.String,
    "PLAYER": pl.String,
    "COACH": pl.String,
    "AGE": pl.Int64,
    "TEAM": pl.String,
    "POINTS_WON": pl.Int64,
    "POINTS_MAX": pl.Int64,
    "AWARD_SHARE": pl.Float64,
    "VOTES_FIRST": pl.Int64,
    "VOTES_SECOND": pl.Int64,
    "VOTES_THIRD": pl.Int64,
    "SOURCE_URL": pl.String,
}
COLUMNS = list(SCHEMA)


def _raw_frame(payload: dict[str, Any]) -> pl.DataFrame:
    for result in payload.get("resultSets") or []:
        if result.get("name") != "PlayerAwards":
            continue
        headers = [str(header) for header in result.get("headers") or []]
        rows = result.get("rowSet") or []
        return pl.DataFrame(
            [{header: (None if value is None else str(value))
              for header, value in zip(headers, row)}
             for row in rows],
            schema={header: pl.String for header in headers},
        )
    return pl.DataFrame(schema={header: pl.String for header in ()})


def parse_player_awards(payload: dict[str, Any]) -> pl.DataFrame:
    raw = _raw_frame(payload)
    records: list[dict[str, Any]] = []
    for row in raw.to_dicts():
        award = DESCRIPTION_AWARD.get(str(row.get("DESCRIPTION") or ""))
        if award is None:
            continue
        season = str(row.get("SEASON") or "")
        first = str(row.get("FIRST_NAME") or "").strip()
        last = str(row.get("LAST_NAME") or "").strip()
        records.append({
            "SEASON": season,
            "AWARD": award,
            "RANK": 1,
            "RANK_LABEL": "1",
            "PLAYER": f"{first} {last}".strip() or None,
            "COACH": None,
            "AGE": None,
            "TEAM": str(row.get("TEAM") or "") or None,
            "POINTS_WON": None,
            "POINTS_MAX": None,
            "AWARD_SHARE": None,
            "VOTES_FIRST": None,
            "VOTES_SECOND": None,
            "VOTES_THIRD": None,
            "SOURCE_URL": "nba_api:PlayerAwards",
        })
    frame = pl.DataFrame(records, schema=SCHEMA)
    return frame.filter(pl.col("SEASON").str.len_chars() > 0)


def fetch_player_awards(player_id: int,
                        timeout: int | None = None) -> FetchResult:
    from nba_api.stats.endpoints import PlayerAwards

    def run() -> pl.DataFrame:
        endpoint = PlayerAwards(
            player_id=player_id, timeout=timeout or _timeout())
        return parse_player_awards(json.loads(endpoint.get_json()))

    return safe(SOURCE, "awards", run)


def _timeout() -> int:
    return settings.default_timeout_seconds
