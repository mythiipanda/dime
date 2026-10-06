import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared import store
from shared.sources.salaries import get_contracts

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
