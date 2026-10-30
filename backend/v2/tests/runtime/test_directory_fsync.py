from __future__ import annotations

import inspect
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

import pytest

from shared import durability
from v2.contracts import EvidenceEnvelope, Plan, PlanNode, RunMode, TaskSpec
from v2.tests.compatibility.replay import save_replay

FLAG = "shared.durability.DIRECTORY_FSYNC_SUPPORTED"
PLATFORM_SUPPORTS = durability.DIRECTORY_FSYNC_SUPPORTED

SITE_MODULES = (
    "v2.tests.compatibility.replay",
)


def test_every_site_module_delegates_instead_of_opening_a_directory() -> None:
    for name in SITE_MODULES:
        module = __import__(name, fromlist=["_"])
        source = inspect.getsource(module)
        assert 'os.name == "posix"' not in source, name
        for line in source.splitlines():
            assert not ("os.open(" in line and "O_RDONLY" in line), f"{name}: {line.strip()}"


def test_open_directory_for_fsync_returns_none_when_unsupported(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(FLAG, False)
    assert durability.open_directory_for_fsync(tmp_path) is None


def test_open_directory_for_fsync_matches_platform_capability(tmp_path) -> None:
    if not PLATFORM_SUPPORTS:
        with pytest.raises(OSError):
            os.open(tmp_path, os.O_RDONLY)
        return
    handle = durability.open_directory_for_fsync(tmp_path)
    assert isinstance(handle, int)
    os.close(handle)
