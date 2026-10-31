import json
import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

FIXTURES = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "bbref_awards"

RECORDED = (
    (1977, "1976-77"),
    (1998, "1997-98"),
    (2015, "2014-15"),
    (2024, "2023-24"),
    (2026, "2025-26"),
)

def _page(year: int):
    def transport(url: str) -> str:
        return (FIXTURES / f"awards_{year}.html").read_text(encoding="utf-8")

    return transport

@pytest.fixture(scope="module")
def recorded_awards(tmp_path_factory):
    import seed_bbref_awards as seed
    from shared import store

    root = tmp_path_factory.mktemp("v2_recorded_awards")
    recorded = root / "recorded.duckdb"
    original = (store.DB_PATH, store.LOCK_PATH)
    store.DB_PATH = recorded
    store.LOCK_PATH = root / ".write.lock"
    try:
        for year, season in RECORDED:
            seed.seed_season(
                season, transport=_page(year), min_interval_s=0.0)
    finally:
        store.DB_PATH, store.LOCK_PATH = original
    return recorded

@pytest.fixture
def awards_warehouse(recorded_awards, tmp_path, monkeypatch):
    from shared import store
    from shared.tools import _core
    from v2.adapters import coverage

    path = tmp_path / "awards.duckdb"
    shutil.copyfile(recorded_awards, path)
    monkeypatch.setattr(store, "DB_PATH", path)
    monkeypatch.setattr(store, "LOCK_PATH", tmp_path / ".write.lock")
    store.warehouse_tables_cache_clear()
    store.warehouse_pool_clear()
    store.warehouse_identity_cache_clear()
    _core.last_completed_season_cache_clear()
    coverage.coverage_cache_clear()
    return path



def test_the_capability_declares_units_for_every_numeric_output():
    from v2.adapters.capabilities import (
        BALLOT_POINTS, CAPABILITIES, COUNT, FRACTION, YEARS)

    units = CAPABILITIES["award_results"].units
    assert units == {
        "age": YEARS,
        "award_share": FRACTION,
        "points_max": BALLOT_POINTS,
        "points_won": BALLOT_POINTS,
        "rank": COUNT,
        "votes_first": COUNT,
        "votes_second": COUNT,
        "votes_third": COUNT,
    }
    definitions = CAPABILITIES["award_results"].metric_definitions
    assert "fraction scale 0-1" in definitions["award_share"]
    assert "points_max" in definitions["points_won"]

def test_the_declared_vocabulary_covers_every_field_the_award_tool_returns(
        awards_warehouse):
    from v2.adapters import call_capability
    from v2.adapters.capabilities import CAPABILITIES

    envelope = call_capability("award_results", {
        "view": "field", "award": "ALL_NBA", "season": "2023-24"})
    returned = set(envelope.rows[0])
    declared = (set(CAPABILITIES["award_results"].units)
                | set(CAPABILITIES["award_results"].metric_definitions))
    assert not returned - declared
    assert {"player", "coach", "award_share", "points_won", "points_max",
            "votes_first", "votes_second", "votes_third", "rank"} <= declared

def test_the_names_a_planner_asks_for_resolve_to_a_returned_field():
    from v2.adapters.capabilities import CAPABILITIES, resolve_metric_column

    spec = CAPABILITIES["award_results"]
    for column in ("PLAYER", "COACH", "AWARD_SHARE", "POINTS_WON",
                   "POINTS_MAX", "VOTES_FIRST", "VOTES_SECOND",
                   "VOTES_THIRD", "RANK"):
        assert resolve_metric_column(spec, column) == column.lower(), column
    assert resolve_metric_column(spec, "PLAYER_NAME") == "player"
    assert resolve_metric_column(spec, "COACH_NAME") == "coach"
    assert resolve_metric_column(spec, "VOTE_SHARE") == "award_share"
    assert resolve_metric_column(spec, "HOME_RUNS") is None

def test_the_capability_description_separates_a_result_from_a_race():
    from v2.adapters.capabilities import CAPABILITY_DESCRIPTIONS

    description = CAPABILITY_DESCRIPTIONS["award_results"]
    assert "Official NBA award results" in description
    assert "never a model score" in description

def test_a_real_season_through_the_capability_returns_the_published_winner(
        awards_warehouse):
    from v2.adapters import call_capability

    envelope = call_capability(
        "award_results", {"view": "winner", "award": "MVP", "season": "2023-24"})
    assert envelope.capability == "award_results"
    assert envelope.season == "2023-24"
    assert envelope.rows == [{
        "season": "2023-24",
        "award": "MVP",
        "player": "Nikola Jokić",
        "coach": None,
        "team": "DEN",
        "age": 28,
        "rank": 1,
        "rank_label": "1",
        "tied": False,
        "award_share": 0.935,
        "points_won": 926,
        "points_max": 990,
        "votes_first": 79,
        "votes_second": None,
        "votes_third": None,
        "winner": "Nikola Jokić",
    }]
    assert envelope.units == {
        "award_share": "fraction_0_1",
        "points_won": "ballot_points",
        "points_max": "ballot_points",
        "votes_first": "count",
        "votes_second": "count",
        "votes_third": "count",
        "age": "years",
        "rank": "count",
    }
    assert "recorded outcome, never a model score" in envelope.coverage
    assert "ORV" in envelope.coverage or "ORV" in envelope.qualification
    assert envelope.source_identity.kind == "warehouse"
    assert envelope.source == "v1:get_award_results:warehouse"
    assert envelope.as_of is not None

