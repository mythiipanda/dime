from __future__ import annotations

import json
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
NODE_ID = "matchup"
EVIDENCE_ID = f"evidence:{NODE_ID}"
HOME = EntityRef(id="1610612738", type="team", display_name="North Bay Kings")
AWAY = EntityRef(id="1610612757", type="team", display_name="South Harbor Sharks")
REQUESTED = ["OFF_RATING", "NET_RATING", "INJURED_PLAYERS"]
WAREHOUSE_SOURCE = "silver_team_ratings:fetch_matchup:warehouse"
UNITS = {"OFF_RATING": "points_per_100_possessions",
         "NET_RATING": "points_per_100_possessions"}
NESTED_ROWS = {
    "teams": [HOME.display_name, AWAY.display_name],
    "ratings": {
        str(HOME.id): {"TEAM": HOME.display_name, "TEAM_ID": int(HOME.id),
                       "OFF_RATING": 116.6, "NET_RATING": 1.3},
        str(AWAY.id): {"TEAM": AWAY.display_name, "TEAM_ID": int(AWAY.id),
                       "OFF_RATING": 115.9, "NET_RATING": 3.4},
    },
    "injuries": {str(HOME.id): [], str(AWAY.id): []},
}
AMBIGUOUS_ROWS = {
    **NESTED_ROWS,
    "splits": {"home": {"NET_RATING": 1.3}, "away": {"NET_RATING": 1.3}},
}
RENAMED_ROWS = {
    "teams": [HOME.display_name, AWAY.display_name],
    "metrics": {"OFFENSIVE_RATING": 116.6, "NET_VALUE": 1.3},
}
RENAMED_UNITS = {"OFFENSIVE_RATING": "points_per_100_possessions",
                 "NET_VALUE": "points_per_100_possessions"}
HOME_TEXT = ("North Bay Kings finished at 116.6 offensive rating and 1.3 net "
             "rating (points per 100 possessions) in 2024-25.")
TIED_TEXT = ("North Bay Kings held a 1.3 net rating (points per 100 possessions) "
             "across splits in 2024-25.")
REFUSAL = "I could not verify a publishable answer"


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
def _chat_budget():
    from v2.api import routes

    routes._CHAT_HITS.clear()
    yield
    routes._CHAT_HITS.clear()


def _envelope(rows, units=None) -> EvidenceEnvelope:
    return EvidenceEnvelope(
        evidence_id=EVIDENCE_ID,
        capability="matchup_brief",
        source=WAREHOUSE_SOURCE,
        observed_at=datetime(2026, 9, 8, 12, tzinfo=UTC),
        season=SEASON,
        as_of=AS_OF,
        entities=[HOME, AWAY],
        rows=rows,
        units=dict(UNITS if units is None else units),
        source_identity={"kind": "warehouse", "warehouse_id": "frozen-eval",
                         "sha256": "a" * 64},
    )


class StampedCapability(FakeCapability):
    def __init__(self, envelope: EvidenceEnvelope) -> None:
        super().__init__("matchup_brief", envelope.rows)
        self._envelope = envelope

    async def execute(self, node, task, evidence):
        return self._envelope


class Intake:
    async def understand(self, request: str) -> TaskSpec:
        return TaskSpec(
            goal=request, mode=RunMode.QUICK,
            deliverable="the matchup numbers",
            requested_outputs=list(REQUESTED),
            season=SeasonRef(value=SEASON, source="user", confidence=1.0))


class Planner:
    async def plan(self, task: TaskSpec) -> Plan:
        return Plan(nodes=[PlanNode(
            id=NODE_ID, description="matchup brief for the season",
            capability_hints=["matchup_brief"])])


class Synthesizer:
    def __init__(self, claims) -> None:
        self._claims = list(claims)

    async def synthesize(self, task, evidence) -> DraftReport:
        return DraftReport(sections=["Matchup"], claims=self._claims)


class PassingSemantic:
    async def verify(self, task, draft, evidence) -> VerificationReport:
        return VerificationReport(
            status=VerificationStatus.PASS,
            claim_results=[{"claim_index": index, "supported": True}
                           for index, _claim in enumerate(draft.claims)])


def _binding(output_id: str, selector: str, value: dict, unit: str | None,
             *, subject: bool = True) -> EvidenceOutputBinding:
    return EvidenceOutputBinding(
        requirement_kind="task", requirement_id=None, output_id=output_id,
        node_id=NODE_ID, evidence_id=EVIDENCE_ID, selector=selector,
        row_selector="rows[0]" if subject else None,
        subject_entity_type="team" if subject else None,
        subject_entity_id=HOME.id if subject else None,
        subject_selector="rows[0].TEAM_ID" if subject else None,
        value=value,
        unit=({"kind": "declared", "value": unit} if unit
              else {"kind": "unitless"}),
        domain="matchup_brief")


def _off_rating() -> EvidenceOutputBinding:
    return _binding("OFF_RATING", "rows[0].OFF_RATING",
                    {"kind": "float", "value": 116.6},
                    "points_per_100_possessions")


def _net_rating(*, subject: bool = True) -> EvidenceOutputBinding:
    return _binding("NET_RATING", "rows[0].NET_RATING",
                    {"kind": "float", "value": 1.3},
                    "points_per_100_possessions", subject=subject)


