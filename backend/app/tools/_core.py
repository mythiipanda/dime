"""Shared warehouse-first fetch helper plus registry constants."""

from typing import Any
import polars as pl

from .. import store
from ..sources.base import FetchResult

SEASON = "2025-26"
MAX_ROWS = 25

STAT_CATEGORIES = frozenset({
    "PTS", "REB", "AST", "STL", "BLK", "MIN", "FGM", "FGA",
    "FG_PCT", "FG3M", "FG3A", "FG3_PCT", "FTM", "FTA", "FT_PCT",
    "OREB", "DREB", "TOV", "PF", "EFF", "DD2", "TD3",
    "USG_PCT", "TOV_PCT", "PIE",
})


def clamp_season(season: object) -> str:
    import re as _re

    s = str(season or "").strip()
    if _re.fullmatch(r"20\d{2}-\d{2}", s):
        return s
    m = _re.fullmatch(r"20(\d{2})", s)
    if m:
        y = int(m.group(1))
        return f"20{y}-{y + 1:02d}" if y < 50 else f"19{y}-{y + 1:02d}"
    return SEASON


def clamp_stat(stat: str) -> str:
    upper = (stat or "").strip().upper()
    return upper if upper in STAT_CATEGORIES else "PTS"


def clamp_scope(scope: str) -> str:
    lower = (scope or "").strip().lower()
    return lower if lower in ("player", "team") else "player"


NICKNAMES = {
    "sga": "Shai Gilgeous-Alexander",
    "shai": "Shai Gilgeous-Alexander",
    "luka": "Luka Doncic",
    "joker": "Nikola Jokic",
    "jokic": "Nikola Jokic",
    "giannis": "Giannis Antetokounmpo",
    "bron": "LeBron James",
    "kd": "Kevin Durant",
    "steph": "Stephen Curry",
    "tatum": "Jayson Tatum",
    "embiid": "Joel Embiid",
    "dame": "Damian Lillard",
    "kyrie": "Kyrie Irving",
    "ad": "Anthony Davis",
    "kat": "Karl-Anthony Towns",
    "dbook": "Devin Booker",
    "ant": "Anthony Edwards",
    "wemby": "Victor Wembanyama",
    "celtics": "Boston Celtics",
    "lakers": "Los Angeles Lakers",
    "knicks": "New York Knicks",
    "dubs": "Golden State Warriors",
    "sixers": "Philadelphia 76ers",
}


def coerce_player_id(value: object) -> int:
    """Accept an id or a name. Names resolve through static tables."""
    raw = str(value).strip()
    try:
        return int(raw)
    except (TypeError, ValueError):
        pass
    raw = NICKNAMES.get(raw.lower(), raw)
    from nba_api.stats.static import players

    name = raw.lower()
    found = players.find_players_by_full_name(raw)
    if not found:
        all_p = players.get_players()
        found = [x for x in all_p if name in x.get("full_name", "").lower()]
    if not found:
        raise ValueError(f"unknown player: {value}")
    return int(found[0]["id"])


def coerce_team_id(value: object) -> int:
    """Accept an id or a name. Names resolve through static tables."""
    raw = str(value).strip()
    try:
        return int(raw)
    except (TypeError, ValueError):
        pass
    raw = NICKNAMES.get(raw.lower(), raw)
    from nba_api.stats.static import teams

    name = raw.lower()
    found = teams.find_teams_by_full_name(raw)
    if not found:
        all_t = teams.get_teams()
        found = [x for x in all_t
                 if name in x.get("full_name", "").lower()
                 or name == x.get("abbreviation", "").lower()]
    if not found:
        raise ValueError(f"unknown team: {value}")
    return int(found[0]["id"])


def _warehouse_or_live(
    table: str,
    where: str,
    params: list[object],
    fetch: Any,
    season: str,
    entity: str = "",
    limit: int = MAX_ROWS,
    live_first: bool = False,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    frame = None
    if not live_first:
        frame = store.read_frame(table, where, params)
    if frame is None or frame.height == 0:
        live: FetchResult = fetch()
        if not live.ok or live.frame.height == 0:
            if live_first:
                frame = store.read_frame(table, where, params)
                if frame is not None and frame.height > 0:
                    meta: dict[str, Any] = {
                        "rows": frame.height, "cached": True, "stale": True,
                        "live_error": live.error or "empty upstream response",
                    }
                    if "_source" in frame.columns:
                        meta["source"] = frame["_source"][0]
                        meta["fetched_at"] = frame["_fetched_at"][0]
                    return frame.head(limit).to_dicts(), meta
            return [], {"source": live.meta.source,
                        "error": live.error or "empty upstream response"}
        store.save_frame(table, live, entity)
        frame = store.read_frame(table, where, params)
        if frame.height == 0:
            frame = live.frame.with_columns(
                [
                    pl.lit(live.meta.source).alias("_source"),
                    pl.lit(live.meta.season).alias("_season"),
                    pl.lit(live.meta.fetched_at).alias("_fetched_at"),
                ]
            )
        return frame.head(limit).to_dicts(), {
            "rows": frame.height, "cached": False,
            "source": live.meta.source, "fetched_at": live.meta.fetched_at,
        }
    meta: dict[str, Any] = {"rows": frame.height, "cached": True}
    if "_source" in frame.columns:
        meta["source"] = frame["_source"][0]
        meta["fetched_at"] = frame["_fetched_at"][0]
    return frame.head(limit).to_dicts(), meta
