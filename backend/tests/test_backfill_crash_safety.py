import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import polars as pl
import pytest

from shared import store


@pytest.fixture
def scratch(monkeypatch, tmp_path):
    db = tmp_path / "crash.duckdb"
    monkeypatch.setattr(store, "DB_PATH", db)
    monkeypatch.setattr(store, "LOCK_PATH", tmp_path / ".write.lock")
    return db


def _unit(game_id, pts):
    return pl.DataFrame([{"GAME_ID": game_id, "PTS": pts}])


def _rows(table, game_id):
    con = store.connect(read_only=True)
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        if table not in tables:
            return []
        return con.execute(
            f"SELECT PTS FROM {table} WHERE GAME_ID = ?", [game_id]
        ).fetchall()
    finally:
        con.close()


def _write(game_id, pts, **kw):
    return store.write_unit(
        "silver_crash", _unit(game_id, pts), season="2024-25", source="t",
        entity=game_id, delete_where="GAME_ID = ?", delete_params=[game_id],
        **kw,
    )


def test_crash_after_delete_keeps_old_data_no_false_watermark(scratch):
    _write("G1", 10)
    assert store.last_fetch("silver_crash", "2024-25", "G1")
    with pytest.raises(RuntimeError, match="simulated crash"):
        _write("G1", 99, _fault="after_delete")

    assert _rows("silver_crash", "G1") == [(10,)]

    assert store.last_fetch("silver_crash", "2024-25", "G1")


def test_crash_after_insert_leaves_no_watermark(scratch):
    with pytest.raises(RuntimeError, match="simulated crash"):
        _write("G2", 5, _fault="after_insert")
    assert _rows("silver_crash", "G2") == []

    assert not store.last_fetch("silver_crash", "2024-25", "G2")


def test_rerun_after_crash_completes_cleanly(scratch):
    with pytest.raises(RuntimeError, match="simulated crash"):
        _write("G3", 7, _fault="after_insert")
    n = _write("G3", 7)
    assert n == 1
    assert _rows("silver_crash", "G3") == [(7,)]
    assert store.last_fetch("silver_crash", "2024-25", "G3")

    _write("G3", 7)
    assert _rows("silver_crash", "G3") == [(7,)]


def test_save_frame_is_atomic(scratch):
    from shared.sources.base import FetchResult, FetchMeta

    meta = FetchMeta(source="t", season="2024-25",
                     fetched_at="2026-01-01T00:00:00")
    res = FetchResult(frame=_unit("G4", 3), meta=meta)
    store.save_frame("silver_crash2", res, entity="G4")
    assert store.last_fetch("silver_crash2", "2024-25", "G4")
