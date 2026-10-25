from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from datetime import UTC, date, datetime
from types import SimpleNamespace

import pytest

from v2.contracts import (
    CalculationOutputBinding,
    Claim,
    ClaimKind,
    ClaimSource,
    DeclaredCalculation,
    DraftReport,
    EntityRef,
    EvidenceEnvelope,
    EvidenceOutputBinding,
    Gap,
    GapKind,
    OutputFinalStatus,
    Plan,
    PlanNode,
    RunMode,
    SeasonRef,
    TaskSpec,
    VerificationReport,
    VerificationStatus,
    VerifiedClaim,
)
from v2.runtime import FakeCapability, PlanExecutor, Runtime
from v2.runtime.assembly import MechanicalVerifier

SEASON = "2024-25"
AS_OF = date(2026, 9, 8)
NODE_ID = "leaders"
EVIDENCE_ID = "evidence:leaders"
REQUESTED = ["PLAYER_NAME", "TOTAL_ASSISTS", "GAMES_PLAYED", "ASSISTS_PER_GAME",
             "STAT_VALUE"]
LEADER_ROWS = [
    {"RANK": 1, "PLAYER_NAME": "Ada Vega", "PLAYER_ID": 9001,
     "AST": 880, "GP": 76, "AST_PER_GAME": 11.6},
    {"RANK": 2, "PLAYER_NAME": "Bram Kessler", "PLAYER_ID": 9002,
     "AST": 716, "GP": 70, "AST_PER_GAME": 10.2},
]
WAREHOUSE_SOURCE = "silver_leaders:fetch_leaders:warehouse"
LIVE_SOURCE = "silver_leaders:fetch_leaders:nba_api"

@pytest.fixture
def anyio_backend():
    return "asyncio"

@pytest.fixture(autouse=True)
def _chat_budget():
    from v2.api import routes

    routes._CHAT_HITS.clear()
    yield
    routes._CHAT_HITS.clear()

def _envelope(*, identity=None, source=WAREHOUSE_SOURCE,
              rows=None) -> EvidenceEnvelope:
    return EvidenceEnvelope(
        evidence_id=EVIDENCE_ID,
        capability="qualified_leaders",
        source=source,
        observed_at=datetime(2026, 9, 8, 12, tzinfo=UTC),
        season=SEASON,
        as_of=AS_OF,
        entities=[
            EntityRef(id=str(row["PLAYER_ID"]), type="player",
                      display_name=row["PLAYER_NAME"])
            for row in (rows if rows is not None else LEADER_ROWS)],
        rows=[dict(row) for row in
              (rows if rows is not None else LEADER_ROWS)],
        units={"AST": "count", "GP": "count", "AST_PER_GAME": "per_game"},
        source_identity=identity,
    )

def _warehouse_envelope(**kwargs) -> EvidenceEnvelope:
    return _envelope(identity={"kind": "warehouse", "warehouse_id": "frozen-eval",
                               "sha256": "a" * 64}, **kwargs)

class StampedCapability(FakeCapability):
    def __init__(self, envelope: EvidenceEnvelope) -> None:
        super().__init__("qualified_leaders", envelope.rows)
        self._envelope = envelope

    async def execute(self, node, task, evidence):
        return self._envelope

class Intake:
    async def understand(self, request: str) -> TaskSpec:
        return TaskSpec(
            goal=request, mode=RunMode.QUICK,
            deliverable="the leader, their total, their games, their average",
            requested_outputs=list(REQUESTED),
            season=SeasonRef(value=SEASON, source="user", confidence=1.0))

class Planner:
    def __init__(self, arguments: dict | None = None) -> None:
        self._arguments = dict(arguments or {})

    async def plan(self, task: TaskSpec) -> Plan:
        return Plan(nodes=[PlanNode(
            id=NODE_ID, description="leaderboard for the season",
            capability_hints=["qualified_leaders"],
            arguments=dict(self._arguments))])

class Synthesizer:
    def __init__(self, claim: Claim) -> None:
        self._claim = claim

    async def synthesize(self, task, evidence) -> DraftReport:
        return DraftReport(sections=["Leader"], claims=[self._claim])

