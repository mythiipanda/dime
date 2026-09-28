"""Multi-season boxscore + lineup backfill over stats.nba.com (nba_api).

What it does
------------
- Enumerates every game per season via LeagueGameFinder
  (Regular Season + Playoffs), cached in backfill_progress.json.
- Per game: traditional boxscore -> silver_boxscores (existing table),
  five detail views (advanced / four_factors / misc / scoring / usage)
  -> bronze_boxscore_ext (raw) + silver_boxscores_ext (wide, 120+ cols).
- Per season: LeagueDashLineups league-wide, base + advanced measures
  -> silver_lineups.
- Optional: PlayByPlayV3 per game -> bronze_pbp + silver_pbp
  (--pbp-seasons 2023-24,2024-25).

Resume / kill-safety
--------------------
- fetch_log watermarks per (dataset, season, entity=game_id); reruns
  skip watermarked games, so a killed run resumes where it stopped and
  a clean rerun performs zero fetches.
- Silver writes are per-game: DELETE existing rows for the game, then
  INSERT. No season-wide table wipes; a crash can never leave a
  half-written season behind.
- Column drift is absorbed (missing columns added via ALTER TABLE),
  never by dropping the table.

Politeness
----------
- --sleep seconds between requests (default 1.5).
- Exponential backoff on 429/timeout: 8s, 16s, 32s, then the game is
  recorded as failed and retried on the next run.

Usage
-----
    DIME_WAREHOUSE=/path/to/warehouse.duckdb \
      python -m scripts.backfill --seasons 2015-16:2024-25 --workers 2
    python -m scripts.backfill --check   # watermark report, no fetching
"""

import argparse
import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Patient retries inside sources/base.py safe(): attempts/backoff are read
# from the environment at call time, so set them before any fetch.
os.environ.setdefault("DIME_LIVE_ATTEMPTS", "3")
os.environ.setdefault("DIME_LIVE_BACKOFF_S", "4")

import polars as pl

from shared import store
from shared.sources import base as _base
from shared.sources import boxscore_ext as _bx
from shared.sources import nba_stats as _nba

PROGRESS_PATH = Path(__file__).resolve().parent / "backfill_progress.json"

SEASON_TYPES = ("Regular Season", "Playoffs")

GAME_TABLE = "silver_boxscores"
EXT_TABLE = "silver_boxscores_ext"
BRONZE_EXT_TABLE = "bronze_boxscore_ext"
LINEUP_TABLE = "silver_lineups"
PBP_TABLE = "silver_pbp"
BRONZE_PBP_TABLE = "bronze_pbp"

