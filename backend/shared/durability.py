from __future__ import annotations

import os
from pathlib import Path

DIRECTORY_FSYNC_SUPPORTED = os.name == "posix"


def open_directory_for_fsync(path: str | Path) -> int | None:
    if not DIRECTORY_FSYNC_SUPPORTED:
        return None
    return os.open(path, os.O_RDONLY)
