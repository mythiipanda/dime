"""Repro: concurrent DuckDB writers collide on the single-writer lock.

Usage: python -m scripts.repro_lock
Pass means all threads wrote without lock errors.
"""

import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import polars as pl

from app import store
from app.sources.base import FetchMeta, FetchResult

ERRORS: list[str] = []


def worker(n: int) -> None:
    try:
        frame = pl.DataFrame({"v": [n]})
        res = FetchResult(frame=frame, meta=FetchMeta(source="repro", season="t"))
        store.save_frame("_repro_lock", res, entity=f"w{n}", replace_season=False)
    except Exception as exc:
        ERRORS.append(str(exc)[:120])


def main() -> None:
    threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    con = store.connect()
    try:
        n = con.execute("SELECT COUNT(*) FROM _repro_lock").fetchone()[0]
        con.execute("DROP TABLE _repro_lock")
    finally:
        con.close()
    print(f"rows: {n}, errors: {len(ERRORS)}")
    for e in ERRORS[:3]:
        print("ERR:", e)
    sys.exit(1 if ERRORS or n != 8 else 0)


if __name__ == "__main__":
    main()
