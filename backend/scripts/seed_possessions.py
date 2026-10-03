import argparse
import json
import os
import sys
import urllib.request
from pathlib import Path

import duckdb
import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared import possessions, store
from shared.tools.wpamodel import win_probability

TABLE = "silver_possessions"
SOURCE = "nba_stats_pbp"
GAMELOG_TABLE = "silver_hist_gamelogs"

BASE = "https://github.com/sportsdataverse/sportsdataverse-data/releases/download"
TAG = "nba_stats_pbp"
ASSET = "nba_play_by_play_{y}.parquet"

SEASONS = list(range(2016, 2026))
DEFAULT_PARQUET_DIR = Path.home() / "workspace" / "goals" / "dime-playground" / \
    "hidden_files" / "possession-log-scratch"
DEFAULT_TARGET = Path.home() / "workspace" / "dime-backfill-scratch" / \
    "possessions.duckdb"

SCHEMA = {
    "game_id": pl.String,
    "possession_number": pl.Int64,
    "period": pl.Int64,
    "clock_in": pl.String,
    "clock_out": pl.String,
    "clock_in_sec": pl.Float64,
    "clock_out_sec": pl.Float64,
    "off_team_id": pl.Int64,
    "def_team_id": pl.Int64,
    "off_abbr": pl.String,
    "def_abbr": pl.String,
    "home_team_id": pl.Int64,
    "away_team_id": pl.Int64,
    "events": pl.String,
    "points": pl.Int64,
    "wpa_delta": pl.Float64,
    "score_home_in": pl.Int64,
    "score_away_in": pl.Int64,
    "score_home_out": pl.Int64,
    "score_away_out": pl.Int64,
}


def season_label(end_year):
    return f"{int(end_year) - 1}-{str(int(end_year))[2:]}"


def season_for_game(game_id):
    try:
        return 2000 + int(str(game_id)[3:5]) + 1
    except (TypeError, ValueError):
        return 0


def fetch(url, dest):
    if dest.exists() and dest.stat().st_size > 0:
        return True
    try:
        req = urllib.request.Request(url,
                                     headers={"User-Agent": "dime-seed/1.0"})
        with urllib.request.urlopen(req, timeout=300) as r, \
                open(dest, "wb") as f:
            f.write(r.read())
        return dest.stat().st_size > 0
    except Exception as exc:
        print(f"skip {url.split('/')[-1]}: {str(exc)[:80]}")
        try:
            dest.unlink()
        except OSError:
            pass
        return False


def ensure_parquet(year, parquet_dir):
    dest = Path(parquet_dir) / ASSET.format(y=year)
    if fetch(f"{BASE}/{TAG}/{ASSET.format(y=year)}", dest):
        return dest
    return None


def season_games(parquet_path):
    con = duckdb.connect()
    try:
        return [r[0] for r in con.execute(
            "SELECT DISTINCT game_id FROM read_parquet(?) ORDER BY game_id",
            [str(parquet_path)]).fetchall() if r[0]]
    finally:
        con.close()


def load_game_rows(parquet_path, game_id):
    frame = pl.read_parquet(parquet_path)
    return game_rows(frame, game_id)


def game_rows(frame, game_id):
    game = frame.filter(pl.col("game_id") == game_id)
    if game.height == 0:
        return []
    return sorted(game.to_dicts(),
                  key=lambda r: int(r.get("order_index") or 0))


def resolve_home_away(source_db, game_id):
    con = duckdb.connect(str(source_db), read_only=True)
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        if GAMELOG_TABLE not in tables:
            return None
        rel = con.execute(
            f"SELECT team_id, matchup, team_abbreviation FROM "
            f"{GAMELOG_TABLE} WHERE game_id = ?",
            [game_id])
        cols = [d[0] for d in rel.description]
        logs = [dict(zip(cols, r)) for r in rel.fetchall()]
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
    return home[0], away[0]


def game_seconds(period, sec):
    try:
        left = float(sec)
        num = int(period)
    except (TypeError, ValueError):
        return 0.0
    if num <= 4:
        return left + 720.0 * (4 - num)
    return left


def wpa_delta(parsed, home_id):
    lead_in = int(parsed["score_home_in"]) - int(parsed["score_away_in"])
    lead_out = int(parsed["score_home_out"]) - int(parsed["score_away_out"])
    before = win_probability(lead_in,
                             game_seconds(parsed["period"],
                                          parsed["clock_in_sec"]))
    after = win_probability(lead_out,
                            game_seconds(parsed["period"],
                                         parsed["clock_out_sec"]))
    delta = float(after) - float(before)
    if int(parsed["off_team_id"]) != int(home_id):
        delta = -delta
    return delta


