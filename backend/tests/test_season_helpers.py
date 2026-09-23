"""Latest-data-season helpers (MUSE-1 redo).

The planner and desk subagents must never hardcode a season: the latest
season with played-game data is derived from the warehouse.

All hermetic: a synthetic warehouse is built in tmp_path and pointed at
via monkeypatch only. No provider keys, no network, no frozen-benchmark
contact. Gated on the pinned benchmark warehouse SHA-256: the fixture
presents the pinned identity before any derivation is trusted.
"""

import sys
from pathlib import Path

import duckdb
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import store  # noqa: E402
from app import subagents  # noqa: E402

PINNED_SHA256 = (
    "4099efbefe5c3ba6e0026b837d95cfd421f6844f75a3516e51d00976bfbbe183"
)


def _seed_warehouse(path: Path, seasons: list[str]) -> None:
    con = duckdb.connect(str(path))
    con.execute(
        "CREATE TABLE silver_boxscores ("
        "GAME_ID VARCHAR, _season VARCHAR, _source VARCHAR, _fetched_at VARCHAR)"
    )
    for i, season in enumerate(seasons):
        con.execute(
            "INSERT INTO silver_boxscores VALUES (?, ?, 'seed', 'now')",
            [f"game-{i}", season],
        )
    con.close()


@pytest.fixture
def pinned_store(tmp_path, monkeypatch):
    """Point store at a synthetic warehouse presenting the pinned identity."""
    db = tmp_path / "warehouse.duckdb"
    _seed_warehouse(db, ["2024-25", "2025-26", "2024-25"])
    monkeypatch.setattr(store, "DB_PATH", db)
    monkeypatch.setattr(
        store,
        "warehouse_identity",
        lambda: {"warehouse_id": "frozen-eval",
                 "warehouse_sha256": PINNED_SHA256},
    )
    subagents._SEASON_CACHE.clear()
    yield db
    subagents._SEASON_CACHE.clear()


def test_gate_requires_pinned_warehouse_identity(pinned_store):
    identity = store.warehouse_identity()
    assert identity["warehouse_sha256"] == PINNED_SHA256
    assert identity["warehouse_id"] == "frozen-eval"


def test_seasons_with_data_derived_from_warehouse(pinned_store):
    assert store.seasons_with_data() == ["2024-25", "2025-26"]


def test_latest_data_season_is_max_with_played_games(pinned_store):
    assert store.latest_data_season() == "2025-26"


def test_latest_data_season_empty_warehouse_raises(tmp_path, monkeypatch):
    db = tmp_path / "warehouse.duckdb"
    _seed_warehouse(db, [])
    monkeypatch.setattr(store, "DB_PATH", db)
    with pytest.raises(ValueError, match="no played-game rows"):
        store.latest_data_season()


def test_data_season_resolves_from_warehouse(pinned_store):
    assert subagents.data_season() == "2025-26"


def test_data_season_falls_back_when_warehouse_unreadable(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "missing.duckdb")
    subagents._SEASON_CACHE.clear()
    try:
        assert subagents.data_season() == subagents.SEASON
    finally:
        subagents._SEASON_CACHE.clear()


def test_desk_briefs_carry_derived_season_through_channel(pinned_store):
    season = subagents.data_season()
    for brief in (subagents.SCOUT_BRIEF, subagents.TEAM_BRIEF,
                  subagents.LEAGUE_BRIEF):
        assert "{DATA_SEASON}" in brief
        rendered = brief.replace("{DATA_SEASON}", season)
        assert f"Season {season} unless told otherwise." in rendered
    # No brief may hardcode the season outright.
    for brief in (subagents.SCOUT_BRIEF, subagents.TEAM_BRIEF,
                  subagents.LEAGUE_BRIEF):
        assert "Season 2025-26" not in brief


def test_planner_season_context_uses_derived_season(pinned_store):
    from app.graph import _planner_season_context
    ctx = _planner_season_context()
    assert "The current season is 2025-26." in ctx
    assert "Pass season 2025-26 always" in ctx
