import os
import subprocess
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
V1_TITLE = "Dime NBA Analyst"
V2_TITLE = "Dime NBA Analyst (v2)"
PROBE = (
    "import sys\n"
    "import entrypoint\n"
    "provider = 'unknown'\n"
    "candidate = sys.modules.get('v2.main')\n"
    "if candidate is not None and candidate.app is entrypoint.app:\n"
    "    provider = 'v2.main'\n"
    "candidate = sys.modules.get('app.main')\n"
    "if candidate is not None and candidate.app is entrypoint.app:\n"
    "    provider = 'app.main'\n"
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


@pytest.mark.parametrize("value,unset,title,provider", [
    ("on", False, V2_TITLE, "v2.main"),
    ("off", False, V1_TITLE, "app.main"),
    ("shadow", False, V1_TITLE, "app.main"),
    ("", True, V1_TITLE, "app.main"),
    ("", False, V1_TITLE, "app.main"),
    ("   ", False, V1_TITLE, "app.main"),
])
def test_mode_mounts_expected_app(value, unset, title, provider):
    assert _title_and_provider(_child(value, unset)) == (title, provider)


@pytest.mark.parametrize("value", ["true", "yes", "1", "typo"])
def test_invalid_raises_at_import(value):
    proc = _child(value)
    assert proc.returncode != 0
    assert "ValueError" in proc.stderr
