import asyncio
import json
import importlib
import os
import re
import subprocess
import sys
import threading
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




def _without_descriptions(node):
    if isinstance(node, dict):
        return {k: _without_descriptions(v) for k, v in node.items() if k != "description"}
    if isinstance(node, list):
        return [_without_descriptions(v) for v in node]
    return node


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


class _BlockingTool:
    def __init__(self, release: threading.Event):
        self.description = "get_recap blocking stub"
        self._release = release
        self.calls: list[dict] = []

    def invoke(self, args):
        self.calls.append(args)
        self._release.wait(30)
        return {"tool": "get_recap", "ok": True, "rows": [dict(RECAP_ROW)]}


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


def test_recap_timeout_returns_a_structured_error(monkeypatch):
    release = threading.Event()
    fake = _BlockingTool(release)
    monkeypatch.setattr(python_tools, "LIVE_CALL_TIMEOUT_S", 0.1)
    tools = _catalogue(monkeypatch, {("shared.tools.team", "get_recap"): fake})
    try:
        res = _invoke(tools["get_recap"],
                      {"game_id": "0022400001", "season": "2024-25"})
    finally:
        release.set()

    assert res["ok"] is False
    assert res["rows"] == []
    assert isinstance(res["columns"], list)
    assert res["columns"] == ["PLAYER", "TEAM", "PTS", "REB", "AST"]
    assert res["tool"] == "get_recap"
    assert res["error"] == (
        "get_recap timed out after 0.1s: the upstream source is a live "
        "stats.nba.com call, not the warehouse. Retry later, or answer "
        "from the warehouse-backed get_boxscore tool."
    )
    assert fake.calls == [{"game_id": "0022400001", "season": "2024-25"}]


def _bridge_budget_ms():
    source = (BACKEND / "analyst" / "python-tools.ts").read_text(encoding="utf-8")
    match = re.search(r"requestTimeoutMs:\s*(\d+)", source)
    assert match
    return int(match.group(1))


def test_recap_timeout_budget_stays_inside_the_bridge_budget():
    budget_ms = _bridge_budget_ms()

    assert python_tools.LIVE_CALL_TIMEOUT_S * 1000 < budget_ms
    assert budget_ms - python_tools.LIVE_CALL_TIMEOUT_S * 1000 >= 3000


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
        emitted = tools[name].args_schema.model_json_schema()
        assert _without_descriptions(emitted) == _without_descriptions(upstream_schema), name


def test_registry_matches_the_typescript_tool_names(monkeypatch):
    tools = _catalogue(monkeypatch, {})

    manifest = json.loads((BACKEND / "analyst" / "tools" / "manifest.json").read_text(encoding="utf-8"))
    declared = [t["name"] for t in manifest["tools"]]

    assert len(declared) == 117
    assert len(declared) == len(tools)
    assert list(tools.keys()) == declared
    for name in ("get_lineups", "get_splits", "get_recap", "get_scouting_report"):
        assert name in tools
        assert tools[name].args_schema.model_json_schema()["required"]


def test_network_inventory_derives_real_warehouse_alternatives(monkeypatch):
    manifest = json.loads((BACKEND / "analyst" / "tools" / "manifest.json").read_text(encoding="utf-8"))
    declared = [t["name"] for t in manifest["tools"]]
    tools = _catalogue(monkeypatch, {})

    assert len(python_tools.NETWORK_TOOL_SOURCES) == 36
    assert set(python_tools.NETWORK_TOOL_SOURCES) <= set(declared)
    assert python_tools.LIVE_ONLY_TOOLS == {"get_recap": "get_boxscore"}
    for name in python_tools.NETWORK_TOOL_SOURCES:
        _source, alternative = python_tools._network_meta(name)
        assert alternative in declared
        assert alternative != name
        assert alternative in tools
        assert (alternative == "get_boxscore"
                or tools[alternative].description.endswith(
                    "Warehouse-backed with live fallback.")), name
        error = python_tools._timeout_error(name)
        assert alternative in error, name
        assert "the warehouse read is unavailable right now" not in error, name
        assert python_tools.NETWORK_TOOL_SOURCES[name]


def test_network_tool_descriptions_state_backing(monkeypatch):
    tools = _catalogue(monkeypatch, {})
    for name in python_tools.NETWORK_TOOL_SOURCES:
        description = tools[name].description
        if name in python_tools.LIVE_ONLY_TOOLS:
            assert description.endswith("Live only."), name
        else:
            assert description.endswith("Warehouse-backed with live fallback."), name


