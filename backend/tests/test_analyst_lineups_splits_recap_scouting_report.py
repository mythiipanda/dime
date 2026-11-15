import asyncio
import importlib
import re
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(BACKEND / "analyst"))

from analyst import python_tools  # noqa: E402
import shared.tools.player as player_module  # noqa: E402
import shared.tools.team as team_module  # noqa: E402

LINEUP_ROW = {
    "GROUP_ID": "101-102-103-104-105",
    "GROUP_NAME": "A. Star-B. Guard-C. Wing-D. Big-E. Center",
    "TEAM_ID": 1610612747,
    "TEAM_ABBREVIATION": "BOS",
    "GP": 38,
    "MIN": 912.4,
    "PTS": 806,
    "PLUS_MINUS": 118.4,
    "FGA": 690.0,
    "OREB": 41.0,
    "TOV": 78.0,
    "FTA": 142.0,
    "SAMPLE_TIER": "medium",
    "EST_POSS": 1825,
    "competitive_net": 6.5,
    "competitive_poss": 1825,
}

SMALL_LINEUP_ROW = {
    **LINEUP_ROW,
    "GROUP_ID": "106-107-108-109-110",
    "GROUP_NAME": "A. Star-B. Guard-C. Wing-F. Bench-G. Rookie",
    "MIN": 42.0,
    "SAMPLE_TIER": "small",
    "SAMPLE": "small: under ~100 possessions",
    "EST_POSS": 84,
    "competitive_net": None,
    "competitive_poss": 0,
}

SPLIT_ROW = {"split": "home", "GP": 30, "PPG": 28.4, "FG_PCT": 0.471}
SPLIT_ROW_WITHOUT_FG = {"split": "vs top-10 defense", "GP": 22, "PPG": 27.2}

RECAP_ROW = {"PLAYER": "A. Star", "TEAM": "BOS", "PTS": 34, "REB": 8, "AST": 6}

SCOUTING_TOP_LINEUP = {
    "GROUP_NAME": "A. Star-B. Guard-C. Wing-D. Big-E. Center",
    "MIN": 912.4,
    "PLUS_MINUS": 118.4,
}

SCOUTING_ROWS = {
    "record": "41-24",
    "games_sample": 65,
    "top_lineup": dict(SCOUTING_TOP_LINEUP),
}

LIST_TOOLS = (
    {
        "name": "get_lineups",
        "module": "shared.tools.team",
        "attribute": "get_lineups",
        "arguments": {"team_id": 1610612747, "season": "2024-25"},
        "rows": [LINEUP_ROW, SMALL_LINEUP_ROW],
        "default_columns": ["GROUP_NAME", "MIN", "PLUS_MINUS", "SAMPLE_TIER",
                            "EST_POSS", "competitive_net", "competitive_poss"],
    },
    {
        "name": "get_splits",
        "module": "shared.tools.player",
        "attribute": "get_splits",
        "arguments": {"player_id": 424242, "season": "2024-25"},
        "rows": [SPLIT_ROW, SPLIT_ROW_WITHOUT_FG],
        "default_columns": ["split", "GP", "PPG", "FG_PCT"],
    },
    {
        "name": "get_recap",
        "module": "shared.tools.team",
        "attribute": "get_recap",
        "arguments": {"game_id": "0022400001", "season": "2024-25"},
        "rows": [RECAP_ROW],
        "default_columns": ["PLAYER", "TEAM", "PTS", "REB", "AST"],
    },
)

SCOUTING_SPEC = {
    "name": "get_scouting_report",
    "module": "shared.tools.team",
    "attribute": "get_scouting_report",
    "arguments": {"team_id": 1610612747, "season": "2024-25"},
    "default_columns": ["section", "value", "GROUP_NAME", "MIN", "PLUS_MINUS"],
}

UPSTREAM_SCHEMAS = {
    "get_lineups": team_module.get_lineups.args_schema.model_json_schema(),
    "get_splits": player_module.get_splits.args_schema.model_json_schema(),
    "get_recap": team_module.get_recap.args_schema.model_json_schema(),
    "get_scouting_report": team_module.get_scouting_report.args_schema.model_json_schema(),
}


class _FakeTool:
    def __init__(self, description: str, result=None, exc: Exception | None = None):
        self.description = description
        self._result = result
        self._exc = exc
        self.calls: list[dict] = []

    def invoke(self, args):
        self.calls.append(args)
        if self._exc is not None:
            raise self._exc
        return self._result


def _catalogue(monkeypatch, stubs: dict[tuple[str, str], object] | None = None):
    for (module_name, attribute), stub in (stubs or {}).items():
        module = importlib.import_module(module_name)
        monkeypatch.setattr(module, attribute, stub)
    return python_tools.catalogue()


def _invoke(tool, arguments: dict):
    return asyncio.run(tool.ainvoke(arguments))


def _stub(spec, result=None, exc=None) -> _FakeTool:
    return _FakeTool(f"{spec['name']} stub", result=result, exc=exc)