class PassingSemantic:
    async def verify(self, task, draft, evidence) -> VerificationReport:
        return VerificationReport(
            status=VerificationStatus.PASS,
            claim_results=[{"claim_index": index, "supported": True}
                           for index, _claim in enumerate(draft.claims)])

def _binding(output_id: str, selector: str, value: dict,
             unit: dict) -> EvidenceOutputBinding:
    return EvidenceOutputBinding(
        requirement_kind="task", requirement_id=None, output_id=output_id,
        node_id=NODE_ID, evidence_id=EVIDENCE_ID, selector=selector,
        row_selector="rows[0]",
        subject_entity_type="player", subject_entity_id="9001",
        subject_selector="rows[0].PLAYER_ID", value=value, unit=unit,
        domain="qualified_leaders")

def _leader_claim(*, assists: int) -> Claim:
    return Claim(
        text=(f"Ada Vega led the league in total assists with {assists} total "
              "assists, playing in 76 games and averaging 11.6 assists per game."),
        kind=ClaimKind.OBSERVED,
        evidence_ids=[EVIDENCE_ID],
        output_bindings=[
            _binding("PLAYER_NAME", "rows[0].PLAYER_NAME",
                     {"kind": "string", "value": "Ada Vega"},
                     {"kind": "unitless"}),
            _binding("TOTAL_ASSISTS", "rows[0].AST",
                     {"kind": "integer", "value": assists},
                     {"kind": "declared", "value": "count"}),
            _binding("GAMES_PLAYED", "rows[0].GP",
                     {"kind": "integer", "value": 76},
                     {"kind": "declared", "value": "count"}),
            _binding("ASSISTS_PER_GAME", "rows[0].AST_PER_GAME",
                     {"kind": "float", "value": 11.6},
                     {"kind": "declared", "value": "per_game"}),
        ])

def _runtime(claim: Claim, envelope: EvidenceEnvelope,
             after: Callable | None = None,
             planner: Planner | None = None) -> Runtime:
    class PublishedRuntime(Runtime):
        async def run(self, request, *, run_id=None, context=()):
            result = await super().run(request, run_id=run_id, context=context)
            return after(result) if after is not None else result

    return PublishedRuntime(
        intake=Intake(), planner=planner or Planner(),
        executor=PlanExecutor({"qualified_leaders": StampedCapability(envelope)}),
        synthesizer=Synthesizer(claim),
        mechanical_verifier=MechanicalVerifier(),
        semantic_verifier=PassingSemantic())

def _stream(monkeypatch, tmp_path, runtime: Runtime) -> tuple[str, dict, dict]:
    return asyncio.run(_stream_async(monkeypatch, tmp_path, runtime))

def _event(text: str, name: str) -> dict:
    payloads = [chunk.split("data: ", 1)[1]
                for chunk in text.split("\n\n")
                if chunk.startswith(f"event: {name}\n")]
    if not payloads:
        return {}
    return json.loads(payloads[-1])

async def _stream_async(monkeypatch, tmp_path, runtime: Runtime) -> tuple[str, dict, dict]:
    import httpx
    from fastapi import FastAPI
    from v2.api import routes
    from v2.projects.service import ProjectStore
    from v2.runtime.ledger import RunLedger

    def build(**kwargs):
        return runtime, RunLedger(kwargs["run_id"])

    monkeypatch.setenv("DIME_RUNTIME_V2", "on")
    monkeypatch.setattr("shared.providers.resolve_model_id",
                        lambda value: ("openrouter", "fixture"))
    monkeypatch.setattr("v2.runtime.assembly.build_runtime", build)
    monkeypatch.setattr(routes, "_PROJECTS", ProjectStore(tmp_path / "p.sqlite"))
    app = FastAPI()
    app.include_router(routes.router, prefix="/api")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/api/v2/chat/stream",
            json={"q": "Who led the league in total assists, and how many?"})
    assert response.status_code == 200
    return (response.text,
            _event(response.text, "custom_data"),
            _event(response.text, "final_answer"))

