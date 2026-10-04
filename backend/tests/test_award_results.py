import json
import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "nba_awards"

PLAYER_IDS = (2544, 203497, 2037, 203506, 201566)


def _payload(player_id: int) -> dict:
    return json.loads(
        (FIXTURES / f"player_awards_{player_id}.json").read_text(
            encoding="utf-8"))


@pytest.fixture(scope="module")
def recorded_awards(tmp_path_factory):
    import seed_nba_awards as seed
    from shared import store
    from shared.sources import nba_awards as src

    root = tmp_path_factory.mktemp("recorded_awards")
    recorded = root / "recorded.duckdb"
    original = (store.DB_PATH, store.LOCK_PATH)
    store.DB_PATH = recorded
    store.LOCK_PATH = root / ".write.lock"
    try:
        for player_id in PLAYER_IDS:
            frame = src.parse_player_awards(_payload(player_id))
            seed.save_player_rows(player_id, frame)
    finally:
        store.DB_PATH, store.LOCK_PATH = original
    return recorded


def _point_at(path: Path, tmp_path: Path, monkeypatch) -> Path:
    from shared import store
    from shared.tools import _core
    from v2.adapters import coverage

    monkeypatch.setattr(store, "DB_PATH", path)
    monkeypatch.setattr(store, "LOCK_PATH", tmp_path / ".write.lock")
    store.warehouse_tables_cache_clear()
    store.warehouse_pool_clear()
    _core.last_completed_season_cache_clear()
    coverage.coverage_cache_clear()
    return path


@pytest.fixture
def awards_warehouse(recorded_awards, tmp_path, monkeypatch):
    path = tmp_path / "awards.duckdb"
    shutil.copyfile(recorded_awards, path)
    return _point_at(path, tmp_path, monkeypatch)


@pytest.fixture
def empty_warehouse(tmp_path, monkeypatch):
    import duckdb

    path = tmp_path / "empty.duckdb"
    duckdb.connect(str(path)).close()
    return _point_at(path, tmp_path, monkeypatch)


def _results(**arguments):
    from shared.tools.award_results import get_award_results

    return get_award_results.invoke(arguments)


def test_a_real_season_returns_the_recorded_winner(awards_warehouse):
    result = _results(view="winner", award="MVP", season="2008-09")
    assert result["ok"] is True, result
    assert result["rows"]["placements"] == [{
        "season": "2008-09",
        "award": "MVP",
        "player": "LeBron James",
        "coach": None,
        "team": "Cleveland Cavaliers",
        "age": None,
        "rank": 1,
        "rank_label": "1",
        "tied": False,
        "award_share": None,
        "points_won": None,
        "points_max": None,
        "votes_first": None,
        "votes_second": None,
        "votes_third": None,
    }]


def test_winners_cover_every_mapped_award(awards_warehouse):
    for award, season, player in (
        ("DPOY", "2023-24", "Rudy Gobert"),
        ("ROY", "2003-04", "LeBron James"),
        ("6MOY", "2015-16", "Jamal Crawford"),
        ("MIP", "2017-18", "Victor Oladipo"),
    ):
        result = _results(view="winner", award=award, season=season)
        assert result["ok"] is True, (award, result)
        assert result["rows"]["placements"][0]["player"] == player


def test_the_result_declares_itself_a_recorded_outcome_not_a_projection(
        awards_warehouse):
    result = _results(view="winner", award="MVP", season="2008-09")
    meta = result["meta"]
    assert meta["dataset"] == "nba_api"
    assert meta["result_type"] == "official_award_result"
    assert meta["model_projection"] is False
    assert meta["ballot"] is False
    assert "nba_api" in meta["method"]


def test_the_field_view_fails_loud_without_ballot_detail(awards_warehouse):
    result = _results(view="field", award="MVP", season="2008-09")
    assert result["ok"] is False
    assert "ballot" in result["error"]
    assert "winners only" in result["error"]


def test_a_coach_award_fails_loud_without_a_player_source(awards_warehouse):
    result = _results(view="winner", award="COY", season="2008-09")
    assert result["ok"] is False
    assert "players only" in result["error"]


def test_a_player_name_no_winner_row_carries_is_an_honest_absence(
        awards_warehouse):
    result = _results(view="player_awards", season="2023-24",
                      player="Ada Vega")
    assert result["ok"] is False
    assert "Ada Vega" in result["error"]


def test_a_player_history_covers_every_season_they_won(awards_warehouse):
    result = _results(view="player_awards", season="2023-24",
                      player="LeBron James")
    assert result["ok"] is True, result
    seasons = sorted({row["season"]
                      for row in result["rows"]["placements"]})
    assert seasons[0] == "2003-04"
    assert "2008-09" in seasons


