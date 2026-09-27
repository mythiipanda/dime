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


def test_question_kind_player():
    assert _gate_question_kind("best defensive players in the league") == "player"


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
    kept, report = _gate_tables("best defensive players in the league", tables)
    titles = [t["title"] for t in kept]
    assert "Team splits" not in titles
    assert "Player ratings · DEF_RATING" in titles
    assert ("Team splits", "kind-mismatch") in report["dropped"]


def test_player_question_drops_team_leaders():
    kept, _ = _gate_tables("best defensive players?", [_team_leaders_table()])
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
