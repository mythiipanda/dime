import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared import store
from shared.sources import nba_stats
from shared.tools._core import current_season

TABLE = "silver_clutch"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", default=None)
    ap.add_argument("--dry-run", action="store_true")
    ns = ap.parse_args(argv)
    season = ns.season or current_season() or "2026-27"
    res = nba_stats.clutch("player", season)
    if not res.ok or res.frame.height == 0:
        print(f"{TABLE}: empty fetch for {season}: {res.error}")
        return 1
    if ns.dry_run:
        print(f"{TABLE} {season}: {res.frame.height} rows (dry-run)")
        return 0
    n = store.save_frame(TABLE, res, entity=f"season:{season}", replace_season=True)
    print(f"{TABLE} {season}: {n} rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