def test_live_timeout_error_template():
    text = python_tools._live_timeout_error("get_recap", "stats.nba.com", "get_boxscore")

    assert text == (
        f"get_recap timed out after {python_tools.LIVE_CALL_TIMEOUT_S:.1f}s: "
        "the upstream source is a live stats.nba.com call, not the warehouse. "
        "Retry later, or answer from the warehouse-backed get_boxscore tool."
    )


def test_import_does_not_pollute_process_env():
    code = (
        "import os, sys;"
        "os.environ.pop('DIME_LIVE_ATTEMPTS', None);"
        f"sys.path.insert(0, {str(BACKEND)!r});"
        f"sys.path.insert(0, {str(BACKEND / 'analyst')!r});"
        "import analyst.python_tools;"
        "assert 'DIME_LIVE_ATTEMPTS' not in os.environ"
    )
    proc = subprocess.run([sys.executable, "-c", code], cwd=str(BACKEND),
                          capture_output=True, text=True)

    assert proc.returncode == 0, proc.stderr


def test_single_live_attempt_when_configured(monkeypatch):
    import shared.sources.base as base
    from shared.config import settings

    assert python_tools.LIVE_CALL_TIMEOUT_S >= settings.default_timeout_seconds
    monkeypatch.setenv("DIME_LIVE_ATTEMPTS", "1")
    calls: list[int] = []

    def _blocked():
        calls.append(1)
        raise RuntimeError("blocked upstream")

    result = base.safe("stub", "2025-26", _blocked)

    assert calls == [1]
    assert result.ok is False


def test_bridge_tool_description_mutation_stays_private(monkeypatch):
    tools = _catalogue(monkeypatch, {})

    for name in ("get_boxscore", "get_games_on_date"):
        bridge_tool = tools[name]
        shared_tool = getattr(team_module, name)
        suffix = ("Live only." if name in python_tools.LIVE_ONLY_TOOLS
                  else "Warehouse-backed with live fallback.")
        assert bridge_tool is not shared_tool, name
        assert bridge_tool.description.endswith(suffix), name
        assert not shared_tool.description.endswith(suffix), name
        before = shared_tool.description
        bridge_tool.description = bridge_tool.description + " bridge-local"
        assert shared_tool.description == before, name


def test_bridge_clone_keeps_all_names_and_schemas(monkeypatch):
    tools = _catalogue(monkeypatch, {})
    manifest = json.loads((BACKEND / "analyst" / "tools" / "manifest.json").read_text(encoding="utf-8"))
    declared = [t["name"] for t in manifest["tools"]]

    assert len(declared) == 117
    assert len(declared) == len(tools)
    assert list(tools.keys()) == declared
    for name, upstream_schema in UPSTREAM_SCHEMAS.items():
        emitted = tools[name].args_schema.model_json_schema()
        assert _without_descriptions(emitted) == _without_descriptions(upstream_schema), name


def test_timeout_error_text_for_each_tool_kind():
    manifest = json.loads((BACKEND / "analyst" / "tools" / "manifest.json").read_text(encoding="utf-8"))
    declared = {t["name"] for t in manifest["tools"]}
    elapsed = f"{python_tools.LIVE_CALL_TIMEOUT_S:.1f}s"

    assert python_tools._timeout_error("get_recap") == (
        f"get_recap timed out after {elapsed}: the upstream source is a live "
        "stats.nba.com call, not the warehouse. Retry later, or answer "
        "from the warehouse-backed get_boxscore tool."
    )
    assert python_tools._timeout_error("get_splits") == (
        f"get_splits timed out after {elapsed}: the upstream source is a live "
        "stats.nba.com call, not the warehouse. Retry later, or answer "
        "from the warehouse-backed get_dataset tool."
    )
    assert python_tools._timeout_error("sql_exec") == (
        f"sql_exec timed out after {elapsed}; "
        "the read did not complete in time; retry later"
    )
    for alternative in python_tools.LIVE_ONLY_TOOLS.values():
        assert alternative in declared


