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
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import polars as pl

from shared import store
from shared.sources import tankathon as _tk

BRONZE = "bronze_draft_boards"
SILVER = "silver_draft_boards"

_DTYPE_SQL = {pl.String: "VARCHAR", pl.Int64: "BIGINT",
              pl.Float64: "DOUBLE", pl.Boolean: "BOOLEAN"}


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


def _save(table: str, frame: pl.DataFrame, season: str, board: str,
          fetched_at: str) -> int:
    frame = _canon(frame).with_columns([
        pl.lit(_tk.SOURCE).alias("_source"),
        pl.lit(season).alias("_season"),
        pl.lit(fetched_at).alias("_fetched_at"),
        pl.lit(board).alias("_entity"),
    ])
    con = store.connect(read_only=False)
    try:
        with store.write_guard():
            con.register("_incoming", frame.clear().to_arrow())
            con.execute(f"CREATE TABLE IF NOT EXISTS {table} AS "
                        "SELECT * FROM _incoming LIMIT 0")
            have = [r[1] for r in con.execute(
                f"PRAGMA table_info({table})").fetchall()]
            for c, dt in frame.schema.items():
                if c not in have:
                    con.execute(f'ALTER TABLE {table} ADD COLUMN "{c}" '
                                f'{_DTYPE_SQL.get(dt, "VARCHAR")}')
                    have.append(c)
            con.unregister("_incoming")
            con.execute(f"DELETE FROM {table} WHERE _season = ? "
                        "AND _entity = ?", [season, board])
            select = ", ".join(
                f'"{c}"' if c in frame.columns else f'NULL AS "{c}"'
                for c in have)
            con.register("_incoming", frame.to_arrow())
            con.execute(f"INSERT INTO {table} SELECT {select} FROM _incoming")
            con.unregister("_incoming")
            con.execute(
                "INSERT INTO fetch_log VALUES (?,?,?,?,?,?)",
                [table, season, board, _tk.SOURCE, fetched_at,
                 frame.height])
            return frame.height
    finally:
        con.close()


def main() -> int:
    fetched_at = datetime.now(timezone.utc).isoformat()
    total = 0
    for board, fn in (("mock_draft", _tk.mock_draft),
                      ("big_board", _tk.big_board)):
        res = fn()
        if not res.ok:
            print(f"{board}: FAILED {res.error}", flush=True)
            return 1
        season = res.meta.season
        n_bronze = _save(BRONZE, res.frame, season, board, fetched_at)
        # Silver: normalize pick/rank into one ORDER column.
        frame = res.frame
        if "PICK" in frame.columns:
            frame = frame.rename({"PICK": "ORDER"})
        elif "RANK" in frame.columns:
            frame = frame.rename({"RANK": "ORDER"})
        n_silver = _save(SILVER, frame, season, board, fetched_at)
        total += n_silver
        print(f"{board} ({season}): bronze {n_bronze} rows, "
              f"silver {n_silver} rows", flush=True)
        time.sleep(2)
    print(f"done: {total} silver rows", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