def test_every_declared_unit_reaches_a_row_the_verifier_can_find(
        awards_warehouse):
    from v2.adapters import call_capability
    from v2.adapters.capabilities import CAPABILITIES
    from v2.domain.evidence import iter_values

    envelope = call_capability("award_results", {
        "view": "field", "award": "ALL_NBA", "season": "2023-24"})
    row_keys = {
        segment.split("[", 1)[0].casefold()
        for item in iter_values(envelope)
        for segment in item.path.split(".")
    }
    declared = {key.casefold() for key in CAPABILITIES["award_results"].units}
    assert not declared - row_keys
    assert set(envelope.units) <= declared


RECORDED_BALLOTS = {
    "2023-24": {"player": "Nikola Jokić", "coach": "Mark Daigneault",
                "award_share": 0.935, "votes_first": 79},
    "2014-15": {"player": "Stephen Curry", "coach": "Mike Budenholzer",
                "award_share": 0.922, "votes_first": 100},
}
AWARD_OUTPUTS = ["PLAYER_NAME", "VOTE_SHARE", "VOTES_FIRST", "COACH"]
OFF_BALLOT_PLAYER = "Victor Wembanyama"
REFUSAL = "I could not verify a publishable answer"


def test_a_coach_asked_for_as_a_player_fails_loudly_end_to_end(awards_warehouse):
    from v2.adapters import call_capability
    from v2.adapters.core import AdapterError

    with pytest.raises(AdapterError) as excinfo:
        call_capability("award_results", {
            "view": "player_awards", "season": "1976-77", "player": "Larry Brown"})
    message = str(excinfo.value)
    assert "get_award_results" in message
    assert "Larry Brown" in message
    assert "coach, not a player" in message
    assert "COY" in message

def test_an_award_a_player_never_won_fails_loudly_end_to_end(awards_warehouse):
    from v2.adapters import call_capability
    from v2.adapters.core import AdapterError

    with pytest.raises(AdapterError) as excinfo:
        call_capability("award_results", {
            "view": "player_awards", "award": "COY", "season": "2023-24",
            "player": "Nikola Jokić"})
    message = str(excinfo.value)
    assert "COY" in message
    assert "Nikola Jokić" in message
    assert "MVP" in message and "ALL_NBA" in message

def test_a_season_whose_ballot_never_existed_fails_loudly_end_to_end(
        awards_warehouse):
    from v2.adapters import call_capability
    from v2.adapters.core import AdapterError

    with pytest.raises(AdapterError) as excinfo:
        call_capability("award_results", {
            "view": "winner", "award": "MVP", "season": "1984-85"})
    assert "1984-85" in str(excinfo.value)

def test_the_tool_argument_is_rejected_on_an_award_view_end_to_end(
        awards_warehouse):
    from v2.adapters import call_capability
    from v2.adapters.core import AdapterError

    with pytest.raises(AdapterError) as excinfo:
        call_capability("award_results", {
            "view": "field", "award": "MVP", "season": "2023-24",
            "player": "Nikola Jokić"})
    assert "player_awards" in str(excinfo.value)


def test_the_projection_and_the_result_declare_themselves_apart(
        awards_warehouse, monkeypatch):
    from shared.tools import awards as projection
    from v2.adapters.capabilities import CAPABILITIES

    monkeypatch.setattr(projection, "clamp_season", lambda season: season)
    monkeypatch.setattr(projection, "_missing_table", lambda: None)
    monkeypatch.setattr(projection, "_standings_for", lambda season: {
        "table": "silver_standings", "coverage": "current"})
    monkeypatch.setattr(projection, "_pool", lambda season: [
        {"player": "A", "team": "AAA", "gp": 50, "mins": 1500,
         "ppg": 20, "eff_pg": 20, "apg": 5, "rpg": 7, "age": 20},
        {"player": "B", "team": "BBB", "gp": 50, "mins": 1500,
         "ppg": 10, "eff_pg": 10, "apg": 2, "rpg": 3, "age": 20},
    ])
    race = projection.get_award_race.invoke({"award": "ROY", "season": "2025-26"})
    assert race["meta"]["results_tool"] == "get_award_results"
    assert "not points, probability, vote share" in race["meta"]["score_definition"]
    assert CAPABILITIES["award_results"].tool_name != "get_award_race"

GOLDEN_CALLS = {
    "award-mvp-winner": ({"view": "winner", "award": "MVP"}, "answer"),
    "award-coach-of-year-winner": ({"view": "winner", "award": "COY"}, "answer"),
    "award-all-nba-first-team": (
        {"view": "winner", "award": "ALL_NBA"}, "answer"),
    "award-mvp-no-published-ballot": (
        {"view": "winner", "award": "MVP"}, "refuse"),
}


def test_the_golden_winner_scenarios_are_not_a_race(awards_warehouse):
    from v2.adapters import call_capability

    envelope = call_capability("award_results", {
        "view": "winner", "award": "ALL_NBA", "season": "2023-24"})
    labels = {row["rank_label"] for row in envelope.rows}
    assert labels == {"1T"}
    assert {row["rank"] for row in envelope.rows} == {1}
    assert "never a model score" in envelope.coverage