def test_live_source_labels_produce_clean_error_text():
    elapsed = f"{python_tools.LIVE_CALL_TIMEOUT_S:.1f}s"
    board = python_tools._timeout_error("get_draft_board")
    dataset = python_tools._timeout_error("get_dataset")
    draft_model = python_tools._timeout_error("get_draft_model")

    assert "barttorvik college stats" in board
    assert board == (
        f"get_draft_board timed out after {elapsed}: the upstream source is a live "
        "barttorvik college stats call, not the warehouse. Retry later, or answer "
        "from the warehouse-backed get_dataset tool."
    )
    assert dataset.count("a live ") == 1
    assert "live live" not in dataset
    assert dataset == (
        f"get_dataset timed out after {elapsed}: the upstream source is a live "
        "upstream sources call, not the warehouse. Retry later, or answer "
        "from the warehouse-backed get_boxscore tool."
    )
    assert draft_model.count("a live ") == 1
    assert "live live" not in draft_model
    assert draft_model == (
        f"get_draft_model timed out after {elapsed}: the upstream source is a live "
        "college stats call, not the warehouse. Retry later, or answer "
        "from the warehouse-backed get_dataset tool."
    )


def test_non_network_tool_uses_the_bridge_budget(monkeypatch):
    budget_ms = _bridge_budget_ms()
    assert budget_ms > python_tools.LIVE_CALL_TIMEOUT_S * 1000

    class _Sleeper:
        description = "sleeper"

        def __init__(self, delay):
            self.delay = delay

        async def ainvoke(self, arguments):
            await asyncio.sleep(self.delay)
            return {"tool": "probe", "ok": True, "rows": [], "columns": []}

    monkeypatch.setattr(python_tools, "LIVE_CALL_TIMEOUT_S", 0.01)
    tools = {"sql_exec": _Sleeper(0.05), "get_splits": _Sleeper(0.05)}

    non_network = asyncio.run(
        python_tools._execute_tool_bounded(tools, "sql_exec", {}))
    assert non_network["ok"] is True

    network = asyncio.run(
        python_tools._execute_tool_bounded(tools, "get_splits", {}))
    assert network["ok"] is False
    assert network["error"] == (
        "get_splits timed out after 0.0s: the upstream source is a live "
        "stats.nba.com call, not the warehouse. Retry later, or answer "
        "from the warehouse-backed get_dataset tool."
    )


def test_central_bound_times_out_a_warehouse_backed_tool(monkeypatch):
    release = threading.Event()
    fake = _BlockingTool(release)
    monkeypatch.setattr(python_tools, "LIVE_CALL_TIMEOUT_S", 0.1)
    tools = _catalogue(monkeypatch, {("shared.tools.player", "get_splits"): fake})
    try:
        res = asyncio.run(python_tools._execute_tool_bounded(
            tools, "get_splits", {"player_id": 424242, "season": "2024-25"}))
    finally:
        release.set()

    assert res["tool"] == "get_splits"
    assert res["ok"] is False
    assert res["rows"] == []
    assert isinstance(res["columns"], list)
    assert res["error"] == (
        "get_splits timed out after 0.1s: the upstream source is a live "
        "stats.nba.com call, not the warehouse. Retry later, or answer "
        "from the warehouse-backed get_dataset tool."
    )


def test_warehouse_backed_result_is_byte_identical(monkeypatch):
    spec = LIST_TOOLS[1]
    expected = {
        "tool": "get_splits", "ok": True,
        "rows": [dict(SPLIT_ROW), dict(SPLIT_ROW_WITHOUT_FG)],
        "columns": ["split", "GP", "PPG", "FG_PCT"],
        "meta": {"source": "warehouse", "season": "2024-25"},
    }
    fake = _stub(spec, result={
        "tool": "get_splits", "ok": True,
        "rows": [dict(row) for row in spec["rows"]],
        "meta": {"source": "warehouse", "season": "2024-25"},
    })
    tools = _catalogue(monkeypatch, {(spec["module"], spec["attribute"]): fake})

    res = _invoke(tools["get_splits"], spec["arguments"])

    assert res == expected


ROWLIST_DEFAULT_COLS = ["a", "b"]
LAST_X_DEFAULT_COLS = ["GAME_DATE", "MATCHUP", "PTS", "REB", "AST", "MIN"]


def test_row_list_result_wraps_non_dict_rows_losslessly():
    res = {"tool": "probe", "ok": True, "rows": [{"a": 1}, 7, "x", {"a": 2}]}

    out = python_tools._row_list_result(res, "probe", ROWLIST_DEFAULT_COLS)

    assert out["ok"] is True
    assert out["rows"] == [{"a": 1}, {"value": 7}, {"value": "x"}, {"a": 2}]
    assert out["columns"] == ["a"]
    assert isinstance(out["rows"], list)
    assert isinstance(out["columns"], list)


