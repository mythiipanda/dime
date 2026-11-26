import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared import store
from shared.sources import nba_stats
from shared.tools._core import current_season

def _save(res, season):
    return store.save_frame("silver_hustle_team", res, entity=f"season:{season}")

def main() -> None:
    season = current_season() or "2026-27"
    res = nba_stats.hustle("team", season)
    frame = res.frame
    print(f"scraped {len(frame)} hustle team rows")
    try:
        n = _save(res, season)
    except Exception as exc:
        msg = str(exc).lower()
        if "lock" not in msg and "conflict" not in msg:
            raise
        time.sleep(5)
        n = _save(res, season)
    print(f"silver_hustle_team: {n} rows saved")
    con = store.connect()
    try:
        (count,) = con.execute(
            "SELECT COUNT(*) FROM silver_hustle_team WHERE _season = ?",
            [season],
        ).fetchone()
    finally:
        con.close()
    print(f"silver_hustle_team {season}: {count} rows")
    if count != 30:
        raise SystemExit(1)

if __name__ == "__main__":
    main()
