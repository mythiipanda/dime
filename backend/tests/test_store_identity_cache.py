import hashlib
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared import change_token, store

def _point_db_at(monkeypatch, tmp_path):
    db = tmp_path / "wh.duckdb"
    db.write_bytes(b"warehouse-bytes-v1")
    monkeypatch.setattr(store, "DB_PATH", db)
    store.warehouse_identity_cache_clear()
    return db

def _hash_bytes_read(monkeypatch):
    consumed = []
    real_digest = store._digest_descriptor

    def counting(descriptor):
        start = os.lseek(descriptor, 0, os.SEEK_CUR)
        digest = real_digest(descriptor)
        consumed.append(os.lseek(descriptor, 0, os.SEEK_CUR) - start)
        return digest

    monkeypatch.setattr(store, "_digest_descriptor", counting)
    return consumed

def test_repeated_calls_return_one_identity_without_rereading_the_bytes(monkeypatch, tmp_path):
    db = _point_db_at(monkeypatch, tmp_path)
    consumed = _hash_bytes_read(monkeypatch)
    first = store.warehouse_identity()
    after_first = list(consumed)
    second = store.warehouse_identity()
    third = store.warehouse_identity()
    assert first == second == third
    assert first.keys() == {"warehouse_id", "warehouse_sha256"}
    assert first["warehouse_sha256"] == hashlib.sha256(b"warehouse-bytes-v1").hexdigest()
    assert after_first == [db.stat().st_size]
    assert consumed == after_first
    assert db in store._warehouse_identity_cache

def test_cache_clear_forces_a_full_reread(monkeypatch, tmp_path):
    db = _point_db_at(monkeypatch, tmp_path)
    consumed = _hash_bytes_read(monkeypatch)
    store.warehouse_identity()
    store.warehouse_identity()
    assert len(consumed) == 1
    store.warehouse_identity_cache_clear()
    again = store.warehouse_identity()
    assert len(consumed) == 2
    assert consumed == [db.stat().st_size, db.stat().st_size]
    assert again["warehouse_sha256"] == hashlib.sha256(b"warehouse-bytes-v1").hexdigest()

