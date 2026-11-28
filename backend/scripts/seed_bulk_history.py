import argparse
import datetime
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import polars as pl

from shared import store

BASE = "https://github.com/sportsdataverse/sportsdataverse-data/releases/download"
SOURCE_GAMES = "sportsdataverse:nba_stats_team_game_logs"
SOURCE_PLAYER_SEASONS = "sportsdataverse:nba_stats_player_season_stats"
SOURCE_TEAM_SEASONS = "sportsdataverse:nba_stats_team_season_stats"

PLAYER_BASE_COLS = [
    "player_id", "player_name", "team_abbreviation", "season", "age", "gp", "min",
    "pts", "reb", "ast", "stl", "blk", "tov", "fgm", "fga", "fg_pct",
    "fg3m", "fg3a", "fg3_pct", "ftm", "fta", "ft_pct",
]
PLAYER_ADV_COLS = ["player_id", "ts_pct", "efg_pct", "usg_pct", "off_rating",
                   "def_rating", "net_rating", "pie", "pace"]
PLAYER_JOIN_KEY = ["player_id", "team_abbreviation"]

def completed_end_year(today: datetime.date | None = None) -> int:
    now = today or datetime.date.today()
    return now.year if now.month >= 6 else now.year - 1


DATASETS = {
    "hist_gamelogs": {
        "table": "silver_hist_gamelogs",
        "source": SOURCE_GAMES,
        "entity": "season:{season}",
        "years": range(1997, completed_end_year() + 1),
        "file": "nba_stats_team_game_logs/team_game_logs_{year}.parquet",
        "min_rows": 1400,
        "transform": "hist_gamelogs",
    },
    "player_seasons": {
        "table": "silver_hist_player_seasons",
        "source": SOURCE_PLAYER_SEASONS,
        "entity": "league",
        "years": range(1997, completed_end_year() + 1),
        "file": "nba_stats_player_season_stats/player_season_stats_{year}.parquet",
        "min_rows": 300,
        "transform": "player_seasons",
    },
    "team_seasons": {
        "table": "silver_hist_team_seasons",
        "source": SOURCE_TEAM_SEASONS,
        "entity": "league",
        "years": range(1997, completed_end_year() + 1),
        "file": "nba_stats_team_season_stats/team_season_stats_{year}.parquet",
        "min_rows": 300,
        "transform": "team_seasons",
    },
}


def label(end_year: int) -> str:
    return f"{end_year - 1}-{str(end_year)[2:]}"


def resolve_target(raw_db: str | None) -> Path | None:
    raw = raw_db or os.environ.get("DIME_WAREHOUSE", "")
    if not raw:
        print("refusing: DIME_WAREHOUSE is not set")
        return None
    target = Path(raw).expanduser().resolve()
    print(f"target: {target}")
    if target == store.CANONICAL_DB_PATH:
        print("refusing: target is the canonical warehouse")
        return None
    return target


def transform_hist_gamelogs(df: pl.DataFrame) -> pl.DataFrame:
    return df.filter(pl.col("season_type").is_in(["regular-season", "playoffs"]))


def transform_player_seasons(df: pl.DataFrame) -> pl.DataFrame:
    rs = df.filter(
        (pl.col("season_type") == "regular-season")
        & (pl.col("per_mode") == "pergame")
    )
    base = rs.filter(pl.col("measure_type") == "base").select(PLAYER_BASE_COLS)
    adv = rs.filter(pl.col("measure_type") == "advanced").select(
        PLAYER_ADV_COLS + ["team_abbreviation"]
    )
    return base.join(adv, on=PLAYER_JOIN_KEY, how="left")


def transform_team_seasons(df: pl.DataFrame) -> pl.DataFrame:
    return df.filter(pl.col("season_type") == "regular-season")


def transform(name: str, df: pl.DataFrame) -> pl.DataFrame:
    if name == "hist_gamelogs":
        return transform_hist_gamelogs(df)
    if name == "player_seasons":
        return transform_player_seasons(df)
    return transform_team_seasons(df)


def unit_done(table: str, season: str, entity: str) -> bool:
    try:
        return bool(store.last_fetch(table, season, entity))
    except Exception:
        return False


def read_frame(spec: dict, year: int) -> pl.DataFrame:
    url = f"{BASE}/{spec['file'].format(year=year)}"
    return pl.read_parquet(url)


def run_dataset(name: str, spec: dict, years: list[int], force: bool,
                dry_run: bool) -> tuple[int, int, list[str]]:
    table = spec["table"]
    source = spec["source"]
    written = 0
    skipped = 0
    failures: list[str] = []
    newest = max(years) if years else 0
    for year in years:
        season = label(year)
        entity = spec["entity"].format(season=season)
        if not force and unit_done(table, season, entity):
            skipped += 1
            continue
        try:
            frame = transform(spec["transform"], read_frame(spec, year))
        except Exception as exc:
            if year == newest:
                print(f"{name} {season}: newest-year upstream not yet available, skipping ({exc})")
                skipped += 1
                continue
            failures.append(f"{name} {season}: fetch/transform failed ({exc})")
            continue
        if frame.height < spec["min_rows"]:
            if year == newest:
                print(f"{name} {season}: newest-year upstream partial ({frame.height} rows), skipping")
                skipped += 1
                continue
            failures.append(
                f"{name} {season}: only {frame.height} rows, "
                f"expected at least {spec['min_rows']}"
            )
            continue
        if dry_run:
            print(f"{name} {season}: dry-run {frame.height} rows -> {table}")
            written += frame.height
            continue
        n = store.write_unit(
            table,
            frame,
            season,
            source,
            entity,
            "_season = ? AND _entity = ?",
            [season, entity],
        )
        written += n
        print(f"{name} {season}: {n} rows -> {table}")
    return written, skipped, failures


def parse_years(raw: str) -> list[int]:
    if not raw:
        return []
    return sorted({int(part) for part in raw.split(",") if part.strip()})


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scratch-db", default="")
    parser.add_argument("--datasets", default="hist_gamelogs,player_seasons,team_seasons")
    parser.add_argument("--years", default="")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    target = resolve_target(args.scratch_db)
    if target is None:
        return 2
    target.parent.mkdir(parents=True, exist_ok=True)

    old_db = store.DB_PATH
    old_lock = store.LOCK_PATH
    store.DB_PATH = target
    store.LOCK_PATH = target.parent / ".write.lock"
    store.warehouse_tables_cache_clear()
    store.warehouse_pool_clear()

    failures: list[str] = []
    total = 0
    skipped = 0
    try:
        requested = [part.strip() for part in args.datasets.split(",") if part.strip()]
        unknown = [name for name in requested if name not in DATASETS]
        if unknown:
            print(f"unknown datasets: {', '.join(unknown)}", file=sys.stderr)
            return 2
        years = parse_years(args.years)
        for name in requested:
            spec = DATASETS[name]
            spec_years = list(spec["years"])
            if years:
                spec_years = [year for year in spec_years if year in years]
            w, s, f = run_dataset(name, spec, spec_years, args.force, args.dry_run)
            total += w
            skipped += s
            failures.extend(f)
    finally:
        store.DB_PATH = old_db
        store.LOCK_PATH = old_lock
        store.warehouse_tables_cache_clear()
        store.warehouse_pool_clear()

    print(f"done: {total} rows written, {skipped} units skipped, {len(failures)} failures")
    for failure in failures:
        print(failure, file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