def test_row_list_result_keeps_all_dict_rows_unchanged():
    raw = [{"a": 1, "b": 2}, {"b": 3, "a": 4}]
    res = {"tool": "probe", "ok": True,
           "rows": [dict(r) for r in raw], "meta": {"source": "warehouse"}}

    out = python_tools._row_list_result(res, "probe", ROWLIST_DEFAULT_COLS)

    assert out["ok"] is True
    assert out["rows"] == raw
    assert out["columns"] == ["a", "b"]
    assert out["meta"] == {"source": "warehouse"}


def test_row_list_result_empty_rows_use_default_columns():
    res = {"tool": "probe", "ok": True, "rows": []}

    out = python_tools._row_list_result(res, "probe", ROWLIST_DEFAULT_COLS)

    assert out["ok"] is True
    assert out["rows"] == []
    assert out["columns"] == ROWLIST_DEFAULT_COLS
    assert isinstance(out["rows"], list)
    assert isinstance(out["columns"], list)


def test_row_list_result_preserves_upstream_error_text():
    res = {"tool": "probe", "ok": False, "error": "upstream refused the request"}

    out = python_tools._row_list_result(res, "probe", ROWLIST_DEFAULT_COLS)

    assert out["ok"] is False
    assert out["rows"] == []
    assert out["columns"] == ROWLIST_DEFAULT_COLS
    assert out["error"] == "upstream refused the request"


def _last_x_spec():
    return {
        "name": "get_last_x",
        "module": "shared.tools.player",
        "attribute": "get_last_x",
        "arguments": {"player_id": 2544, "n": 5, "season": "2024-25"},
        "default_columns": LAST_X_DEFAULT_COLS,
    }


def _invoke_last_x(monkeypatch, result):
    spec = _last_x_spec()
    fake = _stub(spec, result=result)
    tools = _catalogue(monkeypatch, {(spec["module"], spec["attribute"]): fake})
    res = _invoke(tools["get_last_x"], spec["arguments"])
    assert fake.calls == [spec["arguments"]]
    return res


def test_get_last_x_uses_the_same_lossless_row_normalization(monkeypatch):
    res = _invoke_last_x(monkeypatch, {
        "tool": "get_last_x",
        "ok": True,
        "rows": [{"a": 1}, 7, "x", {"a": 2}],
    })

    assert res["ok"] is True
    assert res["rows"] == [{"a": 1}, {"value": 7}, {"value": "x"}, {"a": 2}]
    assert res["columns"] == ["a"]
    assert isinstance(res["rows"], list)
    assert isinstance(res["columns"], list)


def test_get_last_x_keeps_all_dict_rows_and_derives_columns(monkeypatch):
    raw = [{"GAME_DATE": "2026-01-05", "PTS": 30}]
    res = _invoke_last_x(monkeypatch, {
        "tool": "get_last_x",
        "ok": True,
        "rows": [dict(raw[0])],
    })

    assert res["ok"] is True
    assert res["rows"] == raw
    assert res["columns"] == list(raw[0].keys())


def test_get_last_x_empty_rows_use_default_columns(monkeypatch):
    res = _invoke_last_x(monkeypatch, {
        "tool": "get_last_x",
        "ok": True,
        "rows": [],
    })

    assert res["ok"] is True
    assert res["rows"] == []
    assert res["columns"] == LAST_X_DEFAULT_COLS


def test_get_last_x_upstream_error_text_is_preserved(monkeypatch):
    res = _invoke_last_x(monkeypatch, {
        "tool": "get_last_x",
        "ok": False,
        "error": "empty upstream response",
    })

    assert res["ok"] is False
    assert res["rows"] == []
    assert res["columns"] == LAST_X_DEFAULT_COLS
    assert res["error"] == "empty upstream response"


ON_OFF_SPEC = {
    "name": "get_on_off",
    "module": "shared.tools.player",
    "attribute": "get_on_off",
    "arguments": {"player_id": 2544, "team_id": 1610612747, "season": "2024-25"},
}