def _cited(custom: dict) -> dict[str, dict]:
    return {row["output_id"]: row for row in custom["tables"]}

def test_every_number_the_answer_states_carries_its_own_citation(monkeypatch, tmp_path):
    _text, custom, final = _stream(
        monkeypatch, tmp_path,
        _runtime(_leader_claim(assists=880), _warehouse_envelope()))

    assert "880 total assists" in final["text"]
    cited = _cited(custom)
    assert set(cited) == set(REQUESTED) - {"STAT_VALUE"}
    assert cited["TOTAL_ASSISTS"]["value"] == "880"
    assert cited["GAMES_PLAYED"]["value"] == "76"
    assert cited["ASSISTS_PER_GAME"]["value"] == "11.6"
    assert cited["PLAYER_NAME"]["value"] == "Ada Vega"
    for internal in (EVIDENCE_ID, "rows[0].AST", "rows[0].PLAYER_ID",
                     "node_id", "evidence_id", "selector", "subject_selector"):
        assert internal not in final["text"]

def test_every_citation_names_the_source_and_the_vintage_it_came_from(
        monkeypatch, tmp_path):
    _text, custom, final = _stream(
        monkeypatch, tmp_path,
        _runtime(_leader_claim(assists=880), _warehouse_envelope()))

    provenance = _cited(custom)["TOTAL_ASSISTS"]["provenance"]
    assert provenance["capability"] == "qualified_leaders"
    assert provenance["origin"] == "warehouse"
    assert provenance["warehouse_id"] == "frozen-eval"
    assert provenance["season"] == SEASON
    assert provenance["as_of"] == AS_OF.isoformat()
    assert provenance["live_sources"] == []
    assert WAREHOUSE_SOURCE not in final["text"]

def test_a_figure_whose_tool_declared_no_source_is_not_called_warehouse(
        monkeypatch, tmp_path):
    _, custom, _ = _stream(
        monkeypatch, tmp_path, _runtime(_leader_claim(assists=880), _envelope()))

    assert _cited(custom)["TOTAL_ASSISTS"]["provenance"]["origin"] == "undeclared"

def test_a_live_figure_is_labelled_live_and_never_reads_as_warehouse(
        monkeypatch, tmp_path):
    envelope = _envelope(identity={"kind": "live", "source": "nba_api"},
                         source=LIVE_SOURCE)
    _, custom, _ = _stream(
        monkeypatch, tmp_path, _runtime(_leader_claim(assists=880), envelope))

    provenance = _cited(custom)["TOTAL_ASSISTS"]["provenance"]
    assert provenance["origin"] == "live"
    assert provenance["live_sources"] == ["nba_api"]
    assert all(row["provenance"]["origin"] != "warehouse"
               for row in custom["tables"])

def test_a_figure_from_a_refreshed_source_is_labelled_mixed(monkeypatch, tmp_path):
    envelope = _envelope(
        identity={"kind": "composite", "warehouse_id": "frozen-eval",
                  "sha256": "a" * 64, "live_sources": ["nba_api"]},
        source="silver_leaders:fetch_leaders:warehouse+nba_api")
    _, custom, _ = _stream(
        monkeypatch, tmp_path, _runtime(_leader_claim(assists=880), envelope))

    provenance = _cited(custom)["TOTAL_ASSISTS"]["provenance"]
    assert provenance["origin"] == "mixed"
    assert provenance["live_sources"] == ["nba_api"]

def test_the_block_names_every_requested_output_it_does_not_cover(
        monkeypatch, tmp_path):
    _, custom, _ = _stream(
        monkeypatch, tmp_path,
        _runtime(_leader_claim(assists=880), _warehouse_envelope()))

    assert custom["unverified_numbers"] == [
        "STAT VALUE could not be traced to the source data."]

