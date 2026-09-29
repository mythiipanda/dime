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


def test_on_mounts_v2():
    title, provider = _title_and_provider(_child("on"))
    assert title == V2_TITLE
    assert provider == "v2.main"


def test_off_mounts_v1():
    title, provider = _title_and_provider(_child("off"))
    assert title == V1_TITLE
    assert provider == "app.main"


def test_unset_mounts_v1():
    title, provider = _title_and_provider(_child("", unset=True))
    assert title == V1_TITLE
    assert provider == "app.main"


def test_empty_mounts_v1():
    title, provider = _title_and_provider(_child(""))
    assert title == V1_TITLE
    assert provider == "app.main"


def test_whitespace_mounts_v1():
    title, provider = _title_and_provider(_child("   "))
    assert title == V1_TITLE
    assert provider == "app.main"


def test_shadow_mounts_v1():
    title, provider = _title_and_provider(_child("shadow"))
    assert title == V1_TITLE
    assert provider == "app.main"


@pytest.mark.parametrize("value", ["true", "yes", "1", "typo"])
def test_invalid_raises_at_import(value):
    proc = _child(value)
    assert proc.returncode != 0
    assert "ValueError" in proc.stderr
