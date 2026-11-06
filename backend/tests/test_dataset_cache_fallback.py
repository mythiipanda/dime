import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import duckdb
import polars as pl
import pytest

from analyst import dataset_engine
from shared.sources.base import FetchMeta, FetchResult

_TABLE = "silver_player_gamelogs"


def _bridge_read_frame(con):
    def read_frame(table, where="", params=None):
        cursor = con.execute(
            f"SELECT * FROM {table}" + (f" WHERE {where}" if where else ""),
            list(params or []),
        )
        rows = cursor.fetchall()
        columns = [d[0] for d in cursor.description]
        if not rows:
            return pl.DataFrame({name: [] for name in columns})
        return pl.DataFrame(
            {name: [row[i] for row in rows] for i, name in enumerate(columns)}
        )

    return read_frame


@pytest.fixture
def seeded(monkeypatch):
    import types

    con = duckdb.connect(":memory:")
    con.execute(
        f"CREATE TABLE {_TABLE} (PLAYER_NAME VARCHAR, PTS INTEGER, "
        "GAME_DATE VARCHAR, _source VARCHAR, _season VARCHAR, "
        "_fetched_at VARCHAR, _entity VARCHAR)"
    )
    store_stub = types.SimpleNamespace(read_frame=_bridge_read_frame(con))
    shared_stub = types.ModuleType("shared")
    shared_stub.store = store_stub
    monkeypatch.setitem(sys.modules, "shared", shared_stub)
    yield con
    con.close()


def _seed(con, name, pts, season, entity, source="synthetic-cache"):
    con.execute(
        f"INSERT INTO {_TABLE} VALUES (?, ?, ?, ?, ?, ?, ?)",
        [name, pts, "Oct 01, 2024", source, season, "2026-11-06T00:00:00+00:00", entity],
    )


def _failed_live(season="2025-26"):
    return FetchResult(
        frame=pl.DataFrame(),
        meta=FetchMeta(source="synthetic-live", season=season),
        ok=False,
        error="synthetic upstream down",
    )


def test_prior_season_only_rejected_via_dataset(seeded, monkeypatch):
    _seed(seeded, "Prior", 111, "2024-25", "player:999")
    monkeypatch.setattr(
        dataset_engine,
        "_datasets_fetch_live",
        lambda *args, **kwargs: _failed_live(),
    )
    out = dataset_engine.dataset(
        "player_gamelogs", season="2025-26", player_id=999
    )
    assert out["ok"] is False
    assert out["error"] == "synthetic upstream down"
    assert out["source"] == "synthetic-live"
    assert "no cached rows" in out["detail"]
    assert "data" not in out


def test_mixed_season_selects_requested_only(seeded):
    _seed(seeded, "Prior", 111, "2024-25", "player:999", source="prior-source")
    _seed(seeded, "Current", 222, "2025-26", "player:999", source="current-source")
    out = dataset_engine._failed_live_response(
        _failed_live(), True, "player:999", _TABLE, "2025-26"
    )
    assert out["ok"] is True
    assert out["meta"]["stale"] is True
    assert out["meta"]["season"] == "2025-26"
    assert out["meta"]["source"] == "current-source"
    assert [r["PTS"] for r in out["data"]] == [222]
    assert [r["_season"] for r in out["data"]] == ["2025-26"]


def test_entity_isolation(seeded):
    _seed(seeded, "Other", 33, "2025-26", "player:888")
    out = dataset_engine._failed_live_response(
        _failed_live(), True, "player:999", _TABLE, "2025-26"
    )
    assert out["ok"] is False
    assert out["error"] == "synthetic upstream down"


def test_same_season_fallback_succeeds_with_stale_meta(seeded):
    _seed(seeded, "Current", 222, "2025-26", "player:999", source="current-source")
    out = dataset_engine._failed_live_response(
        _failed_live(), True, "player:999", _TABLE, "2025-26"
    )
    assert out["ok"] is True
    assert out["meta"] == {
        "season": "2025-26",
        "rows": 1,
        "cached": True,
        "source": "current-source",
        "fetched_at": "2026-11-06T00:00:00+00:00",
        "stale": True,
        "live_error": "synthetic upstream down",
        "live_source": "synthetic-live",
    }
    assert [r["PTS"] for r in out["data"]] == [222]


def test_empty_cache_fails(seeded):
    out = dataset_engine._failed_live_response(
        _failed_live(), True, "player:999", _TABLE, "2025-26"
    )
    assert out["ok"] is False
    assert out["error"] == "synthetic upstream down"
    assert out["source"] == "synthetic-live"
    assert "no cached rows" in out["detail"]
