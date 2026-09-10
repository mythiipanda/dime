"""Award race tests. Warehouse reads only; skip when tables missing."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

AWARD_TABLES = {"silver_leaders_pts", "silver_advanced", "silver_standings"}


def _warehouse_has_awards() -> bool:
    try:
        from app import store

        con = store.connect()
        try:
            tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        finally:
            con.close()
        if not AWARD_TABLES <= tables:
            return False
        n = store._read_df(
            "SELECT COUNT(*) AS n FROM silver_leaders_pts WHERE _season = ?",
            ["2025-26"])[0]["n"]
        return int(n) > 100
    except Exception:
        return False


KNOWN_STARS = {
    "Nikola Joki", "Luka Don", "Shai Gilgeous", "Victor Wembanyama",
    "Giannis Antetokounmpo", "Joel Embiid", "Jayson Tatum", "Kevin Durant",
    "Stephen Curry", "LeBron James", "Anthony Edwards", "Jalen Brunson",
    "Donovan Mitchell", "Devin Booker", "Anthony Davis", "Cade Cunningham",
}


def test_award_race_mvp_shape_and_formula():
    if not _warehouse_has_awards():
        return
    from app.tools.awards import get_award_race

    res = get_award_race.invoke({"award": "MVP", "season": "2025-26"})
    assert res["ok"] is True
    cands = res["rows"]["candidates"]
    assert len(cands) == 5
    assert [c["rank"] for c in cands] == [1, 2, 3, 4, 5]
    scores = [c["score"] for c in cands]
    assert scores == sorted(scores, reverse=True)
    for c in cands:
        assert c["player"] and c["team"]
        assert len(c["drivers"]) == 3
        assert c["case_for"] and c["case_against"]
    formula = res["meta"]["formula"]
    assert formula == ("0.35*z(PPG) + 0.2*z(team win%) + 0.15*z(net rating)"
                       " + 0.15*z(APG) + 0.15*z(RPG)")
    blob = formula + " ".join(c["player"] for c in cands)
    for bad in ("EPM", "LEBRON", "DARKO", "RAPTOR"):
        assert bad not in blob
    assert "not fabricated" in res["meta"]["advanced_metrics"]
    names = " ".join(c["player"] for c in cands)
    assert sum(1 for s in KNOWN_STARS if s in names) >= 3


def test_award_race_alias_normalization():
    if not _warehouse_has_awards():
        return
    from app.tools.awards import get_award_race

    assert get_award_race.invoke({"award": "mvp"})["meta"]["award"] == "MVP"
    assert get_award_race.invoke(
        {"award": "best defender"})["meta"]["award"] == "DPOY"
    assert get_award_race.invoke(
        {"award": "rookie of the year"})["meta"]["award"] == "ROY"
    assert get_award_race.invoke(
        {"award": "sixth man"})["meta"]["award"] == "6MOY"


def test_award_race_unknown_award():
    from app.tools.awards import get_award_race

    res = get_award_race.invoke({"award": "coach of the year"})
    assert res["ok"] is False
    assert "MVP" in res["error"] and "DPOY" in res["error"]


def test_award_race_mip_degrades_honestly():
    if not _warehouse_has_awards():
        return
    from app.tools.awards import get_award_race

    res = get_award_race.invoke({"award": "MIP", "season": "2025-26"})
    assert res["ok"] is False
    assert "prior-season" in res["error"]


def test_award_race_registered_and_labeled():
    from app import tools
    from app.graph import tool_label
    from app.subagents import _desk_tool_label

    assert "get_award_race" in tools.TOOL_NAMES
    assert tool_label("get_award_race") == "Ranking award races"
    assert _desk_tool_label("get_award_race") == "Ranking award races"
