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
})


def clamp_stat(stat: str) -> str:
    upper = (stat or "").strip().upper()
    return upper if upper in STAT_CATEGORIES else "PTS"


def clamp_scope(scope: str) -> str:
    lower = (scope or "").strip().lower()
    return lower if lower in ("player", "team") else "player"


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
