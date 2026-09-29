"""Seed Tankathon draft boards (upcoming class projections).

Fetches the current mock draft + big board via shared/sources/tankathon.py
and lands them in bronze_draft_boards (raw) + silver_draft_boards (typed).
Complements scripts/seed_draft.py, which covers historical draft *results*
(1997-2024); this covers *projections* for the upcoming class.

Idempotent per (draft year, board): reruns replace the board slice and
rewrite the fetch_log watermark, so a stale parse never accumulates.

Usage:
    DIME_WAREHOUSE=/path/to/warehouse.duckdb python -m scripts.seed_draft_boards
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import polars as pl

from shared import store
from shared.sources import tankathon as _tk

BRONZE = "bronze_draft_boards"
SILVER = "silver_draft_boards"


def _canon(frame: pl.DataFrame) -> pl.DataFrame:
    exprs = []
    for c, dt in frame.schema.items():
        if dt in (pl.Int8, pl.Int16, pl.Int32, pl.Int64, pl.UInt8,
                   pl.UInt16, pl.UInt32, pl.UInt64):
            exprs.append(pl.col(c).cast(pl.Int64))
        elif dt in (pl.Float32, pl.Float64):
            exprs.append(pl.col(c).cast(pl.Float64))
        elif dt == pl.Boolean:
            exprs.append(pl.col(c).cast(pl.Boolean))
        else:
            exprs.append(pl.col(c).cast(pl.String))
    return frame.select(exprs)


def _save(table: str, frame: pl.DataFrame, season: str, board: str) -> int:
    """Idempotent per-board replace + watermark, one transaction.

    store.write_unit runs DELETE + INSERT + watermark atomically: a crash
    rolls back to the previous complete board, so a rerun redoes the
    board instead of skipping it.
    """
    return store.write_unit(table, _canon(frame), season, _tk.SOURCE, board,
                            "_season = ? AND _entity = ?", [season, board])


def main() -> int:
    total = 0
    for board, fn in (("mock_draft", _tk.mock_draft),
                      ("big_board", _tk.big_board)):
        res = fn()
        if not res.ok:
            print(f"{board}: FAILED {res.error}", flush=True)
            return 1
        season = res.meta.season
        n_bronze = _save(BRONZE, res.frame, season, board)
        # Silver: normalize pick/rank into one ORDER column.
        frame = res.frame
        if "PICK" in frame.columns:
            frame = frame.rename({"PICK": "ORDER"})
        elif "RANK" in frame.columns:
            frame = frame.rename({"RANK": "ORDER"})
        n_silver = _save(SILVER, frame, season, board)
        total += n_silver
        print(f"{board} ({season}): bronze {n_bronze} rows, "
              f"silver {n_silver} rows", flush=True)
        time.sleep(2)
    print(f"done: {total} silver rows", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
