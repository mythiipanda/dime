import argparse
import io
import os
import sys
import time
import unicodedata
import re
from pathlib import Path

import pandas as pd
import polars as pl
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from shared import store
from shared.sources.base import FetchMeta, FetchResult

HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                         "AppleWebKit/537.36 Chrome/126.0.0.0 Safari/537.36"}
BASE = "https://www.basketball-reference.com/leagues/NBA_%d_advanced.html"
SOURCE = "basketball-reference:advanced"
TABLE = "silver_impact"
ENTITY = "league"
SLEEP_S = 3.5

KEEP = ["PLAYER_NAME", "TEAM", "POS", "AGE", "G", "MP",
        "WS", "WS48", "OBPM", "DBPM", "BPM", "VORP"]


def norm(name: str) -> str:
    nfkd = unicodedata.normalize("NFKD", name or "")
    ascii_only = "".join(c for c in nfkd if not unicodedata.combining(c))
    return re.sub(r"\s+(jr|sr|ii|iii|iv)\.?$", "", ascii_only.strip(),
                  flags=re.IGNORECASE)


def resolve_target(raw_db: str | None) -> Path | None:
    raw = raw_db or os.environ.get("DIME_WAREHOUSE", "")
    if not raw:
        print("refusing: DIME_WAREHOUSE is not set")
        return None
    target = Path(raw).expanduser().resolve()
    print(f"target: {target}")
    if target == store.CANONICAL_DB_PATH:
        print("refusing: target is the canonical warehouse")
        return None
    return target


def start_year(season: str) -> int:
    year, _, tail = str(season).partition("-")
    if len(year) != 4 or not year.isdigit() or len(tail) != 2 \
            or not tail.isdigit() or int(tail) != (int(year) + 1) % 100:
        raise ValueError(f"season must read YYYY-YY, got {season!r}")
    return int(year)


def season_slugs(first: str, last: str) -> list[str]:
    start, end = start_year(first), start_year(last)
    if end < start:
        raise ValueError(f"empty season range: {first} to {last}")
    return [f"{y}-{(y + 1) % 100:02d}" for y in range(start, end + 1)]


def fetch_advanced(year: int) -> pd.DataFrame:
    last_exc: Exception | None = None
    for attempt in range(4):
        r = requests.get(BASE % year, headers=HEADERS, timeout=30)
        if r.status_code == 429:
            last_exc = RuntimeError(f"429 for {year} advanced")
            time.sleep(8 * (attempt + 1))
            continue
        r.raise_for_status()
        r.encoding = "utf-8"
        df = pd.read_html(io.StringIO(r.text))[0]
        df = df[df[df.columns[1]] != "Player"]
        return df
    raise last_exc or RuntimeError(f"failed fetching {year} advanced")


def clean_frame(df: pd.DataFrame) -> pl.DataFrame:
    df = df.rename(columns={"Player": "PLAYER_NAME", "Team": "TEAM",
                            "Tm": "TEAM", "Pos": "POS", "WS/48": "WS48"})
    df["PLAYER_NAME"] = [norm(str(v)) for v in df["PLAYER_NAME"]]
    df["TEAM"] = df["TEAM"].astype(str)
    df["_tot"] = (df["TEAM"] == "TOT").astype(int)
    df["MP"] = pd.to_numeric(df["MP"], errors="coerce")
    df = df.sort_values(["_tot", "MP"], ascending=False).drop_duplicates(
        subset=["PLAYER_NAME"], keep="first")
    for col in KEEP:
        if col not in df.columns:
            df[col] = None
    out = df[KEEP].copy()
    for col in ["AGE", "G", "MP", "WS", "WS48", "OBPM", "DBPM", "BPM", "VORP"]:
        out[col] = pd.to_numeric(out[col], errors="coerce")
    return pl.from_pandas(out)


def load_season(season: str, dry_run: bool) -> int:
    frame = clean_frame(fetch_advanced(start_year(season) + 1))
    if dry_run:
        print(f"{season}: {frame.height} rows (dry-run)")
        return 0
    res = FetchResult(frame=frame, meta=FetchMeta(source=SOURCE, season=season))
    n = store.save_frame(TABLE, res, entity=ENTITY, replace_season=True)
    print(f"{season}: {n} rows")
    return n


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scratch-db", default="")
    parser.add_argument("--first", default="2021-22")
    parser.add_argument("--last", default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    if not args.last:
        from shared.tools._core import completed_season_for_date
        from datetime import date
        args.last = completed_season_for_date(date.today()) or "2025-26"

    target = resolve_target(args.scratch_db)
    if target is None:
        return 2
    target.parent.mkdir(parents=True, exist_ok=True)

    old_db, old_lock = store.DB_PATH, store.LOCK_PATH
    store.DB_PATH = target
    store.LOCK_PATH = target.parent / ".write.lock"
    store.warehouse_tables_cache_clear()
    store.warehouse_pool_clear()
    total = 0
    try:
        for i, season in enumerate(season_slugs(args.first, args.last)):
            if i:
                time.sleep(SLEEP_S)
            total += load_season(season, args.dry_run)
    finally:
        store.DB_PATH = old_db
        store.LOCK_PATH = old_lock
        store.warehouse_tables_cache_clear()
        store.warehouse_pool_clear()
    print(f"silver_impact rows loaded: {total}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
