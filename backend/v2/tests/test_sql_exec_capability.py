import json
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND))

WAREHOUSE = BACKEND / "data" / "warehouse.duckdb"

pytestmark = pytest.mark.skipif(
    not WAREHOUSE.exists(),
    reason=f"the warehouse is absent at {WAREHOUSE}")

YOUNG_SCORERS = (
    "SELECT COUNT(*) AS n FROM silver_hist_player_seasons "
    "WHERE _season = '{season}' AND age <= 23 AND pts >= 20"
)
MOST_WINS = (
    "SELECT team_city, team_name, wins AS n FROM silver_hist_standings "
    "WHERE _season = '{season}' ORDER BY wins DESC LIMIT 1"
)
FIFTY_WIN_COUNT = (
    "SELECT COUNT(*) AS n FROM silver_hist_standings "
    "WHERE _season = '{season}' AND wins >= 50"
)

EXPECTED = {
    ("2023-24", "young"): 9,
    ("2024-25", "young"): 9,
    ("2024-25", "fifty"): 9,
    ("2023-24", "fifty"): 7,
}

@pytest.fixture
def real_warehouse(monkeypatch):
    from shared import store
    from shared.tools import _core
    from v2.adapters import coverage

    connect = store.connect
    monkeypatch.setattr(store, "DB_PATH", WAREHOUSE)
    monkeypatch.setattr(store, "CANONICAL_DB_PATH", WAREHOUSE)
    monkeypatch.setattr(
        store, "connect", lambda read_only=True: connect(read_only=True))
    store.warehouse_tables_cache_clear()
    store.warehouse_pool_clear()
    store.warehouse_identity_cache_clear()
    _core.last_completed_season_cache_clear()
    coverage.coverage_cache_clear()
    yield WAREHOUSE
    store.warehouse_tables_cache_clear()
    store.warehouse_pool_clear()
    store.warehouse_identity_cache_clear()
    _core.last_completed_season_cache_clear()
    coverage.coverage_cache_clear()

@pytest.fixture(autouse=True)
def _open_chat_budget():
    from v2.api import routes

    routes._CHAT_HITS.clear()
    yield
    routes._CHAT_HITS.clear()

def test_the_capability_names_its_tool_and_its_coverage_tables(
        real_warehouse):
    from shared.tools import v1_tools
    from shared.tools.league import _SQL_TABLES
    from shared.tools.sql_exec import TABLES
    from v2.adapters.capabilities import CAPABILITIES
    from v2.adapters.coverage import (
        absent_tables_for_capability,
        declared_tables_for_capability,
        tables_for_capability,
        warehouse_tables,
    )
    from v2.runtime.assembly import capability_catalog

    assert TABLES == tuple(sorted(_SQL_TABLES))
    spec = CAPABILITIES["sql_exec"]
    assert spec.tool_name == "sql_exec"
    assert spec.tool_name in {tool.name for tool in v1_tools}
    assert declared_tables_for_capability("sql_exec", {}) == TABLES
    on_hand = warehouse_tables()
    assert set(tables_for_capability("sql_exec", {})) <= on_hand
    assert set(tables_for_capability("sql_exec", {})) | set(
        absent_tables_for_capability("sql_exec", {})) == set(TABLES)
    assert "sql_exec" in capability_catalog()
    assert spec.task_season_scoped is True
    assert spec.season_arg == "season"

def test_the_catalog_publishes_sql_as_required(real_warehouse):
    from v2.argument_schemas import compile_capability_catalog
    from v2.runtime.assembly import capability_catalog

    compiled = compile_capability_catalog(capability_catalog())
    row = next(item for item in compiled["capabilities"]
               if item["capability_id"] == "sql_exec")
    assert row["status"] == "REPRESENTABLE"
    sql = next(prop for prop in row["properties"]
               if prop["property"] == "sql")
    assert sql["required"] is True
    season = next(prop for prop in row["properties"]
                  if prop["property"] == "season")
    assert season["required"] is False

def test_the_capability_declares_units_for_every_numeric_output(
        real_warehouse):
    from v2.adapters import call_capability
    from v2.adapters.capabilities import CAPABILITIES

    units = CAPABILITIES["sql_exec"].units
    assert units["n"] == "count"
    assert "count" in CAPABILITIES["sql_exec"].metric_definitions["n"]
    for season in ("2023-24", "2024-25"):
        envelope = call_capability("sql_exec", {
            "sql": YOUNG_SCORERS.format(season=season), "season": season})
        numeric = {
            key for row in envelope.rows for key, value in row.items()
            if isinstance(value, (int, float)) and not isinstance(value, bool)
        }
        assert numeric and numeric <= set(units)
        assert set(envelope.units) <= set(units)

