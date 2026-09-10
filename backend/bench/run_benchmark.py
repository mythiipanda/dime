"""CLI: python -m bench.run_benchmark [--families ...] [--per-family N] ..."""

import argparse
import asyncio
import json
import random
from datetime import datetime, timezone
from pathlib import Path

from .driver import run_all, summarize
from .ground import GENERATORS, SkipTask
from .schemas import GroundTruth, Task

RESULTS_DIR = Path(__file__).resolve().parent / "results"


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
