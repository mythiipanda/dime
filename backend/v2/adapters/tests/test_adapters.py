"""Hermetic adapter tests: recorded v1 payloads in, EvidenceEnvelopes out."""
from datetime import datetime, timezone

import pytest

from v2.adapters import (
    CAPABILITIES,
    AdapterError,
    acall_capability,
    build_envelope,
    call_capability,
)
from v2.adapters import coverage
from v2.contracts import EntityRef, EvidenceEnvelope


class FakeTool:
    """Mimics a sync langchain StructuredTool."""

    def __init__(self, payload):
        self.payload = payload
        self.calls = []
        self.coroutine = None

    def invoke(self, arguments):
        self.calls.append(arguments)
        return self.payload


class FakeAsyncTool:
    """Mimics an async-only langchain StructuredTool (e.g. get_compare)."""

    def __init__(self, payload):
        self.payload = payload
        self.coroutine = True

    async def ainvoke(self, arguments):
        return self.payload


STANDINGS_PAYLOAD = {
    "tool": "get_standings",
    "ok": True,
    "rows": [
        {"TeamID": 1610612738, "team": "Boston Celtics", "abbrev": "BOS",
         "Conference": "East", "WINS": 61, "LOSSES": 21, "WinPCT": 0.744,
         "PointsPG": 118.2, "OppPointsPG": 109.4, "DiffPointsPG": 8.8},
        {"TeamID": 1610612747, "team": "Los Angeles Lakers", "abbrev": "LAL",
         "Conference": "West", "WINS": 50, "LOSSES": 32, "WinPCT": 0.610,
         "PointsPG": 114.1, "OppPointsPG": 112.9, "DiffPointsPG": 1.2},
    ],
    "meta": {"source": "warehouse", "season": "2025-26"},
}

LEADERS_PAYLOAD = {
    "tool": "get_leaders",
    "ok": True,
    "rows": [
        {"RANK": 1, "PLAYER": "Luke Kennard", "TEAM": "LAL", "GP": 70,
         "MIN": 1650.5, "FG3M": 180, "FG3A": 377, "FG3_PCT": 0.478,
         "PERCENTILE": 100.0},
    ],
    "meta": {"source": "warehouse", "season": "2025-26",
             "stat_category": "FG3_PCT", "rows": 1,
             "qualification": "82+ made threes"},
}

RESOLVE_PAYLOAD = {
    "tool": "resolve_entity",
    "ok": True,
    "rows": {
        "players": [{"id": 203507, "full_name": "Giannis Antetokounmpo",
                     "score": 0.99}],
        "teams": [{"id": 1610612749, "full_name": "Milwaukee Bucks",
                   "abbreviation": "MIL"}],
        "exact": True,
        "suggestions": [],
    },
    "meta": {"source": "nba_api_static"},
}

ADVANCED_PAYLOAD = {
    "tool": "get_advanced",
    "ok": True,
    "rows": {"PLAYER_NAME": "Jayson Tatum", "TS_PCT": 54.1,
             "EFG_PCT": 49.3, "USG_PCT": 27.8},
    "meta": {"source": "nba_api", "season": "2025-26",
             "units": "percentages on 0-100 scale"},
}

COMPARE_PAYLOAD = {
    "tool": "get_compare",
    "ok": True,
    "rows": {"a": {"player": "Jayson Tatum"}, "b": {"player": "Jaylen Brown"}},
    "meta": {"source": "warehouse", "season": "2025-26"},
}


def test_registry_covers_initial_pack():
    expected = {
        "entity_resolution", "standings", "team_trajectory", "team_totals", "qualified_leaders",
        "team_ratings", "roster", "player_report", "player_evaluation", "player_comparison",
        "metric_adjudication", "metric_coverage", "shots",
        "shooting_efficiency", "on_off", "lineups", "clutch", "playoffs",
        "trades", "trade_value", "contracts", "game_logs", "four_factors",
        "team_four_factors",
    }
    assert set(CAPABILITIES) == expected
    tool_names = [c.tool_name for c in CAPABILITIES.values()]
    assert len(tool_names) == len(set(tool_names))