def possessions_frame(game_id, parsed, home_id, away_id):
    rows = []
    for item in parsed:
        rows.append({
            "game_id": game_id,
            "possession_number": int(item["possession_number"]),
            "period": int(item["period"]),
            "clock_in": str(item["clock_in"]),
            "clock_out": str(item["clock_out"]),
            "clock_in_sec": float(item["clock_in_sec"]),
            "clock_out_sec": float(item["clock_out_sec"]),
            "off_team_id": int(item["off_team_id"]),
            "def_team_id": int(item["def_team_id"]),
            "off_abbr": str(item["off_abbr"]),
            "def_abbr": str(item["def_abbr"]),
            "home_team_id": int(home_id),
            "away_team_id": int(away_id),
            "events": json.dumps(list(item["events"])),
            "points": int(item["points"]),
            "wpa_delta": wpa_delta(item, home_id),
            "score_home_in": int(item["score_home_in"]),
            "score_away_in": int(item["score_away_in"]),
            "score_home_out": int(item["score_home_out"]),
            "score_away_out": int(item["score_away_out"]),
        })
    return pl.DataFrame(rows, schema=SCHEMA)


def sanity_points(parsed):
    if not parsed:
        return False, "no possessions derived"
    last = parsed[-1]
    final = int(last["score_home_out"]) + int(last["score_away_out"])
    credited = sum(int(item["points"]) for item in parsed)
    if credited != final:
        return False, f"points {credited} != final {final}"
    return True, f"{len(parsed)} possessions"


def unit_complete(season, entity):
    try:
        return bool(store.last_fetch(TABLE, season, entity))
    except Exception:
        return False


def entity_for(game_id):
    return f"game:{game_id}"


def materialize_game(rows, source_db, game_id, season=""):
    if not rows:
        return False, "no pbp rows"
    if not season:
        return False, "season unresolvable"
    try:
        parsed = possessions.parse_game_possessions(rows)
    except ValueError as exc:
        return False, f"parse failed: {exc}"[:160]
    if not parsed:
        return False, "no possessions derived"
    placed = resolve_home_away(source_db, game_id)
    if placed is None:
        return False, "home and away unresolvable"
    home_id, away_id = placed
    ok, note = sanity_points(parsed)
    if not ok:
        return False, note
    frame = possessions_frame(game_id, parsed, home_id, away_id)
    if frame.height == 0:
        return False, "no possessions derived"
    store.write_unit(TABLE, frame, season, SOURCE, entity_for(game_id),
                     "game_id = ?", [game_id])
    return True, note


def resolve_target(raw):
    target = Path(raw or str(DEFAULT_TARGET)).expanduser()
    print(f"target: {target}")
    try:
        if target.resolve() == store.CANONICAL_DB_PATH:
            print("refusing: target is the canonical warehouse")
            return None
    except Exception:
        pass
    return target


def parse_years(raw):
    years = []
    for chunk in str(raw or "").split(","):
        chunk = chunk.strip()
        if chunk:
            years.append(int(chunk))
    bad = [y for y in years if y not in SEASONS]
    if bad:
        print(f"season out of range {bad}: seed covers 2016..2025 only")
        raise SystemExit(1)
    if not years:
        print("no seasons requested")
        raise SystemExit(1)
    return years


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", default=str(DEFAULT_TARGET))
    ap.add_argument("--seasons", default=",".join(str(y) for y in SEASONS))
    ap.add_argument("--pilot-game", default="")
    ap.add_argument("--parquet-dir", default=str(DEFAULT_PARQUET_DIR))
    ap.add_argument("--source-db", default=str(store.CANONICAL_DB_PATH))
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    target = resolve_target(args.target)
    if target is None:
        return 1
    target.parent.mkdir(parents=True, exist_ok=True)
    store.DB_PATH = target
    store.LOCK_PATH = target.parent / ".write.lock"
    parquet_dir = Path(args.parquet_dir)
    parquet_dir.mkdir(parents=True, exist_ok=True)
    if args.pilot_game:
        gid = str(args.pilot_game).strip()
        year = season_for_game(gid)
        if year not in SEASONS:
            print(f"pilot game {gid} maps outside 2016..2025")
            return 1
        path = ensure_parquet(year, parquet_dir)
        if path is None:
            print(f"pilot parquet missing for {year}")
            return 1
        if gid not in season_games(path):
            print(f"pilot game {gid} not in {path.name}")
            return 1
        plans = [(season_label(year), path, [gid])]
    else:
        years = parse_years(args.seasons)
        plans = []
        for year in years:
            path = ensure_parquet(year, parquet_dir)
            if path is None:
                print(f"FAIL season {season_label(year)}: download failed")
                return 1
            ids = season_games(path)
            if args.limit and args.limit > 0:
                ids = ids[:args.limit]
            plans.append((season_label(year), path, ids))
    if args.dry_run:
        total = 0
        for season, path, ids in plans:
            for gid in ids:
                print(f"{TABLE} {season} {gid}")
                total += 1
        print(f"games: {total}")
        return 0
    done = skipped = failed = 0
    for season, path, ids in plans:
        frame = None
        if not args.dry_run and ids:
            frame = pl.read_parquet(path)
        for gid in ids:
            if unit_complete(season, entity_for(gid)):
                print(f"skip {TABLE} {season} {gid}", flush=True)
                done += 1
                continue
            try:
                rows = game_rows(frame, gid) if frame is not None else []
                ok, note = materialize_game(rows, args.source_db, gid,
                                            season)
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