def test_list_tools_success_returns_rows_and_columns(monkeypatch):
    for spec in LIST_TOOLS:
        fake = _stub(spec, result={
            "tool": spec["name"],
            "ok": True,
            "rows": [dict(row) for row in spec["rows"]],
            "meta": {"source": "warehouse", "season": "2024-25"},
        })
        tools = _catalogue(monkeypatch, {(spec["module"], spec["attribute"]): fake})

        res = _invoke(tools[spec["name"]], spec["arguments"])

        assert res["ok"] is True, spec["name"]
        assert isinstance(res["rows"], list), spec["name"]
        assert res["rows"], spec["name"]
        for row in res["rows"]:
            assert isinstance(row, dict), spec["name"]
        assert res["columns"] == list(res["rows"][0].keys()), spec["name"]
        emitted = {key for row in res["rows"] for key in row}
        assert set(res["columns"]) <= emitted, spec["name"]
        assert res["tool"] == spec["name"], spec["name"]
        assert res["meta"]["source"] == "warehouse", spec["name"]
        assert res["meta"]["season"] == "2024-25", spec["name"]
        assert fake.calls == [spec["arguments"]], spec["name"]


def test_lineups_rows_keep_the_upstream_lineup_keys(monkeypatch):
    spec = LIST_TOOLS[0]
    fake = _stub(spec, result={
        "tool": spec["name"],
        "ok": True,
        "rows": [dict(row) for row in spec["rows"]],
        "meta": {"source": "warehouse"},
    })
    tools = _catalogue(monkeypatch, {(spec["module"], spec["attribute"]): fake})

    res = _invoke(tools[spec["name"]], spec["arguments"])

    assert res["rows"][0] == LINEUP_ROW
    assert res["rows"][1]["SAMPLE_TIER"] == "small"
    assert res["rows"][1]["SAMPLE"] == "small: under ~100 possessions"
    for key in ("GROUP_NAME", "MIN", "PLUS_MINUS", "SAMPLE_TIER", "EST_POSS",
                "competitive_net", "competitive_poss"):
        assert key in res["columns"], key


def test_splits_rows_keep_the_upstream_split_keys(monkeypatch):
    spec = LIST_TOOLS[1]
    fake = _stub(spec, result={
        "tool": spec["name"],
        "ok": True,
        "rows": [dict(row) for row in spec["rows"]],
        "meta": {"source": "warehouse"},
    })
    tools = _catalogue(monkeypatch, {(spec["module"], spec["attribute"]): fake})

    res = _invoke(tools[spec["name"]], spec["arguments"])

    assert res["rows"][0] == SPLIT_ROW
    assert res["rows"][1] == SPLIT_ROW_WITHOUT_FG
    assert res["columns"] == ["split", "GP", "PPG", "FG_PCT"]


def test_recap_rows_keep_the_upstream_boxscore_keys(monkeypatch):
    spec = LIST_TOOLS[2]
    fake = _stub(spec, result={
        "tool": spec["name"],
        "ok": True,
        "rows": [dict(row) for row in spec["rows"]],
        "meta": {"source": "nba_api", "rows": 1},
    })
    tools = _catalogue(monkeypatch, {(spec["module"], spec["attribute"]): fake})

    res = _invoke(tools[spec["name"]], spec["arguments"])

    assert res["rows"] == [RECAP_ROW]
    assert res["columns"] == ["PLAYER", "TEAM", "PTS", "REB", "AST"]
    assert res["meta"]["source"] == "nba_api"
    assert res["meta"]["rows"] == 1


def test_scouting_report_flattens_sections_to_rows_array(monkeypatch):
    spec = SCOUTING_SPEC
    fake = _stub(spec, result={
        "tool": spec["name"],
        "ok": True,
        "rows": dict(SCOUTING_ROWS),
        "meta": {"source": "nba_api", "season": "2024-25"},
    })
    tools = _catalogue(monkeypatch, {(spec["module"], spec["attribute"]): fake})

    res = _invoke(tools[spec["name"]], spec["arguments"])

    assert res["ok"] is True
    assert isinstance(res["rows"], list)
    assert [row["section"] for row in res["rows"]] == [
        "record", "games_sample", "top_lineup",
    ]
    assert res["rows"][0] == {"value": "41-24", "section": "record"}
    assert res["rows"][1] == {"value": 65, "section": "games_sample"}
    assert res["rows"][2] == {**SCOUTING_TOP_LINEUP, "section": "top_lineup"}
    assert res["columns"] == list(res["rows"][0].keys())
    assert "section" in res["columns"]
    assert not set(res["columns"]) & set(SCOUTING_ROWS)
    assert res["meta"]["source"] == "nba_api"
    assert fake.calls == [spec["arguments"]]