def test_standings_envelope_shape():
    tool = FakeTool(STANDINGS_PAYLOAD)
    env = call_capability("standings", {"season": "2025-26"},
                          tools={"get_standings": tool})
    assert isinstance(env, EvidenceEnvelope)
    assert tool.calls == [{"season": "2025-26"}]
    assert env.capability == "standings"
    assert env.source == "v1:get_standings:warehouse"
    assert env.season == "2025-26"
    assert env.rows == STANDINGS_PAYLOAD["rows"]
    assert env.units["WinPCT"] == "fraction_0_1"
    assert env.units["WINS"] == "count"
    assert env.observed_at.tzinfo is not None


def test_meta_season_overrides_argument():
    payload = {**STANDINGS_PAYLOAD,
               "meta": {"source": "warehouse", "season": "2024-25"}}
    env = call_capability("standings", {"season": "2024-25"},
                          tools={"get_standings": FakeTool(payload)})
    assert env.season == "2024-25"


def test_evidence_id_is_stable_and_content_addressed():
    args = {"season": "2025-26"}
    first = call_capability("standings", args,
                            tools={"get_standings": FakeTool(STANDINGS_PAYLOAD)})
    second = call_capability("standings", args,
                             tools={"get_standings": FakeTool(STANDINGS_PAYLOAD)})
    assert first.evidence_id == second.evidence_id
    changed = dict(STANDINGS_PAYLOAD)
    changed["rows"] = STANDINGS_PAYLOAD["rows"][:1]
    third = call_capability("standings", args,
                            tools={"get_standings": FakeTool(changed)})
    assert third.evidence_id != first.evidence_id


def test_qualification_prefers_meta_then_capability_default():
    env = call_capability("qualified_leaders",
                          {"stat_category": "FG3_PCT", "season": "2025-26"},
                          tools={"get_leaders": FakeTool(LEADERS_PAYLOAD)})
    assert env.qualification == "82+ made threes"
    no_meta_qual = dict(LEADERS_PAYLOAD)
    no_meta_qual["meta"] = {"source": "warehouse", "season": "2025-26"}
    env = call_capability("qualified_leaders",
                          {"stat_category": "PTS", "season": "2025-26"},
                          tools={"get_leaders": FakeTool(no_meta_qual)})
    assert env.qualification == "Qualified players only (NBA leaderboard minimums)."


def test_entity_resolution_extracts_entity_refs():
    env = call_capability("entity_resolution", {"query": "giannis"},
                          tools={"resolve_entity": FakeTool(RESOLVE_PAYLOAD)})
    kinds = {(e.id, e.type) for e in env.entities}
    assert ("203507", "player") in kinds
    assert ("1610612749", "team") in kinds
    assert env.season is None


def test_async_tool_round_trips():
    env = call_capability("player_comparison",
                          {"a": "Jayson Tatum", "b": "Jaylen Brown",
                           "season": "2025-26"},
                          tools={"get_compare": FakeAsyncTool(COMPARE_PAYLOAD)})
    assert env.rows == COMPARE_PAYLOAD["rows"]


def test_acall_capability_inside_running_loop():
    import asyncio

    async def run():
        return await acall_capability(
            "shooting_efficiency", {"player_id": 1628369, "season": "2025-26"},
            tools={"get_advanced": FakeTool(ADVANCED_PAYLOAD)})

    env = asyncio.run(run())
    assert env.metric_definitions["TS_PCT"].startswith("True shooting")
    assert env.units["TS_PCT"] == "percent_0_100"
    assert env.rows["EFG_PCT"] == 49.3


def test_failed_tool_raises_adapter_error():
    payload = {"tool": "get_standings", "ok": False,
               "error": "No standings on file for 1995-96"}
    with pytest.raises(AdapterError, match="No standings"):
        call_capability("standings", {"season": "1995-96"},
                        tools={"get_standings": FakeTool(payload)})


def test_missing_rows_raises_adapter_error():
    with pytest.raises(AdapterError, match="no rows"):
        call_capability("standings", {"season": "2025-26"},
                        tools={"get_standings": FakeTool({"ok": True})})


