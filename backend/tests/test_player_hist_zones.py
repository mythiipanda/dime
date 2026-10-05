
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared import store
from shared.tools.player import get_shot_compare, get_shot_zones
from shared.tools.zone import ZONE_KEYS


SGA = 1628983
LUKA = 1629029
LEBRON = 2544


def _geo_zone(x, y, v):
    try:
        dist = math.hypot(float(x), float(y)) / 10.0
    except (TypeError, ValueError):
        dist = 999.0
    try:
        ax = abs(float(x))
    except (TypeError, ValueError):
        ax = 0.0
    three = int(v or 0) == 3
    if dist < 8.0:
        return "rim"
    if three and ax >= 220:
        return "corner_3"
    if three:
        return "atb_3"
    if dist < 14.0:
        return "short_mid"
    return "long_mid"


def _season_rows(year):
    con = store.connect(read_only=True)
    try:
        return con.execute(
            "SELECT person_id, x_legacy, y_legacy, shot_value, shot_result"
            " FROM silver_hist_shots WHERE season = ?",
            [year]).fetchall()
    finally:
        con.close()


def _fold(rows, person_id):
    agg = {k: [0, 0] for k in ZONE_KEYS}
    for pid, x, y, v, r in rows:
        if int(pid) != person_id:
            continue
        z = _geo_zone(x, y, v)
        agg[z][1] += 1
        if str(r or "").lower() == "made":
            agg[z][0] += 1
    return agg


def test_hist_source_shape_and_floor_defaults():
    out = get_shot_zones.invoke({"player_id": SGA, "season": "2024-25"})
    assert out["ok"] is True
    assert out["meta"]["source"] == "warehouse:silver_hist_shots"
    assert out["meta"]["season"] == "2024-25"
    assert out["meta"]["min_attempts"] == 50
    zones = {r["zone"] for r in out["rows"]}
    assert zones <= set(ZONE_KEYS)
    assert zones | set(out["meta"]["excluded_zones"]) == set(ZONE_KEYS)
    for r in out["rows"]:
        assert r["FGA"] >= 50
        assert r["FG_PCT"] == round(r["FGM"] / r["FGA"], 3)
        assert r["share"] == round(r["FGA"] / out["meta"]["player_shots"], 3)
        assert 0.0 <= r["share"] <= 1.0


def test_hist_values_match_independent_sql():
    out = get_shot_zones.invoke(
        {"player_id": SGA, "season": "2024-25", "min_attempts": 10})
    assert out["ok"] is True
    rows = _season_rows(2025)
    mine = _fold(rows, SGA)
    assert out["meta"]["player_shots"] == sum(a for _, a in mine.values())
    league = {k: [0, 0] for k in ZONE_KEYS}
    for pid, x, y, v, r in rows:
        z = _geo_zone(x, y, v)
        league[z][1] += 1
        if str(r or "").lower() == "made":
            league[z][0] += 1
    by_zone = {r["zone"]: r for r in out["rows"]}
    assert set(by_zone) == set(ZONE_KEYS)
    for z in ZONE_KEYS:
        m, a = mine[z]
        assert by_zone[z]["FGM"] == m
        assert by_zone[z]["FGA"] == a
        lm, la = league[z]
        league_efg = round((lm + 0.5 * lm) / la, 3) if z in (
            "corner_3", "atb_3") else round(lm / la, 3)
        assert by_zone[z]["LEAGUE_DELTA"] == round(
            by_zone[z]["eFG_PCT"] - league_efg, 3)


def test_floor_excludes_thin_zone_and_clamps():
    tight = get_shot_zones.invoke(
        {"player_id": SGA, "season": "2024-25", "min_attempts": 200})
    assert tight["ok"] is True
    assert {r["zone"] for r in tight["rows"]} == {
        "rim", "short_mid", "long_mid", "atb_3"}
    assert tight["meta"]["excluded_zones"] == ["corner_3"]
    loose = get_shot_zones.invoke(
        {"player_id": SGA, "season": "2024-25", "min_attempts": 10})
    assert loose["meta"]["excluded_zones"] == []
    assert len(loose["rows"]) == 5
    clamped = get_shot_zones.invoke(
        {"player_id": SGA, "season": "2024-25", "min_attempts": 500})
    assert clamped["meta"]["min_attempts"] == 200
    assert clamped["meta"]["excluded_zones"] == ["corner_3"]


def test_multi_season_history():
    for season, expected_year in (("2015-16", 2016), ("2025-26", 2026)):
        out = get_shot_zones.invoke(
            {"player_id": LEBRON, "season": season, "min_attempts": 10})
        assert out["ok"] is True
        assert out["meta"]["source"] == "warehouse:silver_hist_shots"
        con = store.connect(read_only=True)
        try:
            expected = con.execute(
                "SELECT COUNT(*) FROM silver_hist_shots"
                " WHERE season = ? AND person_id = ?",
                [expected_year, LEBRON]).fetchone()[0]
        finally:
            con.close()
        assert out["meta"]["player_shots"] == expected
        assert sum(r["FGA"] for r in out["rows"]) == expected


def test_unknown_player_stays_honest():
    pytest = __import__("pytest")
    with pytest.raises(store.TableAbsent) as info:
        get_shot_zones.invoke({"player_id": 999999999, "season": "2024-25"})
    assert info.value.table == "silver_zone_splits"
    assert str(store.DB_PATH) == info.value.warehouse
    assert store.DB_PATH.name in str(info.value)
    assert "999999999" not in str(info.value)


def test_compare_edges_survive_hist_zones():
    import asyncio

    out = asyncio.run(get_shot_compare.ainvoke(
        {"a": str(SGA), "b": str(LUKA), "season": "2024-25"}))
    assert out["ok"] is True
    assert len(out["rows"]) > 0
    assert "missing" not in out["verdict"]
