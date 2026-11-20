import os
from pathlib import Path

import duckdb

from .. import change_token
from .. import file_lock
from .chat_runs import (
    chat_history,
    compact_thread,
    list_runs,
    list_threads,
    save_chat,
    save_facts,
    save_run,
    thread_facts,
)
from .connections import (
    _CONNECT_BACKOFF_S,
    _CONNECT_RETRIES,
    _LOCK_ERRORS,
    _PooledConnection,
    _connect_once,
    _pool_acquire,
    _pool_drop,
    _pool_evict_all,
    _pool_lock,
    _pool_registry,
    _pool_state,
    _pool_store,
    connect,
    connect_to,
    read_connect,
    snapshot_warehouse,
    state_connect,
    state_write_guard,
    warehouse_pool_clear,
    write_guard,
)
from .queries import (
    _UNIT_DTYPE_SQL,
    _read_df,
    last_fetch,
    read_frame,
    read_frame_optional,
    save_frame,
    write_unit,
)
from .schema import (
    _FULL_FILE_READ_BYTES,
    _OPEN_READ_ONLY,
    _PLAYED_GAME_TABLE,
    _PRESEASON_GAME_ID_PREFIX,
    _SEASON_TABLES,
    _STABLE_READ_ATTEMPTS,
    TableAbsent,
    WarehouseChangedDuringRead,
    WriteConflictError,
    _connection_db_path,
    _descriptor_freshness,
    _descriptor_shape,
    _digest_descriptor,
    _identity_lock,
    _stable_full_file_hexdigest,
    _tables_cache,
    _tables_lock,
    _tables_uncached,
    _warehouse_absent_error,
    _warehouse_freshness_key,
    _warehouse_full_file_hexdigest,
    _warehouse_identity_cache,
    _warehouse_identity_uncached,
    completed_seasons_across_tables,
    seasons_with_data,
    tables,
    warehouse_identity,
    warehouse_identity_cache_clear,
    warehouse_tables_cache_clear,
)

DB_PATH = Path(
    os.environ.get("DIME_WAREHOUSE")
    or (Path(__file__).resolve().parent.parent.parent / "data" / "warehouse.duckdb")
)
LOCK_PATH = DB_PATH.parent / ".write.lock"
CANONICAL_DB_PATH = (
    Path(__file__).resolve().parent.parent.parent / "data" / "warehouse.duckdb"
).resolve()
STATE_PATH = Path(
    os.environ.get("DIME_STATE_DB")
    or (Path(__file__).resolve().parent.parent.parent / "data" / "state.duckdb")
)
STATE_LOCK_PATH = STATE_PATH.parent / ".state-write.lock"

PROVENANCE_COLS = ["_source", "_season", "_fetched_at"]
WAREHOUSE_SHA256_DERIVATION = "sha256-full-file"
