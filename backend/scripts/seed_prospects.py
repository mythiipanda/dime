import argparse
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared import store
from shared.sources import cbb as _cbb
from shared.sources import tankathon as _tk
from scripts.seed_draft_boards import BRONZE, SILVER, _save as _save_board


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


def load_boards(dry_run: bool) -> int:
    total = 0
    for board, fn in (("mock_draft", _tk.mock_draft),
                      ("big_board", _tk.big_board)):
        res = fn()
        if not res.ok or res.frame.height == 0:
            print(f"{board}: FAILED {res.error}", flush=True)
            continue
        season = res.meta.season
        if dry_run:
            print(f"{board} ({season}): {res.frame.height} rows (dry-run)")
            continue
        frame = res.frame
        if "PICK" in frame.columns:
            frame = frame.rename({"PICK": "ORDER"})
        elif "RANK" in frame.columns:
            frame = frame.rename({"RANK": "ORDER"})
        n_bronze = _save_board(BRONZE, res.frame, season, board)
        n = _save_board(SILVER, frame, season, board)
        total += n
        print(f"{board} ({season}): bronze {n_bronze} rows, "
              f"silver {n} rows", flush=True)
        time.sleep(2)
    return total


def load_prospect_stats(year: int, dry_run: bool) -> int:
    res = _cbb.get_player_stats(year)
    if not res.ok or res.frame.height == 0:
        print(f"prospect stats {year}: FAILED {res.error}", flush=True)
        return 0
    if dry_run:
        print(f"silver_prospect_stats ({year}): {res.frame.height} rows "
              f"(dry-run)")
        return 0
    n = store.save_frame("silver_prospect_stats", res, entity="league")
    print(f"silver_prospect_stats ({year}): {n} rows")
    return n


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scratch-db", default="")
    parser.add_argument("--year", type=int, default=2027,
                        help="draft/class year (season end year)")
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
        total += load_boards(args.dry_run)
        total += load_prospect_stats(args.year, args.dry_run)
    finally:
        store.DB_PATH = old_db
        store.LOCK_PATH = old_lock
        store.warehouse_tables_cache_clear()
        store.warehouse_pool_clear()
    print(f"prospect rows loaded: {total}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
