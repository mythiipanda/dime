import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import polars as pl

from shared import store
from shared.sources.base import FetchMeta, FetchResult

BASE = "https://github.com/sportsdataverse/sportsdataverse-data/releases/download/espn_nba_player_core"
TABLE = "silver_player_bio"
FIRST_YEAR = 1994
LAST_YEAR = 2027
MIN_SEASONS = 25
MIN_ROWS = 200

KEEP = [
    "season", "athlete_id", "slug", "first_name", "last_name", "display_name",
    "height", "weight", "date_of_birth", "birth_city", "birth_state",
    "birth_country", "position_abbreviation", "college_id", "experience_years",
    "draft_year", "draft_round", "draft_selection", "status_name", "active",
]

def label(end_year: int) -> str:
    return f"{end_year - 1}-{str(end_year)[2:]}"

def main() -> int:
    import os
    if not os.environ.get("DIME_WAREHOUSE", ""):
        print("refusing: DIME_WAREHOUSE is not set")
        return 2
    total = 0
    seasons = 0
    for y in range(FIRST_YEAR, LAST_YEAR + 1):
        url = f"{BASE}/player_core_{y}.parquet"
        try:
            df = pl.read_parquet(url)
        except Exception as exc:
            print(f"bio {label(y)}: skip {exc}", flush=True)
            continue
        df = df.select([c for c in KEEP if c in df.columns])
        if df.height < MIN_ROWS:
            print(f"bio {label(y)}: only {df.height} rows", flush=True)
            continue
        res = FetchResult(
            frame=df,
            meta=FetchMeta(source="sportsdataverse:espn_nba_player_core",
                           season=label(y)),
        )
        n = store.save_frame(TABLE, res, entity=f"season:{label(y)}",
                             replace_season=True)
        total += n
        seasons += 1
        print(f"bio {label(y)}: {n} rows", flush=True)
    print(f"{TABLE}: {seasons} seasons, {total} rows")
    if seasons < MIN_SEASONS:
        print(f"FAIL: only {seasons} seasons seeded")
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
