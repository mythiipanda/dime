import errno
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared import file_lock
from shared import store
from v2.runtime import ledger as ledger_module
from v2.runtime.ledger import FileLedger, LedgerKind

_HOLDER_SOURCE = (
    "import sys, time\n"
    "from pathlib import Path\n"
    "sys.path.insert(0, sys.argv[1])\n"
    "from shared import file_lock\n"
    "handle = open(sys.argv[2], 'r+b')\n"
    "file_lock.try_lock_exclusive(handle)\n"
    "sys.stdout.write('locked\\n')\n"
    "sys.stdout.flush()\n"
    "time.sleep(float(sys.argv[3]))\n"
    "handle.close()\n"
)

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
_SUBPROCESS_TIMEOUT_S = 60


def _start_holder(tmp_path: Path, lock_path: Path, hold_s: float) -> subprocess.Popen:
    script = tmp_path / "holder.py"
    script.write_text(_HOLDER_SOURCE, encoding="utf-8")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_bytes(b"\x00")
    proc = subprocess.Popen(
        [sys.executable, str(script), str(_BACKEND_ROOT), str(lock_path), str(hold_s)],
        stdout=subprocess.PIPE,
        text=True,
    )
    assert proc.stdout.readline().strip() == "locked"
    return proc


def _close_quietly(handle) -> None:
    try:
        handle.close()
    except OSError:
        pass


def test_is_contention_separates_contention_from_fatal_errors():
    assert file_lock.is_contention(BlockingIOError()) is True
    assert file_lock.is_contention(OSError(errno.EBADF, "bad descriptor")) is False
    assert file_lock.is_contention(OSError(errno.ENOSPC, "no space")) is False
    assert file_lock.is_contention(OSError(errno.EINVAL, "bad argument")) is False
    assert file_lock.is_contention(OSError(errno.ENOENT, "missing")) is False
    assert file_lock.is_contention(OSError(errno.EACCES, "denied")) is (not file_lock.POSIX)


def test_try_lock_exclusive_rejects_a_live_holder_in_another_process(tmp_path):
    lock_path = tmp_path / "busy.lock"
    proc = _start_holder(tmp_path, lock_path, 30)
    try:
        with open(lock_path, "r+b") as handle:
            started = time.monotonic()
            with pytest.raises(BlockingIOError):
                file_lock.try_lock_exclusive(handle)
            assert time.monotonic() - started < 5.0
    finally:
        proc.terminate()
        proc.wait(timeout=_SUBPROCESS_TIMEOUT_S)


def test_lock_is_released_when_another_process_exits_without_unlock(tmp_path):
    lock_path = tmp_path / "released.lock"
    proc = _start_holder(tmp_path, lock_path, 0.5)
    with open(lock_path, "r+b") as handle:
        with pytest.raises(BlockingIOError):
            file_lock.try_lock_exclusive(handle)
    proc.wait(timeout=_SUBPROCESS_TIMEOUT_S)
    assert proc.returncode == 0
    with open(lock_path, "r+b") as handle:
        file_lock.try_lock_exclusive(handle)
        file_lock.unlock(handle)


def test_lock_is_released_when_the_handle_is_closed(tmp_path):
    lock_path = tmp_path / "closed.lock"
    lock_path.write_bytes(b"\x00")
    handle = open(lock_path, "r+b")
    file_lock.try_lock_exclusive(handle)
    handle.close()
    second = open(lock_path, "r+b")
    try:
        file_lock.try_lock_exclusive(second)
        file_lock.unlock(second)
    finally:
        _close_quietly(second)


def test_unlock_is_safe_when_the_region_is_not_held(tmp_path):
    lock_path = tmp_path / "idempotent.lock"
    lock_path.write_bytes(b"\x00")
    with open(lock_path, "r+b") as handle:
        file_lock.unlock(handle)
        file_lock.try_lock_exclusive(handle)
        file_lock.unlock(handle)
        file_lock.unlock(handle)


def test_try_lock_exclusive_surfaces_a_fatal_oserror_instead_of_contention(tmp_path):
    lock_path = tmp_path / "fatal.lock"
    lock_path.write_bytes(b"\x00")
    handle = open(lock_path, "r+b")
    os.close(handle.fileno())
    try:
        with pytest.raises(OSError) as excinfo:
            file_lock.try_lock_exclusive(handle)
        assert not isinstance(excinfo.value, BlockingIOError)
        assert excinfo.value.errno == errno.EBADF
    finally:
        _close_quietly(handle)


def test_lock_exclusive_timeout_raises_instead_of_spinning(tmp_path):
    lock_path = tmp_path / "spin.lock"
    proc = _start_holder(tmp_path, lock_path, 30)
    try:
        with open(lock_path, "r+b") as handle:
            started = time.monotonic()
            with pytest.raises(TimeoutError, match="exclusive lock timed out"):
                file_lock.lock_exclusive(handle, timeout_s=0.4)
            assert time.monotonic() - started < 15
    finally:
        proc.terminate()
        proc.wait(timeout=_SUBPROCESS_TIMEOUT_S)