def test_unknown_capability_and_missing_tool():
    with pytest.raises(AdapterError, match="unknown capability"):
        call_capability("not_a_capability", {}, tools={})
    with pytest.raises(AdapterError, match="not available"):
        call_capability("standings", {"season": "2025-26"}, tools={})


def test_ambiguity_note_and_empty_rows_become_warnings():
    payload = dict(RESOLVE_PAYLOAD)
    payload["ambiguity_note"] = "'James' loosely matches several active players."
    env = call_capability("entity_resolution", {"query": "James"},
                          tools={"resolve_entity": FakeTool(payload)})
    assert any("loosely matches" in w for w in env.warnings)
    empty = {"tool": "get_standings", "ok": True, "rows": [],
             "meta": {"source": "warehouse", "season": "2025-26"}}
    env = call_capability("standings", {"season": "2025-26"},
                          tools={"get_standings": FakeTool(empty)})
    assert "empty result set" in env.warnings


def test_caller_entities_are_preserved():
    entity = EntityRef(id="1610612738", type="team",
                       display_name="Boston Celtics")
    env = call_capability("standings", {"season": "2025-26"},
                          entities=[entity],
                          tools={"get_standings": FakeTool(STANDINGS_PAYLOAD)})
    assert env.entities == [entity]


def test_observed_at_is_deterministic_when_injected():
    spec = CAPABILITIES["standings"]
    when = datetime(2026, 9, 14, 18, 0, tzinfo=timezone.utc)
    env = build_envelope(spec, {"season": "2025-26"}, STANDINGS_PAYLOAD,
                         observed_at=when)
    assert env.observed_at == when


def test_sync_tool_runs_off_event_loop():
    import asyncio
    import threading

    loop_thread = threading.get_ident()

    class ThreadRecordingTool(FakeTool):
        def invoke(self, arguments):
            self.thread_id = threading.get_ident()
            return super().invoke(arguments)

    async def run():
        tool = ThreadRecordingTool(STANDINGS_PAYLOAD)
        await acall_capability(
            "standings", {"season": "2025-26"}, tools={"get_standings": tool})
        return tool.thread_id

    assert asyncio.run(run()) != loop_thread


COVERAGE_TOOLS = {"metric_coverage": coverage.metric_coverage}


def test_metric_coverage_proprietary_one_player():
    env = call_capability(
        "metric_coverage",
        {"metrics": ["EPM", "LEBRON"], "player": "Jalen Brunson",
         "season": "2025-26"},
        tools=COVERAGE_TOOLS)
    assert env.capability == "metric_coverage"
    assert env.source == "v2:metric_coverage:warehouse coverage"
    assert env.season == "2025-26"
    joined = " ".join(env.warnings)
    assert "not available" in joined
    assert "never estimates" in joined
    assert "Jalen Brunson" in joined
    assert all(r["player"] == "Jalen Brunson" for r in env.rows)
    assert all(r["status"] == "unavailable" for r in env.rows)
    answer = env.rows and env.warnings[0] or ""
    assert "LeBron James" not in answer


def test_metric_coverage_available_metric_names_table():
    env = call_capability(
        "metric_coverage", {"metrics": ["RAPM-lite", "true shooting"]},
        tools=COVERAGE_TOOLS)
    by_metric = {r["metric"]: r for r in env.rows}
    assert by_metric["RAPM-lite"]["status"] == "available"
    assert "silver_rapm" in by_metric["RAPM-lite"]["note"]
    assert by_metric["true shooting"]["status"] == "available"
    assert env.warnings == []


def test_metric_coverage_string_metrics_and_unknown():
    env = call_capability(
        "metric_coverage", {"metrics": "EPM, RAPM, plus/minus"},
        tools=COVERAGE_TOOLS)
    statuses = {r["metric"]: r["status"] for r in env.rows}
    assert statuses["EPM"] == "unavailable"
    assert statuses["RAPM-lite"] == "available"
    assert statuses["plus/minus"] == "unknown"
    assert any("not a recognized metric" in w for w in env.warnings)


def test_metric_coverage_without_player_or_season():
    env = call_capability("metric_coverage", {"metrics": ["DARKO"]},
                          tools=COVERAGE_TOOLS)
    assert env.season is None
    assert "player" not in env.rows[0]
    assert "not available" in env.warnings[0]