_PBP_KEY_RENAME = {
    "gameId": "GAME_ID",
    "actionNumber": "ACTION_NUMBER",
    "teamId": "TEAM_ID",
    "teamTricode": "TEAM_ABBREVIATION",
    "personId": "PLAYER_ID",
    "playerName": "PLAYER_NAME",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# --------------------------------------------------------------------------
# seasons / progress
# --------------------------------------------------------------------------

def parse_seasons(spec: str) -> list[str]:
    out: list[str] = []
    for part in spec.split(","):
        part = part.strip()
        if ":" in part:
            a, b = part.split(":", 1)
            ya, yb = int(a.split("-")[0]), int(b.split("-")[0])
            for y in range(ya, yb + 1):
                out.append(f"{y}-{str(y + 1)[2:]}")
        elif part:
            out.append(part)
    return out


def load_progress() -> dict:
    if PROGRESS_PATH.exists():
        try:
            return json.loads(PROGRESS_PATH.read_text())
        except Exception:
            return {}
    return {}


def save_progress(state: dict) -> None:
    state["updated"] = _now()
    PROGRESS_PATH.write_text(json.dumps(state, indent=1))


# --------------------------------------------------------------------------
# fetching with backoff
# --------------------------------------------------------------------------

def _is_retryable(msg: str) -> bool:
    m = msg.lower()
    return ("429" in m or "too many" in m or "timeout" in m
            or "timed out" in m or "temporar" in m)


def fetch_with_backoff(label: str, fn, sleep_s: float):
    """Call fn() -> FetchResult, backing off on rate limits/timeouts.

    Returns (FetchResult|None, fatal_error). None result with a fatal
    error means do not retry this game on this run.
    """
    delay = 8.0
    last_err = ""
    for attempt in range(4):
        try:
            res = fn()
            if isinstance(res, pl.DataFrame):
                # internal call sites returning bare frames
                res = _base.FetchResult(
                    frame=res,
                    meta=_base.FetchMeta(source="nba_api", season=""))
        except Exception as exc:  # noqa: BLE001 - driver boundary
            res = _base.empty("nba_api", "", f"{type(exc).__name__}: {exc}")
        if res.ok:
            return res, ""
        last_err = res.error or "unknown fetch failure"
        if _is_retryable(last_err) and attempt < 3:
            time.sleep(delay)
            delay *= 2
            continue
        return None, f"{label}: {last_err}"
    return None, f"{label}: backoff exhausted ({last_err[:120]})"


# --------------------------------------------------------------------------
# game enumeration
# --------------------------------------------------------------------------

def season_games(season: str, sleep_s: float, state: dict) -> list[str]:
    cached = state.get("games", {}).get(season)
    if cached:
        ids = [g for st in SEASON_TYPES for g in cached.get(st, [])]
        return list(dict.fromkeys(ids))
    from nba_api.stats.endpoints import LeagueGameFinder

    found: dict[str, list[str]] = {}
    for st in SEASON_TYPES:
        def _run(s=season, t=st):
            ep = LeagueGameFinder(season_nullable=s,
                                  season_type_nullable=t, timeout=30)
            df = ep.get_data_frames()[0]
            try:
                return pl.from_pandas(df)
            except Exception:
                return pl.DataFrame()

        res, err = fetch_with_backoff(f"game-finder {season} {st}", _run,
                                      sleep_s)
        if res is None:
            raise RuntimeError(err)
        ids = (res.frame.get_column("GAME_ID").cast(pl.String).to_list()
               if "GAME_ID" in res.frame.columns else [])
        # LeagueGameFinder returns one row per team per game: dedupe.
        found[st] = list(dict.fromkeys(ids))
        time.sleep(sleep_s)
    state.setdefault("games", {})[season] = found
    save_progress(state)
    return [g for st in SEASON_TYPES for g in found.get(st, [])]


# --------------------------------------------------------------------------
# warehouse writes (per-game, drift-tolerant, never drop tables)
# --------------------------------------------------------------------------
#
# All writes go through store.write_unit: DELETE + INSERT + watermark in
# a SINGLE transaction, so a crash rolls back to the previous complete
# state and a rerun redoes the unit instead of skipping it.


def _canon(frame: pl.DataFrame) -> pl.DataFrame:
    """Cast columns to a small canonical type set so seasons with int32
    vs int64 drift (or similar) land in one schema."""
    exprs = []
    for c, dt in frame.schema.items():
        if dt == pl.String or dt == pl.Utf8:
            exprs.append(pl.col(c).cast(pl.String))
        elif dt in (pl.Int8, pl.Int16, pl.Int32, pl.Int64,
                    pl.UInt8, pl.UInt16, pl.UInt32, pl.UInt64):
            exprs.append(pl.col(c).cast(pl.Int64))
        elif dt in (pl.Float32, pl.Float64):
            exprs.append(pl.col(c).cast(pl.Float64))
        elif dt == pl.Boolean:
            exprs.append(pl.col(c).cast(pl.Boolean))
        else:
            exprs.append(pl.col(c).cast(pl.String))
    return frame.select(exprs)


def insert_game_rows(table: str, frame: pl.DataFrame, season: str,
                     source: str, entity: str, game_id: str,
                     view: str = "") -> int:
    """Idempotent per-game write: delete this game's rows, then insert.

    Never drops the table; absorbs column drift via ALTER TABLE.
    The DELETE, INSERT, and fetch_log watermark run in a SINGLE
    transaction (store.write_unit): a crash rolls back to the previous
    complete state, so a rerun redoes the game instead of skipping it.
    """
    if frame.height == 0:
        return 0
    frame = _canon(frame)
    # Raw bronze frames keep API-native camelCase columns; derive the
    # GAME_ID key the idempotent delete predicate needs.
    if "GAME_ID" not in frame.columns and "gameId" in frame.columns:
        frame = frame.with_columns(
            pl.col("gameId").cast(pl.String).alias("GAME_ID"))
    if view:
        frame = frame.with_columns(pl.lit(view).alias("VIEW"))
    where = ["GAME_ID = ?"]
    params: list = [game_id]
    if view:
        where.append('"VIEW" = ?')
        params.append(view)
    return store.write_unit(table, frame, season, source, entity,
                            " AND ".join(where), params)


def watermarked(table: str, season: str, entity: str) -> bool:
    # Fresh warehouse: the file may not exist yet (read-only open fails).
    try:
        return bool(store.last_fetch(table, season, entity))
    except Exception:
        return False


def watermarked_entities(table: str, season: str) -> set[str]:
    """All watermarked entities for a (dataset, season) in ONE query.

    Per-game last_fetch() opens a connection per call; over 13k games
    that dominates runtime. Batch it for scans, keep the single-shot
    helper for point checks.
    """
    try:
        con = store.connect(read_only=True)
    except Exception:
        return set()
    try:
        try:
            tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
            if "fetch_log" not in tables:
                return set()
            rows = con.execute(
                "SELECT entity FROM fetch_log WHERE dataset = ? AND season = ?",
                [table, season],
            ).fetchall()
            return {r[0] for r in rows if r and r[0]}
        except Exception:
            return set()
    finally:
        con.close()


# --------------------------------------------------------------------------
# per-game backfill
# --------------------------------------------------------------------------

class Counters:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.games = 0
        self.rows_ext = 0
        self.rows_trad = 0
        self.fetches = 0
        self.skipped = 0
        self.failed: list[str] = []

    def bump(self, **kw) -> None:
        with self.lock:
            for k, v in kw.items():
                if k == "failed":
                    self.failed.append(v)
                else:
                    setattr(self, k, getattr(self, k) + v)


def _rename_traditional(frame: pl.DataFrame) -> pl.DataFrame:
    rename = {"gameId": "GAME_ID", "personId": "PLAYER_ID",
              "teamId": "TEAM_ID"}
    existing = {k: v for k, v in rename.items() if k in frame.columns}
    return frame.rename(existing) if existing else frame


def backfill_game(game_id: str, season: str, views: list[str],
                  sleep_s: float, ctr: Counters) -> None:
    if watermarked(EXT_TABLE, season, game_id) and (
            "traditional" not in views
            or watermarked(GAME_TABLE, season, game_id)):
        ctr.bump(skipped=1)
        return

    if "traditional" in views and not watermarked(GAME_TABLE, season,
                                                  game_id):
        res, err = fetch_with_backoff(
            f"traditional {game_id}",
            lambda: _nba.boxscore_traditional(game_id, season), sleep_s)
        time.sleep(sleep_s)
        ctr.bump(fetches=1)
        if res is None:
            ctr.bump(failed=f"{game_id} traditional: {err}")
        else:
            n = insert_game_rows(GAME_TABLE, _rename_traditional(res.frame),
                                 season, _nba.SOURCE, game_id, game_id)
            ctr.bump(rows_trad=n)

    ext_views = [v for v in views if v in _bx.VIEWS]
    if ext_views and not watermarked(EXT_TABLE, season, game_id):
        raw: dict[str, pl.DataFrame] = {}
        silver: dict[str, pl.DataFrame] = {}
        ok = True
        for v in ext_views:
            res, err = fetch_with_backoff(
                f"{v} {game_id}",
                lambda v=v: _bx.fetch_view(v, game_id, season), sleep_s)
            time.sleep(sleep_s)
            ctr.bump(fetches=1)
            if res is None:
                ctr.bump(failed=f"{game_id} {v}: {err}")
                ok = False
                break
            raw[v] = res.frame
        if ok:
            for v, frame in raw.items():
                n = insert_game_rows(BRONZE_EXT_TABLE, frame, season,
                                     _bx.SOURCE, f"{game_id}:{v}", game_id,
                                     view=v)
                silver[v] = _bx.to_silver(v, frame)
            joined = _bx.join_views(silver)
            if joined.height:
                n = insert_game_rows(EXT_TABLE, joined, season, _bx.SOURCE,
                                     game_id, game_id)
                ctr.bump(rows_ext=n)
    ctr.bump(games=1)


# --------------------------------------------------------------------------
# lineups (per season, league-wide)
# --------------------------------------------------------------------------

def backfill_lineups(season: str, sleep_s: float, ctr: Counters) -> None:
    entity = f"lineups:{season}"
    if watermarked(LINEUP_TABLE, season, entity):
        return
    from nba_api.stats.endpoints import LeagueDashLineups

    frames = []
    for measure, kw in (("base", {}),
                        ("advanced", {"measure_type_detailed_defense":
                                      "Advanced"})):
        def _run(kw=kw):
            ep = LeagueDashLineups(season=season, timeout=30, **kw)
            df = ep.get_data_frames()[0]
            try:
                return pl.from_pandas(df)
            except Exception:
                return pl.DataFrame()

        res, err = fetch_with_backoff(f"lineups {season} {measure}", _run,
                                      sleep_s)
        time.sleep(sleep_s)
        ctr.bump(fetches=1)
        if res is None:
            ctr.bump(failed=f"{season} lineups {measure}: {err}")
            return
        frames.append(res.frame.with_columns(
            pl.lit(measure).alias("MEASURE")))
    frame = pl.concat(frames, how="diagonal")
    frame = _canon(frame)  # MEASURE already set per-frame in the loop above
    # One transaction: DELETE + INSERT + watermark are all-or-nothing,
    # so a crash can't leave a half-written season or a false watermark.
    store.write_unit(LINEUP_TABLE, frame, season, "nba_api", entity,
                     "_season = ? AND _entity LIKE 'lineups:%'", [season])
    print(f"[{season}] lineups: {frame.height} rows", flush=True)


# --------------------------------------------------------------------------
# play-by-play (per game, recent seasons)
# --------------------------------------------------------------------------

def _snake(name: str) -> str:
    import re as _re
    return _re.sub(r"__+", "_",
                   _re.sub(r"(?<!^)(?=[A-Z])", "_", name).upper())


def _normalize_pbp(frame: pl.DataFrame) -> pl.DataFrame:
    rename = {}
    for c in frame.columns:
        c = str(c)
        rename[c] = _PBP_KEY_RENAME.get(c, _snake(c))
    return frame.rename(rename)


def backfill_pbp_game(game_id: str, season: str, sleep_s: float,
                      ctr: Counters) -> None:
    if watermarked(PBP_TABLE, season, game_id):
        ctr.bump(skipped=1)
        return
    from nba_api.stats.endpoints import PlayByPlayV3

    def _run():
        ep = PlayByPlayV3(game_id=game_id, timeout=30)
        frames = ep.get_data_frames()
        try:
            return pl.from_pandas(frames[0])
        except Exception:
            return pl.DataFrame()

    res, err = fetch_with_backoff(f"pbp {game_id}", _run, sleep_s)
    time.sleep(sleep_s)
    ctr.bump(fetches=1)
    if res is None:
        ctr.bump(failed=f"{game_id} pbp: {err}")
        return
    insert_game_rows(BRONZE_PBP_TABLE, res.frame, season, "nba_api",
                     game_id, game_id)
    n = insert_game_rows(PBP_TABLE, _normalize_pbp(res.frame), season,
                         "nba_api", game_id, game_id)
    ctr.bump(rows_ext=n, games=1)


# --------------------------------------------------------------------------
# driver
# --------------------------------------------------------------------------

def report_watermarks(seasons: list[str], state: dict) -> None:
    for season in seasons:
        games = state.get("games", {}).get(season, {})
        total = sum(len(v) for v in games.values()) if games else 0
        if not total:
            print(f"{season}: game list not enumerated yet")
            continue
        ids = [g for st in SEASON_TYPES for g in games.get(st, [])]
        done_ext = watermarked_entities(EXT_TABLE, season)
        done_trad = watermarked_entities(GAME_TABLE, season)
        done_pbp = watermarked_entities(PBP_TABLE, season)
        lu = "yes" if watermarked(LINEUP_TABLE, season,
                                  f"lineups:{season}") else "no"
        print(f"{season}: {total} games | trad "
              f"{len(done_trad & set(ids))} | ext {len(done_ext & set(ids))} "
              f"| pbp {len(done_pbp & set(ids))} | lineups {lu}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--seasons", default="2015-16:2024-25",
                    help="'2015-16:2024-25' range or comma list")
    ap.add_argument("--views", default="all",
                    help="comma list incl. traditional, or 'all'")
    ap.add_argument("--sleep", type=float, default=1.5,
                    help="seconds between requests")
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--lineups", action=argparse.BooleanOptionalAction,
                    default=True)
    ap.add_argument("--pbp-seasons", default="",
                    help="comma list of seasons for PBP depth, e.g. "
                         "'2023-24,2024-25'")
    ap.add_argument("--limit", type=int, default=0,
                    help="max games per season (testing)")
    ap.add_argument("--check", action="store_true",
                    help="watermark report only, no fetching")
    args = ap.parse_args(argv)

    seasons = parse_seasons(args.seasons)
    views = (["traditional"] + list(_bx.VIEWS) if args.views == "all"
             else [v.strip() for v in args.views.split(",") if v.strip()])
    state = load_progress()
    if args.check:
        report_watermarks(seasons, state)
        return 0

    print(f"warehouse: {store.DB_PATH}", flush=True)
    ctr = Counters()
    t0 = time.time()

    for season in seasons:
        try:
            games = season_games(season, args.sleep, state)
        except RuntimeError as exc:
            print(f"[{season}] game enumeration failed: {exc}", flush=True)
            continue
        if args.limit:
            games = games[:args.limit]
        done_ext = watermarked_entities(EXT_TABLE, season)
        done_trad = watermarked_entities(GAME_TABLE, season)
        pending = [g for g in games
                   if not (g in done_ext
                           and ("traditional" not in views
                                or g in done_trad))]
        print(f"[{season}] {len(games)} games, {len(pending)} pending",
              flush=True)
        if args.lineups:
            backfill_lineups(season, args.sleep, ctr)
        if pending:
            with ThreadPoolExecutor(
                    max_workers=max(1, args.workers)) as pool:
                futs = [pool.submit(backfill_game, g, season, views,
                                    args.sleep, ctr) for g in pending]
                for f in futs:
                    f.result()
        el = time.time() - t0
        print(f"[{season}] done: {ctr.games} games, {ctr.rows_trad} trad "
              f"rows, {ctr.rows_ext} ext rows, {ctr.fetches} fetches, "
              f"{ctr.skipped} skipped, {len(ctr.failed)} failed "
              f"({el/60:.1f}m elapsed)", flush=True)

    pbp_seasons = [s.strip() for s in args.pbp_seasons.split(",")
                   if s.strip()]
    for season in pbp_seasons:
        games = season_games(season, args.sleep, state)
        done_pbp = watermarked_entities(PBP_TABLE, season)
        pending = [g for g in games if g not in done_pbp]
        print(f"[pbp {season}] {len(games)} games, {len(pending)} pending",
              flush=True)
        with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
            futs = [pool.submit(backfill_pbp_game, g, season, args.sleep,
                                ctr) for g in pending]
            for f in futs:
                f.result()

    if ctr.failed:
        print(f"failed ({len(ctr.failed)}), first 10:", flush=True)
        for f in ctr.failed[:10]:
            print(f"  {f}", flush=True)
    save_progress(state)
    el = time.time() - t0
    print(f"FINISHED: {ctr.games} games, {ctr.rows_trad} trad rows, "
          f"{ctr.rows_ext} ext/pbp rows, {ctr.fetches} fetches, "
          f"{ctr.skipped} skipped, {len(ctr.failed)} failed "
          f"({el/60:.1f}m elapsed)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
