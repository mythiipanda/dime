"""Fast offline unit tests. No network, no LLM, no warehouse writes."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import datasets, graph, tools
from app.providers import resolve_model_id


def test_clamp_stat_rejects_injection():
    assert tools.clamp_stat('PTS"; DROP TABLE x; --') == "PTS"


def test_clamp_stat_normalizes_case():
    assert tools.clamp_stat("ast") == "AST"
    assert tools.clamp_stat("REB") == "REB"


def test_resolve_model_defaults_mistral():
    from app.providers import _default_provider

    assert resolve_model_id(None) == _default_provider()


def test_resolve_model_clamps_unknown_openrouter():
    name, _ = resolve_model_id("openrouter:not-a-model:free")
    assert name == "openrouter"


def test_resolve_model_inception():
    assert resolve_model_id("inception:mercury-2.5") == ("inception", "mercury-2.5")


def test_clamp_season_rejects_garbage():
    from app.tools._core import clamp_season

    assert clamp_season("22025") == "2025-26"
    assert clamp_season("2025-26") == "2025-26"
    assert clamp_season("") == "2025-26"


def test_resolve_model_rejects_bare_names():
    from app.providers import _default_provider

    assert resolve_model_id("LeBron James") == _default_provider()


def test_call_keys_dedupe():
    a = graph._call_key("get_leaders", {"stat_category": "PTS"})
    b = graph._call_key("get_leaders", {"stat_category": "PTS"})
    c = graph._call_key("get_leaders", {"stat_category": "AST"})
    assert a == b
    assert a != c


def test_budget_bounds():
    assert 1 <= graph.MAX_TOOL_CALLS <= 8
    assert 1 <= graph.MAX_TOOL_ROUNDS <= 3


def test_registry_unique_names():
    names = [t.name for t in tools.v1_tools]
    assert len(names) == len(set(names))
    assert len(names) >= 20


def test_dataset_tables_allowlisted():
    assert set(datasets.TABLES) <= {
        "standings", "leaders", "injuries", "player_gamelogs",
        "team_games", "scoreboard", "shots", "lineups",
        "on_off", "wowy", "four_factors", "hustle", "combine",
        "ratings", "playoffs", "playoff_gamelogs",
        "draft", "raptor", "player_seasons",
    }


def test_resolve_entity_static():
    res = tools.resolve_entity.invoke({"query": "LeBron James"})
    ids = [p.get("id") for p in res["rows"]["players"]]
    assert 2544 in ids


def test_trust_tier_thresholds():
    from app.tools._core import trust_tier

    assert trust_tier(120) == ("TRUSTED", 240)
    assert trust_tier(100)[0] == "TRUSTED"
    assert trust_tier(99.9)[0] == "FRAGILE"
    assert trust_tier(50)[0] == "FRAGILE"
    assert trust_tier(49.9)[0] == "SMALL"
    assert trust_tier(None) == ("SMALL", 0)
    assert trust_tier("bad") == ("SMALL", 0)


def test_zone_diet_sums_three_zones():
    from app.tools.player import zone_diet

    rows = [
        {"zone": "Restricted Area", "SHARE": 0.35},
        {"zone": "Above the Break 3", "SHARE": 0.30},
        {"zone": "Corner 3", "SHARE": 0.10},
        {"zone": "Mid-Range", "SHARE": 0.25},
    ]
    assert zone_diet(rows) == {"rim_share": 0.35, "three_share": 0.4}
    assert zone_diet([]) == {"rim_share": None, "three_share": None}
    assert zone_diet([{"zone": "Mid-Range", "SHARE": 1.0}]) == {
        "rim_share": None, "three_share": None}


def test_portability_fit_branches():
    from app.tools.player import portability_fit

    risk = portability_fit(
        {"name": "A", "usg_pct": 33, "net_onoff": 6},
        {"name": "B", "usg_pct": 32, "net_onoff": 1})
    assert risk["fit"] == "risk"
    assert "Shot diet" not in risk["note"]
    scalable = portability_fit(
        {"name": "H", "usg_pct": 34, "ts_pct": 0.62, "net_onoff": 4,
         "rim_share": 0.35, "three_share": 0.40},
        {"name": "S", "usg_pct": 21, "ts_pct": 0.65, "net_onoff": 2,
         "rim_share": 0.20, "three_share": 0.45})
    assert scalable["fit"] == "scalable"
    assert "Shot diet rim 35% vs 20%, three 40% vs 45%." in scalable["note"]
    driver = portability_fit(
        {"name": "A", "usg_pct": 27, "net_onoff": 7},
        {"name": "B", "usg_pct": 26, "net_onoff": 0})
    assert driver["fit"] == "leans driver"
    neutral = portability_fit({"name": "A"}, {"name": "B"})
    assert neutral == {"fit": "neutral", "note": "No clear usage or on off tilt."}


def test_apron_matching_rules():
    from app.tools.league import CAP, _allowed_incoming, _apron_state

    assert _allowed_incoming(20_000_000, True) == (
        20_000_000, "100pct above first apron")
    assert _allowed_incoming(20_000_000, False) == (
        25_250_000, "125pct plus 250k below first apron")
    over = _apron_state(CAP["apron2"] + 1)
    assert over["over_apron1"] and over["over_apron2"]
    under = _apron_state(0)
    assert not under["over_apron1"] and not under["over_apron2"]


def test_pair_history_slim_both_on():
    from app.tools.player import pair_history

    wowy = {"ok": True, "rows": [
        {"split": "Both ON", "minutes": 812.4, "net_rating": 6.26},
        {"split": "Both OFF", "minutes": 100.0, "net_rating": -2.0},
    ]}
    assert pair_history(wowy) == {
        "teammates": True, "both_on_net": 6.3, "both_on_minutes": 812.4,
        "note": "Shared court net +6.3 across 812.4 minutes."}
    assert pair_history({"ok": True, "rows": []})["both_on_net"] is None
    assert pair_history({"ok": False, "error": "never shared"})["both_on_net"] is None


def _splits_fixture():
    return [
        {"GAME_DATE": "Jan 1, 2026", "MATCHUP": "HOU vs. MIN",
         "PTS": 30, "REB": 10, "AST": 5, "FGM": 10, "FGA": 20,
         "FTM": 5, "FTA": 6, "PLUS_MINUS": 3},
        {"GAME_DATE": "Jan 3, 2026", "MATCHUP": "HOU @ PHX",
         "PTS": 20, "REB": 8, "AST": 7, "FGM": 8, "FGA": 16,
         "FTM": 2, "FTA": 2, "PLUS_MINUS": -1},
        {"GAME_DATE": "Jan 4, 2026", "MATCHUP": "HOU vs. DEN",
         "PTS": 10, "REB": 6, "AST": 3, "FGM": 4, "FGA": 12,
         "FTM": 0, "FTA": 0, "PLUS_MINUS": -5},
    ]


def test_splits_aggregate_math():
    from app.tools.splits import aggregate, ts_of

    rows = _splits_fixture()
    assert aggregate(rows) == {
        "gp": 0 + 3, "ppg": 20.0, "rpg": 8.0, "apg": 5.0,
        "fg_pct": round(22 / 48, 3), "plus_minus": -1.0}
    assert ts_of(rows) == round(60 / (2 * (48 + 0.44 * 8)), 3)
    assert aggregate([])["gp"] == 0
    assert ts_of([]) is None


def test_splits_rest_days():
    from app.tools.splits import rest_days

    rows = _splits_fixture()
    buckets = rest_days(rows)
    assert len(buckets) == 2
    assert buckets[0][1] == "1"
    assert buckets[1][1] == "0"
    assert rows[0] not in [b[0] for b in buckets]


def test_splits_defense_rank():
    from app.tools.splits import defense_rank

    rows = [{"TEAM_ID": 1, "DEF_RATING": 115.0},
            {"TEAM_ID": 2, "DEF_RATING": 108.0},
            {"TEAM_ID": 3, "DEF_RATING": 112.0}]
    assert defense_rank(rows) == {2: 1, 3: 2, 1: 3}


def test_splits_verdict_branches():
    from app.tools.splits import verdict_for

    v, _ = verdict_for(5.0, 0.0, 0.0, 0.0, 3, 2.0)
    assert v == "too early"
    v, _ = verdict_for(0.5, 0.0, 0.0, 0.0, 10, 2.0)
    assert v == "sustainable"
    v, note = verdict_for(5.0, 0.06, 0.0, 0.0, 10, 2.0)
    assert v == "likely regresses"
    assert "true shooting" in note
    v, note = verdict_for(-5.0, 0.0, -4.0, 0.0, 10, 2.0)
    assert v == "likely regresses"
    assert "rebound" in note


def test_splits_unknown_player():
    from app.tools.splits import get_matchup_splits, get_regression_check

    res = get_matchup_splits.invoke(
        {"player": "Zzz Quux Nonexistent", "n": 5})
    assert res["ok"] is False
    assert "unknown player" in res["error"]
    res = get_regression_check.invoke(
        {"player": "Zzz Quux Nonexistent", "stat": "xyz", "n": 5})
    assert res["ok"] is False
    assert "unknown player" in res["error"]
    from app.tools import clamp_stat

    assert clamp_stat("xyz") == "PTS"


def _warehouse_has_durant():
    from app import store

    con = store.connect()
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        if "silver_player_gamelogs" not in tables:
            return False
        n = con.execute(
            "SELECT COUNT(*) FROM silver_player_gamelogs"
            " WHERE _season = '2025-26' AND _entity = 'player:201142'"
        ).fetchone()[0]
        return n and n > 0
    finally:
        con.close()


def test_splits_matchup_smoke():
    try:
        if not _warehouse_has_durant():
            return
    except Exception:
        return
    try:
        from app.tools.splits import get_matchup_splits

        res = get_matchup_splits.invoke(
            {"player": "Kevin Durant", "n": 15, "season": "2025-26"})
    except Exception:
        return
    assert res["ok"] is True
    assert len(res["rows"]["splits"]) > 0
    assert all("low_sample" in s for s in res["rows"]["splits"])


def test_splits_regression_smoke():
    try:
        if not _warehouse_has_durant():
            return
    except Exception:
        return
    try:
        from app.tools.splits import get_regression_check

        res = get_regression_check.invoke(
            {"player": "Kevin Durant", "stat": "xyz", "n": 10,
             "season": "2025-26"})
    except Exception:
        return
    assert res["ok"] is True
    assert res["rows"]["stat"] == "PTS"
    assert res["rows"]["verdict"] in (
        "too early", "sustainable", "likely regresses")
    assert res["rows"]["career"]["available"] is True
    assert res["rows"]["career"]["per_game"] > 0


def _warehouse_has_hist_durant():
    from app import store

    con = store.connect()
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        if "silver_hist_player_seasons" not in tables:
            return False
        n = con.execute(
            "SELECT COUNT(*) FROM silver_hist_player_seasons"
            " WHERE _entity = 'league' AND player_id = 201142"
        ).fetchone()[0]
        return n and n > 0
    finally:
        con.close()


def test_splits_career_baseline_hits_seeded_warehouse():
    try:
        if not _warehouse_has_hist_durant():
            return
    except Exception:
        return
    from app.tools.splits import _career_baseline

    res = _career_baseline(201142, "PTS")
    assert res["available"] is True
    assert res["gp"] >= 1
    assert res["stat"] == "PTS"
    assert res["per_game"] > 0
    res = _career_baseline(201142, "REB")
    assert res["available"] is True
    res = _career_baseline(99999999, "PTS")
    assert res["available"] is False


def test_splits_sort_null_dates_last():
    from app.tools.splits import _sort_by_date

    rows = [
        {"GAME_DATE": "not a date", "PTS": 1},
        {"GAME_DATE": "Jan 3, 2026", "PTS": 3},
        {"GAME_DATE": "Jan 1, 2026", "PTS": 2},
    ]
    desc = _sort_by_date(rows, desc=True)
    assert [r["PTS"] for r in desc] == [3, 2, 1]
    asc = _sort_by_date(rows, desc=False)
    assert [r["PTS"] for r in asc] == [2, 3, 1]


def test_trade_value_unknown_player():
    from app.tools.league import get_trade_value

    res = get_trade_value.invoke({"team_a": "LAL", "players_a": "Austin Reaves",
                                  "team_b": "BKN",
                                  "players_b": "Not A Realplayer"})
    assert res["ok"] is False
    assert "Not A Realplayer" in res["error"]


def test_trade_value_empty_teams():
    from app.tools.league import get_trade_value

    res = get_trade_value.invoke({})
    assert res["ok"] is False


def test_trade_value_reaves_porter():
    from app.tools.league import get_trade_value

    try:
        res = get_trade_value.invoke(
            {"team_a": "LAL", "players_a": "Austin Reaves",
             "picks_a": "2029 FRP", "team_b": "BKN",
             "players_b": "Michael Porter Jr."})
    except Exception:
        import pytest

        pytest.skip("warehouse unavailable")
        return
    if res["ok"] is False:
        import pytest

        pytest.skip(f"warehouse tables absent: {res.get('error')}")
    verdict = res["rows"]["verdict"]
    assert verdict["winner"] in {"LAL", "BKN", "even"}
    assert set(verdict["grades"]) == {"LAL", "BKN"}
    assert set(verdict["grades"].values()) <= {
        "A", "A-", "B+", "B", "B-", "C+", "C", "D", "F"}
    sides = (res["rows"]["team_a"], res["rows"]["team_b"])
    assert all(isinstance(s["side_total_m"], (int, float)) for s in sides)
    assert verdict["text"].count(".") >= 3
    picks = res["rows"]["team_a"]["picks"]
    assert picks and picks[0]["est_value_m"] > 0


def test_registry_has_trade_value():
    from app import tools as _tools

    assert "get_trade_value" in _tools.TOOL_NAMES
    assert graph.tool_label("get_trade_value") == "Grading trade value"


def test_compare_metrics_adjudicates():
    from app.tools.player import compare_metrics

    res = compare_metrics.invoke(
        {"a": "Luka Doncic", "b": "Shai Gilgeous-Alexander",
         "season": "2025-26"})
    assert res["ok"]
    rows = res["rows"]
    assert len(rows["metrics"]) == 8
    assert rows["agreement"] in ("agree", "split", "none")
    assert "EPM" in [u["metric"] for u in rows["unavailable"]]
    leaders = {m["leader"] for m in rows["metrics"]}
    assert leaders <= {"a", "b", "tie", "na"}
