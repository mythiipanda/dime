"""Load real NBA salaries from Basketball-Reference contracts into the warehouse.

Source: https://www.basketball-reference.com/contracts/ (keyless, 4s gaps).
Normals: silver_salaries (PLAYER_NAME, TEAM, SALARY_2025_26, GUARANTEED).

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
    frame = res.frame
    print(f"scraped {len(frame)} salary rows (season {res.meta.season})")
    n = store.save_frame("silver_salaries", res, entity=f"season:{res.meta.season}")
    print(f"silver_salaries: {n} rows saved")


if __name__ == "__main__":
    main()
