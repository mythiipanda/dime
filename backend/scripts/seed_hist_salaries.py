import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared import store
from shared.sources.hist_salaries import history

TABLE = "silver_hist_salaries"
MIN_ROWS = 14_000
MIN_SEASONS = 34


def _save(res):
    return store.save_frame(TABLE, res, entity="league")


def main() -> None:
    res = history()
    print(f"hist salary rows: {len(res.frame)}")
    if not res.ok or res.frame.height == 0:
        raise SystemExit(res.error or "hist salaries fetch failed")
    try:
        n = _save(res)
    except Exception as exc:
        msg = str(exc).lower()
        if "lock" not in msg and "conflict" not in msg:
            raise
        time.sleep(5)
        n = _save(res)
    print(f"{TABLE}: {n} rows saved")
    con = store.connect()
    try:
        (count,) = con.execute(
            f"SELECT COUNT(DISTINCT SEASON) FROM {TABLE}").fetchone()
        (rows,) = con.execute(
            f"SELECT COUNT(*) FROM {TABLE}").fetchone()
    finally:
        con.close()
    print(f"{TABLE}: {count} seasons, {rows} rows")
    if count < MIN_SEASONS or rows < MIN_ROWS:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
