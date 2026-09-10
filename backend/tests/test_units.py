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
        "draft", "raptor", "player_seasons", "schedule",
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