def test_the_names_a_planner_asks_for_resolve_to_a_returned_column():
    from v2.adapters.capabilities import CAPABILITIES, resolve_metric_column

    spec = CAPABILITIES["sql_exec"]
    assert resolve_metric_column(spec, "n") == "n"
    assert resolve_metric_column(spec, "TOTAL_COUNT") == "n"
    assert resolve_metric_column(spec, "WINS") == "wins"
    assert resolve_metric_column(spec, "HOME_RUNS") is None

def test_the_capability_description_separates_a_query_from_a_curated_table():
    from v2.adapters.capabilities import CAPABILITY_DESCRIPTIONS

    description = CAPABILITY_DESCRIPTIONS["sql_exec"]
    assert "Agent-written" in description
    assert "no prebuilt tool" in description
    assert "never" in description and "curated" in description

@pytest.mark.parametrize("season,kind,expected", [
    ("2023-24", "young", 9),
    ("2024-25", "young", 9),
    ("2024-25", "fifty", 9),
    ("2023-24", "fifty", 7),
])
def test_a_question_no_prebuilt_tool_answers_returns_real_cited_rows(
        real_warehouse, season, kind, expected):
    from v2.adapters import call_capability

    template = YOUNG_SCORERS if kind == "young" else FIFTY_WIN_COUNT
    assert EXPECTED[(season, kind)] == expected
    envelope = call_capability("sql_exec", {
        "sql": template.format(season=season), "season": season})
    assert envelope.capability == "sql_exec"
    assert envelope.season == season
    assert envelope.rows == [{"n": expected}]
    assert envelope.units == {"n": "count"}
    assert envelope.source == "v1:sql_exec:warehouse"
    assert "Agent-written SQL" in envelope.coverage
    assert "silver_hist_" in envelope.coverage
    assert envelope.source_identity.kind == "warehouse"

@pytest.mark.parametrize("season", ["2023-24", "2024-25"])
def test_the_most_wins_question_names_the_real_team_and_total(
        real_warehouse, season):
    from v2.adapters import call_capability

    envelope = call_capability("sql_exec", {
        "sql": MOST_WINS.format(season=season), "season": season})
    assert envelope.rows[0]["n"] == (
        64 if season == "2023-24" else 68)
    assert envelope.rows[0]["team_name"] == (
        "Celtics" if season == "2023-24" else "Thunder")

def test_the_query_is_part_of_the_evidence_identity(real_warehouse):
    from v2.adapters import call_capability

    first = call_capability("sql_exec", {
        "sql": YOUNG_SCORERS.format(season="2023-24"), "season": "2023-24"})
    rerun = call_capability("sql_exec", {
        "sql": YOUNG_SCORERS.format(season="2023-24"), "season": "2023-24"})
    other = call_capability("sql_exec", {
        "sql": FIFTY_WIN_COUNT.format(season="2023-24"), "season": "2023-24"})
    assert first.evidence_id == rerun.evidence_id
    assert first.evidence_id != other.evidence_id

@pytest.mark.parametrize("bad,violation", [
    ("DROP TABLE silver_standings", "only SELECT/WITH queries are allowed"),
    ("INSERT INTO silver_standings VALUES ('X', 1, '2025-26')",
     "only SELECT/WITH queries are allowed"),
    ("UPDATE silver_standings SET wins = 99",
     "only SELECT/WITH queries are allowed"),
    ("DELETE FROM silver_standings",
     "only SELECT/WITH queries are allowed"),
    ("SELECT * FROM silver_standings; DELETE FROM silver_standings",
     "stacked statements are not allowed"),
])
def test_a_write_attempt_is_refused_before_execution_naming_the_violation(
        real_warehouse, bad, violation):
    import duckdb

    from v2.adapters import call_capability
    from v2.adapters.core import AdapterError

    before = duckdb.connect(str(WAREHOUSE), read_only=True).execute(
        "SELECT COUNT(*) FROM silver_hist_standings").fetchone()[0]
    with pytest.raises(AdapterError) as excinfo:
        call_capability("sql_exec", {"sql": bad, "season": "2024-25"})
    assert violation in str(excinfo.value)
    assert bad[:60] in str(excinfo.value)
    after = duckdb.connect(str(WAREHOUSE), read_only=True).execute(
        "SELECT COUNT(*) FROM silver_hist_standings").fetchone()[0]
    assert before == after

