import hashlib
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared import store

def _point_db_at(monkeypatch, tmp_path):
    db = tmp_path / "wh.duckdb"
    db.write_bytes(b"warehouse-bytes-v1")
    monkeypatch.setattr(store, "DB_PATH", db)
    store.warehouse_identity_cache_clear()
    return db

def test_repeated_calls_do_not_rehash(monkeypatch, tmp_path):
    _point_db_at(monkeypatch, tmp_path)
    real_new = hashlib.new
    calls = []

    def counting(name, *a, **k):
        calls.append(1)
        return real_new(name, *a, **k)

    monkeypatch.setattr(store.hashlib, "new", counting)
    first = store.warehouse_identity()
    second = store.warehouse_identity()
    assert first == second
    assert first.keys() == {"warehouse_id", "warehouse_sha256"}
    assert len(calls) == 2

def test_modifying_file_yields_new_sha256(monkeypatch, tmp_path):
    db = _point_db_at(monkeypatch, tmp_path)
    before = store.warehouse_identity()
    db.write_bytes(b"warehouse-bytes-v2-longer-payload")
    after = store.warehouse_identity()
    assert after.keys() == {"warehouse_id", "warehouse_sha256"}
    assert after["warehouse_sha256"] != before["warehouse_sha256"]
    assert after["warehouse_id"] == before["warehouse_id"]

def test_cache_clear_forces_recompute(monkeypatch, tmp_path):
    _point_db_at(monkeypatch, tmp_path)
    real_new = hashlib.new
    calls = []

    def counting(name, *a, **k):
        calls.append(1)
        return real_new(name, *a, **k)

    monkeypatch.setattr(store.hashlib, "new", counting)
    store.warehouse_identity()
    store.warehouse_identity()
    assert len(calls) == 2
    store.warehouse_identity_cache_clear()
    again = store.warehouse_identity()
    assert len(calls) == 3
    assert again.keys() == {"warehouse_id", "warehouse_sha256"}

def test_byte_swap_same_size_restored_mtime_yields_new_sha256(monkeypatch, tmp_path):
    db = _point_db_at(monkeypatch, tmp_path)
    payload = bytes(range(256)) * 128
    db.write_bytes(payload)
    store.warehouse_identity_cache_clear()
    real_sha256 = hashlib.sha256
    first = store.warehouse_identity()
    assert first["warehouse_sha256"] == real_sha256(
        len(payload).to_bytes(8, "little") + payload[:8192]
        + payload[16384:24576] + payload[24576:32768]).hexdigest()
    assert first["warehouse_sha256"] != real_sha256(payload).hexdigest()
    st = db.stat()
    swapped = payload[::-1]
    assert len(swapped) == len(payload)
    assert swapped != payload
    db.write_bytes(swapped)
    os.utime(db, ns=(st.st_atime_ns, st.st_mtime_ns))
    assert db.stat().st_mtime_ns == st.st_mtime_ns
    assert db.stat().st_size == st.st_size
    second = store.warehouse_identity()
    assert second["warehouse_sha256"] == real_sha256(
        len(swapped).to_bytes(8, "little") + swapped[:8192]
        + swapped[16384:24576] + swapped[24576:32768]).hexdigest()
    assert second["warehouse_sha256"] != real_sha256(swapped).hexdigest()
    assert second["warehouse_sha256"] != first["warehouse_sha256"]
    third = store.warehouse_identity()
    assert third == second


def _point_db_at_absent(monkeypatch, tmp_path):
    db = tmp_path / "absent.duckdb"
    assert not db.exists()
    monkeypatch.setattr(store, "DB_PATH", db)
    monkeypatch.setattr(store, "STATE_PATH", tmp_path / "state.duckdb")
    monkeypatch.setattr(store, "STATE_LOCK_PATH", tmp_path / ".state.lock")
    store.warehouse_identity_cache_clear()
    return db


