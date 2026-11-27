import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(BACKEND / "analyst"))

from shared.tools import argnorm


@pytest.mark.parametrize(("raw", "want"), [
    ("2024-25", "2024-25"),
    ("2024/25", "2024-25"),
    ("2024–25", "2024-25"),
    ("2024_25", "2024-25"),
    ("2024.25", "2024-25"),
    ("2024 25", "2024-25"),
    ("season 2024-25", "2024-25"),
    ("the 2024/25 season", "2024-25"),
    ("25-26", "2025-26"),
    ("2024-2025", "2024-25"),
    ("2025", "2025"),
])
def test_canonical_season_forms(raw, want):
    assert argnorm.canonical_season(raw) == want


def test_canonical_season_range_is_a_miss():
    with pytest.raises(argnorm.ArgMiss) as err:
        argnorm.canonical_season("2021-23")
    assert err.value.kind == "season"
    assert "2021-22" in err.value.candidates


@pytest.mark.parametrize("raw", ["abc", "20245", "next year", ""])
def test_canonical_season_rejects_garbage(raw):
    assert argnorm.canonical_season(raw) is None


@pytest.mark.parametrize(("raw", "want"), [
    ("3/5/2024", "03/05/2024"),
    ("03/05/2024", "03/05/2024"),
    ("3-5-24", "03/05/2024"),
    ("2024-03-05", "03/05/2024"),
    ("Mar 5 2024", "03/05/2024"),
])
def test_canonical_date_us(raw, want):
    assert argnorm.canonical_date(raw) == want


@pytest.mark.parametrize(("raw", "want"), [
    ("2024-3-5", "2024-03-05"),
    ("3/5/2024", "2024-03-05"),
    ("2024-03-05", "2024-03-05"),
])
def test_canonical_date_iso(raw, want):
    assert argnorm.canonical_date_iso(raw) == want


def test_normalize_call_args_season_and_team():
    out = argnorm.normalize_call_args(
        "get_team_season", {"season": "2024/25", "team": "Boston Celtics"})
    assert out["season"] == "2024-25"
    assert out["team"] == "Boston Celtics"


def test_normalize_call_args_unknown_fields_passthrough():
    out = argnorm.normalize_call_args("get_x", {"foo": "bar", "limit": 5})
    assert out == {"foo": "bar", "limit": 5}


def test_normalize_call_args_player_team_prefixed_id():
    out = argnorm.normalize_call_args("get_x", {"player": "MEM:203912"})
    assert out["player"] == 203912


def test_normalize_call_args_player_miss_structured():
    with pytest.raises(argnorm.ArgMiss) as err:
        argnorm.normalize_call_args("get_x", {"player": "Zqx Notaplayer"})
    payload = err.value.payload()
    assert payload["kind"] == "player"
    assert payload["field"] == "player"


def test_normalize_call_args_blank_team_passthrough():
    out = argnorm.normalize_call_args("get_x", {"team": ""})
    assert out["team"] == ""


def test_normalize_call_args_league_scope_team_structured():
    with pytest.raises(argnorm.ArgMiss) as err:
        argnorm.normalize_call_args("get_x", {"team": "league"})
    assert err.value.payload()["kind"] == "team"


def test_normalize_call_args_season_miss():
    with pytest.raises(argnorm.ArgMiss) as err:
        argnorm.normalize_call_args("get_x", {"season": "2021-23"})
    assert "2021-22" in err.value.candidates


def test_normalize_call_args_bare_year_passthrough():
    out = argnorm.normalize_call_args("get_x", {"season": "2025"})
    assert out["season"] == "2025"


def test_normalize_call_args_season_list():
    out = argnorm.normalize_call_args("get_x", {"seasons": "2023-24,2024/25"})
    assert out["seasons"] == "2023-24, 2024-25"


def test_arg_miss_result_shape():
    miss = argnorm.ArgMiss("team", "team", "Team", ["BOS", "NYK"])
    result = argnorm.arg_miss_result("get_x", miss)
    assert result["ok"] is False
    assert result["arg_miss"]["did_you_mean"] == ["BOS", "NYK"]