def test_a_missing_evidence_envelope_still_fails_the_run(monkeypatch, tmp_path):
    def vanish(result):
        execution = result.execution.model_copy(update={"evidence_by_node": {}})
        return result.model_copy(update={"execution": execution})

    text, custom, final = _stream(
        monkeypatch, tmp_path,
        _runtime(_leader_claim(assists=880), _warehouse_envelope(), after=vanish))

    assert custom == {}
    assert final["carry"]["verification"] == "partial"
    assert final["carry"]["verified_claims"] == 0
    assert final["text"].startswith("I could not verify a publishable answer")
    assert "event: custom_data" not in text

def test_a_value_the_warehouse_changed_under_the_run_fails_the_run(
        monkeypatch, tmp_path):
    drifted = [dict(row, AST=1) for row in LEADER_ROWS]

    def rewrite(result):
        execution = result.execution.model_copy(update={
            "evidence_by_node": {
                node_id: item.model_copy(update={"rows": drifted})
                for node_id, item in result.execution.evidence_by_node.items()}})
        return result.model_copy(update={"execution": execution})

    text, custom, final = _stream(
        monkeypatch, tmp_path,
        _runtime(_leader_claim(assists=880), _warehouse_envelope(), after=rewrite))

    assert custom == {}
    assert final["carry"]["verification"] == "partial"
    assert "event: custom_data" not in text

def _source_of(envelope: EvidenceEnvelope) -> ClaimSource:
    return ClaimSource(
        evidence_id=envelope.evidence_id, source=envelope.source,
        capability=envelope.capability, observed_at=envelope.observed_at,
        as_of=envelope.as_of, vintages=dict(envelope.vintages))

def _citation_result(*, claims, evidence, evidence_by_node, nodes,
                     gaps=(), calculations=()):
    statuses = [
        OutputFinalStatus(
            requirement_kind=binding.requirement_kind,
            requirement_id=binding.requirement_id,
            output_id=binding.output_id, status="complete",
            claim_index=claim.claim_index, binding=binding)
        for claim in claims
        for binding in claim.output_bindings
    ]
    task = TaskSpec(
        goal="citation serialization", mode=RunMode.QUICK,
        deliverable="citation serialization",
        season=SeasonRef(value=SEASON, source="user", confidence=1.0))
    return SimpleNamespace(
        verified_claims=list(claims), gaps=list(gaps),
        execution=SimpleNamespace(
            evidence=list(evidence),
            evidence_by_node=dict(evidence_by_node),
            plan=Plan(nodes=list(nodes))),
        output_statuses=statuses, task=task,
        draft=SimpleNamespace(calculations=list(calculations)))

@pytest.mark.anyio
async def test_final_carry_preserves_admitted_citation_with_executed_scope(
        monkeypatch, tmp_path):
    envelope = _warehouse_envelope(
        source="v1:get_leaders:warehouse:silver_leaders")
    scope = {"season": SEASON, "ranking_direction": "desc"}
    _text, _custom, final = await _stream_async(
        monkeypatch, tmp_path,
        _runtime(_leader_claim(assists=880), envelope, planner=Planner(scope)))

    citations = final["carry"]["citations"]
    assert len(citations) == 1
    citation = citations[0]
    assert citation["claim_index"] == 0
    assert citation["evidence_id"] == EVIDENCE_ID
    assert citation["node_id"] == NODE_ID
    assert citation["source"] == "v1:get_leaders:warehouse:silver_leaders"
    assert citation["table"] == "silver_leaders"
    assert citation["provenance"] == {
        "capability": "qualified_leaders", "origin": "warehouse",
        "warehouse_id": "frozen-eval", "season": SEASON,
        "as_of": AS_OF.isoformat(), "live_sources": []}
    assert citation["window_start"] is None
    assert citation["window_end"] is None
    assert citation["executed_arguments"] is None
    assert citation["planned_arguments"] == scope
    assert {item["output_id"] for item in citation["outputs"]} == {
        "PLAYER_NAME", "TOTAL_ASSISTS", "GAMES_PLAYED", "ASSISTS_PER_GAME"}
    assert citation["calculations"] == []
    assert EVIDENCE_ID not in final["text"]

