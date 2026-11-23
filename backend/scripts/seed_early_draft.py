import argparse
import os
import sys
from pathlib import Path

import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from shared import store
from shared.sources.base import FetchMeta, FetchResult

TABLE = "silver_hist_draft"
ENTITY = "draft"
SOURCE = "stats.nba.com:drafthistory"
FIRST = 1947
LAST = 1995


def label(draft_year: int) -> str:
    return f"{draft_year}-{(draft_year + 1) % 100:02d}"


def fetch_all() -> pl.DataFrame:
    from nba_api.stats.endpoints import drafthistory
    df = drafthistory.DraftHistory(timeout=60).get_data_frames()[0]
    return pl.from_pandas(df, include_index=False)


def loaded_seasons() -> set[str]:
    try:
        con = store.connect(read_only=True)
        tables = {row[0] for row in con.execute("SHOW TABLES").fetchall()}
        if TABLE not in tables:
            return set()
        rows = con.execute(
            f"SELECT DISTINCT _season FROM {TABLE}").fetchall()
        con.close()
        return {r[0] for r in rows}
    except Exception:
        return set()


def run(years: list[int], frame: pl.DataFrame | None = None) -> int:
    frame = frame if frame is not None else fetch_all()
    frame = frame.with_columns(
        pl.col("SEASON").cast(pl.Int64, strict=False).alias("DRAFT_YEAR"))
    frame = frame.with_columns((pl.col("DRAFT_YEAR") + 1).alias("SEASON"))
    done = loaded_seasons()
    total = 0
    for y in years:
        if label(y) in done:
            print(f"{label(y)}: already loaded, skip")
            continue
        chunk = frame.filter(pl.col("DRAFT_YEAR") == y)
        if chunk.height == 0:
            print(f"{label(y)}: no rows upstream, skip")
            continue
        chunk = chunk.with_columns(
            [pl.col(c).cast(pl.Int64, strict=False) for c in
             ("PERSON_ID", "SEASON", "ROUND_NUMBER", "ROUND_PICK",
              "OVERALL_PICK", "TEAM_ID", "PLAYER_PROFILE_FLAG",
              "DRAFT_YEAR")] +
            [pl.col(c).cast(pl.String, strict=False) for c in
             ("PLAYER_NAME", "DRAFT_TYPE", "TEAM_CITY", "TEAM_NAME",
              "TEAM_ABBREVIATION", "ORGANIZATION",
              "ORGANIZATION_TYPE")])
        res = FetchResult(frame=chunk,
                          meta=FetchMeta(SOURCE, label(y)))
        n = store.save_frame(TABLE, res, ENTITY, replace_season=True)
        total += n
        print(f"{label(y)}: {n} picks")
    return total


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Backfill silver_hist_draft for 1947-1995 drafts via "
                    "nba_api DraftHistory (one call, per-season saves).")
    ap.add_argument("--years", default="",
                    help="comma list of draft years, e.g. 1947,1960,1984")
    ns = ap.parse_args(argv)
    if not os.environ.get("DIME_WAREHOUSE"):
        print("refusing: DIME_WAREHOUSE is not set")
        return 1
    years = ([int(x) for x in ns.years.split(",") if x.strip()]
             if ns.years else list(range(FIRST, LAST + 1)))
    n = run(years)
    print(f"loaded {n} rows into {TABLE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
