from __future__ import annotations

import json
import math
import os
import signal
import subprocess
import sys
import tempfile
from pathlib import Path

from shared import store

WORKER = Path(__file__).with_name("worker.py")


def enabled() -> bool:
    return os.environ.get("DIME_NOTEBOOK_PYTHON") == "1"


def run(source: str, timeout_s: float) -> dict:
    env = {"PATH": os.defpath, "MPLBACKEND": "Agg", "OPENBLAS_NUM_THREADS": "1",
           "OMP_NUM_THREADS": "1", "POLARS_MAX_THREADS": "2"}
    with tempfile.TemporaryDirectory(prefix="dime-notebook-") as directory:
        env.update(HOME=directory, TMPDIR=directory, MPLCONFIGDIR=directory)
        job = Path(directory) / "job.json"
        job.write_text(json.dumps({"source": source, "warehouse": str(store.DB_PATH.resolve()),
                                   "cpu_s": math.ceil(timeout_s) + 1}))
        with (Path(directory) / "stdout").open("wb") as stdout, (Path(directory) / "stderr").open("wb") as stderr:
            process = subprocess.Popen([sys.executable, "-I", str(WORKER), str(job)], cwd=directory,
                                       env=env, stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr,
                                       start_new_session=True)
            try:
                process.wait(timeout=timeout_s)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except (AttributeError, ProcessLookupError):
                    process.kill()
                process.wait()
                def captured(name):
                    path = Path(directory) / name
                    return path.read_bytes()[:65536].decode(errors="replace") if path.exists() else ""
                return {"ok": False, "error": f"Python timed out after {timeout_s:g}s", "timed_out": True,
                        "stdout": captured("captured-stdout"), "stderr": captured("captured-stderr"),
                        "tables": [], "figures": []}
        result = Path(directory) / "result.json"
        if result.is_file() and result.stat().st_size <= 8 * 1024 * 1024:
            return json.loads(result.read_text())
        return {"ok": False, "error": f"Python worker exited with code {process.returncode}",
                "stdout": (Path(directory) / "stdout").read_bytes()[:65536].decode(errors="replace"),
                "stderr": (Path(directory) / "stderr").read_bytes()[:65536].decode(errors="replace"),
                "tables": [], "figures": []}
