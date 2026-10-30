"""Run the same Pi analyst producer used by HTTP."""
import argparse
import asyncio
import json
import os
from pathlib import Path
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analyst.configuration import resolve_product_model, worker_environment
from analyst.product_session import stream_product_session


def session_options(model):
    from shared import store

    backend = Path(__file__).resolve().parents[1]
    node = shutil.which("node")
    if node is None:
        raise ValueError("Node runtime unavailable")
    return dict(model=resolve_product_model(model), node=node, python=sys.executable,
                env=worker_environment(), warehouse=store.DB_PATH.resolve(),
                private_root=Path(os.environ.get("DIME_PI_PRIVATE_DIR", str(backend / "data/pi-private"))),
                sources_dir=Path(os.environ.get("DIME_PI_SOURCES_DIR", str(backend / "data/pi-sources"))),
                conversations=None, store=None)


async def run_question(question, options, *, stdout, stderr):
    failed = False
    final = False
    async for chunk in stream_product_session(q=question, **options):
        for frame in chunk.strip().split("\n\n"):
            lines = frame.splitlines()
            event = json.loads(next(line[6:] for line in lines if line.startswith("data: ")))
            kind = lines[0][7:]
            if kind == "failure":
                failed = True
                print(event["message"], file=stderr)
            elif kind == "final_answer":
                final = True
                print(event["text"], file=stdout)
                for ref in event["carry"]["source_refs"]:
                    print("source: " + ref, file=stderr)
            elif kind == "work_log":
                print("run: " + event["run_id"], file=stderr)
    return 1 if failed or not final else 0


def main(argv=None, *, configure=session_options, stdout=None, stderr=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("question")
    parser.add_argument("--model", default=None)
    args = parser.parse_args(argv)
    stdout, stderr = stdout or sys.stdout, stderr or sys.stderr
    try:
        options = configure(args.model)
    except (ValueError, OSError) as exc:
        print("Configuration error: " + str(exc), file=stderr)
        return 1
    return asyncio.run(run_question(args.question, options, stdout=stdout, stderr=stderr))


if __name__ == "__main__":
    raise SystemExit(main())
