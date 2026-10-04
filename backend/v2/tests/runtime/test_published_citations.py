from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, date, datetime

import pytest

from v2.contracts import (
    Claim,
    ClaimKind,
    DraftReport,
    EntityRef,
    EvidenceEnvelope,
    EvidenceOutputBinding,
    Plan,
    PlanNode,
    RunMode,
    SeasonRef,
    TaskSpec,
    VerificationReport,
    VerificationStatus,
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
    async def plan(self, task: TaskSpec) -> Plan:
        return Plan(nodes=[PlanNode(
            id=NODE_ID, description="leaderboard for the season",
            capability_hints=["qualified_leaders"])])


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
             after: Callable | None = None) -> Runtime:
    class PublishedRuntime(Runtime):
        async def run(self, request, *, run_id=None, context=()):
            result = await super().run(request, run_id=run_id, context=context)
            return after(result) if after is not None else result

    return PublishedRuntime(
        intake=Intake(), planner=Planner(),
        executor=PlanExecutor({"qualified_leaders": StampedCapability(envelope)}),
        synthesizer=Synthesizer(claim),
        mechanical_verifier=MechanicalVerifier(),
        semantic_verifier=PassingSemantic())


def _stream(monkeypatch, tmp_path, runtime: Runtime) -> tuple[str, dict, dict]:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
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
    response = TestClient(app).post(
        "/api/v2/chat/stream",
        json={"q": "Who led the league in total assists, and how many?"})
    assert response.status_code == 200
    return (response.text,
            _event(response.text, "custom_data"),
            _event(response.text, "final_answer"))


def _event(text: str, name: str) -> dict:
    payloads = [chunk.split("data: ", 1)[1]
                for chunk in text.split("\n\n")
                if chunk.startswith(f"event: {name}\n")]
    if not payloads:
        return {}
    return json.loads(payloads[-1])


def _cited(custom: dict) -> dict[str, dict]:
    return {row["output_id"]: row for row in custom["tables"]}


def test_every_number_the_answer_states_carries_its_own_citation(monkeypatch, tmp_path):
    text, custom, final = _stream(
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
        assert internal not in text


def test_every_citation_names_the_source_and_the_vintage_it_came_from(
        monkeypatch, tmp_path):
    text, custom, _ = _stream(
        monkeypatch, tmp_path,
        _runtime(_leader_claim(assists=880), _warehouse_envelope()))

    provenance = _cited(custom)["TOTAL_ASSISTS"]["provenance"]
    assert provenance["capability"] == "qualified_leaders"
    assert provenance["origin"] == "warehouse"
    assert provenance["warehouse_id"] == "frozen-eval"
    assert provenance["season"] == SEASON
    assert provenance["as_of"] == AS_OF.isoformat()
    assert provenance["live_sources"] == []
    assert WAREHOUSE_SOURCE not in text


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

