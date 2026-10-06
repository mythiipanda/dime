import argparse
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.providers import resolve_model_id
from v2.runtime.assembly import build_runtime
from v2.runtime.policy import ExecutionPolicy

def main() -> int:
    args = argparse.ArgumentParser()
    args.add_argument("question")
    args.add_argument("--run-id", default="lat6")
    args.add_argument("--ledger-dir", default=".")
    args.add_argument("--model", default=None)
    ns = args.parse_args()
    provider, model_name = resolve_model_id(
        ns.model or os.environ.get("DIME_V2_MODEL"))

    async def run():
        policy = ExecutionPolicy.live(ledger_dir=ns.ledger_dir)
        runtime, _ = build_runtime(
            provider=provider, model_name=model_name, run_id=ns.run_id,
            policy=policy)
        return await runtime.run(ns.question, run_id=ns.run_id)

    result = asyncio.run(run())
    print("claims=%d gaps=%d" % (len(result.verified_claims), len(result.gaps)))
    print("ledger: %s" % (Path(ns.ledger_dir) / (ns.run_id + ".jsonl")))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
