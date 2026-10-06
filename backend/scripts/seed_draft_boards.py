
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
