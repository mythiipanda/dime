"""CLI: python -m bench.run_benchmark [--families ...] [--per-family N] ..."""

import argparse
import asyncio
import json
import os
import random
import shutil
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

from app import store as _store

from .driver import run_all, summarize
from .ground import GENERATORS, SkipTask
from .schemas import GroundTruth, Task

RESULTS_DIR = Path(__file__).resolve().parent / "results"


def _snapshot_warehouse(retries: int = 5) -> Path:
    dest = Path(tempfile.mkdtemp(prefix="dimebench_")) / "warehouse.duckdb"
    last: Exception | None = None
    for _ in range(retries):
        try:
            with _store.write_guard(timeout_s=10):
                shutil.copy2(_store.DB_PATH, dest)
            con = _store.duckdb.connect(str(dest), read_only=True)
            con.execute("SELECT COUNT(*) FROM information_schema.tables").fetchone()
            con.close()
            return dest
        except Exception as exc:
            last = exc
            time.sleep(2)
    raise RuntimeError(f"warehouse snapshot failed: {last}")


_snap_parser = argparse.ArgumentParser(add_help=False)
_snap_parser.add_argument("--no-snapshot", action="store_true")
_snap_known, _ = _snap_parser.parse_known_args()
if not _snap_known.no_snapshot:
    os.environ["DIME_WAREHOUSE"] = str(_snapshot_warehouse())
    _store.DB_PATH = Path(os.environ["DIME_WAREHOUSE"])
    _store.LOCK_PATH = _store.DB_PATH.parent / ".write.lock"
    print(f"DimeBench: benchmarking against warehouse snapshot "
          f"{os.environ['DIME_WAREHOUSE']}", flush=True)


def build_tasks(families: list[str], per_family: int, seed: int,
                timeout: int) -> list[tuple[Task, GroundTruth]]:
    pairs = []
    for family in families:
        gen = GENERATORS[family]
        for idx in range(per_family):
            task_id = f"{family}-{idx}-{seed}"
            rng = random.Random(f"{seed}:{family}:{idx}")
            ctx = {"task_id": task_id, "seed": seed, "timeout_s": timeout}
            try:
                pairs.append(gen(rng, ctx))
            except SkipTask as exc:
                task = Task(task_id=task_id, family=family, question="",
                            gold_tool_families=[family], timeout_s=timeout,
                            seed=seed)
                truth = GroundTruth(task_id=task_id,
                                    facts={"__skipped__": f"skipped: {exc}"},
                                    computed_at="", source="")
                pairs.append((task, truth))
            except Exception as exc:
                task = Task(task_id=task_id, family=family, question="",
                            gold_tool_families=[family], timeout_s=timeout,
                            seed=seed)
                truth = GroundTruth(
                    task_id=task_id,
                    facts={"__skipped__": f"skipped: generator failed: {exc}"},
                    computed_at="", source="")
                pairs.append((task, truth))
    return pairs


def main() -> None:
    parser = argparse.ArgumentParser(description="DimeBench runner")
    parser.add_argument("--families", default=",".join(sorted(GENERATORS)),
                        help="comma-separated subset of families")
    parser.add_argument("--per-family", type=int, default=2)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--model", default=None)
    parser.add_argument("--no-snapshot", action="store_true",
                        help="use the live warehouse instead of a snapshot copy")
    args = parser.parse_args()
    families = [f.strip() for f in args.families.split(",") if f.strip()]
    unknown = [f for f in families if f not in GENERATORS]
    if unknown:
        raise SystemExit(f"unknown families: {unknown}")
    pairs = build_tasks(families, args.per_family, args.seed, args.timeout)
    results = asyncio.run(run_all(pairs, args.model))
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    jsonl_path = RESULTS_DIR / f"bench_{stamp}.jsonl"
    md_path = RESULTS_DIR / f"bench_{stamp}.md"
    with open(jsonl_path, "w") as fh:
        for r in results:
            fh.write(json.dumps(r.to_dict(), default=str) + "\n")
    report, _ = summarize(results)
    with open(md_path, "w") as fh:
        fh.write(report)
    print(report)
    print(f"wrote {jsonl_path}")
    print(f"wrote {md_path}")


if __name__ == "__main__":
    main()
