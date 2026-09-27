"""Termination gate: tables must match the question kind and carry rows;
rate-stat claims must name their minutes floor. Regression tests for the
Colby Jones episode (TEAM SPLITS + LEADERS PTS rendered for player-kind
questions) and the empty COMPARE view."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.graph import (  # noqa: E402
    _gate_qualifications,
    _gate_question_kind,
    _gate_table_level,
    _gate_tables,
    verify_minutes_qual,
    verify_numbers_traced,
    verify_table_kind,
)


def _player_table():
    return {"title": "Player ratings · DEF_RATING", "kind": "leaders",
            "rows": [{"RANK": 1, "PLAYER": "Colby Jones", "TEAM": "SAC",
                      "MINUTES": 120, "DEF_RATING": 53.3}],
            "meta": {"qualification": "1,000+ total minutes",
                     "coverage": ("On-court team rating while each player "
                                  "played. This does not isolate individual "
                                  "offensive or defensive value.")}}


def _team_splits_table():
    return {"title": "Team splits", "kind": "dataset",
            "rows": [{"TEAM": "BOS", "W": 56, "L": 26}],
            "meta": {}}


def _team_leaders_table():
    return {"title": "League leaders · PTS", "kind": "leaders",
            "rows": [{"TEAM": "BOS", "PTS": 9800}],
            "meta": {}}


def test_question_kind_generic_no_entities():
    # No keyword/regex guessing: a generic question with no named entities
    # returns "other" so phrasing never drops tables (Instinct QA 2026-09-27).
    assert _gate_question_kind("best defensive players in the league") == "other"
    assert _gate_question_kind("best offense this season?") == "other"


def test_question_kind_named_players():
    assert _gate_question_kind("Compare Luka Doncic and Shai Gilgeous-Alexander") == "player"


def test_question_kind_team():
    assert _gate_question_kind("boston celtics stats") == "team"


def test_question_kind_mixed_keeps_everything():
    tables = [_player_table(), _team_splits_table()]
    kept, report = _gate_tables("Luka Doncic vs Boston Celtics", tables)
    assert len(kept) == 2
    assert report["question_kind"] == "mixed"


def test_player_question_drops_team_splits():
    tables = [_player_table(), _team_splits_table()]
    kept, report = _gate_tables("Compare Luka Doncic and Shai Gilgeous-Alexander", tables)
    titles = [t["title"] for t in kept]
    assert "Team splits" not in titles
    assert "Player ratings · DEF_RATING" in titles
    assert ("Team splits", "kind-mismatch") in report["dropped"]


def test_player_question_drops_team_leaders():
    kept, _ = _gate_tables("Compare Luka Doncic and Shai Gilgeous-Alexander",
                           [_team_leaders_table()])
    assert kept == []


def test_team_question_keeps_team_tables():
    kept, _ = _gate_tables("boston celtics stats", [_team_splits_table()])
    assert len(kept) == 1


def test_empty_view_dropped():
    tables = [{"title": "Player comparison", "kind": "compare", "rows": []}]
    kept, report = _gate_tables("Compare Luka Doncic and Shai Gilgeous-Alexander", tables)
    assert kept == []
    assert report["dropped"] == [("Player comparison", "empty")]


def test_table_level_from_rows():
    assert _gate_table_level(_player_table()) == "player"
    assert _gate_table_level(_team_splits_table()) == "team"
    assert _gate_table_level({"title": "Dataset", "rows": [{"a": 1}]}) == "unknown"


def test_qualification_appended_when_missing():
    text = "Colby Jones is the best defender at 53.3 defensive rating."
    out, report = _gate_qualifications(text, [_player_table()])
    assert "Qualification: 1,000+ total minutes." in out
    assert report["applied"] == ["qualification", "coverage"]
    # superlative claim also names the on-court caveat
    assert "does not isolate individual" in out


def test_qualification_not_duplicated():
    text = "Colby Jones leads with a 53.3 defensive rating (1,000+ total minutes)."
    out, report = _gate_qualifications(text, [_player_table()])
    assert out == text
    assert report["applied"] == []


def test_no_numbers_no_qualification():
    text = "I could not find that in the dataset."
    out, _ = _gate_qualifications(text, [_player_table()])
    assert out == text


def test_coverage_not_appended_without_superlative():
    text = "The top five by defensive rating are listed below."
    out, report = _gate_qualifications(text, [_player_table()])
    assert "does not isolate individual" not in out

def test_no_entity_question_keeps_team_table():
    # Instinct QA repro (2026-09-27): "best offense this season?" was
    # classified as PLAYER by keyword regex ("best") and silently dropped
    # a legit TEAM splits table (BOS 56 wins). With structural-only
    # classification, no-entity questions keep all non-empty tables.
    kept, report = _gate_tables("best offense this season?", [_team_splits_table()])
    assert len(kept) == 1
    assert kept[0]["title"] == "Team splits"
    assert report["question_kind"] == "other"
    assert report["dropped"] == []


def _traced_state():
    return {
        "tool_results": [{"title": "Leaders",
                          "rows": [{"PLAYER": "Luka Doncic", "SPG": 2.1,
                                    "MINUTES": 2400}]}],
        "ledger": [],
    }


def test_verify_numbers_traced_flags_untraced():
    state = _traced_state()
    assert verify_numbers_traced(state, "Luka Doncic averages 99.9 points.") == ["99.9"]
    # thin wrapper only: never writes state["_verify"]
    assert "_verify" not in state


def test_verify_numbers_traced_passes_traced():
    assert verify_numbers_traced(_traced_state(), "Luka Doncic averages 2.1 steals.") == []


def test_empty_team_table_dropped():
    kept, report = _gate_tables("boston celtics stats",
                                [{"title": "Team splits", "kind": "dataset", "rows": []}])
    assert kept == []
    assert report["dropped"] == [("Team splits", "empty")]


def test_verify_table_kind_both_directions():
    pq = "Compare Luka Doncic and Shai Gilgeous-Alexander"
    tq = "boston celtics stats"
    assert verify_table_kind(pq, _team_splits_table()) is False
    assert verify_table_kind(tq, _player_table()) is False
    assert verify_table_kind(pq, _player_table()) is True
    assert verify_table_kind(tq, _team_splits_table()) is True


def test_verify_table_kind_mixed_other_unknown_never_reject():
    assert verify_table_kind("Luka Doncic vs Boston Celtics", _team_splits_table()) is True
    assert verify_table_kind("best offense this season?", _team_splits_table()) is True
    unknown = {"title": "Dataset", "rows": [{"a": 1}]}
    assert verify_table_kind("boston celtics stats", unknown) is True


def test_team_question_drops_player_table():
    kept, report = _gate_tables("boston celtics stats",
                                [_player_table(), _team_splits_table()])
    titles = [t["title"] for t in kept]
    assert "Player ratings · DEF_RATING" not in titles
    assert "Team splits" in titles
    assert ("Player ratings · DEF_RATING", "kind-mismatch") in report["dropped"]


def test_minutes_qual_flags_unqualified_rate_claim():
    text = "Luka Doncic leads the league in steals (2.1 SPG)."
    viols = verify_minutes_qual(text, [])
    assert len(viols) == 1
    assert "2.1 SPG" in viols[0]


def test_minutes_qual_passes_with_floor():
    text = "Luka Doncic leads the league in steals (2.1 SPG, min 500 minutes)."
    assert verify_minutes_qual(text, []) == []


def test_minutes_qual_ignores_plain_numbers():
    assert verify_minutes_qual("Boston won 56 games.", []) == []


def test_minutes_qual_flags_percent_first_format():
    assert len(verify_minutes_qual("He shoots 61.6% TS.", [])) == 1
    assert verify_minutes_qual("He shoots 61.6% TS (32.1 MPG).", []) == []
