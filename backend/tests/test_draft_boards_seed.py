import sys
from pathlib import Path

import duckdb
import polars as pl
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts import seed_draft_boards as sdb
from shared import store
from shared.sources.base import FetchMeta, FetchResult


@pytest.fixture()
def scratch(tmp_path):
    db = tmp_path / "wh.duckdb"
    old_db, old_lock = store.DB_PATH, store.LOCK_PATH
    store.DB_PATH = db
    store.LOCK_PATH = tmp_path / ".write.lock"
    store.warehouse_tables_cache_clear()
    store.warehouse_pool_clear()
    yield db
    store.DB_PATH, store.LOCK_PATH = old_db, old_lock
    store.warehouse_tables_cache_clear()
    store.warehouse_pool_clear()


def _frame(board, names):
    return pl.DataFrame({
        "RANK" if board == "big_board" else "PICK": list(range(1, len(names) + 1)),
        "PLAYER_NAME": names,
        "PLAYER_SLUG": [n.lower().replace(" ", "-") for n in names],
        "POSITION": ["G"] * len(names),
        "SCHOOL": ["Duke"] * len(names),
        "TEAM_ABBREVIATION": [""] * len(names),
        "HEIGHT": ["6-5"] * len(names),
        "WEIGHT_LBS": [200] * len(names),
        "CLASS_YEAR": ["Fr"] * len(names),
        "AGE": [18.5] * len(names),
        "BOARD": [board] * len(names),
    })


def _result(frame, season="2027"):
    return FetchResult(frame=frame, meta=FetchMeta(source="tankathon", season=season))


def _seed_both(monkeypatch, big_names, mock_names):
    monkeypatch.setattr(sdb._tk, "big_board", lambda: _result(_frame("big_board", big_names)))
    monkeypatch.setattr(sdb._tk, "mock_draft", lambda: _result(_frame("mock_draft", mock_names)))
    assert sdb.main() == 0


def test_boards_seed_distinct_shapes_without_intra_board_dupes(scratch, monkeypatch):
    shared = ["Alpha One", "Beta Two", "Gamma Three"]
    _seed_both(monkeypatch, shared + ["Delta Four"], shared)
    con = duckdb.connect(str(scratch), read_only=True)
    try:
        for board, expected in (("big_board", 4), ("mock_draft", 3)):
            rows = con.execute(
                "SELECT COUNT(*), COUNT(DISTINCT PLAYER_NAME) FROM silver_draft_boards WHERE BOARD = ?",
                [board]).fetchone()
            assert rows[0] == expected
            assert rows[0] == rows[1], f"{board} carries duplicate player names"
        overlap = con.execute(
            """SELECT COUNT(*) FROM silver_draft_boards a
               JOIN silver_draft_boards b
               ON a.PLAYER_NAME = b.PLAYER_NAME AND a.BOARD = 'big_board' AND b.BOARD = 'mock_draft'""").fetchone()[0]
        assert overlap == 3
    finally:
        con.close()


def test_reseed_replaces_instead_of_doubling(scratch, monkeypatch):
    names = ["Alpha One", "Beta Two"]
    _seed_both(monkeypatch, names, names)
    _seed_both(monkeypatch, names, names)
    con = duckdb.connect(str(scratch), read_only=True)
    try:
        total = con.execute("SELECT COUNT(*) FROM silver_draft_boards").fetchone()[0]
        assert total == 4
    finally:
        con.close()
