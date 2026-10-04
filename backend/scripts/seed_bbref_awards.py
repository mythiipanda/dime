import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import polars as pl

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))

from shared import store  # noqa: E402
from shared.sources import bbref_awards as src  # noqa: E402
from shared.sources.base import FetchMeta, FetchResult  # noqa: E402

TABLE = "silver_bbref_awards"
PROGRESS_FILE = HERE / "seed_bbref_awards_progress.json"
LOG_FILE = HERE / "seed_bbref_awards.log"
SEASON_SHAPE = re.compile(r"^\d{4}-\d{2}$")
CONSECUTIVE_FAILURE_LIMIT = 3


class SeasonPlanError(RuntimeError):
    pass


def log(message: str) -> None:
    line = f"{datetime.now().isoformat(timespec='seconds')} {message}"
    print(line, flush=True)
    with open(LOG_FILE, "a") as handle:
        handle.write(line + "\n")


def entity_for(season: str) -> str:
    return f"season:{season}"


def load_progress(progress_file: Path = PROGRESS_FILE) -> dict:
    if progress_file.exists():
        return json.loads(progress_file.read_text())
    return {"done": [], "failed": {}}


def mark_done(progress_file: Path, season: str) -> None:
    state = load_progress(progress_file)
    if season not in state["done"]:
        state["done"] = sorted(state["done"] + [season])
    state["failed"].pop(season, None)
    progress_file.write_text(json.dumps(state, indent=1))


def mark_failed(progress_file: Path, season: str, reason: str) -> None:
    state = load_progress(progress_file)
    state["failed"][season] = str(reason)[:300]
    state["done"] = [done for done in state["done"] if done != season]
    progress_file.write_text(json.dumps(state, indent=1))


def pending_seasons(seasons: list[str],
                    progress_file: Path = PROGRESS_FILE) -> list[str]:
    done = set(load_progress(progress_file)["done"])
    return [season for season in seasons if season not in done]


def warehouse_seasons(con) -> list[str]:
    found: set[str] = set()
    for (table,) in con.execute(
            "SELECT table_name FROM information_schema.tables").fetchall():
        if not str(table).startswith("silver_"):
            continue
        columns = {row[1] for row in con.execute(
            f'PRAGMA table_info("{table}")').fetchall()}
        if "_season" not in columns:
            continue
        for (value,) in con.execute(
                f'SELECT DISTINCT _season FROM "{table}"').fetchall():
            if value and SEASON_SHAPE.fullmatch(str(value)):
                found.add(str(value))
    return sorted(found)


def plan_seasons(published: list[int], from_season: str = "",
                 to_season: str = "") -> list[str]:
    con = store.connect()
    try:
        seasons = warehouse_seasons(con)
    finally:
        con.close()
    if not seasons:
        raise SeasonPlanError(
            "no YYYY-YY _season values in any silver_ table, so there is no "
            "warehouse span to target")
    years = {src.season_year(season) for season in seasons}
    available = set(published)
    planned = [season for season in seasons
               if src.season_year(season) in available]
    if from_season:
        planned = [season for season in planned if season >= from_season]
    if to_season:
        planned = [season for season in planned if season <= to_season]
    if not planned:
        raise SeasonPlanError(
            f"no warehouse season survives the filter "
            f"(from={from_season!r} to={to_season!r}, "
            f"{len(years)} warehouse seasons, {len(published)} published)")
    return planned


def save_rows(season: str, rows: pl.DataFrame) -> int:
    result = FetchResult(frame=rows,
                         meta=FetchMeta(source=src.SOURCE, season=season))
    return store.save_frame(TABLE, result, entity=entity_for(season))


def seed_season(season: str, transport=None, min_interval_s: float = 0.0,
                progress_file: Path | None = None) -> int:
    year = src.season_year(season)
    result = src.fetch_season(year, transport=transport,
                              min_interval_s=min_interval_s or src.MIN_INTERVAL_S)
    written = save_rows(season, result.frame)
    if progress_file is not None:
        mark_done(progress_file, season)
    log(f"{season}: {written} rows from {src.season_url(year)}")
    return written


def main(argv: list[str]) -> int:
    args = argv[1:]
    from_season = _flag(args, "--from-season") or ""
    to_season = _flag(args, "--to-season") or ""
    only = _flag(args, "--seasons")
    only = only.split(",") if only else []
    limit = int(_flag(args, "--limit") or 0)
    progress_file = Path(_flag(args, "--progress") or PROGRESS_FILE)

    transport = src.paced_transport()
    published = src.fetch_index(transport=transport)
    log(f"index: {len(published)} published seasons "
        f"{published[0]}-{published[-1]}")
    seasons = only or plan_seasons(published, from_season, to_season)
    queue = pending_seasons(seasons, progress_file)
    if limit:
        queue = queue[:limit]
    log(f"plan: {len(queue)} seasons to fetch out of {len(seasons)} planned")
    if not queue:
        log("nothing pending")
        return 0

    started = time.monotonic()
    done_rows = 0
    consecutive_failures = 0
    for index, season in enumerate(queue, 1):
        try:
            done_rows += seed_season(season, transport=transport,
                                     progress_file=progress_file)
        except Exception as exc:
            consecutive_failures += 1
            mark_failed(progress_file, season, f"{type(exc).__name__}: {exc}")
            log(f"{season}: FAILED {type(exc).__name__}: {exc}")
            if consecutive_failures >= CONSECUTIVE_FAILURE_LIMIT:
                log(f"stopping after {consecutive_failures} consecutive "
                    f"failures; the source is refusing requests, so the rest "
                    f"of the queue stays pending rather than hammering it")
                break
            continue
        consecutive_failures = 0
        if index % 5 == 0 or index == len(queue):
            log(f"[{index}/{len(queue)}] {season}: running total {done_rows} rows, "
                f"{time.monotonic() - started:.0f}s")

    state = load_progress(progress_file)
    failed = sorted(state["failed"])
    log(f"DONE rows={done_rows} done={len(state['done'])} failed={len(failed)}")
    for season in failed:
        log(f"  gap {season}: {state['failed'][season]}")
    if failed:
        print(f"{len(failed)} seasons failed: {', '.join(failed)}", file=sys.stderr)
        return 1
    return 0


def _flag(args: list[str], name: str) -> str | None:
    return args[args.index(name) + 1] if name in args else None


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
