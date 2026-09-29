import hashlib
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
    real_sha256 = hashlib.sha256
    calls = []

    def counting(data=b"", *a, **k):
        calls.append(1)
        return real_sha256(data, *a, **k)

    monkeypatch.setattr(store.hashlib, "sha256", counting)
    first = store.warehouse_identity()
    second = store.warehouse_identity()
    assert first == second
    assert first.keys() == {"warehouse_id", "warehouse_sha256"}
    assert len(calls) == 1


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
    real_sha256 = hashlib.sha256
    calls = []

    def counting(data=b"", *a, **k):
        calls.append(1)
        return real_sha256(data, *a, **k)

    monkeypatch.setattr(store.hashlib, "sha256", counting)
    store.warehouse_identity()
    store.warehouse_identity()
    assert len(calls) == 1
    store.warehouse_identity_cache_clear()
    again = store.warehouse_identity()
    assert len(calls) == 2
    assert again.keys() == {"warehouse_id", "warehouse_sha256"}
