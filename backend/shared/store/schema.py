import hashlib
import os
import sys
import threading
from pathlib import Path

import duckdb


def _pkg():
    return sys.modules[__package__]


class WarehouseChangedDuringRead(RuntimeError):
    pass


def _warehouse_absent_error(path: Path | str) -> FileNotFoundError:
    return FileNotFoundError(f"warehouse absent: {path}")


_FULL_FILE_READ_BYTES = 1 << 20
_STABLE_READ_ATTEMPTS = 3
_OPEN_READ_ONLY = os.O_RDONLY | getattr(os, "O_BINARY", 0)


def _descriptor_shape(descriptor: int) -> tuple[int, int, int, int] | None:
    try:
        st = os.fstat(descriptor)
    except OSError:
        return None
    return (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns)


def _descriptor_freshness(descriptor: int) -> tuple[int, int, int, int, int] | None:
    pkg = _pkg()
    shape = pkg._descriptor_shape(descriptor)
    if shape is None:
        return None
    token = pkg.change_token.change_token(descriptor)
    if token is None:
        return None
    return shape + (token,)


def _warehouse_freshness_key(path: Path | str) -> tuple[int, int, int, int, int] | None:
    try:
        descriptor = os.open(path, _OPEN_READ_ONLY)
    except OSError:
        return None
    try:
        return _pkg()._descriptor_freshness(descriptor)
    finally:
        os.close(descriptor)


def _digest_descriptor(descriptor: int) -> str:
    pkg = _pkg()
    digest = hashlib.sha256()
    os.lseek(descriptor, 0, os.SEEK_SET)
    while True:
        block = os.read(descriptor, pkg._FULL_FILE_READ_BYTES)
        if not block:
            return digest.hexdigest()
        digest.update(block)


def _stable_full_file_hexdigest(
    path: Path,
) -> tuple[str, tuple[int, int, int, int, int] | None]:
    pkg = _pkg()
    unstable: tuple | None = None
    for _ in range(_STABLE_READ_ATTEMPTS):
        try:
            descriptor = os.open(path, _OPEN_READ_ONLY)
        except FileNotFoundError:
            raise pkg._warehouse_absent_error(path) from None
        try:
            opened_shape = pkg._descriptor_shape(descriptor)
            opened = pkg._descriptor_freshness(descriptor)
            digest = pkg._digest_descriptor(descriptor)
            closed_shape = pkg._descriptor_shape(descriptor)
            closed = pkg._descriptor_freshness(descriptor)
            if opened_shape == closed_shape and opened == closed:
                return digest, opened
        finally:
            os.close(descriptor)
        unstable = (opened_shape, closed_shape, opened, closed)
    raise WarehouseChangedDuringRead(
        f"warehouse {path} changed while it was being hashed; refusing to report "
        f"an identity for bytes that never coexisted (last shapes {unstable!r})"
    )


def _warehouse_identity_uncached(path: Path) -> dict[str, str]:
    pkg = _pkg()
    digest, _ = pkg._stable_full_file_hexdigest(path)
    return {
        "warehouse_id": "frozen-eval" if path == pkg.CANONICAL_DB_PATH else "configured-runtime",
        "warehouse_sha256": digest,
    }


_warehouse_identity_cache: dict[Path, tuple[tuple[int, int, int, int, int], dict[str, str]]] = {}
_identity_lock = threading.RLock()


def warehouse_identity_cache_clear() -> None:
    with _identity_lock:
        _warehouse_identity_cache.clear()


def _warehouse_full_file_hexdigest(path: Path) -> str:
    return _pkg()._stable_full_file_hexdigest(path)[0]


def warehouse_identity() -> dict[str, str]:
    pkg = _pkg()
    path = Path(pkg.DB_PATH).resolve()
    freshness = pkg._warehouse_freshness_key(path)
    if freshness is None:
        return pkg._warehouse_identity_uncached(path)
    with _identity_lock:
        entry = _warehouse_identity_cache.get(path)
        if entry is not None and entry[0] == freshness:
            return entry[1]
    identity = pkg._warehouse_identity_uncached(path)
    with _identity_lock:
        if pkg._warehouse_freshness_key(path) == freshness:
            _warehouse_identity_cache[path] = (freshness, identity)
    return identity


_tables_cache: dict[Path, tuple[tuple[int, int, int, int, int], frozenset[str]]] = {}
_tables_lock = threading.RLock()


def warehouse_tables_cache_clear() -> None:
    with _tables_lock:
        _tables_cache.clear()


class WriteConflictError(TimeoutError):
    def __init__(self, warehouse: Path | str) -> None:
        self.warehouse = str(warehouse)
        super().__init__(
            f"warehouse write for {Path(self.warehouse).name} refused: "
            f"another writer holds it; serialize writes through write_guard"
        )


def _connection_db_path(con) -> Path | None:
    try:
        rows = con.execute("PRAGMA database_list").fetchall()
    except Exception:
        return None
    try:
        for row in rows:
            file = row[2] if len(row) > 2 else None
            if file:
                return Path(str(file))
        return None
    except Exception:
        return None


def _tables_uncached(path: Path) -> tuple[frozenset[str], Path | None]:
    pkg = _pkg()
    if path == Path(pkg.DB_PATH).resolve():
        con = pkg.read_connect()
    else:
        con = pkg.duckdb.connect(str(path), read_only=True)
    try:
        names = frozenset(r[0] for r in con.execute("SHOW TABLES").fetchall())
        return names, _connection_db_path(con)
    finally:
        try:
            con.close()
        except Exception:
            pass


def tables(path: Path | str | None = None) -> set[str]:
    pkg = _pkg()
    key = Path(pkg.DB_PATH) if path is None else Path(path)
    freshness = pkg._warehouse_freshness_key(key)
    with _tables_lock:
        entry = _tables_cache.get(key)
        if freshness is not None and entry is not None and entry[0] == freshness:
            return set(entry[1])
    names, source = pkg._tables_uncached(key)
    with _tables_lock:
        if freshness is not None:
            try:
                matches = source is not None and source.resolve() == key.resolve()
            except OSError:
                matches = False
            if matches:
                _tables_cache[key] = (freshness, names)
        return set(names)


_PLAYED_GAME_TABLE = "silver_hist_gamelogs"
_SEASON_TABLES = (
    _PLAYED_GAME_TABLE,
    "silver_boxscores",
    "silver_team_games",
    "silver_player_gamelogs",
)
_PRESEASON_GAME_ID_PREFIX = "001"


def seasons_with_data(table: str = _PLAYED_GAME_TABLE) -> list[str]:
    con = _pkg().read_connect()
    try:
        rows = con.execute(
            f"SELECT DISTINCT _season FROM {table} "
            f"WHERE GAME_ID NOT LIKE '{_PRESEASON_GAME_ID_PREFIX}%' "
            "ORDER BY _season"
        ).fetchall()
    finally:
        con.close()
    return [r[0] for r in rows if r and r[0]]


def completed_seasons_across_tables() -> list[str]:
    found: set[str] = set()
    for table in _SEASON_TABLES:
        try:
            found.update(seasons_with_data(table))
        except Exception:
            continue
    return sorted(found)


class TableAbsent(LookupError):
    def __init__(self, table: str, warehouse: Path | str) -> None:
        self.table = str(table)
        self.warehouse = str(warehouse)
        super().__init__(
            f"warehouse table {self.table!r} is absent from "
            f"{Path(self.warehouse).name}; an empty read here would be "
            f"indistinguishable from a table that holds no matching rows"
        )
