import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "bbref_awards"

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

    root = tmp_path_factory.mktemp("recorded_awards")
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

def test_a_real_season_returns_the_published_winner_and_share(awards_warehouse):
    result = _results(view="winner", award="MVP", season="2023-24")
    assert result["ok"] is True, result
    assert result["rows"] == [{
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

def test_the_result_declares_itself_a_recorded_outcome_not_a_projection(
        awards_warehouse):
    meta = _results(view="winner", award="MVP", season="2023-24")["meta"]
    assert meta["result_type"] == "official_award_result"
    assert meta["model_projection"] is False
    assert meta["source"] == "warehouse"
    assert meta["dataset"] == "basketball-reference"
    assert meta["award"] == "MVP"
    assert meta["award_label"] == "Most Valuable Player"
    assert meta["season"] == "2023-24"
    assert meta["ballot"] is True
    assert meta["vote_columns"] == ["votes_first"]
    assert meta["fetched_at"].startswith("20")
    assert "read verbatim" in meta["method"]
    assert "recorded" in meta["coverage"]
    assert "never a model score, projection, or live race" in meta["coverage"]
    assert meta["rank_semantics"].startswith("rank is the published leading rank")

def test_a_coach_award_names_a_coach_and_never_a_player(awards_warehouse):
    result = _results(view="winner", award="COY", season="1997-98")
    assert result["ok"] is True, result
    placement = result["rows"][0]
    assert placement["coach"] == "Larry Bird"
    assert placement["player"] is None
    assert placement["team"] == "IND"
    assert placement["award_share"] == 0.431
    assert placement["points_won"] == 50
    assert result["meta"]["award_subject"] == "coach"

def test_a_coach_award_that_a_player_did_not_win_is_an_honest_absence(
        awards_warehouse):
    result = _results(view="player_awards", award="COY", season="2023-24",
                      player="Nikola Jokić")
    assert result["ok"] is False
    assert "Nikola Jokić" in result["error"]
    assert "COY" in result["error"]
    assert "2023-24" in result["error"]
    assert "MVP" in result["error"] and "ALL_NBA" in result["error"]

def test_a_coach_asked_for_as_a_player_is_told_he_is_a_coach(awards_warehouse):
    result = _results(view="player_awards", season="1976-77", player="Larry Brown")
    assert result["ok"] is False
    assert "Larry Brown" in result["error"]
    assert "COY" in result["error"]
    assert "coach, not a player" in result["error"]
    assert "1976-77" in result["error"]

def test_a_player_name_no_ballot_carries_is_an_honest_absence(awards_warehouse):
    result = _results(view="player_awards", season="2023-24",
                      player="Amar'e Stoudemire")
    assert result["ok"] is False
    assert "Amar'e Stoudemire" in result["error"]
    assert "2023-24" in result["error"]

def test_a_player_history_covers_every_season_they_appear_on(awards_warehouse):
    result = _results(view="player_awards", season="2025-26",
                      player="Nikola Jokić")
    assert result["ok"] is True, result
    assert [(row["season"], row["award"], row["rank"], row["rank_label"])
            for row in result["rows"]] == [
        ("2025-26", "ALL_NBA", 1, "1T"),
        ("2025-26", "MVP", 2, "2"),
        ("2023-24", "ALL_NBA", 1, "1T"),
        ("2023-24", "MVP", 1, "1"),
    ]
    assert result["meta"]["history_through"] == "2025-26"
    assert result["meta"]["seasons_covered"] == ["2023-24", "2025-26"]
    assert result["meta"]["season"] == "2025-26"

def test_a_player_history_narrows_to_one_award_when_asked(awards_warehouse):
    result = _results(view="player_awards", award="MVP", season="2025-26",
                      player="Nikola Jokić")
    assert result["ok"] is True, result
    assert {row["award"] for row in result["rows"]} == {"MVP"}
    assert [row["award_share"] for row in result["rows"]] == [
        0.634, 0.935]

def test_the_field_returns_every_published_placement_with_its_votes(
        awards_warehouse):
    result = _results(view="field", award="DPOY", season="2023-24")
    assert result["ok"] is True, result
    placements = result["rows"]
    assert len(placements) == 13
    assert [row["rank"] for row in placements] == sorted(
        row["rank"] for row in placements)
    leader = placements[0]
    assert leader["player"] == "Rudy Gobert"
    assert leader["award_share"] == 0.875
    assert leader["votes_first"] == 72
    assert result["meta"]["count"] == 13

def test_a_tied_rank_keeps_the_published_rank_and_marks_the_tie(awards_warehouse):
    result = _results(view="field", award="DPOY", season="2023-24")
    tied = [row for row in result["rows"] if row["rank"] == 10]
    assert [row["rank_label"] for row in tied] == ["10T", "10T", "10T", "10T"]
    assert {row["tied"] for row in tied} == {True}
    assert {row["player"] for row in tied} == {
        "Alex Caruso", "Domantas Sabonis", "Jalen Suggs", "Jarrett Allen"}
    assert [row["rank"] for row in result["rows"]
            if row["tied"] is False and row["rank"] == 10] == []

def test_a_tied_first_team_keeps_every_leading_player(awards_warehouse):
    result = _results(view="winner", award="ALL_NBA", season="2023-24")
    assert result["ok"] is True, result
    placements = result["rows"]
    assert len(placements) == 5
    assert {row["rank"] for row in placements} == {1}
    assert {row["rank_label"] for row in placements} == {"1T"}
    assert {row["tied"] for row in placements} == {True}
    assert result["meta"]["honors_teams"] == 3

def test_a_team_award_is_not_reported_as_a_tie(awards_warehouse):
    result = _results(view="winner", award="ALL_DEFENSE", season="2023-24")
    assert result["ok"] is True, result
    placements = result["rows"]
    assert len(placements) == 5
    assert {row["rank"] for row in placements} == {1}
    assert {row["rank_label"] for row in placements} == {"1st"}
    assert {row["tied"] for row in placements} == {False}
    assert result["meta"]["honors_teams"] == 3

def test_a_row_that_made_no_team_keeps_a_null_rank_and_its_published_label(
        awards_warehouse):
    result = _results(view="field", award="ALL_NBA", season="2023-24")
    other = [row for row in result["rows"]
             if row["rank_label"] == "ORV"]
    assert len(other) == 10
    assert {row["rank"] for row in other} == {None}
    assert {row["tied"] for row in other} == {False}
    assert all(row["player"] for row in other)
    ranked = [row for row in result["rows"] if row["rank"]]
    assert min(row["rank"] for row in ranked) == 1
    assert result["rows"][-1]["rank"] is None

def test_a_ballot_without_vote_counts_reports_them_as_absent(awards_warehouse):
    result = _results(view="field", award="ALL_DEFENSE", season="2023-24")
    assert result["ok"] is True, result
    assert result["meta"]["ballot"] is False
    assert result["meta"]["vote_columns"] == []
    assert {row["votes_first"] for row in result["rows"]} == {None}
    assert result["rows"][0]["rank_label"] == "1st"

def test_a_season_whose_ballot_never_existed_fails_naming_the_season(
        awards_warehouse):
    result = _results(view="winner", award="MVP", season="1981-82")
    assert result["ok"] is False
    assert result["rows"] == {}
    assert "1981-82" in result["error"]
    assert "1976-77" in result["error"] and "2025-26" in result["error"]
    assert "never estimates a missing ballot" in result["error"]

def test_a_season_before_the_first_published_ballot_fails_naming_the_season(
        awards_warehouse):
    result = _results(view="winner", award="MVP", season="1975-76")
    assert result["ok"] is False
    assert "1975-76" in result["error"]
    assert "1976-77" in result["error"]

def test_a_missing_awards_table_fails_naming_the_table(empty_warehouse):
    result = _results(view="winner", award="MVP", season="2023-24")
    assert result["ok"] is False
    assert result["reason"] == "table_missing"
    assert "silver_bbref_awards" in result["error"]


def test_a_missing_awards_table_fails_every_view_with_the_same_reason(
        empty_warehouse):
    for view, arguments in (
            ("winner", {"award": "MVP"}),
            ("field", {"award": "MVP"}),
            ("player_awards", {"player": "LeBron James"})):
        result = _results(view=view, season="2023-24", **arguments)
        assert result["ok"] is False, view
        assert result["reason"] == "table_missing", view


def test_an_unknown_view_fails_with_a_machine_reason(empty_warehouse):
    from shared.tools.award_results import get_award_results

    result = get_award_results.func(
        view="podiums", award="MVP", season="2023-24")
    assert result["ok"] is False
    assert result["reason"] == "unknown_view"

def test_an_award_surface_form_normalizes_to_its_published_code(awards_warehouse):
    result = _results(view="winner", award="Most Improved Player of the Year",
                      season="2023-24")
    assert result["ok"] is True, result
    assert result["meta"]["award"] == "MIP"
    assert result["rows"][0]["award"] == "MIP"

def test_an_unrecognized_award_fails_naming_the_published_codes(awards_warehouse):
    result = _results(view="winner", award="Most Valuable Rookie",
                      season="2023-24")
    assert result["ok"] is False
    assert "Most Valuable Rookie" in result["error"]
    for code in ("MVP", "DPOY", "ROY", "6MOY", "MIP", "COY", "ALL_NBA",
                 "ALL_DEFENSE", "ALL_ROOKIE"):
        assert code in result["error"]

def test_the_typed_boundary_rejects_a_view_it_does_not_publish(awards_warehouse):
    import pytest

    with pytest.raises(Exception) as excinfo:
        _results(view="podium", award="MVP", season="2023-24")
    assert "winner" in str(excinfo.value)

def test_a_view_outside_the_enum_fails_naming_the_views(awards_warehouse):
    from shared.tools.award_results import get_award_results

    result = get_award_results.func(
        view="podium", award="MVP", season="2023-24")
    assert result["ok"] is False
    for view in ("winner", "field", "player_awards"):
        assert view in result["error"]

def test_a_view_that_needs_an_award_says_so(awards_warehouse):
    result = _results(view="winner", season="2023-24")
    assert result["ok"] is False
    assert "award" in result["error"]

def test_a_player_view_without_a_player_says_so(awards_warehouse):
    result = _results(view="player_awards", season="2023-24")
    assert result["ok"] is False
    assert "player" in result["error"]

def test_a_player_argument_on_an_award_view_fails_loudly(awards_warehouse):
    result = _results(view="field", award="MVP", season="2023-24",
                      player="Nikola Jokić")
    assert result["ok"] is False
    assert "player_awards" in result["error"]

def test_every_published_award_normalizes_from_its_surface_forms():
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

def test_an_omitted_season_resolves_to_the_latest_published_ballot(
        awards_warehouse):
    result = _results(view="winner", award="MVP")
    assert result["ok"] is True, result
    assert result["meta"]["season"] == "2025-26"
    assert result["rows"][0]["player"] == "Shai Gilgeous-Alexander"


def test_a_player_name_matches_case_insensitively(awards_warehouse):
    loud = _results(view="player_awards", season="2023-24",
                    player="LeBron James")
    quiet = _results(view="player_awards", season="2023-24",
                     player="lebron james")
    assert loud["ok"] is quiet["ok"] is True
    assert (len(loud["rows"]) ==
            len(quiet["rows"]) > 0)


def test_winner_meta_emits_official_kind(awards_warehouse):
    result = _results(view="winner", award="MVP", season="2023-24")
    assert result["ok"] is True, result
    assert result["meta"]["method_kind"] == "official"
def test_a_player_name_matches_without_its_diacritic(awards_warehouse):
    accented = _results(view="player_awards", season="2023-24",
                        player="Nikola Jokić")
    plain = _results(view="player_awards", season="2023-24",
                     player="nikola jokic")
    assert accented["ok"] is plain["ok"] is True
    assert accented["rows"] == plain["rows"]