def test_a_query_outside_the_declared_set_is_refused(real_warehouse):
    from shared.tools.league import _SQL_TABLES
    from v2.adapters import call_capability
    from v2.adapters.core import AdapterError

    bad = "SELECT * FROM silver_award_winners WHERE _season = '2024-25'"
    assert "silver_award_winners" not in set(_SQL_TABLES)
    with pytest.raises(AdapterError) as excinfo:
        call_capability("sql_exec", {"sql": bad, "season": "2024-25"})
    assert "unknown or unavailable tables" in str(excinfo.value)
    assert bad[:60] in str(excinfo.value)

def test_a_query_returning_nothing_fails_loudly_with_the_query_attached(
        real_warehouse):
    from v2.adapters import call_capability
    from v2.adapters.core import AdapterError

    sql = ("SELECT player_name, pts FROM silver_hist_player_seasons "
           "WHERE _season = '2024-25' AND age <= 10 AND pts >= 50")
    with pytest.raises(AdapterError) as excinfo:
        call_capability("sql_exec", {"sql": sql, "season": "2024-25"})
    assert "0 rows" in str(excinfo.value)
    assert sql[:60] in str(excinfo.value)

def test_a_wrong_subject_negative_fails_loudly_end_to_end(real_warehouse):
    from v2.adapters import call_capability
    from v2.adapters.core import AdapterError

    sql = ("SELECT player_name, pts FROM silver_hist_player_seasons "
           "WHERE _season = '2024-25' AND player_name = 'Nobody McNobody'")
    with pytest.raises(AdapterError) as excinfo:
        call_capability("sql_exec", {"sql": sql, "season": "2024-25"})
    assert "0 rows" in str(excinfo.value)
    assert "Nobody McNobody" in str(excinfo.value)

def test_intake_blames_a_declared_table_for_an_uncovered_sql_season(
        real_warehouse):
    from v2.adapters.capabilities import CAPABILITIES
    from v2.adapters.models import ModelIntake
    from v2.contracts import EvidenceRequirement, SeasonRef, TaskSpec

    def task(season: str) -> TaskSpec:
        return TaskSpec(
            goal="How many young players averaged 20 points?",
            mode="quick",
            deliverable="answer",
            season=SeasonRef(value=season, source="user", confidence=1.0),
            required_evidence=["sql_exec"],
            requirements=[EvidenceRequirement(
                id="analytics",
                description="Agent SQL evidence",
                capability_options=["sql_exec"],
                capability_arguments={
                    "sql": YOUNG_SCORERS.format(season=season),
                    "season": season},
            )],
        )

    covered = ModelIntake._mark_uncovered_season(task("2023-24"))
    assert covered.open_questions == []
    assert covered.assumptions == []
    blocked = ModelIntake._mark_uncovered_season(task("2030-31"))
    joined = " ".join([*blocked.open_questions, *blocked.assumptions])
    assert "2030-31" in joined
    assert "silver_hist_player_seasons" in joined
    assert CAPABILITIES["sql_exec"].task_season_scoped is True

class CountIntake:
    def __init__(self, season: str, sql: str,
                 outputs: list[str] | None = None) -> None:
        from v2.contracts import RunMode, SeasonRef, TaskSpec

        self._task = TaskSpec(
            goal=f"How many in {season}?",
            mode=RunMode.QUICK,
            deliverable="the count",
            requested_outputs=outputs or ["TOTAL_COUNT"],
            season=SeasonRef(value=season, source="user", confidence=1.0))

    async def understand(self, request: str, context=()):
        return self._task

class CountPlanner:
    def __init__(self, sql: str) -> None:
        self._sql = sql

    async def plan(self, task, failure_context=None):
        from v2.contracts import Plan, PlanNode

        return Plan(nodes=[PlanNode(
            id="analytics", description="agent-written analytical query",
            capability_hints=["sql_exec"],
            arguments={"sql": self._sql})])

class CountSynthesizer:
    async def synthesize(self, task, evidence):
        from v2.contracts import (
            Claim, ClaimKind, DraftReport, EvidenceOutputBinding)

        envelope = next(iter(evidence))
        total = envelope.rows[0]["n"]
        binding = EvidenceOutputBinding(
            requirement_kind="task", requirement_id=None,
            output_id="TOTAL_COUNT", node_id="analytics",
            evidence_id=envelope.evidence_id, selector="rows[0].n",
            value={"kind": "integer", "value": total},
            unit={"kind": "declared", "value": "count"},
            domain="sql_exec")
        return DraftReport(
            sections=["Count"],
            claims=[Claim(
                text=f"{total} rows match the analytical query.",
                kind=ClaimKind.OBSERVED,
                evidence_ids=[envelope.evidence_id],
                output_bindings=[binding])])

