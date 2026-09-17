"""Promote historical playoff slices.

Team rows for every offline historical season are promoted from silver_hist_gamelogs. Player playoff game
logs come from the existing nba_api source for every player in the historical
2023-24 player-season population. Writes are season-scoped and idempotent.
A resumable progress file prevents a full player refetch after interruption.

Usage:
  python -m scripts.seed_2023_24_playoffs --check
  python -m scripts.seed_2023_24_playoffs --team-only
  python -m scripts.seed_2023_24_playoffs --team-only --season 2022-23
  python -m scripts.seed_2023_24_playoffs --all-team-seasons
  python -m scripts.seed_2023_24_playoffs [--limit N]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import store
from app.sources import nba_stats
from app.sources.base import FetchMeta, FetchResult

SEASON = "2023-24"
END_YEAR = 2024
SEASON_ID = "22023"
SOURCE = "sportsdataverse"
PROGRESS_FILE = Path(__file__).with_name("seed_2023_24_playoffs_progress.json")

TEAM_COLS = [
    "SEASON_ID", "TEAM_ID", "TEAM_ABBREVIATION", "TEAM_NAME", "GAME_ID",
    "GAME_DATE", "MATCHUP", "WL", "MIN", "PTS", "FGM", "FGA", "FG_PCT",
    "FG3M", "FG3A", "FG3_PCT", "FTM", "FTA", "FT_PCT", "OREB", "DREB",
    "REB", "AST", "STL", "BLK", "TOV", "PF", "PLUS_MINUS",
]


def canonical_season(end_year: int) -> str:
    return f"{end_year - 1:04d}-{end_year % 100:02d}"


def available_team_seasons(con) -> list[int]:
    return [int(row[0]) for row in con.execute(
        """SELECT DISTINCT season FROM silver_hist_gamelogs
        WHERE season_type = 'playoffs' AND season IS NOT NULL
        ORDER BY season"""
    ).fetchall()]


def team_rows(con, end_year: int = END_YEAR) -> pl.DataFrame:
    cols = ", ".join(f'{name.lower()} AS "{name}"' for name in TEAM_COLS)
    return pl.from_arrow(con.execute(
        f"""SELECT {cols} FROM silver_hist_gamelogs
        WHERE season = ? AND season_type = 'playoffs'
        ORDER BY game_date, game_id, team_id""",
        [end_year],
    ).to_arrow_table())


def validate_team_rows(frame: pl.DataFrame) -> None:
    if frame.is_empty():
        raise ValueError("historical source has no playoff team rows")
    if frame.select(pl.col("TEAM_ID").n_unique()).item() < 2:
        raise ValueError("playoff seed must contain multiple teams")
    counts = frame.group_by("GAME_ID").len()
    if counts.filter(pl.col("len") != 2).height:
        raise ValueError("every playoff game must have exactly two team rows")
    if frame.select(pl.struct(["TEAM_ID", "GAME_ID"]).n_unique()).item() != frame.height:
        raise ValueError("playoff team seed contains duplicate team-game rows")


def seed_team_rows(end_year: int = END_YEAR) -> int:
    season = canonical_season(end_year)
    con = store.connect()
    try:
        frame = team_rows(con, end_year)
    finally:
        con.close()
    validate_team_rows(frame)
    result = FetchResult(frame=frame, meta=FetchMeta(source=SOURCE, season=season))
    return store.save_frame("silver_playoffs", result, replace_season=True)


def seed_all_team_rows() -> dict[str, int]:
    con = store.connect(read_only=True)
    try:
        seasons = available_team_seasons(con)
    finally:
        con.close()
    return {canonical_season(end_year): seed_team_rows(end_year)
            for end_year in seasons}


def player_ids(con) -> list[int]:
    return [int(row[0]) for row in con.execute(
        """SELECT DISTINCT player_id FROM silver_hist_player_seasons
        WHERE season = ? AND player_id IS NOT NULL ORDER BY player_id""",
        [END_YEAR],
    ).fetchall()]


def _progress() -> dict:
    if PROGRESS_FILE.exists():
        return json.loads(PROGRESS_FILE.read_text())
    return {"done": [], "failed": {}}


def seed_player_rows(limit: int | None = None) -> dict[str, int]:
    con = store.connect()
    try:
        ids = player_ids(con)
    finally:
        con.close()
    if limit is not None:
        ids = ids[:limit]
    progress = _progress()
    done = {int(value) for value in progress.get("done", [])}
    failed = dict(progress.get("failed", {}))
    counts = {"players": 0, "rows": 0, "failed": 0}
    for player_id in ids:
        if player_id in done:
            continue
        result = nba_stats.player_playoff_gamelog(player_id, SEASON)
        if not result.ok:
            failed[str(player_id)] = result.error or "empty upstream response"
            counts["failed"] += 1
        else:
            frame = result.frame
            if frame.height:
                # NBA endpoint returns the target table shape; save_frame adds
                # source, season, fetch time, and player entity provenance.
                saved = store.save_frame(
                    "silver_playoff_gamelogs",
                    FetchResult(frame=frame, meta=FetchMeta(
                        source=result.meta.source, season=SEASON,
                        fetched_at=result.meta.fetched_at)),
                    entity=f"player:{player_id}",
                )
                counts["rows"] += saved
            done.add(player_id)
            failed.pop(str(player_id), None)
            counts["players"] += 1
        progress = {"done": sorted(done), "failed": failed}
        PROGRESS_FILE.write_text(json.dumps(progress, indent=1))
    return counts


def check() -> dict[str, int]:
    con = store.connect(read_only=True)
    try:
        tables = {row[0] for row in con.execute("SHOW TABLES").fetchall()}
        out = {}
        for table in ("silver_playoffs", "silver_playoff_gamelogs"):
            out[table] = (con.execute(
                f"SELECT COUNT(*) FROM {table} WHERE _season = ?", [SEASON]
            ).fetchone()[0] if table in tables else 0)
        return out
    finally:
        con.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--team-only", action="store_true")
    parser.add_argument("--all-team-seasons", action="store_true")
    parser.add_argument("--season", default=SEASON)
    parser.add_argument("--limit", type=int)
    args = parser.parse_args(argv)
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be >= 1")
    if args.check:
        counts = check()
        print(json.dumps(counts, sort_keys=True))
        return 0 if all(counts.values()) else 1
    if args.all_team_seasons:
        print(json.dumps(seed_all_team_rows(), sort_keys=True))
        return 0
    try:
        start, end = args.season.split("-", 1)
        end_year = int(start) + 1
        if int(end) != end_year % 100:
            raise ValueError
    except (ValueError, AttributeError):
        parser.error("--season must use consecutive YYYY-YY format")
    print(f"silver_playoffs: wrote {seed_team_rows(end_year)} rows")
    if not args.team_only:
        if args.season != SEASON:
            parser.error("player promotion is currently supported only for 2023-24")
        print(json.dumps(seed_player_rows(args.limit), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
