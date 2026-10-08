import argparse
import os
import sys
from pathlib import Path

import duckdb
import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared import stints, store

TABLE = "silver_stints"
SOURCE = "silver_hist_possessions"
POSSESSION_TABLE = "silver_hist_possessions"
GAMELOG_TABLE = "silver_hist_gamelogs"

SCHEMA = {
    "game_id": pl.String,
    "stint_number": pl.Int64,
    "poss_start": pl.Int64,
    "poss_end": pl.Int64,
    "period_in": pl.Int64,
    "clock_in": pl.String,
    "period_out": pl.Int64,
    "clock_out": pl.String,
    "clock_in_sec": pl.Float64,
    "clock_out_sec": pl.Float64,
    "duration_sec": pl.Float64,
    "home_team_id": pl.Int64,
    "away_team_id": pl.Int64,
    "home_abbr": pl.String,
    "away_abbr": pl.String,
    "home_player_1": pl.Int64,
    "home_player_2": pl.Int64,
    "home_player_3": pl.Int64,
    "home_player_4": pl.Int64,
    "home_player_5": pl.Int64,
    "away_player_1": pl.Int64,
    "away_player_2": pl.Int64,
    "away_player_3": pl.Int64,
    "away_player_4": pl.Int64,
    "away_player_5": pl.Int64,
    "score_home_in": pl.Int64,
    "score_away_in": pl.Int64,
    "score_home_out": pl.Int64,
    "score_away_out": pl.Int64,
    "home_swing": pl.Int64,
}

POSSESSION_COLS = [
    "possession_number",
    "period",
    "start_seconds_remaining",
    "end_seconds_remaining",
    "offense_team_id",
    "points",
    "off_player_1",
    "off_player_2",
    "off_player_3",
    "off_player_4",
    "off_player_5",
    "def_player_1",
    "def_player_2",
    "def_player_3",
    "def_player_4",
    "def_player_5",
]


def _tables(con):
    return {r[0] for r in con.execute("SHOW TABLES").fetchall()}


def _rows(con, sql, params):
    rel = con.execute(sql, params or [])
    cols = [d[0] for d in rel.description]
    return [dict(zip(cols, r)) for r in rel.fetchall()]


def load_possessions(source_db, game_id):
    con = duckdb.connect(str(source_db), read_only=True)
    try:
        if POSSESSION_TABLE not in _tables(con):
            return [], ""
        cols = ", ".join(POSSESSION_COLS)
        rows = _rows(
            con,
            f"SELECT {cols}, _season FROM {POSSESSION_TABLE} "
            "WHERE game_id = ? ORDER BY possession_number",
            [game_id])
    finally:
        con.close()
    seasons = sorted({str(r.get("_season") or "") for r in rows})
    seasons = [s for s in seasons if s]
    if len(seasons) != 1:
        return rows, ""
    return rows, seasons[0]


def resolve_home_away(source_db, game_id):
    con = duckdb.connect(str(source_db), read_only=True)
    try:
        if GAMELOG_TABLE not in _tables(con):
            return None
        logs = _rows(
            con,
            f"SELECT team_id, matchup, team_abbreviation FROM "
            f"{GAMELOG_TABLE} WHERE game_id = ?",
            [game_id])
    finally:
        con.close()
    home = away = None
    for row in logs:
        try:
            tid = int(row.get("team_id"))
        except (TypeError, ValueError):
            continue
        matchup = str(row.get("matchup") or "")
        abbr = str(row.get("team_abbreviation") or "")
        if " vs. " in matchup:
            home = (tid, abbr)
        elif " @ " in matchup:
            away = (tid, abbr)
    if home is None or away is None or home[0] == away[0]:
        return None
    if not home[1] or not away[1]:
        return None
    return home[0], away[0], home[1], away[1]


def stints_frame(game_id, rows, season, placed):
    home_id, away_id, home_abbr, away_abbr = placed
    built = stints.build_stints(
        game_id, rows, home_id, away_id, home_abbr, away_abbr)
    slim = [{k: r.get(k) for k in SCHEMA} for r in built]
    return pl.DataFrame(slim, schema=SCHEMA)


def unit_complete(season, entity):
    try:
        return bool(store.last_fetch(TABLE, season, entity))
    except Exception:
        return False


def materialize_game(source_db, game_id, season=""):
    rows, row_season = load_possessions(source_db, game_id)
    if not rows:
        return False, "no possession rows"
    season = season or row_season
    if not season:
        return False, "season unresolvable"
    placed = resolve_home_away(source_db, game_id)
    if placed is None:
        return False, "home and away unresolvable"
    frame = stints_frame(game_id, rows, season, placed)
    if frame.height == 0:
        return False, "no stints derived"
    store.write_unit(TABLE, frame, season, SOURCE, game_id,
                     "game_id = ?", [game_id])
    return True, f"{frame.height} stints"


def available_seasons(source_db):
    con = duckdb.connect(str(source_db), read_only=True)
    try:
        if POSSESSION_TABLE not in _tables(con):
            return []
        return [r[0] for r in con.execute(
            f"SELECT DISTINCT _season FROM {POSSESSION_TABLE} "
            "ORDER BY _season").fetchall() if r[0]]
    finally:
        con.close()


def season_games(source_db, season):
    con = duckdb.connect(str(source_db), read_only=True)
    try:
        if POSSESSION_TABLE not in _tables(con):
            return []
        return [r[0] for r in con.execute(
            f"SELECT DISTINCT game_id FROM {POSSESSION_TABLE} "
            "WHERE _season = ? ORDER BY game_id", [season]).fetchall()
            if r[0]]
    finally:
        con.close()


def resolve_target(raw_db):
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


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", default="")
    ap.add_argument("--game-id", default="")
    ap.add_argument("--db", default="")
    ap.add_argument("--source-db", default="")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    target = resolve_target(args.db)
    if target is None:
        return 1
    target.parent.mkdir(parents=True, exist_ok=True)
    store.DB_PATH = target
    store.LOCK_PATH = target.parent / ".write.lock"
    source_db = args.source_db or str(store.CANONICAL_DB_PATH)
    if args.game_id:
        rows, row_season = load_possessions(source_db, args.game_id)
        seasons = [row_season] if row_season else []
        games = {row_season: [args.game_id]} if row_season else {}
    else:
        picked = [s.strip() for s in str(args.season).split(",") if s.strip()]
        seasons = picked or available_seasons(source_db)
        games = {}
        for season in seasons:
            ids = season_games(source_db, season)
            if args.limit and args.limit > 0:
                ids = ids[:args.limit]
            games[season] = ids
    if args.dry_run:
        for season in seasons:
            for gid in games.get(season, []):
                print(f"{TABLE} {season} {gid}")
        print(f"games: {sum(len(v) for v in games.values())}")
        return 0
    done = skipped = failed = 0
    for season in seasons:
        for gid in games.get(season, []):
            if unit_complete(season, gid):
                print(f"skip {TABLE} {season} {gid}", flush=True)
                skipped += 1
                continue
            try:
                ok, note = materialize_game(source_db, gid, season)
            except Exception as exc:
                print(f"failed {TABLE} {season} {gid}: {exc}"[:200],
                      flush=True)
                failed += 1
                continue
            if ok:
                print(f"saved {TABLE} {season} {gid} {note}", flush=True)
                done += 1
            else:
                print(f"skip {TABLE} {season} {gid}: {note}", flush=True)
                skipped += 1
    print(f"done games={done} skipped={skipped} failed={failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
