import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared import store
from shared.sources.cap_history import history

TABLE = "silver_cap_history"
MIN_SEASONS = 42


def _save(res):
    return store.save_frame(TABLE, res, entity="league")


def main() -> None:
    res = history()
    print(f"cap history rows: {len(res.frame)}")
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
            f"SELECT COUNT(DISTINCT season) FROM {TABLE}").fetchone()
        (aprons,) = con.execute(
            f"SELECT COUNT(*) FROM {TABLE} WHERE apron_1 IS NOT NULL"
        ).fetchone()
    finally:
        con.close()
    print(f"{TABLE}: {count} seasons, {aprons} apron-era rows")
    if count < MIN_SEASONS or aprons < 3:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