def test_citation_excludes_withheld_and_unbound_claims():
    from v2.api.routes import _public_citations

    envelope = _warehouse_envelope(
        source="v1:get_leaders:warehouse:silver_leaders")
    withheld = VerifiedClaim(
        claim_index=0, claim=_leader_claim(assists=880),
        evidence_ids=[EVIDENCE_ID], sources=[_source_of(envelope)],
        output_bindings=_leader_claim(assists=880).output_bindings)
    unbound = VerifiedClaim(
        claim_index=2,
        claim=Claim(
            text="Ada Vega led with 880 assists.", kind=ClaimKind.OBSERVED,
            evidence_ids=[EVIDENCE_ID]),
        evidence_ids=[EVIDENCE_ID], sources=[_source_of(envelope)])
    published = VerifiedClaim(
        claim_index=1, claim=_leader_claim(assists=880),
        evidence_ids=[EVIDENCE_ID], sources=[_source_of(envelope)],
        output_bindings=_leader_claim(assists=880).output_bindings)
    result = _citation_result(
        claims=[withheld, published, unbound], evidence=[envelope],
        evidence_by_node={NODE_ID: envelope},
        nodes=[PlanNode(id=NODE_ID, description="leaderboard",
                        capability_hints=["qualified_leaders"],
                        arguments={"season": SEASON})],
        gaps=[Gap(kind=GapKind.SYNTHESIS_INCOMPLETE, message="withheld",
                  blocks=["claim:0"])])

    citations = _public_citations(result)
    assert [item["claim_index"] for item in citations] == [1]
    assert len(citations[0]["outputs"]) == 4

def test_citation_excludes_source_without_admitted_envelope():
    from v2.api.routes import _public_citations

    envelope = _warehouse_envelope(
        source="v1:get_leaders:warehouse:silver_leaders")
    claim = _leader_claim(assists=880)
    verified = VerifiedClaim(
        claim_index=0, claim=claim, evidence_ids=[EVIDENCE_ID],
        sources=[_source_of(envelope)], output_bindings=claim.output_bindings)
    result = _citation_result(
        claims=[verified], evidence=[], evidence_by_node={},
        nodes=[PlanNode(id=NODE_ID, description="leaderboard",
                        capability_hints=["qualified_leaders"],
                        arguments={"season": SEASON})])

    assert _public_citations(result) == []

def test_citation_traces_derived_output_to_operand_evidence():
    from v2.api.routes import _public_citations

    envelope = EvidenceEnvelope(
        evidence_id="evidence:operands", capability="qualified_leaders",
        source="v1:get_leaders:warehouse:silver_leaders",
        observed_at=datetime(2026, 9, 8, 12, tzinfo=UTC), season=SEASON,
        rows=[{"A": 4, "B": 6}],
        source_identity={"kind": "warehouse", "warehouse_id": "frozen-eval",
                         "sha256": "a" * 64})
    calculation = DeclaredCalculation(
        calculation_id="calc1", requirement_id="calc_req", operation="add",
        inputs=[
            {"evidence_id": envelope.evidence_id, "path": "rows[0].A"},
            {"evidence_id": envelope.evidence_id, "path": "rows[0].B"},
        ],
        result="10", unit="count")
    binding = CalculationOutputBinding(
        requirement_kind="calculation", requirement_id="calc_req",
        output_id="TOTAL", calculation_id="calc1")
    claim = Claim(
        text="The total is 10.", kind=ClaimKind.DERIVED,
        evidence_ids=[envelope.evidence_id], calculation_id="calc1",
        output_bindings=[binding])
    verified = VerifiedClaim(
        claim_index=0, claim=claim, evidence_ids=[envelope.evidence_id],
        sources=[_source_of(envelope)], output_bindings=[binding])
    result = _citation_result(
        claims=[verified], evidence=[envelope],
        evidence_by_node={"calc_node": envelope},
        nodes=[PlanNode(id="calc_node", description="calc",
                        capability_hints=["qualified_leaders"],
                        arguments={"season": SEASON})],
        calculations=[calculation])

    citations = _public_citations(result)
    assert len(citations) == 1
    citation = citations[0]
    assert citation["evidence_id"] == envelope.evidence_id
    assert citation["node_id"] == "calc_node"
    assert citation["executed_arguments"] is None
    assert citation["planned_arguments"] == {"season": SEASON}
    assert citation["outputs"] == []
    assert [item["input_path"] for item in citation["calculations"]] == [
        "rows[0].A", "rows[0].B"]
    assert all(item["calculation_id"] == "calc1" for item in citation["calculations"])
    assert all(item["result"] == "10" for item in citation["calculations"])
    assert citation["calculations"][0]["inputs"] == [
        {"evidence_id": envelope.evidence_id, "path": "rows[0].A"},
        {"evidence_id": envelope.evidence_id, "path": "rows[0].B"},
    ]

