import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evals.score_golden import score_item


def _dev_items():
    path = Path(__file__).resolve().parent / "golden_qa_dev.jsonl"
    return {json.loads(line)["id"]: json.loads(line)
            for line in path.read_text().splitlines() if line.strip()}


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


def test_dev_team_items_accept_either_name():
    items = _dev_items()
    cases = {
        "G006": ("The Thunder finished 11.1", "Oklahoma City finished 11.1"),
        "G007": ("Denver posted 121.2", "The Nuggets posted 121.2"),
        "G008": ("The Thunder allowed 106.5", "Oklahoma City allowed 106.5"),
        "G009": ("The Knicks won 4-1", "New York won 4-1"),
        "G010": ("Cleveland went 64-18", "The Cavaliers went 64-18"),
    }
    for gid, (first_only, second_only) in cases.items():
        item = items[gid]
        assert item["must_contain"] == []
        assert len(item["any_of"]) == 2
        assert score_item(item, first_only)["pass"] is True
        assert score_item(item, second_only)["pass"] is True
