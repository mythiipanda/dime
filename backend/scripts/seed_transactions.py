import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

import polars as pl

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))

from seed_odds import _curl_transport
from shared import store
from shared.sources import nba_transactions as src
from shared.sources.base import FetchMeta, FetchResult

TABLE = "silver_nba_transactions"
PROGRESS_FILE = HERE / "seed_transactions_progress.json"
LOG_FILE = HERE / "seed_transactions.log"
SOURCE = "nba-transactions"
SEASON_SHAPE = re.compile(r"^\d{4}-\d{2}$")

MOVEMENT_TABLE = "silver_transactions"
MOVEMENT_SOURCE = "nba_official"
FEED_URL = "https://stats.nba.com/js/data/playermovement/NBA_Player_Movement.json"

COLUMNS = ["txn_date", "txn_type", "player", "player_id",
           "team", "team_id", "detail"]

class SeederError(RuntimeError):
    pass

def log(message: str) -> None:
    line = f"{datetime.now().isoformat(timespec='seconds')} {message}"
    print(line, flush=True)
    with open(LOG_FILE, "a") as handle:
        handle.write(line + "\n")

def load_progress(progress_file: Path) -> dict:
    if progress_file.exists():
        return json.loads(progress_file.read_text())
    return {"done": [], "failed": {}}

def mark_done(progress_file: Path, season: str) -> None:
    state = load_progress(progress_file)
    if season not in state["done"]:
        state["done"] = sorted(state["done"] + [season])
    state["failed"].pop(season, None)
    progress_file.write_text(json.dumps(state, indent=1))

def mark_failed(progress_file: Path, season: str, reason: str) -> None:
    state = load_progress(progress_file)
    state["failed"][season] = str(reason)[:300]
    state["done"] = [d for d in state["done"] if d != season]
    progress_file.write_text(json.dumps(state, indent=1))

def season_rows(frame: pl.DataFrame, season: str) -> pl.DataFrame:
    return frame.filter(pl.col("SEASON") == season)

def existing_season(con, season: str) -> pl.DataFrame | None:
    tables = {r[0] for r in con.execute(
        "SELECT table_name FROM information_schema.tables").fetchall()}
    if TABLE not in tables:
        return None
    try:
        return con.execute(
            f'SELECT {", ".join(src.COLUMNS)} FROM "{TABLE}" WHERE SEASON = ?',
            [season]).pl()
    except Exception:
        return None

def same_slice(existing: pl.DataFrame | None, incoming: pl.DataFrame) -> bool:
    if existing is None:
        return False
    keys = [c for c in src.COLUMNS if c != "FETCHED_AT"]
    existing_rows = existing.sort(keys[:3]).select(keys)
    incoming_rows = incoming.sort(keys[:3]).select(keys)
    return existing_rows.equals(incoming_rows)

def seed_season(season: str, frame: pl.DataFrame, con, progress_file: Path,
                dry_run: bool) -> int:
    incoming = season_rows(frame, season)
    if incoming.height == 0:
        raise SeederError(
            f"season {season}: nba-transactions union has 0 rows from "
            f"{src.SOURCE_CSV} and {src.SOURCE_JSON}")
    existing = existing_season(con, season)
    if same_slice(existing, incoming):
        log(f"{season}: unchanged ({incoming.height} rows), skipping write")
        if not dry_run:
            mark_done(progress_file, season)
        return 0
    if dry_run:
        log(f"{season}: DRY-RUN would write {incoming.height} rows")
        return incoming.height
    result = FetchResult(frame=incoming,
                         meta=FetchMeta(source=SOURCE, season=season))
    written = store.save_frame(TABLE, result, entity=f"season:{season}")
    mark_done(progress_file, season)
    log(f"{season}: {written} rows from {incoming['SOURCE_FILE'][0]}")
    return written

def plan_seasons(frame: pl.DataFrame, from_season: str, to_season: str,
                 only: list[str]) -> list[str]:
    available = sorted(frame["SEASON"].unique().to_list())
    if only:
        return [s for s in only]
    planned = available
    if from_season:
        planned = [s for s in planned if s >= from_season]
    if to_season:
        planned = [s for s in planned if s <= to_season]
    return planned

def season_for_date(date: str) -> str:
    year, month = int(date[:4]), int(date[5:7])
    if month >= 10:
        return f"{year}-{str(year + 1)[2:]}"
    return f"{year - 1}-{str(year)[2:]}"

def fetch_transactions(transport=_curl_transport) -> dict:
    body = transport(FEED_URL, {"Referer": "https://www.nba.com/",
                                "User-Agent": "Mozilla/5.0"}, {})
    payload = json.loads(body)
    try:
        rows = payload["NBA_Player_Movement"]["rows"]
    except (KeyError, TypeError):
        raise ValueError("malformed movement payload: missing rows")
    if not isinstance(rows, list):
        raise ValueError("malformed movement payload: rows is not a list")
    return payload

