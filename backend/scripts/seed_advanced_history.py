
import argparse
import sys
import time
from pathlib import Path
from typing import Callable, TypedDict

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared import store
from shared.sources import nba_stats
from shared.sources.base import FetchResult

TABLE = "silver_advanced"
ENTITY = "player-advanced"
SOURCE = nba_stats.SOURCE

FIRST_SEASON = "2019-20"
LAST_SEASON = "2024-25"
DELAY_S = 2.0

REQUIRED_COLUMNS = ("PLAYER_ID", "PLAYER_NAME", "AGE", "TS_PCT",
                    "NET_RATING", "DEF_RATING")


class SeasonFetchError(RuntimeError):
    pass


class SeasonReport(TypedDict):
    loaded: dict[str, int]
    skipped: list[str]
    rows: int


def _start_year(season: str) -> int:
    year, _, tail = str(season).partition("-")
    if len(year) != 4 or not year.isdigit():
        raise ValueError(f"season must read YYYY-YY, got {season!r}")
    if len(tail) != 2 or not tail.isdigit() or int(tail) != (int(year) + 1) % 100:
        raise ValueError(f"season must span consecutive years, got {season!r}")
    return int(year)


def season_slugs(first: str = FIRST_SEASON, last: str = LAST_SEASON) -> list[str]:
    start, end = _start_year(first), _start_year(last)
    if end < start:
        raise ValueError(f"empty season range: {first} to {last}")
    return [f"{y}-{(y + 1) % 100:02d}" for y in range(start, end + 1)]


def loaded_seasons() -> set[str]:
    con = store.connect()
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        if TABLE not in tables:
            return set()
        rows = con.execute(
            f"SELECT DISTINCT _season FROM {TABLE} WHERE _season IS NOT NULL"
        ).fetchall()
        return {r[0] for r in rows}
    finally:
        con.close()


def fetch_season(season: str) -> FetchResult:
    return nba_stats.player_advanced(season)


def require_complete(season: str, result: FetchResult) -> None:
    if not result.ok or result.frame.height == 0:
        raise SeasonFetchError(
            f"{TABLE} {season}: fetch returned no rows "
            f"({result.error or 'empty upstream response'})")
    missing = [name for name in REQUIRED_COLUMNS if name not in result.frame.columns]
    if missing:
        raise SeasonFetchError(f"{TABLE} {season}: fetch lacks {missing}")


def seed_season(season: str, result: FetchResult) -> int:
    require_complete(season, result)
    return store.save_frame(TABLE, result, entity=ENTITY, replace_season=True)


def run(seasons: list[str],
        fetch: Callable[[str], FetchResult] = fetch_season,
        delay_s: float = DELAY_S) -> SeasonReport:
    done = loaded_seasons()
    skipped: list[str] = []
    loaded: dict[str, int] = {}
    fetched = 0
    for season in seasons:
        if season in done:
            skipped.append(season)
            continue
        if fetched:
            time.sleep(delay_s)
        loaded[season] = seed_season(season, fetch(season))
        fetched += 1
        done.add(season)
    return {"loaded": loaded, "skipped": skipped, "rows": sum(loaded.values())}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Backfill LeagueDashPlayerStats Advanced into "
                    f"{TABLE}. Seasons already in the table are skipped.")
    ap.add_argument("--first", default=FIRST_SEASON)
    ap.add_argument("--last", default=LAST_SEASON)
    ap.add_argument("--delay", type=float, default=DELAY_S,
                    help="seconds between upstream calls")
    ns = ap.parse_args(argv)

    seasons = season_slugs(ns.first, ns.last)
    try:
        report = run(seasons, delay_s=ns.delay)
    except SeasonFetchError as exc:
        print(f"FAIL {exc}", flush=True)
        return 1

    for season in report["skipped"]:
        print(f"{TABLE} {season}: already loaded, skipped")
    for season, rows in sorted(report["loaded"].items()):
        print(f"{TABLE} {season}: {rows} rows")
    print(f"{TABLE}: {len(report['loaded'])} seasons loaded, {report['rows']} rows, "
          f"{len(report['skipped'])} skipped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
