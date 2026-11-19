import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from shared import store
from shared.sources.base import FetchMeta, FetchResult

SDV = "https://github.com/sportsdataverse/sportsdataverse-data/releases/download"
SRC_TGL = "sportsdataverse:nba_stats_team_game_logs"
SRC_PGL = "sportsdataverse:nba_stats_player_game_logs"
SRC_PSS = "sportsdataverse:nba_stats_player_season_stats"
SRC_STANDINGS = "nba_api"
LEADER_CATS = ["PTS", "REB", "AST", "STL", "BLK", "DREB"]

TEAM_GAME_SELECT = """
SELECT
  team_id AS "Team_ID",
  game_id AS "Game_ID",
  UPPER(STRFTIME(CAST(game_date AS DATE), '%b %d, %Y')) AS "GAME_DATE",
  matchup AS "MATCHUP",
  wl AS "WL",
  SUM(CASE WHEN wl = 'W' THEN 1 ELSE 0 END) OVER
    (PARTITION BY team_id ORDER BY game_date, game_id
     ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS "W",
  SUM(CASE WHEN wl = 'L' THEN 1 ELSE 0 END) OVER
    (PARTITION BY team_id ORDER BY game_date, game_id
     ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS "L",
  CAST(SUM(CASE WHEN wl = 'W' THEN 1 ELSE 0 END) OVER
    (PARTITION BY team_id ORDER BY game_date, game_id
     ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS DOUBLE) /
    CAST(ROW_NUMBER() OVER
    (PARTITION BY team_id ORDER BY game_date, game_id) AS DOUBLE) AS "W_PCT",
  min AS "MIN", fgm AS "FGM", fga AS "FGA", fg_pct AS "FG_PCT",
  fg3m AS "FG3M", fg3a AS "FG3A", fg3_pct AS "FG3_PCT",
  ftm AS "FTM", fta AS "FTA", ft_pct AS "FT_PCT",
  oreb AS "OREB", dreb AS "DREB", reb AS "REB", ast AS "AST",
  stl AS "STL", blk AS "BLK", tov AS "TOV", pf AS "PF", pts AS "PTS"
FROM silver_hist_gamelogs
WHERE season = ? AND season_type = 'regular-season'
"""


def end_year(season: str) -> int:
    year, _, tail = str(season).partition("-")
    if len(year) != 4 or not year.isdigit() or len(tail) != 2 \
            or not tail.isdigit() or int(tail) != (int(year) + 1) % 100:
        raise ValueError(f"season must read YYYY-YY, got {season!r}")
    return int(year) + 1


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


def save(table: str, frame: pl.DataFrame, source: str, season: str,
         entity: str, dry_run: bool) -> int:
    if dry_run:
        print(f"{table}: {frame.height} rows (dry-run)")
        return 0
    res = FetchResult(frame=frame, meta=FetchMeta(source=source, season=season))
    n = store.save_frame(table, res, entity=entity, replace_season=True)
    print(f"{table}: {n} rows")
    return n


def load_hist_gamelogs(season: str, dry_run: bool) -> int:
    y = end_year(season)
    df = pl.read_parquet(f"{SDV}/nba_stats_team_game_logs/team_game_logs_{y}.parquet")
    df = df.filter(pl.col("season_type").is_in(["regular-season", "playoffs"]))
    df = df.with_columns(pl.lit(y).alias("season"))
    return save("silver_hist_gamelogs", df, SRC_TGL, season,
                f"season:{season}", dry_run)