def map_transactions(payload: dict) -> pl.DataFrame:
    try:
        rows = payload["NBA_Player_Movement"]["rows"]
    except (KeyError, TypeError, AttributeError):
        raise ValueError("malformed movement payload: missing rows")
    if not isinstance(rows, list):
        raise ValueError("malformed movement payload: rows is not a list")
    frame = pl.DataFrame([{
        "txn_date": r["TRANSACTION_DATE"][:10],
        "txn_type": r["Transaction_Type"],
        "player": r.get("PLAYER_SLUG"),
        "player_id": r.get("PLAYER_ID"),
        "team": r.get("TEAM_SLUG"),
        "team_id": r.get("TEAM_ID"),
        "detail": r["TRANSACTION_DESCRIPTION"],
    } for r in rows], strict=False)
    if frame.height == 0:
        return pl.DataFrame([], schema={c: pl.String for c in COLUMNS})
    return frame.select(COLUMNS)

def partition_by_season(frame: pl.DataFrame) -> dict:
    parts: dict = {}
    for row in frame.to_dicts():
        season = season_for_date(row["txn_date"])
        parts.setdefault(season, []).append(row)
    return {s: pl.DataFrame(r, strict=False).select(frame.columns)
            for s, r in sorted(parts.items())}

def _seeded(season: str, entity: str) -> bool:
    try:
        return bool(store.last_fetch(MOVEMENT_TABLE, season, entity))
    except Exception:
        return False

def seed_all(fetch_fn=fetch_transactions) -> dict:
    frame = map_transactions(fetch_fn())
    if frame.height == 0:
        return {}
    result = {}
    for season, part in partition_by_season(frame).items():
        entity = f"season:{season}"
        if _seeded(season, entity):
            result[season] = 0
            continue
        result[season] = store.write_unit(
            MOVEMENT_TABLE, part, season, MOVEMENT_SOURCE, entity,
            "_season = ? AND _entity = ?", [season, entity])
    return result

def main_union(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="seed_transactions")
    parser.add_argument("--from-season", default="")
    parser.add_argument("--to-season", default="")
    parser.add_argument("--seasons", default="")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--progress", default=str(PROGRESS_FILE))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--csv-file", default="")
    parser.add_argument("--json-file", default="")
    parser.add_argument("--csv-url", default=src.CSV_URL)
    parser.add_argument("--json-url", default=src.JSON_URL)
    args = parser.parse_args(argv)

    transport = src.paced_transport()
    if args.csv_file:
        csv_text = Path(args.csv_file).read_text(encoding="utf-8")
    else:
        log(f"fetching {args.csv_url}")
        csv_text = transport(args.csv_url)
    if args.json_file:
        json_text = Path(args.json_file).read_text(encoding="utf-8")
    else:
        log(f"fetching {args.json_url}")
        json_text = transport(args.json_url)
    csv_frame = src.parse_csv(csv_text)
    json_frame = src.parse_json(json_text)
    frame = src.union(csv_frame, json_frame)
    log(f"parsed csv={csv_frame.height} json={json_frame.height} "
        f"union_after_dedup={frame.height}")
    if args.dry_run:
        for season in sorted(frame["SEASON"].unique().to_list()):
            rows = season_rows(frame, season)
            log(f"DRY-RUN {season}: {rows.height} rows, sources "
                f"{sorted(set(rows['SOURCE']))}")
        return 0

    only = [s.strip() for s in args.seasons.split(",") if s.strip()]
    planned = plan_seasons(frame, args.from_season, args.to_season, only)
    progress_file = Path(args.progress)
    done = set(load_progress(progress_file)["done"])
    queue = [s for s in planned if s not in done]
    if args.limit:
        queue = queue[: args.limit]
    log(f"plan: {len(queue)} seasons pending, {len(done)} done")

    con = store.connect()
    try:
        for season in queue:
            try:
                seed_season(season, frame, con, progress_file, dry_run=False)
            except SeederError as exc:
                mark_failed(progress_file, season, str(exc))
                log(f"{season}: FAILED {exc}")
                print(f"{season}: FAILED {exc}", file=sys.stderr)
                return 1
    finally:
        con.close()

    log(f"DONE union_rows={frame.height} progress_done={len(load_progress(progress_file)['done'])}")
    return 0

def main_movement(argv=None, fetch_fn=None) -> int:
    ap = argparse.ArgumentParser(description="Seed silver_transactions from the NBA movement feed.")
    ap.parse_args(argv)
    try:
        result = seed_all(fetch_fn or fetch_transactions)
    except Exception as exc:
        print(f"abort: transactions seed failed ({exc})")
        return 1
    total = sum(result.values())
    for season, n in result.items():
        print(f"{season}: {n} rows saved")
    print(f"silver_transactions: {total} rows saved across {len(result)} seasons")
    return 0

def main(argv=None, fetch_fn=None) -> int:
    tokens = list(argv) if argv is not None else list(sys.argv[1:])
    if tokens and not tokens[0].startswith("-"):
        tokens = tokens[1:]
    if any(token.startswith("--") for token in tokens):
        return main_union(tokens)
    return main_movement(tokens, fetch_fn)

if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