def test_off_probe_region_byte_mutation_with_restored_mtime_and_size_is_never_stale(monkeypatch, tmp_path):
    db = tmp_path / "wide.bin"
    payload = b"a" * 65536
    db.write_bytes(payload)
    monkeypatch.setattr(store, "DB_PATH", db)
    store.warehouse_identity_cache_clear()
    first = store.warehouse_identity()
    assert first["warehouse_sha256"] == hashlib.sha256(payload).hexdigest()
    stat = db.stat()
    mutated = bytearray(payload)
    mutated[20000] = ord("b")
    db.write_bytes(mutated)
    os.utime(db, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    assert db.stat().st_mtime_ns == stat.st_mtime_ns
    assert db.stat().st_size == stat.st_size
    second = store.warehouse_identity()
    assert second["warehouse_sha256"] == hashlib.sha256(bytes(mutated)).hexdigest()
    assert second["warehouse_sha256"] != first["warehouse_sha256"]
    assert store.warehouse_identity() == second

def test_in_place_single_byte_mutation_with_restored_mtime_is_never_stale(monkeypatch, tmp_path):
    db = tmp_path / "inplace.bin"
    payload = b"z" * 40000
    db.write_bytes(payload)
    monkeypatch.setattr(store, "DB_PATH", db)
    store.warehouse_identity_cache_clear()
    first = store.warehouse_identity()
    stat = db.stat()
    with open(db, "r+b") as handle:
        handle.seek(20000)
        handle.write(b"q")
    os.utime(db, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    mutated = bytearray(payload)
    mutated[20000] = ord("q")
    second = store.warehouse_identity()
    assert db.stat().st_mtime_ns == stat.st_mtime_ns
    assert db.stat().st_size == stat.st_size
    assert second["warehouse_sha256"] == hashlib.sha256(bytes(mutated)).hexdigest()
    assert second["warehouse_sha256"] != first["warehouse_sha256"]

def test_rewrite_with_restored_mtime_yields_new_sha256(monkeypatch, tmp_path):
    db = _point_db_at(monkeypatch, tmp_path)
    before = store.warehouse_identity()
    db.write_bytes(b"warehouse-bytes-v2-longer-payload")
    after = store.warehouse_identity()
    assert after.keys() == {"warehouse_id", "warehouse_sha256"}
    assert after["warehouse_sha256"] != before["warehouse_sha256"]
    assert after["warehouse_id"] == before["warehouse_id"]

def _torn_digest_for(db: Path, payload: bytes, mutated: bytes, offset: int, stat_ns):
    def torn(descriptor):
        digest = hashlib.sha256()
        os.lseek(descriptor, 0, os.SEEK_SET)
        half = len(payload) // 2
        digest.update(os.read(descriptor, half))
        with open(db, "r+b") as handle:
            handle.seek(offset)
            handle.write(mutated)
        os.utime(db, ns=stat_ns)
        digest.update(os.read(descriptor, len(payload) - half))
        return digest.hexdigest()
    return torn

def test_a_write_during_the_hash_is_never_reported_as_a_stable_identity(monkeypatch, tmp_path):
    db = tmp_path / "raced.bin"
    payload = b"r" * 65536
    db.write_bytes(payload)
    monkeypatch.setattr(store, "DB_PATH", db)
    store.warehouse_identity_cache_clear()
    stat = db.stat()
    monkeypatch.setattr(store, "_digest_descriptor",
                        _torn_digest_for(db, payload, b"s", 20000, (stat.st_atime_ns, stat.st_mtime_ns)))
    monkeypatch.setattr(store, "_STABLE_READ_ATTEMPTS", 1)
    with pytest.raises(store.WarehouseChangedDuringRead) as caught:
        store.warehouse_identity()
    assert "changed while it was being hashed" in str(caught.value)
    assert db not in store._warehouse_identity_cache

def test_a_write_during_the_hash_is_retried_into_the_final_bytes(monkeypatch, tmp_path):
    db = tmp_path / "retried.bin"
    payload = b"r" * 65536
    db.write_bytes(payload)
    monkeypatch.setattr(store, "DB_PATH", db)
    store.warehouse_identity_cache_clear()
    stat = db.stat()
    real_digest = store._digest_descriptor
    torn = _torn_digest_for(db, payload, b"s", 20000, (stat.st_atime_ns, stat.st_mtime_ns))
    calls = []

    def once_then_real(descriptor):
        calls.append(1)
        return torn(descriptor) if len(calls) == 1 else real_digest(descriptor)

    monkeypatch.setattr(store, "_digest_descriptor", once_then_real)
    final = bytearray(payload)
    final[20000] = ord("s")
    identity = store.warehouse_identity()
    assert identity["warehouse_sha256"] == hashlib.sha256(bytes(final)).hexdigest()
    assert identity["warehouse_sha256"] != hashlib.sha256(payload).hexdigest()
    assert len(calls) == 2
    assert store.warehouse_identity() == identity

def test_identity_declines_to_cache_when_the_platform_has_no_change_token(monkeypatch, tmp_path):
    db = _point_db_at(monkeypatch, tmp_path)
    consumed = _hash_bytes_read(monkeypatch)
    monkeypatch.setattr(change_token, "change_token", lambda descriptor: None)
    first = store.warehouse_identity()
    second = store.warehouse_identity()
    assert first == second
    assert first["warehouse_sha256"] == hashlib.sha256(b"warehouse-bytes-v1").hexdigest()
    assert store._warehouse_identity_cache == {}
    assert consumed == [db.stat().st_size, db.stat().st_size]
    db.write_bytes(b"warehouse-bytes-v3")
    third = store.warehouse_identity()
    assert third["warehouse_sha256"] == hashlib.sha256(b"warehouse-bytes-v3").hexdigest()
    assert store._warehouse_identity_cache == {}

def test_change_token_advances_when_mtime_and_size_are_restored(tmp_path):
    db = tmp_path / "token.bin"
    db.write_bytes(b"t" * 8192)
    descriptor = os.open(db, os.O_RDONLY | getattr(os, "O_BINARY", 0))
    try:
        before = change_token.change_token(descriptor)
    finally:
        os.close(descriptor)
    assert isinstance(before, int)
    stat = db.stat()
    with open(db, "r+b") as handle:
        handle.seek(4096)
        handle.write(b"m")
    os.utime(db, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    descriptor = os.open(db, os.O_RDONLY | getattr(os, "O_BINARY", 0))
    try:
        after = change_token.change_token(descriptor)
    finally:
        os.close(descriptor)
    assert db.stat().st_mtime_ns == stat.st_mtime_ns
    assert db.stat().st_size == stat.st_size
    assert after != before

@pytest.mark.skipif(not change_token.WINDOWS,
                    reason="read invariance of the change token is asserted only "
                           "on the NTFS semantics measured by this lane")
def test_change_token_does_not_advance_when_the_file_is_only_read(tmp_path):
    db = tmp_path / "readonly.bin"
    db.write_bytes(b"t" * 8192)
    observed = []
    for _ in range(3):
        with open(db, "rb") as handle:
            handle.read()
        descriptor = os.open(db, os.O_RDONLY | getattr(os, "O_BINARY", 0))
        try:
            observed.append(change_token.change_token(descriptor))
        finally:
            os.close(descriptor)
    assert len(set(observed)) == 1

def test_freshness_key_changes_when_the_file_is_replaced_with_restored_mtime(tmp_path):
    db = tmp_path / "swapped.bin"
    replacement = tmp_path / "replacement.bin"
    db.write_bytes(b"A" * 20000)
    replacement.write_bytes(b"A" * 10000 + b"B" + b"A" * 9999)
    before = store._warehouse_freshness_key(db)
    stat = os.stat(db)
    os.replace(replacement, db)
    os.utime(db, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    after = store._warehouse_freshness_key(db)
    assert before is not None and after is not None
    assert db.stat().st_size == stat.st_size
    assert db.stat().st_mtime_ns == stat.st_mtime_ns
    assert before != after

def test_tables_cache_sees_a_replaced_warehouse_with_restored_mtime(tmp_path):
    import duckdb

    db = tmp_path / "rewrite.duckdb"
    first = duckdb.connect(str(db))
    first.execute("CREATE TABLE t1(x INTEGER)")
    first.close()
    store.warehouse_pool_clear()
    store.warehouse_tables_cache_clear()
    try:
        assert store.tables(db) == {"t1"}
        stat = os.stat(db)
        other = tmp_path / "other.duckdb"
        second = duckdb.connect(str(other))
        second.execute("CREATE TABLE t2(y VARCHAR)")
        second.close()
        os.replace(other, db)
        os.utime(db, ns=(stat.st_atime_ns, stat.st_mtime_ns))
        assert store.tables(db) == {"t2"}
    finally:
        store.warehouse_pool_clear()
        store.warehouse_tables_cache_clear()

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


def test_warehouse_vanishing_after_the_freshness_probe_raises_the_absent_error(monkeypatch, tmp_path):
    db = tmp_path / "vanish.duckdb"
    db.write_bytes(b"x" * 40000)
    monkeypatch.setattr(store, "DB_PATH", db)
    store.warehouse_identity_cache_clear()
    real_freshness_key = store._warehouse_freshness_key
    calls = []

    def once_probe_then_vanish(path, *args, **kwargs):
        calls.append(1)
        result = real_freshness_key(path)
        if len(calls) == 1:
            db.unlink()
        return result

    monkeypatch.setattr(store, "_warehouse_freshness_key", once_probe_then_vanish)
    with pytest.raises(FileNotFoundError) as caught:
        store.warehouse_identity()
    assert str(caught.value) == f"warehouse absent: {db}"
    assert store._warehouse_identity_cache == {}


def test_a_warehouse_replaced_between_probe_and_hash_is_never_cached_under_the_old_key(monkeypatch, tmp_path):
    db = tmp_path / "swapped.duckdb"
    original = b"o" * 20000
    replacement = tmp_path / "replacement.duckdb"
    db.write_bytes(original)
    monkeypatch.setattr(store, "DB_PATH", db)
    store.warehouse_identity_cache_clear()
    real_uncached = store._warehouse_identity_uncached

    def swap_then_hash(path):
        replacement.write_bytes(b"n" * len(original))
        os.replace(replacement, path)
        return real_uncached(path)

    monkeypatch.setattr(store, "_warehouse_identity_uncached", swap_then_hash)
    identity = store.warehouse_identity()
    assert identity["warehouse_sha256"] == hashlib.sha256(b"n" * len(original)).hexdigest()
    assert identity["warehouse_sha256"] != hashlib.sha256(original).hexdigest()
    assert store._warehouse_identity_cache == {}
    assert store.warehouse_identity() == identity


def test_reported_sha_is_the_whole_file_digest_for_every_size(tmp_path):
    for size in (0, 1, 8191, 8192, 8193, 24576, 32768, 65536):
        payload = bytes((index * 7 + 3) % 256 for index in range(size))
        db = tmp_path / f"whole-{size}.bin"
        db.write_bytes(payload)
        assert store._warehouse_full_file_hexdigest(db) == hashlib.sha256(payload).hexdigest()


def test_no_sampled_warehouse_probe_remains_in_the_store():
    assert not hasattr(store, "_warehouse_probe_hexdigest")
    assert "_warehouse_probe_hexdigest" not in Path(store.__file__).read_text(encoding="utf-8")


def test_whole_file_is_hashed_in_bounded_blocks_per_warehouse_state(monkeypatch, tmp_path):
    db = _point_db_at(monkeypatch, tmp_path)
    payload = bytes(range(256)) * 512
    db.write_bytes(payload)
    monkeypatch.setattr(store, "_FULL_FILE_READ_BYTES", 4096)
    consumed = _hash_bytes_read(monkeypatch)
    first = store.warehouse_identity()
    blocks_after_first = list(consumed)
    second = store.warehouse_identity()
    third = store.warehouse_identity()
    assert first == second == third
    assert first["warehouse_sha256"] == hashlib.sha256(payload).hexdigest()
    assert sum(blocks_after_first) == len(payload)
    assert consumed == blocks_after_first
    assert store._FULL_FILE_READ_BYTES <= 1 << 20
    assert db in store._warehouse_identity_cache


def test_derivation_contract_is_a_named_version():
    assert store.WAREHOUSE_SHA256_DERIVATION == "sha256-full-file"
    import inspect
    signature = inspect.signature(store._warehouse_identity_uncached)
    assert list(signature.parameters) == ["path"]
    assert "probe" not in inspect.getsource(store._warehouse_identity_uncached)
    assert "sample" not in inspect.getsource(store._warehouse_identity_uncached)


def test_manifest_records_the_derivation_version(monkeypatch, tmp_path):
    db = _point_db_at(monkeypatch, tmp_path)
    from v2.api import routes
    routes.runtime_warehouse_identity.cache_clear()
    try:
        recorded = routes.runtime_warehouse_identity()
        assert recorded["sha256_derivation"] == store.WAREHOUSE_SHA256_DERIVATION
        assert recorded["sha256"] == hashlib.sha256(b"warehouse-bytes-v1").hexdigest()
        routes.runtime_asset_manifest.cache_clear()
        manifest = routes.runtime_asset_manifest()
        assert dict(manifest.warehouse) == recorded
    finally:
        routes.runtime_warehouse_identity.cache_clear()
        routes.runtime_asset_manifest.cache_clear()


def test_manifest_recorded_under_another_derivation_is_rejected_as_incompatible(
        monkeypatch, tmp_path):
    import json
    from v2.api import routes
    db = _point_db_at(monkeypatch, tmp_path)
    routes.runtime_warehouse_identity.cache_clear()
    routes.runtime_asset_manifest.cache_clear()
    try:
        observed = routes.runtime_asset_manifest().as_dict()
    finally:
        routes.runtime_warehouse_identity.cache_clear()
        routes.runtime_asset_manifest.cache_clear()
    for recorded_derivation in (None, "sha256-sampled", "sha256-head-tail"):
        candidate = json.loads(json.dumps(observed))
        if recorded_derivation is None:
            del candidate["warehouse"]["sha256_derivation"]
        else:
            candidate["warehouse"]["sha256_derivation"] = recorded_derivation
        path = tmp_path / f"stale-derivation-{recorded_derivation}.json"
        path.write_text(json.dumps(candidate))
        with pytest.raises(RuntimeError, match="derivation"):
            routes.preflight_runtime_assets(path)


def test_absent_error_factory_is_single_sourced():
    source = Path(store.__file__).read_text(encoding="utf-8")
    assert source.count("f\"warehouse absent: {path}\"") == 1
    assert "f\"warehouse absent: {DB_PATH}\"" not in source
    factory_definition = "def _warehouse_absent_error(path: Path | str) -> FileNotFoundError:"
    assert factory_definition in source
    constructions = [line.strip() for line in source.splitlines()
                     if "FileNotFoundError(" in line]
    assert constructions == ["return FileNotFoundError(f\"warehouse absent: {path}\")"]
    assert source.count("raise _warehouse_absent_error(") == 2


def _point_db_at_absent(monkeypatch, tmp_path):
    db = tmp_path / "absent.duckdb"
    assert not db.exists()
    monkeypatch.setattr(store, "DB_PATH", db)
    monkeypatch.setattr(store, "STATE_PATH", tmp_path / "state.duckdb")
    monkeypatch.setattr(store, "STATE_LOCK_PATH", tmp_path / ".state.lock")
    store.warehouse_identity_cache_clear()
    return db