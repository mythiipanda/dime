import hashlib
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared import store  # noqa: E402


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