def test_sql_exec_citation_preserves_exact_sql_without_inventing_table():
    from v2.api.routes import _public_citations

    sql = (
        "SELECT TEAM, EFG_PCT FROM silver_four_factors_team "
        "WHERE _season = '2025-26' ORDER BY EFG_PCT DESC LIMIT 5")
    envelope = EvidenceEnvelope(
        evidence_id="sql_exec:abc", capability="sql_exec",
        source="v1:sql_exec:warehouse",
        observed_at=datetime(2026, 9, 8, 12, tzinfo=UTC),
        season="2025-26", rows=[{"TEAM": "BOS", "EFG_PCT": 0.5}],
        execution_arguments={"season": "2025-26", "sql": sql},
        source_identity={"kind": "warehouse", "warehouse_id": "frozen-eval",
                         "sha256": "a" * 64})
    binding = EvidenceOutputBinding(
        requirement_kind="task", requirement_id=None, output_id="EFG_PCT",
        node_id="sql", evidence_id=envelope.evidence_id,
        selector="rows[0].EFG_PCT", value={"kind": "float", "value": 0.5},
        unit={"kind": "unitless"}, domain="sql_exec")
    claim = Claim(
        text="Boston had an EFG of 0.5.", kind=ClaimKind.OBSERVED,
        evidence_ids=[envelope.evidence_id], output_bindings=[binding])
    verified = VerifiedClaim(
        claim_index=0, claim=claim, evidence_ids=[envelope.evidence_id],
        sources=[_source_of(envelope)], output_bindings=[binding])
    result = _citation_result(
        claims=[verified], evidence=[envelope],
        evidence_by_node={"sql": envelope},
        nodes=[PlanNode(id="sql", description="sql", capability_hints=["sql_exec"],
                        arguments={"season": "2024-25", "sql": "planned stale"})])

    citations = _public_citations(result)
    assert len(citations) == 1
    citation = citations[0]
    assert citation["table"] is None
    assert citation["source"] == "v1:sql_exec:warehouse"
    assert citation["executed_arguments"] == {"season": "2025-26", "sql": sql}
    assert citation["planned_arguments"] == {
        "season": "2024-25", "sql": "planned stale"}
    assert citation["outputs"][0]["selector"] == "rows[0].EFG_PCT"

def test_citation_does_not_invent_missing_calculation_operand_lineage():
    from v2.api.routes import _public_citations

    calculation = DeclaredCalculation(
        calculation_id="calc1", requirement_id="calc_req", operation="add",
        inputs=[{"evidence_id": "evidence:missing", "path": "rows[0].A"}],
        result="10", unit="count")
    binding = CalculationOutputBinding(
        requirement_kind="calculation", requirement_id="calc_req",
        output_id="TOTAL", calculation_id="calc1")
    claim = Claim(
        text="The total is 10.", kind=ClaimKind.DERIVED,
        evidence_ids=["evidence:missing"], calculation_id="calc1",
        output_bindings=[binding])
    verified = VerifiedClaim(
        claim_index=0, claim=claim, evidence_ids=["evidence:missing"],
        sources=[], output_bindings=[binding])
    result = _citation_result(
        claims=[verified], evidence=[], evidence_by_node={},
        nodes=[PlanNode(id="calc_node", description="calc",
                        capability_hints=["qualified_leaders"])],
        calculations=[calculation])

    assert _public_citations(result) == []