def load_player_gamelogs(season: str, dry_run: bool) -> int:
    y = end_year(season)
    df = pl.read_parquet(f"{SDV}/nba_stats_player_game_logs/player_game_logs_{y}.parquet")
    df = df.filter(pl.col("season_type") == "regular-season")
    import datetime as _dt

    def fmt(d):
        try:
            return _dt.date.fromisoformat(str(d)).strftime("%b %-d, %Y")
        except (TypeError, ValueError):
            return str(d)

    out = pl.DataFrame({
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
    return save("silver_player_gamelogs", out, SRC_PGL, season,
                "league", dry_run)


def build_team_games(season: str, dry_run: bool) -> int:
    con = store.connect()
    try:
        df = con.execute(TEAM_GAME_SELECT + " ORDER BY 1, 2",
                         [end_year(season)]).pl()
    finally:
        con.close()
    if dry_run:
        print(f"silver_team_games: {df.height} rows (dry-run)")
        return 0
    fetched = datetime.now(timezone.utc).isoformat()
    df = df.with_columns([
        pl.lit(SRC_TGL).alias("_source"),
        pl.lit(season).alias("_season"),
        pl.lit(fetched).alias("_fetched_at"),
        pl.lit("league").alias("_entity"),
    ])
    res = FetchResult(frame=df, meta=FetchMeta(source=SRC_TGL, season=season,
                                             fetched_at=fetched))
    n = store.save_frame("silver_team_games", res, entity="league",
                         replace_season=True)
    print(f"silver_team_games: {n} rows")
    return n


def load_player_season(season: str, dry_run: bool) -> int:
    y = end_year(season)
    pss = pl.read_parquet(f"{SDV}/nba_stats_player_season_stats/"
                          f"player_season_stats_{y}.parquet")
    pss = pss.filter(pl.col("season_type") == "regular-season")
    ages = {r[0]: r[1] for r in pss.select(
        ["player_id", "age"]).iter_rows()}
    pgl = pl.read_parquet(f"{SDV}/nba_stats_player_game_logs/"
                          f"player_game_logs_{y}.parquet")
    pgl = pgl.filter(pl.col("season_type") == "regular-season")
    agg = pgl.group_by("player_id").agg([
        pl.col("player_name").first().alias("PLAYER"),
        pl.col("team_abbreviation").last().alias("TEAM"),
        pl.len().alias("GP"),
        pl.col("min").mean().round(1).alias("MPG"),
        pl.col("pts").mean().round(1).alias("PPG"),
        pl.col("reb").mean().round(1).alias("RPG"),
        pl.col("ast").mean().round(1).alias("APG"),
        pl.col("stl").mean().round(1).alias("SPG"),
        pl.col("blk").mean().round(1).alias("BPG"),
        (pl.col("fgm").sum() / pl.col("fga").sum()).round(3)
            .alias("FG_PCT"),
        (pl.col("fg3m").sum() / pl.col("fg3a").sum()).round(3)
            .alias("FG3_PCT"),
        (pl.col("ftm").sum() / pl.col("fta").sum()).round(3)
            .alias("FT_PCT"),
    ])
    out = pl.DataFrame({
        "PLAYER_ID": agg["player_id"],
        "PLAYER": agg["PLAYER"],
        "TEAM": agg["TEAM"],
        "AGE": [ages.get(p) for p in agg["player_id"].to_list()],
        "GP": agg["GP"],
        "GS": [None] * agg.height,
        "MPG": agg["MPG"], "PPG": agg["PPG"], "RPG": agg["RPG"],
        "APG": agg["APG"], "SPG": agg["SPG"], "BPG": agg["BPG"],
        "FG_PCT": agg["FG_PCT"], "FG3_PCT": agg["FG3_PCT"],
        "FT_PCT": agg["FT_PCT"],
    }).sort("PPG", descending=True)
    return save("silver_player_season", out, SRC_PSS, season,
                "league", dry_run)


def load_standings(season: str, dry_run: bool) -> int:
    from shared.sources import nba_stats
    res = nba_stats.standings(season)
    if not res.ok or res.frame.height == 0:
        print("standings fetch failed:", res.error)
        return 0
    if dry_run:
        print(f"silver_standings: {res.frame.height} rows (dry-run)")
        return 0
    n = store.save_frame("silver_standings", res, replace_season=True)
    print(f"silver_standings: {n} rows")
    return n


def load_leaders(season: str, dry_run: bool) -> int:
    from shared.sources import nba_stats
    total = 0
    for cat in LEADER_CATS:
        res = nba_stats.leaders(cat, season)
        if not res.ok or res.frame.height == 0:
            print(f"leaders {cat} fetch failed:", res.error)
            continue
        table = f"silver_leaders_{cat.lower()}"
        if dry_run:
            print(f"{table}: {res.frame.height} rows (dry-run)")
            continue
        n = store.save_frame(table, res, replace_season=True)
        print(f"{table}: {n} rows")
        total += n
    return total


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scratch-db", default="")
    parser.add_argument("--season", default="2026-27")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-live", action="store_true",
                        help="only load sportsdataverse bulk tables")
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
        total += load_hist_gamelogs(args.season, args.dry_run)
        total += load_player_gamelogs(args.season, args.dry_run)
        total += build_team_games(args.season, args.dry_run)
        total += load_player_season(args.season, args.dry_run)
        if not args.skip_live:
            total += load_standings(args.season, args.dry_run)
            total += load_leaders(args.season, args.dry_run)
    finally:
        store.DB_PATH = old_db
        store.LOCK_PATH = old_lock
        store.warehouse_tables_cache_clear()
        store.warehouse_pool_clear()
    print(f"current-season rows loaded: {total}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