def test_a_player_history_narrows_to_one_award_when_asked(awards_warehouse):
    result = _results(view="player_awards", season="2023-24",
                      player="LeBron James", award="MVP")
    assert result["ok"] is True, result
    assert {row["award"] for row in result["rows"]["placements"]} == {"MVP"}
    assert len(result["rows"]["placements"]) == 4


def test_a_season_with_no_winners_fails_naming_the_season(awards_warehouse):
    result = _results(view="winner", award="MVP", season="1990-91")
    assert result["ok"] is False
    assert "1990-91" in result["error"]


def test_a_missing_awards_table_fails_naming_the_table(empty_warehouse):
    from shared.tools.award_results import TABLE

    result = _results(view="winner", award="MVP", season="2008-09")
    assert result["ok"] is False
    assert TABLE in result["error"]


def test_an_award_surface_form_normalizes_to_its_recorded_code(
        awards_warehouse):
    result = _results(view="winner", award="most valuable player",
                      season="2008-09")
    assert result["ok"] is True, result
    assert result["meta"]["award"] == "MVP"


def test_an_unrecognized_award_fails_naming_the_recorded_codes(
        awards_warehouse):
    result = _results(view="winner", award="Hank Award", season="2008-09")
    assert result["ok"] is False
    assert "MVP" in result["error"]


def test_the_typed_boundary_rejects_a_view_it_does_not_publish(
        awards_warehouse):
    with pytest.raises(Exception):
        _results(view="race", award="MVP", season="2008-09")


def test_a_view_that_needs_an_award_says_so(awards_warehouse):
    result = _results(view="winner", season="2008-09")
    assert result["ok"] is False
    assert "award" in result["error"]


def test_a_player_view_without_a_player_says_so(awards_warehouse):
    result = _results(view="player_awards", season="2008-09")
    assert result["ok"] is False
    assert "player" in result["error"]


def test_a_player_argument_on_an_award_view_fails_loudly(awards_warehouse):
    result = _results(view="winner", award="MVP", season="2008-09",
                      player="LeBron James")
    assert result["ok"] is False


def test_every_recorded_award_normalizes_from_its_surface_forms():
    from shared.tools.award_results import AWARDS, normalize_award

    assert set(AWARDS) == {
        "MVP", "DPOY", "ROY", "6MOY", "MIP", "COY", "ALL_NBA", "ALL_DEFENSE",
        "ALL_ROOKIE"}
    for surface, code in (
        ("mvp", "MVP"),
        ("Most Valuable Player", "MVP"),
        ("dpoy", "DPOY"),
        ("defensive player of the year", "DPOY"),
        ("rookie of the year", "ROY"),
        ("6MOY", "6MOY"),
        ("Sixth Man of the Year", "6MOY"),
        ("most improved", "MIP"),
        ("Coach of the Year", "COY"),
        ("all-nba", "ALL_NBA"),
        ("All NBA Team", "ALL_NBA"),
        ("all defensive team", "ALL_DEFENSE"),
        ("All-Rookie Team", "ALL_ROOKIE"),
    ):
        assert normalize_award(surface) == code, surface
    assert normalize_award("Hank Award") is None
    assert normalize_award(None) is None


def test_the_projection_registry_and_the_result_registry_agree_on_every_code():
    from shared.tools.award_results import AWARDS
    from shared.tools.awards import PROJECTION_SPECS

    assert set(PROJECTION_SPECS) <= set(AWARDS)
    assert all(AWARDS[code]["projectable"] for code in PROJECTION_SPECS)
    assert not any(AWARDS[code]["projectable"] for code in set(AWARDS)
                   - set(PROJECTION_SPECS))


def test_an_omitted_season_resolves_to_the_latest_recorded_season(
        awards_warehouse):
    result = _results(view="winner", award="ALL_DEFENSE")
    assert result["ok"] is True, result
    assert result["meta"]["season"] == "2025-26"
    assert result["rows"]["placements"][0]["player"] == "Rudy Gobert"


def test_a_player_name_matches_case_insensitively(awards_warehouse):
    loud = _results(view="player_awards", season="2023-24",
                    player="LeBron James")
    quiet = _results(view="player_awards", season="2023-24",
                     player="lebron james")
    assert loud["ok"] is quiet["ok"] is True
    assert (len(loud["rows"]["placements"]) ==
            len(quiet["rows"]["placements"]) > 0)
