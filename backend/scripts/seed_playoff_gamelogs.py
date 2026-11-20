from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared import store
from shared.sources.base import FetchMeta, FetchResult
from scripts.seed_current_season import SDV, SRC_PGL, end_year, resolve_target

TABLE = "silver_playoff_gamelogs"
DEFAULT_SEASONS = ["2023-24", "2024-25", "2025-26"]


def playoff_frame(season: str) -> pl.DataFrame:
    y = end_year(season)
    df = pl.read_parquet(
        f"{SDV}/nba_stats_player_game_logs/player_game_logs_{y}.parquet")
    df = df.filter(pl.col("season_type") == "playoffs")
    import datetime as _dt

    def fmt(d):
        try:
            return _dt.date.fromisoformat(str(d)).strftime("%b %-d, %Y")
        except (TypeError, ValueError):
            return str(d)

    return pl.DataFrame({
        "SEASON_ID": df["season_id"],
        "Player_ID": df["player_id"],
        "Game_ID": df["game_id"],
        "GAME_DATE": [fmt(d) for d in df["game_date"].to_list()],
        "MATCHUP": df["matchup"],
        "WL": df["wl"],
        "MIN": df["min"],
        "FGM": df["fgm"], "FGA": df["fga"], "FG_PCT": df["fg_pct"],
        "FG3M": df["fg3m"], "FG3A": df["fg3a"], "FG3_PCT": df["fg3_pct"],
        "FTM": df["ftm"], "FTA": df["fta"], "FT_PCT": df["ft_pct"],
        "OREB": df["oreb"], "DREB": df["dreb"], "REB": df["reb"],
        "AST": df["ast"], "STL": df["stl"], "BLK": df["blk"],
        "TOV": df["tov"], "PF": df["pf"], "PTS": df["pts"],
        "PLUS_MINUS": df["plus_minus"] if "plus_minus" in df.columns
            else [None] * df.height,
        "VIDEO_AVAILABLE": [1] * df.height,
    })


def load_season(season: str, dry_run: bool) -> int:
    try:
        out = playoff_frame(season)
    except Exception as exc:
        print(f"{TABLE} {season}: source unavailable ({exc}); skipped")
        return 0
    if out.height == 0:
        print(f"{TABLE} {season}: no playoff rows in source; skipped")
        return 0
    if dry_run:
        print(f"{TABLE} {season}: {out.height} rows (dry-run)")
        return 0
    con = store.connect()
    try:
        con.execute(
            f"DELETE FROM {TABLE} WHERE _season = ?", [season])
    except Exception:
        pass
    finally:
        con.close()
    res = FetchResult(frame=out, meta=FetchMeta(source=SRC_PGL, season=season))
    n = store.save_frame(TABLE, res, entity="league", replace_season=True)
    print(f"{TABLE} {season}: {n} rows")
    return n


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scratch-db", default="")
    parser.add_argument("--seasons", nargs="*", default=DEFAULT_SEASONS)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    target = resolve_target(args.scratch_db)
    if target is None:
        return 2
    target.parent.mkdir(parents=True, exist_ok=True)

    old_db, old_lock = store.DB_PATH, store.LOCK_PATH
    store.DB_PATH = target
    store.LOCK_PATH = target.parent / ".write.lock"
    store.warehouse_tables_cache_clear()
    store.warehouse_pool_clear()
    total = 0
    try:
        for season in args.seasons:
            total += load_season(season, args.dry_run)
    finally:
        store.DB_PATH = old_db
        store.LOCK_PATH = old_lock
        store.warehouse_tables_cache_clear()
        store.warehouse_pool_clear()
    print(f"{TABLE}: {total} rows total")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
