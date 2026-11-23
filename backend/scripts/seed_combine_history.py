import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared import store
from shared.sources import nba_stats

TABLE = "silver_combine"
FIRST_YEAR = 2000
LAST_YEAR = 2025
MIN_SEASONS = 20

def main() -> int:
    target = os.environ.get("DIME_WAREHOUSE", "")
    if not target:
        print("refusing: DIME_WAREHOUSE is not set")
        return 2
    total = 0
    seasons = 0
    for year in range(FIRST_YEAR, LAST_YEAR + 1):
        res = nba_stats.combine(str(year))
        if not res.ok or res.frame.height == 0:
            print(f"combine {year}: FAILED {res.error}", flush=True)
            continue
        n = store.save_frame(TABLE, res, entity=f"season:{res.meta.season}",
                             replace_season=True)
        total += n
        seasons += 1
        print(f"combine {year}: {n} rows", flush=True)
        time.sleep(1)
    print(f"{TABLE}: {seasons} seasons, {total} rows")
    if seasons < MIN_SEASONS:
        print(f"FAIL: only {seasons} seasons seeded")
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