def test_scouting_report_section_key_cannot_be_overwritten_by_upstream(monkeypatch):
    spec = SCOUTING_SPEC
    fake = _stub(spec, result={
        "tool": spec["name"],
        "ok": True,
        "rows": {
            "record": "41-24",
            "games_sample": 65,
            "top_lineup": {
                "section": "upstream-hijack",
                "GROUP_NAME": "A. Star-B. Guard-C. Wing-D. Big-E. Center",
                "MIN": 912.4,
                "PLUS_MINUS": 118.4,
            },
        },
        "meta": {"source": "nba_api"},
    })
    tools = _catalogue(monkeypatch, {(spec["module"], spec["attribute"]): fake})

    res = _invoke(tools[spec["name"]], spec["arguments"])

    assert res["rows"][2]["section"] == "top_lineup"
    assert res["rows"][2]["GROUP_NAME"] == SCOUTING_TOP_LINEUP["GROUP_NAME"]
    assert res["rows"][2]["MIN"] == 912.4
    assert res["rows"][2]["PLUS_MINUS"] == 118.4


def test_upstream_error_text_is_preserved(monkeypatch):
    for spec in LIST_TOOLS + (SCOUTING_SPEC,):
        fake = _stub(spec, result={
            "tool": spec["name"],
            "ok": False,
            "error": "upstream refused the request",
            "meta": {"source": "warehouse"},
        })
        tools = _catalogue(monkeypatch, {(spec["module"], spec["attribute"]): fake})

        res = _invoke(tools[spec["name"]], spec["arguments"])

        assert res["ok"] is False, spec["name"]
        assert res["rows"] == [], spec["name"]
        assert isinstance(res["columns"], list), spec["name"]
        assert res["columns"] == spec["default_columns"], spec["name"]
        assert res["error"] == "upstream refused the request", spec["name"]
        assert res["tool"] == spec["name"], spec["name"]
        assert res["meta"]["source"] == "warehouse", spec["name"]


def test_upstream_exception_becomes_actionable_error(monkeypatch):
    for spec in LIST_TOOLS + (SCOUTING_SPEC,):
        fake = _stub(spec, exc=RuntimeError("warehouse unavailable"))
        tools = _catalogue(monkeypatch, {(spec["module"], spec["attribute"]): fake})

        res = _invoke(tools[spec["name"]], spec["arguments"])

        assert res["ok"] is False, spec["name"]
        assert res["rows"] == [], spec["name"]
        assert isinstance(res["columns"], list), spec["name"]
        assert res["columns"] == spec["default_columns"], spec["name"]
        assert res["error"] == "RuntimeError: warehouse unavailable", spec["name"]
        assert res["tool"] == spec["name"], spec["name"]


def test_list_tools_reject_a_non_list_rows_payload(monkeypatch):
    for spec in LIST_TOOLS:
        fake = _stub(spec, result={
            "tool": spec["name"],
            "ok": True,
            "rows": {"unexpected": "shape"},
            "meta": {"source": "warehouse"},
        })
        tools = _catalogue(monkeypatch, {(spec["module"], spec["attribute"]): fake})

        res = _invoke(tools[spec["name"]], spec["arguments"])

        assert res["ok"] is False, spec["name"]
        assert res["rows"] == [], spec["name"]
        assert isinstance(res["columns"], list), spec["name"]
        assert res["columns"] == spec["default_columns"], spec["name"]
        assert f"{spec['name']} returned dict rows, expected a list" in res["error"]
        assert res["tool"] == spec["name"], spec["name"]


def test_scouting_report_rejects_a_non_section_rows_payload(monkeypatch):
    spec = SCOUTING_SPEC
    fake = _stub(spec, result={
        "tool": spec["name"],
        "ok": True,
        "rows": [{"GROUP_NAME": "unit"}],
        "meta": {"source": "nba_api"},
    })
    tools = _catalogue(monkeypatch, {(spec["module"], spec["attribute"]): fake})

    res = _invoke(tools[spec["name"]], spec["arguments"])

    assert res["ok"] is False
    assert res["rows"] == []
    assert isinstance(res["columns"], list)
    assert res["columns"] == spec["default_columns"]
    assert "get_scouting_report returned list rows, expected a section object" in res["error"]


def test_wrapper_input_schema_matches_the_shared_tool(monkeypatch):
    tools = _catalogue(monkeypatch, {})

    for name, upstream_schema in UPSTREAM_SCHEMAS.items():
        assert tools[name].args_schema.model_json_schema() == upstream_schema, name


def test_registry_matches_the_typescript_tool_names(monkeypatch):
    tools = _catalogue(monkeypatch, {})

    source = (BACKEND / "analyst" / "python-tools.ts").read_text(encoding="utf-8")
    block = source.split(
        "export const ANALYST_TOOL_NAMES: readonly PythonToolName[] = [", 1)[1]
    block = block.split("] as const;", 1)[0]
    declared = re.findall(r'"([^"]+)"', block)

    assert len(declared) == 93
    assert list(tools.keys()) == declared
    for name in ("get_lineups", "get_splits", "get_recap", "get_scouting_report"):
        assert name in tools
        assert tools[name].args_schema.model_json_schema()["required"]
