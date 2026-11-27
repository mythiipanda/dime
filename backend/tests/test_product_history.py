import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "analyst"))

WAREHOUSE = os.path.join(os.path.dirname(__file__), "..", "data", "warehouse.duckdb")
pytestmark = pytest.mark.skipif(
    not os.path.exists(WAREHOUSE) or os.path.getsize(WAREHOUSE) > 200 * 1024 * 1024,
    reason="warehouse fixture unavailable",
)


def test_history_registered():
    from analyst.direct_data import internal_catalogue

    for name in ("product_history_career", "product_history_era_comps", "product_history_leaders"):
        assert name in internal_catalogue()


def test_history_leaders_era_board():
    from analyst.direct_data import product_history_leaders

    out = product_history_leaders.invoke({"season": "1996-97", "category": "pts"})
    assert out["ok"] is True
    assert out["rows"][0]["player"] == "Michael Jordan"
    assert out["rows"][0]["z"] > 2
    assert out["meta"]["pool"] > 300


def test_history_leaders_rejects_bad_category():
    from analyst.direct_data import product_history_leaders

    assert product_history_leaders.invoke({"season": "1996-97", "category": "bogus"})["ok"] is False
    assert product_history_leaders.invoke({"season": "", "category": "pts"})["ok"] is False


def test_history_career_and_comps():
    from analyst.direct_data import product_history_career, product_history_era_comps

    career = product_history_career.invoke({"player": "Michael Jordan"})
    assert career["ok"] is True
    assert len(career["rows"]) >= 2
    comps = product_history_era_comps.invoke({"player_id": 0, "player": "Michael Jordan", "season": "1996-97", "k": 3, "start_season": "", "end_season": ""})
    assert comps["ok"] is True
    assert len(comps["rows"]) == 3
