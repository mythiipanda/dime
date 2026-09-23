"""Latest-data-season derivation (MUSE-1 redo).

Synthetic warehouse only: seeded in tmp_path and pointed at via monkeypatch.
No provider keys, no network.
"""

import sys
from pathlib import Path

import duckdb
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import store  # noqa: E402
from app import subagents  # noqa: E402


def _rows(seasons: list[str], preseason: bool = False) -> list[tuple[str, str]]:
    """(game_id, season) rows; preseason rows use the 001 game-id prefix."""
    prefix = "001" if preseason else "002"
    out = []
    for si, season in enumerate(seasons):
        for gi in range(3):
            out.append((f"{prefix}25{si:02d}{gi:04d}", season))
    return out


def _seed_warehouse(path: Path, rows: list[tuple[str, str]]) -> None:
    con = duckdb.connect(str(path))
    con.execute(
        "CREATE TABLE silver_boxscores ("
        "GAME_ID VARCHAR, _season VARCHAR, _source VARCHAR, _fetched_at VARCHAR)"
    )
    for game_id, season in rows:
        con.execute(
            "INSERT INTO silver_boxscores VALUES (?, ?, 'seed', 'now')",
            [game_id, season],
        )
    con.close()


@pytest.fixture
def warehouse_store(tmp_path, monkeypatch):
    db = tmp_path / "warehouse.duckdb"
    _seed_warehouse(db, _rows(["2024-25", "2025-26", "2024-25"]))
    monkeypatch.setattr(store, "DB_PATH", db)
    subagents._SEASON_CACHE.clear()
    yield db
    subagents._SEASON_CACHE.clear()


def test_seasons_with_data_derived_from_warehouse(warehouse_store):
    assert store.seasons_with_data() == ["2024-25", "2025-26"]


def test_latest_data_season_is_max_with_played_games(warehouse_store):
    assert store.latest_data_season() == "2025-26"


def test_latest_data_season_rolls_forward_to_new_season(tmp_path, monkeypatch):
    """A warehouse holding 2026-27 played-game data must resolve to 2026-27."""
    db = tmp_path / "warehouse.duckdb"
    _seed_warehouse(db, _rows(["2024-25", "2025-26"]) + _rows(["2026-27"]))
    monkeypatch.setattr(store, "DB_PATH", db)
    assert store.seasons_with_data() == ["2024-25", "2025-26", "2026-27"]
    assert store.latest_data_season() == "2026-27"


def test_preseason_only_season_is_not_promoted(tmp_path, monkeypatch):
    """Preseason-only 2026-27 rows must not promote 2026-27 to latest."""
    db = tmp_path / "warehouse.duckdb"
    _seed_warehouse(
        db, _rows(["2024-25", "2025-26"]) + _rows(["2026-27"], preseason=True)
    )
    monkeypatch.setattr(store, "DB_PATH", db)
    assert store.seasons_with_data() == ["2024-25", "2025-26"]
    assert store.latest_data_season() == "2025-26"


def test_latest_data_season_empty_warehouse_raises(tmp_path, monkeypatch):
    db = tmp_path / "warehouse.duckdb"
    _seed_warehouse(db, [])
    monkeypatch.setattr(store, "DB_PATH", db)
    with pytest.raises(ValueError, match="no played-game rows"):
        store.latest_data_season()


def test_data_season_resolves_from_warehouse(warehouse_store):
    assert subagents.data_season() == "2025-26"


def test_data_season_falls_back_with_warning(tmp_path, monkeypatch, caplog):
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "missing.duckdb")
    subagents._SEASON_CACHE.clear()
    try:
        with caplog.at_level("WARNING", logger="app.subagents"):
            assert subagents.data_season() == subagents.SEASON
        assert "falling back" in caplog.text
    finally:
        subagents._SEASON_CACHE.clear()


def test_desk_briefs_carry_derived_season_through_channel(warehouse_store):
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


def test_planner_season_context_states_warehouse_fact(warehouse_store):
    from app.graph import _planner_season_context
    ctx = _planner_season_context()
    assert ("Latest season with played-game data in the warehouse: 2025-26."
            in ctx)
    assert "Use it for this/current season" in ctx
    # 'last season' must not be collapsed into the derived season here.
    assert "last season" not in ctx


def test_planner_season_context_follows_roll_forward(tmp_path, monkeypatch):
    from app.graph import _planner_season_context
    db = tmp_path / "warehouse.duckdb"
    _seed_warehouse(db, _rows(["2025-26"]) + _rows(["2026-27"]))
    monkeypatch.setattr(store, "DB_PATH", db)
    subagents._SEASON_CACHE.clear()
    try:
        ctx = _planner_season_context()
        assert ("Latest season with played-game data in the warehouse: 2026-27."
                in ctx)
    finally:
        subagents._SEASON_CACHE.clear()