def test_absent_warehouse_raises_the_deliberate_absent_error(monkeypatch, tmp_path):
    db = _point_db_at_absent(monkeypatch, tmp_path)
    with pytest.raises(FileNotFoundError) as caught:
        store.warehouse_identity()
    assert str(caught.value) == f"warehouse absent: {db}"


def test_absent_warehouse_error_type_is_unchanged_for_callers(monkeypatch, tmp_path):
    _point_db_at_absent(monkeypatch, tmp_path)
    with pytest.raises(FileNotFoundError) as caught:
        store.warehouse_identity()
    assert isinstance(caught.value, OSError)


def test_absent_warehouse_matches_the_error_connect_raises(monkeypatch, tmp_path):
    db = _point_db_at_absent(monkeypatch, tmp_path)
    with pytest.raises(FileNotFoundError) as identity_error:
        store.warehouse_identity()
    with pytest.raises(FileNotFoundError) as connect_error:
        store.connect(read_only=True)
    assert type(identity_error.value) is type(connect_error.value)
    assert str(identity_error.value) == str(connect_error.value) == (
        f"warehouse absent: {db}")
    assert identity_error.value.args == connect_error.value.args
    assert identity_error.value.errno == connect_error.value.errno


def test_absent_warehouse_never_returns_an_invented_identity(monkeypatch, tmp_path):
    _point_db_at_absent(monkeypatch, tmp_path)
    for _ in range(3):
        with pytest.raises(FileNotFoundError):
            store.warehouse_identity()
    assert store._warehouse_identity_cache == {}


def test_runtime_manifest_identity_surfaces_the_absent_error(monkeypatch, tmp_path):
    _point_db_at_absent(monkeypatch, tmp_path)
    from v2.api import routes
    routes.runtime_warehouse_identity.cache_clear()
    with pytest.raises(FileNotFoundError, match="warehouse absent"):
        routes.runtime_warehouse_identity()


def test_warehouse_vanishing_between_stat_and_hash_raises_the_absent_error(
        monkeypatch, tmp_path):
    db = tmp_path / "vanish.duckdb"
    db.write_bytes(b"x" * 40000)
    monkeypatch.setattr(store, "DB_PATH", db)
    store.warehouse_identity_cache_clear()
    real_stat = Path.stat
    stats = {"n": 0}

    def vanishing_stat(self, *args, **kwargs):
        result = real_stat(self, *args, **kwargs)
        if self == db:
            stats["n"] += 1
            if stats["n"] >= 2:
                db.unlink()
        return result

    monkeypatch.setattr(Path, "stat", vanishing_stat)
    with pytest.raises(FileNotFoundError) as caught:
        store.warehouse_identity()
    assert str(caught.value) == f"warehouse absent: {db}"


def test_sampled_identity_differs_from_full_file_fallback_for_identical_bytes(
        monkeypatch, tmp_path):
    db = tmp_path / "deriv.duckdb"
    payload = bytes(range(256)) * 128
    db.write_bytes(payload)
    monkeypatch.setattr(store, "DB_PATH", db)
    store.warehouse_identity_cache_clear()
    sampled = store.warehouse_identity()
    real_new = store.hashlib.new

    def failing_new(*args, **kwargs):
        raise PermissionError(13, "Permission denied")

    store.warehouse_identity_cache_clear()
    monkeypatch.setattr(store.hashlib, "new", failing_new)
    fallback = store.warehouse_identity()
    monkeypatch.setattr(store.hashlib, "new", real_new)

    assert fallback["warehouse_id"] == sampled["warehouse_id"]
    assert fallback["warehouse_sha256"] != sampled["warehouse_sha256"]
    assert sampled["warehouse_sha256"] != hashlib.sha256(payload).hexdigest()
    assert fallback["warehouse_sha256"] == hashlib.sha256(payload).hexdigest()


def test_absent_error_factory_is_single_sourced():
    source = Path(store.__file__).read_text(encoding="utf-8")
    assert source.count("f\"warehouse absent: {path}\"") == 1
    assert "f\"warehouse absent: {DB_PATH}\"" not in source
    assert source.count("raise _warehouse_absent_error(") == 3
