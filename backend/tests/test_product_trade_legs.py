import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "analyst"))

WAREHOUSE = os.path.join(os.path.dirname(__file__), "..", "data", "warehouse.duckdb")
pytestmark = pytest.mark.skipif(
    not os.path.exists(WAREHOUSE) or os.path.getsize(WAREHOUSE) > 200 * 1024 * 1024,
    reason="warehouse fixture unavailable",
)


@pytest.fixture(scope="module")
def two_leg():
    from analyst.direct_data import product_trade_legs

    legs = [
        {"from": "BOS", "to": "ATL", "players": "Sam Hauser", "picks": []},
        {"from": "ATL", "to": "BOS", "players": "", "picks": [{"year": 2028, "round": 1}]},
    ]
    return product_trade_legs.invoke({"legs": json.dumps(legs), "season": "2026-27"})


def test_trade_legs_shape(two_leg):
    assert two_leg["ok"] is True
    assert isinstance(two_leg["rows"], list)
    teams = {row["team"] for row in two_leg["rows"]}
    assert "BOS" in teams and "ATL" in teams


def test_trade_legs_registered():
    from analyst.direct_data import internal_catalogue

    assert "product_trade_legs" in internal_catalogue()


def test_trade_legs_rejects_garbage():
    from analyst.direct_data import product_trade_legs

    assert product_trade_legs.invoke({"legs": "", "season": "2026-27"})["ok"] is False
    assert product_trade_legs.invoke({"legs": "not json", "season": "2026-27"})["ok"] is False
    assert product_trade_legs.invoke({"legs": json.dumps([{"from": "BOS"}]), "season": "2026-27"})["ok"] is False
