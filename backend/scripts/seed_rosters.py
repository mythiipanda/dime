import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import polars as pl

from shared import store
from shared.sources.base import FetchMeta, FetchResult
from shared.tools._core import current_season

TABLE = "silver_rosters"
SOURCE = "nba_api"
DELAY_S = 1.0


def fetch_coaches(season: str) -> pl.DataFrame:
    from nba_api.stats.endpoints import CommonTeamRoster
    from nba_api.stats.static import teams as static_teams

    frames = []
    for t in static_teams.get_teams():
        tid = t["id"]
        ep = CommonTeamRoster(team_id=tid, season=season, timeout=30)
        coaches = ep.get_data_frames()[1]
        if coaches.empty:
            continue
        frame = pl.from_pandas(coaches)
        frame = frame.with_columns(pl.lit(tid).cast(pl.Int64).alias("TEAM_ID"))
        frames.append(frame)
        time.sleep(DELAY_S)
    if not frames:
        return pl.DataFrame()
    return pl.concat(frames, how="diagonal_relaxed")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", default=None)
    ap.add_argument("--dry-run", action="store_true")
    ns = ap.parse_args(argv)
    season = ns.season or current_season() or "2026-27"
    frame = fetch_coaches(season)
    if frame.height == 0:
        print(f"{TABLE}: no coach rows returned for {season}")
        return 1
    if ns.dry_run:
        print(f"{TABLE} {season}: {frame.height} rows (dry-run)")
        return 0
    res = FetchResult(frame=frame, meta=FetchMeta(source=SOURCE, season=season))
    n = 0
    for tid in frame.get_column("TEAM_ID").unique().to_list():
        sub = frame.filter(pl.col("TEAM_ID") == tid)
        sub_res = FetchResult(frame=sub, meta=FetchMeta(source=SOURCE, season=season))
        n += store.save_frame(TABLE, sub_res, entity=f"team:{tid}")
    print(f"{TABLE} {season}: {n} rows across {frame.get_column('TEAM_ID').n_unique()} teams")
    return 0


if __name__ == "__main__":
    sys.exit(main())
