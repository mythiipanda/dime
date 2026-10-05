import json
import sys
import time
from pathlib import Path

import polars as pl

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))

from shared import store  # noqa: E402
from shared.sources import nba_awards as src  # noqa: E402
from shared.sources.base import FetchMeta, FetchResult  # noqa: E402

TABLE = src.TABLE
PROGRESS_FILE = HERE / "seed_nba_awards_progress.json"
LOG_FILE = HERE / "seed_nba_awards.log"
MIN_INTERVAL_S = 0.6
CONSECUTIVE_FAILURE_LIMIT = 5


def log(message: str) -> None:
    line = f"{time.strftime('%Y-%m-%dT%H:%M:%S')} {message}"
    print(line, flush=True)
    with open(LOG_FILE, "a") as handle:
        handle.write(line + "\n")


def load_progress(progress_file: Path = PROGRESS_FILE) -> dict:
    if progress_file.exists():
        return json.loads(progress_file.read_text())
    return {"done": [], "failed": {}}


def mark_done(progress_file: Path, player_id: int) -> None:
    state = load_progress(progress_file)
    if player_id not in state["done"]:
        state["done"] = sorted(state["done"] + [player_id])
    state["failed"].pop(str(player_id), None)
    progress_file.write_text(json.dumps(state, indent=1))


def mark_failed(progress_file: Path, player_id: int, reason: str) -> None:
    state = load_progress(progress_file)
    state["failed"][str(player_id)] = str(reason)[:300]
    state["done"] = [done for done in state["done"] if done != player_id]
    progress_file.write_text(json.dumps(state, indent=1))


def player_universe() -> list[tuple[int, str]]:
    from nba_api.stats.static import players as static_players

    return [(row["id"], row["full_name"])
            for row in static_players.get_players()]


def save_player_rows(player_id: int, frame: pl.DataFrame) -> int:
    written = 0
    for season in frame["SEASON"].unique().to_list():
        rows = frame.filter(pl.col("SEASON") == season)
        result = FetchResult(
            frame=rows,
            meta=FetchMeta(source=src.SOURCE, season=str(season)))
        written += store.save_frame(
            TABLE, result, entity=f"player:{player_id}")
    return written


def seed_player(player_id: int,
                progress_file: Path | None = None) -> int:
    result = src.fetch_player_awards(player_id)
    if not result.ok:
        raise RuntimeError(result.error or "fetch failed")
    written = save_player_rows(player_id, result.frame)
    if progress_file is not None:
        mark_done(progress_file, player_id)
    return written


def main(argv: list[str]) -> int:
    args = argv[1:]
    only = _flag(args, "--player-ids")
    only_ids = [int(value) for value in only.split(",")] if only else []
    limit = int(_flag(args, "--limit") or 0)
    progress_file = Path(_flag(args, "--progress") or PROGRESS_FILE)

    universe = player_universe()
    if only_ids:
        wanted = set(only_ids)
        universe = [(pid, name) for pid, name in universe if pid in wanted]
    done = set(load_progress(progress_file)["done"])
    queue = [(pid, name) for pid, name in universe if pid not in done]
    if limit:
        queue = queue[:limit]
    log(f"plan: {len(queue)} players to fetch out of {len(universe)} "
        f"({len(done)} already done)")
    if not queue:
        log("nothing pending")
        return 0

    started = time.monotonic()
    done_rows = 0
    consecutive_failures = 0
    for index, (player_id, name) in enumerate(queue, 1):
        try:
            rows = seed_player(player_id, progress_file=progress_file)
        except Exception as exc:
            consecutive_failures += 1
            mark_failed(progress_file, player_id,
                        f"{type(exc).__name__}: {exc}")
            log(f"{player_id} {name}: FAILED {type(exc).__name__}: {exc}")
            if consecutive_failures >= CONSECUTIVE_FAILURE_LIMIT:
                log(f"stopping after {consecutive_failures} consecutive "
                    f"failures; the rest of the queue stays pending")
                break
            continue
        consecutive_failures = 0
        done_rows += rows
        if index % 25 == 0 or index == len(queue):
            log(f"[{index}/{len(queue)}] {name}: running total {done_rows} "
                f"rows, {time.monotonic() - started:.0f}s")
        time.sleep(MIN_INTERVAL_S)

    state = load_progress(progress_file)
    failed = sorted(state["failed"])
    log(f"DONE rows={done_rows} done={len(state['done'])} "
        f"failed={len(failed)}")
    for player_id in failed:
        log(f"  gap {player_id}: {state['failed'][player_id]}")
    if failed:
        print(f"{len(failed)} players failed", file=sys.stderr)
        return 1
    return 0


def _flag(args: list[str], name: str) -> str | None:
    return args[args.index(name) + 1] if name in args else None


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