def test_lock_exclusive_with_a_timeout_surfaces_fatal_errors_without_retrying(tmp_path):
    lock_path = tmp_path / "fatal_spin.lock"
    lock_path.write_bytes(b"\x00")
    handle = open(lock_path, "r+b")
    os.close(handle.fileno())
    try:
        started = time.monotonic()
        with pytest.raises(OSError) as excinfo:
            file_lock.lock_exclusive(handle, timeout_s=30.0)
        assert not isinstance(excinfo.value, TimeoutError)
        assert excinfo.value.errno == errno.EBADF
        assert time.monotonic() - started < 15
    finally:
        _close_quietly(handle)


def test_store_write_guard_releases_the_lock_when_the_body_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "warehouse.duckdb")
    monkeypatch.setattr(store, "LOCK_PATH", tmp_path / ".write.lock")
    with pytest.raises(RuntimeError, match="injected"):
        with store.write_guard(timeout_s=5.0):
            raise RuntimeError("injected")
    with store.write_guard(timeout_s=1.0):
        pass


def test_store_write_guard_times_out_when_another_process_holds_the_lock(tmp_path, monkeypatch):
    lock_path = tmp_path / ".write.lock"
    proc = _start_holder(tmp_path, lock_path, 30)
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "warehouse.duckdb")
    monkeypatch.setattr(store, "LOCK_PATH", lock_path)
    try:
        started = time.monotonic()
        with pytest.raises(TimeoutError, match="warehouse write lock timed out"):
            with store.write_guard(timeout_s=0.4):
                pass
        assert time.monotonic() - started < 15
    finally:
        proc.terminate()
        proc.wait(timeout=_SUBPROCESS_TIMEOUT_S)


def test_store_write_guard_surfaces_fatal_lock_errors_instead_of_waiting(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "warehouse.duckdb")
    monkeypatch.setattr(store, "LOCK_PATH", tmp_path / ".write.lock")
    monkeypatch.setattr(
        file_lock,
        "try_lock_exclusive",
        lambda handle: (_ for _ in ()).throw(OSError(errno.ENOSPC, "no space left")),
    )
    started = time.monotonic()
    with pytest.raises(OSError) as excinfo:
        with store.write_guard(timeout_s=30.0):
            pass
    assert not isinstance(excinfo.value, TimeoutError)
    assert excinfo.value.errno == errno.ENOSPC
    assert time.monotonic() - started < 15


def test_store_state_write_guard_times_out_when_another_process_holds_the_lock(tmp_path, monkeypatch):
    lock_path = tmp_path / ".state.lock"
    proc = _start_holder(tmp_path, lock_path, 30)
    monkeypatch.setattr(store, "STATE_PATH", tmp_path / "state.json")
    monkeypatch.setattr(store, "STATE_LOCK_PATH", lock_path)
    try:
        with pytest.raises(TimeoutError, match="state write lock timed out"):
            with store.state_write_guard(timeout_s=0.4):
                pass
    finally:
        proc.terminate()
        proc.wait(timeout=_SUBPROCESS_TIMEOUT_S)


def test_store_state_write_guard_releases_the_lock_when_the_body_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "STATE_PATH", tmp_path / "state.json")
    monkeypatch.setattr(store, "STATE_LOCK_PATH", tmp_path / ".state.lock")
    with pytest.raises(RuntimeError, match="injected"):
        with store.state_write_guard(timeout_s=5.0):
            raise RuntimeError("injected")
    with store.state_write_guard(timeout_s=1.0):
        pass


def test_ledger_append_times_out_while_another_process_holds_the_ledger_lock(tmp_path, monkeypatch):
    path = tmp_path / "run.jsonl"
    FileLedger(path, "run")
    lock_path = path.with_name(path.name + ".lock")
    proc = _start_holder(tmp_path, lock_path, 30)
    monkeypatch.setattr(ledger_module, "_LEDGER_LOCK_TIMEOUT_S", 0.4)
    try:
        with pytest.raises(TimeoutError):
            FileLedger(path, "run")
    finally:
        monkeypatch.setattr(ledger_module, "_LEDGER_LOCK_TIMEOUT_S", 60.0)
        proc.terminate()
        proc.wait(timeout=_SUBPROCESS_TIMEOUT_S)
    monkeypatch.setattr(ledger_module, "_LEDGER_LOCK_TIMEOUT_S", 5.0)
    recovered = FileLedger(path, "run")
    entry = recovered.append(LedgerKind.TURN_START, turn_id="turn", data={"request": "q"})
    assert entry.sequence == 1
    assert [x.sequence for x in recovered.entries] == [1]
    assert path.read_bytes().count(b"\n") == 1


def test_ledger_append_serializes_behind_another_process_and_leaves_no_truncation(tmp_path):
    path = tmp_path / "run.jsonl"
    ledger = FileLedger(path, "run")
    lock_path = path.with_name(path.name + ".lock")
    proc = _start_holder(tmp_path, lock_path, 1.0)
    original_timeout = ledger_module._LEDGER_LOCK_TIMEOUT_S
    ledger_module._LEDGER_LOCK_TIMEOUT_S = 30.0
    try:
        entry = ledger.append(LedgerKind.TURN_START, turn_id="turn", data={"request": "q"})
    finally:
        ledger_module._LEDGER_LOCK_TIMEOUT_S = original_timeout
        proc.wait(timeout=_SUBPROCESS_TIMEOUT_S)
    assert entry.sequence == 1
    assert proc.returncode == 0
    assert [x.sequence for x in FileLedger(path, "run").entries] == [1]