def _injuries() -> EvidenceOutputBinding:
    return _binding("INJURED_PLAYERS", "rows[0].INJURY_COUNT",
                    {"kind": "integer", "value": 3}, None)


def _claim(*bindings, text=HOME_TEXT) -> Claim:
    return Claim(text=text, kind=ClaimKind.OBSERVED,
                 evidence_ids=[EVIDENCE_ID], output_bindings=list(bindings))


def _runtime(claims, rows, units=None) -> Runtime:
    envelope = _envelope(rows, units)
    return Runtime(
        intake=Intake(), planner=Planner(),
        executor=PlanExecutor({"matchup_brief": StampedCapability(envelope)}),
        synthesizer=Synthesizer(claims),
        mechanical_verifier=MechanicalVerifier(),
        semantic_verifier=PassingSemantic())


def _stream(monkeypatch, tmp_path, runtime: Runtime):
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
        json={"q": "How did the North Bay Kings rate in 2024-25?"})
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


def test_the_verified_answer_a_flat_selector_used_to_strand_now_publishes(
        monkeypatch, tmp_path):
    text, custom, final = _stream(
        monkeypatch, tmp_path,
        _runtime([_claim(_off_rating(), _net_rating())], NESTED_ROWS))

    cited = _cited(custom)
    assert cited["OFF_RATING"]["value"] == "116.6"
    assert cited["NET_RATING"]["value"] == "1.3"
    assert cited["OFF_RATING"]["subject_id"] == HOME.id
    assert cited["OFF_RATING"]["provenance"] == {
        "capability": "matchup_brief", "origin": "warehouse",
        "warehouse_id": "frozen-eval", "season": SEASON,
        "as_of": AS_OF.isoformat(), "live_sources": []}
    assert [item["status"] for item in final["carry"]["output_statuses"]
            if item["output_id"] != "INJURED_PLAYERS"] == ["complete", "complete"]
    assert final["text"].startswith("North Bay Kings finished")
    assert REFUSAL not in final["text"]
    assert final["carry"]["verified_claims"] == 1
    for internal in (EVIDENCE_ID, "rows[0].OFF_RATING", "TEAM_ID", "ratings"):
        assert internal not in text


def test_one_selector_that_names_no_value_drops_only_its_own_field(
        monkeypatch, tmp_path):
    text, custom, final = _stream(
        monkeypatch, tmp_path,
        _runtime([_claim(_injuries(), _off_rating(), _net_rating())],
                 NESTED_ROWS))

    cited = _cited(custom)
    assert {row["output_id"]: row["value"] for row in custom["tables"]} == {
        "OFF_RATING": "116.6", "NET_RATING": "1.3"}
    assert "INJURED_PLAYERS" not in cited
    assert custom["unverified_numbers"] == [
        "INJURED PLAYERS could not be traced to the source data."]
    assert REFUSAL not in final["text"]
    assert final["carry"]["verified_claims"] == 1


def test_a_selector_that_names_two_rows_publishes_neither_of_them(
        monkeypatch, tmp_path):
    text, custom, final = _stream(
        monkeypatch, tmp_path,
        _runtime([_claim(_injuries(), _net_rating(subject=False))],
                 AMBIGUOUS_ROWS))

    assert custom["tables"] == []
    assert custom["unverified_numbers"] == [
        "INJURED PLAYERS could not be traced to the source data.",
        "NET RATING could not be traced to the source data.",
        "OFF RATING could not be traced to the source data.",
    ]
    assert REFUSAL not in final["text"]
    assert final["carry"]["verified_claims"] == 1


def test_an_ambiguous_selector_withholds_only_its_own_claim(
        monkeypatch, tmp_path):
    text, custom, final = _stream(
        monkeypatch, tmp_path,
        _runtime([_claim(_off_rating()),
                  _claim(_net_rating(subject=False), text=TIED_TEXT)],
                 AMBIGUOUS_ROWS))

    cited = _cited(custom)
    assert cited["OFF_RATING"]["value"] == "116.6"
    assert "NET_RATING" not in cited
    assert "NET RATING could not be traced to the source data." in (
        custom["unverified_numbers"])
    assert "NET_RATING could not be verified (rejected)." in final["text"]
    assert REFUSAL not in final["text"]
    assert final["carry"]["verified_claims"] == 2


def test_a_verified_run_whose_selectors_all_miss_never_reads_as_a_clean_refusal(
        monkeypatch, tmp_path):
    text, custom, final = _stream(
        monkeypatch, tmp_path, _runtime([_claim(_off_rating(), _net_rating())],
                                        RENAMED_ROWS, RENAMED_UNITS))

    assert custom["tables"] == []
    assert REFUSAL not in final["text"]
    assert final["carry"]["verified_claims"] == 1
    assert final["text"].splitlines() == [
        "Some requested outputs could not be published.",
        "OFF_RATING could not be verified (rejected).",
        "NET_RATING could not be verified (rejected).",
        "INJURED_PLAYERS could not be verified (missing)."]
    assert custom["unverified_numbers"] == [
        "OFF RATING could not be traced to the source data.",
        "NET RATING could not be traced to the source data.",
        "INJURED PLAYERS could not be traced to the source data.",
    ]
