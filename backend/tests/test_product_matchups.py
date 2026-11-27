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
    from analyst.direct_data import product_matchups

    return product_matchups.invoke({"season": ""})


def test_matchups_ok_and_slate(payload):
    assert payload.get("ok") is True
    assert payload.get("date")
    assert isinstance(payload.get("games"), list)


def test_game_shape_and_team_stats(payload):
    games = payload.get("games") or []
    if not games:
        pytest.skip("no games on the current slate")
    game = games[0]
    assert game["id"]
    assert game["time"]
    for side in ("away", "home"):
        team = game[side]
        assert team["abbr"]
        assert team["name"]
        if team.get("net_rating") is not None:
            assert -40 < team["net_rating"] < 40
            assert 80 < team["off_rating"] < 140
            assert 80 < team["def_rating"] < 140
        for result in team["form"]:
            assert result in ("W", "L")
        assert len(team["form"]) <= 10
        assert isinstance(team["injuries"], list)


def test_records_present_when_ratings_join(payload):
    games = payload.get("games") or []
    if not games:
        pytest.skip("no games on the current slate")
    records = [g["away"]["record"] for g in games] + [g["home"]["record"] for g in games]
    assert any("-" in record for record in records)
