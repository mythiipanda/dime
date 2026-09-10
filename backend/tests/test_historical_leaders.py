"""Historical leaders tests. Warehouse reads only; skip when tables missing."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _warehouse_has_history() -> bool:
    try:
        from app import store

        con = store.connect()
        try:
            tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        finally:
            con.close()
        if "silver_hist_player_seasons" not in tables:
            return False
        n = store._read_df(
            "SELECT COUNT(*) AS n FROM silver_hist_player_seasons WHERE season = ?",
            [2025])[0]["n"]
        return int(n) > 100
    except Exception:
        return False


def test_per_season_leaders_shape_and_order():
    if not _warehouse_has_history():
        return
    from app.tools.history import get_historical_leaders

    res = get_historical_leaders.invoke({
        "category": "pts", "start_season": 2023,
        "end_season": 2025, "limit": 3, "mode": "leaders",
    })
    assert res["ok"] is True
    seasons = res["rows"]["seasons"]
    assert [s["season"] for s in seasons] == [2023, 2024, 2025]
    for s in seasons:
        vals = [r["value"] for r in s["leaders"]]
        assert len(vals) == 3
        assert vals == sorted(vals, reverse=True)
        for r in s["leaders"]:
            assert r["player"] and r["team"] and r["gp"] >= 20
    assert res["meta"]["source"] == "warehouse (documented estimates)"


def test_single_season_best_has_known_campaign():
    if not _warehouse_has_history():
        return
    from app.tools.history import get_historical_leaders

    res = get_historical_leaders.invoke({
        "category": "pts", "start_season": 2015,
        "end_season": 2025, "limit": 5, "mode": "best",
    })
    assert res["ok"] is True
    leaders = res["rows"]["leaders"]
    vals = [r["value"] for r in leaders]
    assert vals == sorted(vals, reverse=True)
    blob = " ".join(r["player"] for r in leaders)
    assert "Harden" in blob
    assert leaders[0]["value"] >= 34.0


def test_invalid_category_rejected():
    from app.tools.history import get_historical_leaders

    res = get_historical_leaders.invoke({"category": "dunks"})
    assert res["ok"] is False
    assert "pts" in res["error"]


def test_season_clamp_never_2026():
    if not _warehouse_has_history():
        return
    from app.tools.history import get_historical_leaders

    res = get_historical_leaders.invoke({
        "category": "pts", "start_season": 1990,
        "end_season": 2026, "limit": 1, "mode": "leaders",
    })
    assert res["ok"] is True
    assert res["meta"]["start_season"] == 2015
    assert res["meta"]["end_season"] == 2025
    assert res["rows"]["seasons"][-1]["season"] == 2025


def test_empty_range_honest():
    if not _warehouse_has_history():
        return
    from app.tools.history import get_historical_leaders

    res = get_historical_leaders.invoke({
        "category": "raptor", "start_season": 2024,
        "end_season": 2025, "limit": 5, "mode": "best",
    })
    assert res["ok"] is False
    assert "no RAPTOR coverage" in res["error"]


def test_limit_clamp():
    if not _warehouse_has_history():
        return
    from app.tools.history import get_historical_leaders

    res = get_historical_leaders.invoke({
        "category": "reb", "start_season": 2024,
        "end_season": 2025, "limit": 100, "mode": "best",
    })
    assert res["meta"]["limit"] == 25
    assert len(res["rows"]["leaders"]) <= 25
    res = get_historical_leaders.invoke({
        "category": "reb", "start_season": 2024,
        "end_season": 2025, "limit": 0, "mode": "best",
    })
    assert res["meta"]["limit"] == 1
    assert len(res["rows"]["leaders"]) == 1


def test_registered():
    from app import tools

    assert "get_historical_leaders" in tools.TOOL_NAMES
