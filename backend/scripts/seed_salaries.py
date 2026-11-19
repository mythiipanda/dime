import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared import store
from shared.contracts import resolve_player_ids
from shared.sources.salaries import get_contracts

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--scratch-db', type=Path)
    args = parser.parse_args()
    target = args.scratch_db or Path(os.environ.get('DIME_WAREHOUSE') or store.DB_PATH)
    if target.resolve() == store.CANONICAL_DB_PATH:
        parser.error('use --scratch-db or noncanonical DIME_WAREHOUSE')
    if not target.is_file():
        parser.error('scratch warehouse must be an existing copy')
    store.DB_PATH = target.resolve()
    store.LOCK_PATH = store.DB_PATH.parent / '.write.lock'
    res = get_contracts()
    if not res.ok or not res.meta.season or res.meta.season == "unknown":
        print(f"abort: y1 unobserved ({res.error or 'no season'})")
        raise SystemExit(1)
    with store.connect(read_only=True) as con:
        res.frame = resolve_player_ids(res.frame, con)
    frame = res.frame
    print(f"scraped {len(frame)} salary rows (observed y1 {res.meta.season})")
    matched = frame['PLAYER_ID'].drop_nulls().len()
    print(f'PLAYER_ID matched={matched} unmatched={len(frame) - matched}')
    n = store.save_frame("silver_salaries", res, entity='',
                           replace_season=True)
    print(f"silver_salaries: {n} rows saved (fetch_log season {res.meta.season})")

if __name__ == "__main__":
    main()