def test_get_on_off_wraps_non_dict_rows_losslessly(monkeypatch):
    dict_row = {"Stat": "PTS", "On": 110.2, "Off": 105.1, "On-Off": 5.1}
    fake = _stub(ON_OFF_SPEC, result={
        "tool": "get_on_off",
        "ok": True,
        "rows": [dict(dict_row), 42],
    })
    tools = _catalogue(monkeypatch, {(ON_OFF_SPEC["module"], ON_OFF_SPEC["attribute"]): fake})

    res = _invoke(tools["get_on_off"], ON_OFF_SPEC["arguments"])

    assert fake.calls == [ON_OFF_SPEC["arguments"]]
    assert res["ok"] is True
    assert res.get("error") is None
    assert res["rows"] == [dict_row, {"value": 42}]
    assert isinstance(res["rows"], list)
    assert isinstance(res["columns"], list)


DRAFT_BOARD_SPEC = {
    "name": "get_draft_board",
    "module": "shared.tools.league",
    "attribute": "get_draft_board",
    "arguments": {"season": "2025"},
    "rows": [{"rank": 1, "player": "A. Prospect", "pos": "G"}],
    "default_columns": ["rank", "player", "pos", "school", "draft_score", "bpm"],
}

COMBINE_SPEC = {
    "name": "get_combine",
    "module": "shared.tools.league",
    "attribute": "get_combine",
    "arguments": {"season": "2025"},
    "rows": [{"player": "A. Prospect", "pos": "G", "wingspan": 80.5}],
    "default_columns": ["player", "pos", "height_wo_shoes", "height_w_shoes",
                        "weight", "wingspan", "standing_reach"],
}

YOUNG_USAGE_SPEC = {
    "name": "get_young_player_usage",
    "module": "shared.tools.league",
    "attribute": "get_young_player_usage",
    "arguments": {"max_age": 22, "min_minutes": 1000, "season": None},
    "rows": [{"RANK": 1, "PLAYER": "A. Young", "USG_PCT": 28.4}],
    "default_columns": ["RANK", "PLAYER", "TEAM", "AGE", "GP", "MPG", "MINUTES",
                        "USG_PCT"],
}

CATALOGUE_PRECHECK_SPECS = (DRAFT_BOARD_SPEC, COMBINE_SPEC, YOUNG_USAGE_SPEC)


def test_catalogue_draft_combine_usage_reach_upstream_without_nameerror(monkeypatch):
    fakes = {}
    stubs = {}
    for spec in CATALOGUE_PRECHECK_SPECS:
        fake = _stub(spec, result={
            "tool": spec["name"],
            "ok": True,
            "rows": [dict(row) for row in spec["rows"]],
            "meta": {"source": "fixture"},
        })
        fakes[spec["name"]] = fake
        stubs[(spec["module"], spec["attribute"])] = fake
    tools = _catalogue(monkeypatch, stubs)

    for spec in CATALOGUE_PRECHECK_SPECS:
        res = _invoke(tools[spec["name"]], spec["arguments"])

        assert "NameError" not in str(res.get("error")), spec["name"]
        assert res.get("error") is None, spec["name"]
        assert res["ok"] is True, spec["name"]
        assert res["tool"] == spec["name"], spec["name"]
        assert isinstance(res["rows"], list), spec["name"]
        assert res["rows"] == spec["rows"], spec["name"]
        assert isinstance(res["columns"], list), spec["name"]
        assert res["columns"] == list(spec["rows"][0].keys()), spec["name"]
        assert fakes[spec["name"]].calls == [spec["arguments"]], spec["name"]


def test_catalogue_draft_combine_pi_offline_guard_survives(monkeypatch):
    guarded = (DRAFT_BOARD_SPEC, COMBINE_SPEC)
    fakes = {}
    stubs = {}
    for spec in guarded:
        fake = _stub(spec, result={
            "tool": spec["name"],
            "ok": True,
            "rows": [dict(row) for row in spec["rows"]],
        })
        fakes[spec["name"]] = fake
        stubs[(spec["module"], spec["attribute"])] = fake
    tools = _catalogue(monkeypatch, stubs)
    monkeypatch.setenv("PI_OFFLINE", "1")

    for spec in guarded:
        res = _invoke(tools[spec["name"]], spec["arguments"])

        assert "NameError" not in str(res.get("error")), spec["name"]
        assert res["error"] == "RuntimeError: offline mode: live fetching disabled", spec["name"]
        assert res["ok"] is False, spec["name"]
        assert res["rows"] == [], spec["name"]
        assert res["columns"] == spec["default_columns"], spec["name"]
        assert fakes[spec["name"]].calls == [], spec["name"]
