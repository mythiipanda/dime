import os

import pytest

WAREHOUSE = os.path.join(os.path.dirname(__file__), "..", "data", "warehouse.duckdb")
pytestmark = pytest.mark.skipif(
    not (os.path.exists(WAREHOUSE) and os.path.getsize(WAREHOUSE) > 100_000_000),
    reason="runtime warehouse unavailable",
)


@pytest.fixture(scope="module")
def payload():
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "analyst"))
    os.environ.setdefault("DIME_WAREHOUSE", os.path.abspath(WAREHOUSE))
    from analyst.direct_data import product_awards

    return product_awards.invoke({"season": ""})


def test_awards_payload_ok(payload):
    assert payload.get("ok") is True
    assert isinstance(payload.get("awards"), list)
    assert len(payload["awards"]) >= 3


def test_mvp_candidates_ranked_with_drivers(payload):
    boards = {a["award"]: a for a in payload["awards"]}
    mvp = boards.get("MVP")
    assert mvp is not None
    if not mvp["ok"]:
        pytest.skip(f"MVP projection unavailable: {mvp.get('error')}")
    candidates = mvp["candidates"]
    assert len(candidates) >= 3
    ranks = [c["rank"] for c in candidates]
    assert ranks == sorted(ranks)
    top = candidates[0]
    assert top["player"] and top["team"]
    assert top["score"] >= candidates[-1]["score"]
    assert top["drivers"]
    assert {"stat", "value", "z"} <= set(top["drivers"][0])
    assert top["case_for"]


def test_unavailable_awards_fail_honestly(payload):
    for board in payload["awards"]:
        if not board["ok"]:
            assert board["error"]
            assert board["candidates"] == []
