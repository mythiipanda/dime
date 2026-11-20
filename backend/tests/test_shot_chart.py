import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared import store
from shared.tools.shots import get_shot_chart


def _con():
    return store.connect(read_only=True)


def _shots_season(con):
    rows = con.execute(
        "SELECT DISTINCT _season FROM silver_shots ORDER BY 1"
    ).fetchall()
    if not rows:
        pytest.skip("silver_shots empty")
    return rows[-1][0]


def _some_player(con, season):
    rows = con.execute(
        "SELECT PLAYER_ID, PLAYER_NAME, COUNT(*) FROM silver_shots "
        "WHERE _season = ? GROUP BY 1, 2 ORDER BY 3 DESC LIMIT 1",
        [season],
    ).fetchall()
    return rows[0][1], rows[0][0]


def test_player_chart_zone_consistency():
    con = _con()
    season = _shots_season(con)
    name, pid = _some_player(con, season)
    out = get_shot_chart.invoke({"player": name, "season": season})
    assert out["ok"] is True
    assert out["scope"]["player"]
    assert out["season"] == season
    zones = out["zones"]
    assert zones, "expected nonempty zone list"
    total_att = 0
    for z in zones:
        assert set(z) >= {"x", "y", "att", "makes", "pct", "league_pct", "delta_pp", "zone", "label"}
        assert z["att"] > 0
        assert 0 <= z["makes"] <= z["att"]
        assert abs(z["pct"] - 100.0 * z["makes"] / z["att"]) < 0.051
        if z["league_pct"] is not None:
            assert abs(z["delta_pp"] - (z["pct"] - z["league_pct"])) < 0.06
        assert -30 <= z["x"] <= 30 and 0 <= z["y"] <= 45
        total_att += z["att"]
    assert total_att == out["meta"]["shots_scanned"]
    assert out["meta"]["source"] == "warehouse silver_shots"
    assert out["meta"]["season"] == season
    assert out["meta"]["as_of"]
    assert "silver_shots" in out["meta"]["sql"]


def test_team_chart_and_opponent_filter():
    con = _con()
    season = _shots_season(con)
    row = con.execute(
        "SELECT TEAM_ID, HTM, VTM FROM silver_shots WHERE _season = ? LIMIT 1",
        [season],
    ).fetchone()
    team_id, htm, vtm = row[0], row[1], row[2]
    from shared.tools.shots.zones import _team_abbr

    abbr = _team_abbr(team_id)
    full = get_shot_chart.invoke({"team": abbr, "season": season})
    assert full["ok"] is True
    vs = get_shot_chart.invoke({"team": abbr, "season": season, "opponent": vtm})
    assert vs["ok"] is True
    assert vs["opponent"] == vtm
    att_full = sum(z["att"] for z in full["zones"])
    att_vs = sum(z["att"] for z in vs["zones"])
    assert 0 < att_vs <= att_full
    direct = con.execute(
        "SELECT COUNT(*) FROM silver_shots WHERE _season = ? AND TEAM_ID = ? "
        "AND substr(GAME_ID, 1, 3) = '002' AND (HTM = ? OR VTM = ?)",
        [season, team_id, vtm, vtm],
    ).fetchone()[0]
    assert att_vs == direct


def test_requires_exactly_one_scope_and_known_season():
    out = get_shot_chart.invoke({})
    assert out["ok"] is False
    out = get_shot_chart.invoke({"player": "x", "team": "y"})
    assert out["ok"] is False
    con = _con()
    season = _shots_season(con)
    bad = get_shot_chart.invoke({"team": "LAL", "season": "1999-00"})
    assert bad["ok"] is False
    name, _ = _some_player(con, season)
    one = get_shot_chart.invoke({"player": name, "season": season})
    assert one["ok"] is True