class CountSemantic:
    async def verify(self, task, draft, evidence):
        from v2.contracts import VerificationReport, VerificationStatus

        return VerificationReport(
            status=VerificationStatus.PASS,
            claim_results=[{"claim_index": index, "supported": True}
                           for index, _claim in enumerate(draft.claims)])

def _event(text: str, name: str) -> dict:
    payloads = [chunk.split("data: ", 1)[1]
                for chunk in text.split("\n\n")
                if chunk.startswith(f"event: {name}\n")]
    assert payloads
    return json.loads(payloads[-1])

def _count_stream(season, sql, monkeypatch, tmp_path):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from v2.adapters.core import ToolCapability
    from v2.api import routes
    from v2.projects.service import ProjectStore
    from v2.runtime import PlanExecutor, Runtime
    from v2.runtime.assembly import MechanicalVerifier
    from v2.runtime.ledger import RunLedger

    runtime = Runtime(
        intake=CountIntake(season, sql), planner=CountPlanner(sql),
        executor=PlanExecutor(
            {"sql_exec": ToolCapability("sql_exec")}),
        synthesizer=CountSynthesizer(),
        mechanical_verifier=MechanicalVerifier(),
        semantic_verifier=CountSemantic())

    def build(**kwargs):
        return runtime, RunLedger(kwargs["run_id"])

    monkeypatch.setenv("DIME_RUNTIME_V2", "on")
    monkeypatch.setattr("shared.providers.resolve_model_id",
                        lambda value: ("openrouter", "fixture"))
    monkeypatch.setattr("v2.runtime.assembly.build_runtime", build)
    monkeypatch.setattr(routes, "_PROJECTS", ProjectStore(tmp_path / "p.sqlite"))
    app = FastAPI()
    app.include_router(routes.router, prefix="/api")
    response = TestClient(app).post(
        "/api/v2/chat/stream", json={"q": f"How many in {season}?"})
    assert response.status_code == 200
    return (_event(response.text, "custom_data"),
            _event(response.text, "final_answer"))

def test_an_unmapped_count_streams_end_to_end_with_sql_provenance(
        real_warehouse, monkeypatch, tmp_path):
    sql = YOUNG_SCORERS.format(season="2023-24")
    custom, final = _count_stream("2023-24", sql, monkeypatch, tmp_path)

    assert [row["output_id"] for row in custom["tables"]] == ["TOTAL_COUNT"]
    assert custom["tables"][0]["value"] == "9"
    assert custom["tables"][0]["provenance"]["capability"] == "sql_exec"
    assert custom["tables"][0]["provenance"]["origin"] == "warehouse"
    assert custom["unverified_numbers"] == []
    assert "I could not verify a publishable answer" not in final["text"]
    assert final["carry"]["verified_claims"] == 1

class MixedSynthesizer:
    async def synthesize(self, task, evidence):
        from v2.contracts import (
            Claim, ClaimKind, DraftReport, EvidenceOutputBinding)

        envelope = next(iter(evidence))
        total = envelope.rows[0]["n"]
        return DraftReport(
            sections=["Count"],
            claims=[
                Claim(
                    text=f"{total} rows match the analytical query.",
                    kind=ClaimKind.OBSERVED,
                    evidence_ids=[envelope.evidence_id],
                    output_bindings=[EvidenceOutputBinding(
                        requirement_kind="task", requirement_id=None,
                        output_id="TOTAL_COUNT", node_id="analytics",
                        evidence_id=envelope.evidence_id,
                        selector="rows[0].n",
                        value={"kind": "integer", "value": total},
                        unit={"kind": "declared", "value": "count"},
                        domain="sql_exec")]),
                Claim(
                    text="Nobody McNobody led the group.",
                    kind=ClaimKind.OBSERVED,
                    evidence_ids=[envelope.evidence_id],
                    output_bindings=[EvidenceOutputBinding(
                        requirement_kind="task", requirement_id=None,
                        output_id="PLAYER_NAME", node_id="analytics",
                        evidence_id=envelope.evidence_id,
                        selector="rows[0].player_name",
                        value={"kind": "string",
                               "value": "Nobody McNobody"},
                        unit={"kind": "unitless"},
                        domain="sql_exec")]),
            ])

