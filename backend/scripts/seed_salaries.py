"""Load real NBA salaries from Basketball-Reference contracts into the warehouse.

Source: https://www.basketball-reference.com/contracts/ (keyless, 4s gaps).
Normals: silver_salaries (PLAYER_NAME, TEAM, SALARY_2025_26, GUARANTEED).

SALARY_2025_26 is a frozen spec name. It holds the observed y1 money for
the scraped vintage. The vintage is the observed y1 header, stored as
_season plus the fetch_log season on every run. Never trust the column
name for the vintage. Aborts without writing when y1 is unobserved.

This is the table get_trade_check prefers (real contracts over estimates).
Takes ~2 minutes (30 team pages).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import store
from app.sources.salaries import get_contracts


def main() -> None:
    res = get_contracts()
    if not res.ok or not res.meta.season or res.meta.season == "unknown":
        print(f"abort: y1 unobserved ({res.error or 'no season'})")
        raise SystemExit(1)
    frame = res.frame
    print(f"scraped {len(frame)} salary rows (observed y1 {res.meta.season})")
    n = store.save_frame("silver_salaries", res, entity=f"season:{res.meta.season}",
                           replace_season=True)
    print(f"silver_salaries: {n} rows saved (fetch_log season {res.meta.season})")


if __name__ == "__main__":
    main()
