import os
import subprocess
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
V2_TITLE = "Dime NBA Analyst (v2)"
PROBE = (
    "import sys\n"
    "import entrypoint\n"
    "provider = 'unknown'\n"
    "candidate = sys.modules.get('v2.main')\n"
    "if candidate is not None and candidate.app is entrypoint.app:\n"
    "    provider = 'v2.main'\n"
    "print(entrypoint.app.title)\n"
    "print(provider)\n"
)


def _child(value, unset=False):
    env = dict(os.environ)
    env.pop("DIME_RUNTIME_V2", None)
    if not unset:
        env["DIME_RUNTIME_V2"] = value
    return subprocess.run(
        [sys.executable, "-c", PROBE],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
    )


def _title_and_provider(proc):
    assert proc.returncode == 0
    lines = proc.stdout.strip().splitlines()
    assert len(lines) == 2
    return lines[0], lines[1]


@pytest.mark.parametrize("value,unset", [
    ("on", False),
    ("off", False),
    ("shadow", False),
    ("", True),
    ("", False),
    ("   ", False),
    ("typo", False),
])
def test_always_mounts_v2(value, unset):
    assert _title_and_provider(_child(value, unset)) == (V2_TITLE, "v2.main")
