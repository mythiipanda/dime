import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evals.score_golden import score_item


def _item(**overrides):
    base = {"id": "T", "question": "q", "season": "2025-26",
            "exact": [], "must_contain": []}
    base.update(overrides)
    return base


def test_numeric_expect_does_not_match_inside_longer_number():
    assert score_item(
        _item(exact=["0107"]), "total 10107")[ "pass"] is False
    assert score_item(
        _item(exact=["28", "21"]), "281 points")["pass"] is False
    assert score_item(
        _item(exact=["9.4"]), "finished 19.4 on the year")["pass"] is False
    assert score_item(
        _item(exact=["9.4"]), "net rating 9.4")["pass"] is True
    assert score_item(
        _item(exact=["4-1"]), "won 4-1")["pass"] is True
    assert score_item(
        _item(exact=["4-1"]), "won 14-10")["pass"] is False


def test_any_of_team_name_needs_only_one():
    item = _item(exact=["9.4"], must_contain=[],
                 any_of=["Celtics", "Boston"])
    assert score_item(item, "Boston net rating 9.4")["pass"] is True
    assert score_item(item, "Celtics net rating 9.4")["pass"] is True
    assert score_item(item, "net rating 9.4")["pass"] is False