def test_default_registry_includes_native_coverage_tool():
    pytest.importorskip("app.tools")
    from v2.adapters.core import _default_tools

    assert "metric_coverage" in _default_tools()

@pytest.mark.anyio
async def test_tool_capability_executes_through_runtime_protocol():
    from v2.adapters import ToolCapability
    from v2.contracts import Plan, PlanNode, RunMode, SeasonRef, TaskSpec
    from v2.runtime import PlanExecutor

    class StandingsTool:
        name = "get_standings"

        async def ainvoke(self, arguments):
            assert arguments == {"season": "2025-26"}
            return {"ok": True, "rows": [{"team": "Boston", "wins": 61}],
                    "meta": {"source": "fixture", "season": "2025-26"}}

    capability = ToolCapability("standings", tools={"get_standings": StandingsTool()})
    task = TaskSpec(goal="Boston record", mode=RunMode.QUICK, deliverable="text",
                    season=SeasonRef(value="2025-26", source="resolved", confidence=1))
    plan = Plan(nodes=[PlanNode(id="record", description="team record",
        capability_hints=["standings"], completion_test="Boston row present")])

    result = await PlanExecutor({"standings": capability}).execute(task, plan)

    assert result.evidence[0].capability == "standings"
    assert result.evidence[0].rows == [{"team": "Boston", "wins": 61}]

def test_leader_envelope_filters_units_and_declares_rank_coverage():
    env = call_capability("qualified_leaders", {"season": "2025-26"},
                          tools={"get_leaders": FakeTool(LEADERS_PAYLOAD)})
    assert set(env.units) == {"GP", "MIN", "FG3_PCT"}
    assert "population ranks" in env.coverage


def test_multi_vintage_trade_metadata_is_preserved() -> None:
    payload = {
        "tool": "get_trade_value", "ok": True,
        "rows": {"player": "Jaylen Brown", "salary_26_27": 57_100_000},
        "meta": {"source": "salary-sheet", "production_season": "2025-26",
                 "salary_season": "2026-27 (column SALARY_2025_26)"},
    }
    env = call_capability(
        "trade_value", {"team_a": "BOS", "players_a": "Jaylen Brown",
                        "team_b": "LAC", "players_b": "Paul George"},
        tools={"get_trade_value": FakeTool(payload)},
    )
    assert env.season is None
    assert env.vintages == {"production_season": "2025-26",
                            "salary_season": "2026-27"}
    assert env.task_season_scoped is False


def test_trade_legality_inherits_salary_vintage_from_contract_parent() -> None:
    from datetime import UTC, datetime
    from v2.adapters.core import _task_arguments
    from v2.contracts import EvidenceEnvelope, PlanNode, SeasonRef, TaskSpec

    contract = EvidenceEnvelope(
        evidence_id="salary", capability="contracts", source="warehouse",
        observed_at=datetime.now(UTC), season="2026-27",
        vintages={"salary_season": "2026-27"}, task_season_scoped=False,
        rows={"team": "BOS"},
    )
    task = TaskSpec(goal="trade", mode="deep_dive", deliverable="analysis",
                    season=SeasonRef(value="2025-26", source="user", confidence=1))
    node = PlanNode(
        id="legal", description="legality", capability_hints=["trades"],
        arguments={"team_a": "BOS", "players_a": "Jaylen Brown",
                   "team_b": "LAC", "players_b": "Paul George"},
        completion_test="legality result",
    )
    arguments = _task_arguments("trades", node, task, [contract])
    assert arguments["season"] == "2026-27"


def test_tool_capability_preflight_rejects_unknown_arguments() -> None:
    from v2.adapters import ToolCapability
    from v2.contracts import PlanNode

    capability = ToolCapability("standings")
    node = PlanNode(
        id="record", description="record", capability_hints=["standings"],
        arguments={"season": "2025-26", "invented": True},
        completion_test="record returned",
    )
    with pytest.raises(ValueError, match="unknown arguments.*invented"):
        capability.validate_arguments(node)