def test_a_binding_naming_a_subject_off_the_rows_is_rejected(
        real_warehouse, monkeypatch, tmp_path):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from v2.adapters import call_capability
    from v2.adapters.core import ToolCapability
    from v2.api import routes
    from v2.projects.service import ProjectStore
    from v2.runtime import PlanExecutor, Runtime
    from v2.runtime.assembly import MechanicalVerifier
    from v2.runtime.ledger import RunLedger

    rows = call_capability("sql_exec", {
        "sql": YOUNG_SCORERS.format(season="2023-24"), "season": "2023-24"}).rows
    assert "Nobody McNobody" not in {row.get("player_name") for row in rows}

    runtime = Runtime(
        intake=CountIntake("2023-24",
                           YOUNG_SCORERS.format(season="2023-24"),
                           ["TOTAL_COUNT", "PLAYER_NAME"]),
        planner=CountPlanner(YOUNG_SCORERS.format(season="2023-24")),
        executor=PlanExecutor(
            {"sql_exec": ToolCapability("sql_exec")}),
        synthesizer=MixedSynthesizer(),
        mechanical_verifier=MechanicalVerifier(),
        semantic_verifier=CountSemantic())

    def build(**kwargs):
        return runtime, RunLedger(kwargs["run_id"])

    monkeypatch.setenv("DIME_RUNTIME_V2", "on")
    monkeypatch.setattr("shared.providers.resolve_model_id",
                        lambda value: ("openrouter", "fixture"))
    monkeypatch.setattr("v2.runtime.assembly.build_runtime", build)
    monkeypatch.setattr(routes, "_PROJECTS", ProjectStore(tmp_path / "p.sqlite"))
    app = FastAPI()
    app.include_router(routes.router, prefix="/api")
    response = TestClient(app).post(
        "/api/v2/chat/stream", json={"q": "How many in 2023-24?"})
    assert response.status_code == 200
    custom = _event(response.text, "custom_data")
    final = _event(response.text, "final_answer")

    statuses = [(item["output_id"], item["status"])
                for item in final["carry"]["output_statuses"]]
    assert ("TOTAL_COUNT", "complete") in statuses
    assert ("PLAYER_NAME", "rejected") in statuses
    cited = {row["output_id"]: row["value"] for row in custom["tables"]}
    assert cited == {"TOTAL_COUNT": "9"}
    assert {row["provenance"]["capability"]
            for row in custom["tables"]} == {"sql_exec"}
    assert final["carry"]["verified_claims"] == 2

GOLDEN_CALLS = {
    "sql-young-scorers-2324": (
        YOUNG_SCORERS.format(season="2023-24"), "answer"),
    "sql-most-wins-2425": (
        MOST_WINS.format(season="2024-25"), "answer"),
}

def _golden_scenarios():
    from v2.tests.compatibility.harness import load_pack

    pack = load_pack(Path(__file__).resolve().parent
                     / "compatibility" / "fixtures" / "scenarios.json")
    return [scenario for scenario in pack["scenarios"]
            if scenario["id"] in GOLDEN_CALLS]

def test_the_pack_carries_a_golden_question_for_every_sql_call_shape():
    assert {scenario["id"] for scenario in _golden_scenarios()} == set(
        GOLDEN_CALLS)
    for scenario in _golden_scenarios():
        assert "sql" in scenario["tags"]
        assert scenario["budget"]["max_tool_calls"] <= 2

def test_every_golden_sql_question_is_answered_by_the_real_warehouse(
        real_warehouse):
    from v2.adapters import call_capability
    from v2.domain.evidence import iter_values

    for scenario in _golden_scenarios():
        sql = GOLDEN_CALLS[scenario["id"]][0]
        question = scenario["chain"][0]
        envelope = call_capability("sql_exec", {
            "sql": sql, "season": scenario["season"]})
        assert envelope.season == scenario["season"], question
        values = {
            str(item.value).replace(",", "")
            for item in iter_values(envelope) if item.value is not None
        }
        requirement = scenario.get("evidence_requirement", {})
        assert "sql_exec" in requirement["any_capability"], question
        for needle in requirement["required_values"]:
            assert needle.replace(",", "") in values, (question, needle)
        for needle in requirement.get("metric_definitions_contain", []):
            assert any(needle in value
                       for value in envelope.metric_definitions.values()), (
                           question, needle)
