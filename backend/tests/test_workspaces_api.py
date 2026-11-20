import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


from workspaces.service import WorkspaceStore

PROC_SELF_FD = Path("/proc/self/fd")

requires_fd_enumeration = pytest.mark.skipif(
    not PROC_SELF_FD.is_dir(),
    reason=("open-handle enumeration has no stdlib equivalent off POSIX; "
            "the leak check is only provable where /proc/self/fd exists"),
)














@requires_fd_enumeration
def test_no_connection_growth_across_crud_sequence(tmp_path):
    from workspaces.service import WorkspaceStore

    path = str(tmp_path / "leak.sqlite3")

    def open_handles():
        count = 0
        for fd in os.listdir(PROC_SELF_FD):
            try:
                if os.readlink(f"{PROC_SELF_FD}/{fd}") == path:
                    count += 1
            except OSError:
                pass
        return count

    store = WorkspaceStore(path)
    baseline = open_handles()
    for index in range(5):
        workspace, _ = store.create(f"w{index}", "o")
        store.update_members(workspace.id, add_thread_ids=["t"])
        store.get(workspace.id)
        store.delete(workspace.id)
    assert open_handles() == baseline






def test_fd_enumeration_assumption_is_single_sourced_across_backend():
    backend = Path(__file__).resolve().parent.parent
    offenders = []
    for path in sorted(backend.rglob("*.py")):
        if path.resolve() == Path(__file__).resolve():
            continue
        if "/proc/self/fd" in path.read_text(encoding="utf-8"):
            offenders.append(str(path.relative_to(backend)))
    assert offenders == []


def test_leak_check_skips_exactly_when_fd_enumeration_is_unavailable():
    marker = test_no_connection_growth_across_crud_sequence.pytestmark[0]
    assert marker.name == "skipif"
    assert marker.args[0] == (not PROC_SELF_FD.is_dir())
    assert isinstance(marker.kwargs["reason"], str) and marker.kwargs["reason"]
