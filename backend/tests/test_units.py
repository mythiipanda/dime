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
    assert resolve_model_id(None) == ("inception", "mercury-2.5")


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
    name, model = resolve_model_id("LeBron James")
    assert (name, model) == ("inception", "mercury-2.5")


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
        "ratings", "playoffs",
    }


def test_resolve_entity_static():
    res = tools.resolve_entity.invoke({"query": "LeBron James"})
    ids = [p.get("id") for p in res["rows"]["players"]]
    assert 2544 in ids