def test_param_kinds_override_a_b():
    kinds = {"get_matchup_brief": {"a": "team", "b": "team"}}
    out = argnorm.normalize_call_args(
        "get_matchup_brief", {"a": "BOS", "b": "New York Knicks"}, kinds)
    assert out["a"] == "BOS"


def test_param_kinds_date_iso():
    kinds = {"get_transactions": {"start": "date_iso"}}
    out = argnorm.normalize_call_args(
        "get_transactions", {"start": "3/5/2024"}, kinds)
    assert out["start"] == "2024-03-05"


def test_norm_name_strips_punctuation():
    from shared.tools._core import _norm_name
    assert _norm_name("Tim Hardaway Jr.") == _norm_name("Tim Hardaway Jr")


def test_coerce_player_id_team_prefix():
    from shared.tools._core import coerce_player_id
    assert coerce_player_id("MEM:203912") == 203912


def test_field_kind_default_and_override():
    assert argnorm.field_kind("anything", "season") == "season"
    assert argnorm.field_kind("get_shot_compare", "a",
                              {"get_shot_compare": {"a": "player"}}) == "player"
    assert argnorm.field_kind("anything", "zzz") is None

def test_numbered_player_parts_consolidate_into_players():
    from shared.tools.argnorm import normalize_call_args
    out = normalize_call_args("get_lineup_on_off", {
        "team": "DEN", "player_1": "Nikola Jokic", "player_2": "Jamal Murray", "season": "2024-25",
    }, None)
    assert out["players"] == "Nikola Jokic, Jamal Murray"
    assert "player_1" not in out and "player_2" not in out

def test_lettered_player_parts_left_for_tool_schema():
    from shared.tools.argnorm import normalize_call_args
    out = normalize_call_args("get_lineup_on_off", {
        "team": "MEM", "player_a": "Desmond Bane", "player_b": "Ja Morant",
    }, None)
    assert "players" not in out
    assert out["player_a"] == "Desmond Bane"

def test_single_numbered_part_not_consolidated():
    from shared.tools.argnorm import normalize_call_args
    out = normalize_call_args("get_lineup_on_off", {"player_1": "Solo"}, None)
    assert "players" not in out
    assert out["player_1"] == "Solo"


def test_product_compare_id_season_specs_survive_normalization():
    kinds = {"product_compare": {"players": "player_season_spec_list"}}
    out = argnorm.normalize_call_args(
        "product_compare",
        {"players": "1628369:2025-26,203999:2025-26"},
        kinds)
    assert out["players"] == "1628369:2025-26, 203999:2025-26"


def test_product_compare_spec_season_is_canonicalized():
    kinds = {"product_compare": {"players": "player_season_spec_list"}}
    out = argnorm.normalize_call_args(
        "product_compare",
        {"players": "1628369:2025/26"},
        kinds)
    assert out["players"] == "1628369:2025-26"


def test_product_compare_spec_rejects_names_and_bad_ids():
    kinds = {"product_compare": {"players": "player_season_spec_list"}}
    with pytest.raises(argnorm.ArgMiss):
        argnorm.normalize_call_args(
            "product_compare", {"players": "Jayson Tatum:2025-26"}, kinds)
    with pytest.raises(argnorm.ArgMiss):
        argnorm.normalize_call_args(
            "product_compare", {"players": "1628369:not-a-season"}, kinds)


def test_product_compare_manifest_wiring():
    import json
    manifest = json.loads((BACKEND / "analyst" / "tools" / "manifest.json").read_text())
    kinds = {tool: dict(fields) for tool, fields in manifest.get("param_kinds", {}).items()}
    out = argnorm.normalize_call_args(
        "product_compare",
        {"players": "1628369:2025-26,203999:2025-26"},
        kinds)
    assert out["players"] == "1628369:2025-26, 203999:2025-26"
