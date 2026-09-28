"""Suite: eval prompts (existing structural eval, wrapped).

Runs backend/tests/run_eval_standalone.py as a subprocess and parses its
verdict lines. It checks the 20 labeled prompts against skill files and
guard behavior (no keyword routing); it does not evaluate real finder
outputs or answer correctness — that is the skill_finder and judge
suites' job.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from suites import SuiteResult  # noqa: E402
from trace import emit  # noqa: E402

RUNNER = (Path(__file__).resolve().parent.parent.parent / "tests"
          / "run_eval_standalone.py")


def run(ctx):
    res = SuiteResult(name="eval_prompts", mode="hermetic")
    emit("suite_started", {"suite": "eval_prompts", "mode": "hermetic"})
    try:
        out = subprocess.run(
            [sys.executable, str(RUNNER)], capture_output=True, text=True,
            timeout=300)
    except Exception as exc:
        res.fail("runner-exec", f"could not run standalone runner: {exc}")
        return res
    text = out.stdout + out.stderr
    per_prompt = re.findall(r"^(p\d+)\s+\S+\s+(PASS|FAIL)", text,
                            re.MULTILINE)
    for pid, verdict in per_prompt:
        if verdict == "PASS":
            res.ok()
        else:
            line = next((l for l in text.splitlines()
                         if l.startswith(pid)), pid)
            res.fail(pid, line[:200])
    m = re.search(r"RESULT A \(metadata\): (\d+)/(\d+)", text)
    if m:
        res.notes.append(f"metadata {m.group(1)}/{m.group(2)}")
    m = re.search(r"RESULT B \(response quality\): (\d+)/(\d+)", text)
    if m:
        res.notes.append(f"response-quality {m.group(1)}/{m.group(2)}")
    if out.returncode != 0 and not per_prompt:
        res.fail("runner-exit",
                 f"exit {out.returncode}; output:\n{text[:500]}")
    elif out.returncode != 0:
        res.notes.append(f"runner exit {out.returncode} "
                         "(below its 18/20 bar)")
    res.notes.append("structural only: prompt/skill/guard checks, not live "
                     "finder outputs or answer correctness")
    emit("suite_finished", {"suite": "eval_prompts", "mode": res.mode,
                            "passed": res.passed, "failed": res.failed,
                            "skipped": res.skipped})
    return res
