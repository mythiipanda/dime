import json
import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

FIXTURES = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "nba_awards"

PLAYER_IDS = (2544, 203497, 2037, 203506, 201566)


def _payload(player_id: int) -> dict:
    return json.loads(
        (FIXTURES / f"player_awards_{player_id}.json").read_text(
            encoding="utf-8"))


@pytest.fixture(scope="module")
def recorded_awards(tmp_path_factory):
    import seed_nba_awards as seed
    from shared import store
    from shared.sources import nba_awards as src

    root = tmp_path_factory.mktemp("v2_recorded_awards")
    recorded = root / "recorded.duckdb"
    original = (store.DB_PATH, store.LOCK_PATH)
    store.DB_PATH = recorded
    store.LOCK_PATH = root / ".write.lock"
    try:
        for player_id in PLAYER_IDS:
            frame = src.parse_player_awards(_payload(player_id))
            seed.save_player_rows(player_id, frame)
    finally:
        store.DB_PATH, store.LOCK_PATH = original
    return recorded


@pytest.fixture
def awards_warehouse(recorded_awards, tmp_path, monkeypatch):
    from shared import store
    from shared.tools import _core
    from v2.adapters import coverage

    path = tmp_path / "awards.duckdb"
    shutil.copyfile(recorded_awards, path)
    monkeypatch.setattr(store, "DB_PATH", path)
    monkeypatch.setattr(store, "LOCK_PATH", tmp_path / ".write.lock")
    store.warehouse_tables_cache_clear()
    store.warehouse_pool_clear()
    store.warehouse_identity_cache_clear()
    _core.last_completed_season_cache_clear()
    coverage.coverage_cache_clear()
    return path


@pytest.fixture(autouse=True)
def _open_chat_budget():
    from v2.api import routes

    routes._CHAT_HITS.clear()
    yield
    routes._CHAT_HITS.clear()


def test_the_capability_names_its_tool_and_its_coverage_table():
    from shared.tools import v1_tools
    from v2.adapters.capabilities import CAPABILITIES
    from v2.adapters.coverage import tables_for_capability
    from v2.runtime.assembly import capability_catalog

    spec = CAPABILITIES["award_results"]
    assert spec.tool_name == "get_award_results"
    assert spec.tool_name in {tool.name for tool in v1_tools}
    assert tables_for_capability("award_results", {}) == ("silver_award_winners",)
    assert "award_results" in capability_catalog()
    assert spec.task_season_scoped is True
    assert spec.season_arg == "season"


def test_the_catalog_publishes_the_view_enum_so_no_routing_can_pick_one():
    from v2.argument_schemas import compile_capability_catalog
    from v2.runtime.assembly import capability_catalog

    compiled = compile_capability_catalog(capability_catalog())
    row = next(item for item in compiled["capabilities"]
               if item["capability_id"] == "award_results")
    assert row["status"] == "REPRESENTABLE"
    view = next(prop for prop in row["properties"] if prop["property"] == "view")
    assert view["required"] is True
    assert view["branches"][0]["constraints"]["enum"] == [
        "winner", "field", "player_awards"]


def test_the_capability_declares_units_for_every_numeric_output():
    from v2.adapters.capabilities import CAPABILITIES, COUNT

    units = CAPABILITIES["award_results"].units
    assert units == {"rank": COUNT}
    definitions = CAPABILITIES["award_results"].metric_definitions
    assert "Always 1" in definitions["rank"]


def test_the_declared_vocabulary_covers_every_field_the_award_tool_returns(
        awards_warehouse):
    from v2.adapters import call_capability
    from v2.adapters.capabilities import CAPABILITIES

    envelope = call_capability("award_results", {
        "view": "winner", "award": "MVP", "season": "2008-09"})
    returned = set(envelope.rows["placements"][0])
    declared = (set(CAPABILITIES["award_results"].units)
                | set(CAPABILITIES["award_results"].metric_definitions))
    assert not returned - declared
    assert {"player", "rank"} <= declared


def test_the_names_a_planner_asks_for_resolve_to_a_returned_field():
    from v2.adapters.capabilities import CAPABILITIES, resolve_metric_column

    spec = CAPABILITIES["award_results"]
    for column in ("PLAYER", "RANK"):
        assert resolve_metric_column(spec, column) == column.lower(), column
    assert resolve_metric_column(spec, "PLAYER_NAME") == "player"
    assert resolve_metric_column(spec, "COACH_NAME") == "coach"
    assert resolve_metric_column(spec, "VOTE_SHARE") is None
    assert resolve_metric_column(spec, "HOME_RUNS") is None


def test_the_capability_description_separates_a_result_from_a_race():
    from v2.adapters.capabilities import CAPABILITY_DESCRIPTIONS

    description = CAPABILITY_DESCRIPTIONS["award_results"]
    assert "Official recorded NBA award winners" in description
    assert "never a model score" in description


def test_a_real_season_through_the_capability_returns_the_recorded_winner(
        awards_warehouse):
    from v2.adapters import call_capability

    envelope = call_capability(
        "award_results", {"view": "winner", "award": "MVP", "season": "2008-09"})
    assert envelope.capability == "award_results"
    assert envelope.season == "2008-09"
    assert envelope.rows["placements"] == [{
        "season": "2008-09",
        "award": "MVP",
        "player": "LeBron James",
        "coach": None,
        "team": "Cleveland Cavaliers",
        "age": None,
        "rank": 1,
        "rank_label": "1",
        "tied": False,
        "award_share": None,
        "points_won": None,
        "points_max": None,
        "votes_first": None,
        "votes_second": None,
        "votes_third": None,
    }]
    assert envelope.units == {"rank": "count"}
    assert "never a model score" in envelope.coverage
    assert envelope.source_identity.kind == "warehouse"
    assert envelope.source == "v1:get_award_results:warehouse"
    assert envelope.as_of is not None


def test_every_declared_unit_reaches_a_row_the_verifier_can_find(
        awards_warehouse):
    from v2.adapters import call_capability
    from v2.adapters.capabilities import CAPABILITIES
    from v2.domain.evidence import iter_values

    envelope = call_capability("award_results", {
        "view": "winner", "award": "MVP", "season": "2008-09"})
    row_keys = {
        segment.split("[", 1)[0].casefold()
        for item in iter_values(envelope)
        for segment in item.path.split(".")
    }
    declared = {key.casefold() for key in CAPABILITIES["award_results"].units}
    assert not declared - row_keys
    assert set(envelope.units) <= declared


class WinnerIntake:
    def __init__(self) -> None:
        from v2.contracts import RunMode, SeasonRef, TaskSpec

        self._task = TaskSpec(
            goal="Who won the 2008-09 MVP?",
            mode=RunMode.QUICK,
            deliverable="the winner",
            requested_outputs=["PLAYER_NAME"],
            season=SeasonRef(value="2008-09", source="user", confidence=1.0))

    async def understand(self, request: str, context=()):
        return self._task


class WinnerPlanner:
    async def plan(self, task, failure_context=None):
        from v2.contracts import Plan, PlanNode

        return Plan(nodes=[PlanNode(
            id="mvp_winner", description="official 2008-09 MVP result",
            capability_hints=["award_results"],
            arguments={"view": "winner", "award": "MVP"})])


class WinnerSynthesizer:
    async def synthesize(self, task, evidence):
        from v2.contracts import Claim, ClaimKind, DraftReport, EvidenceOutputBinding

        envelope = next(iter(evidence))
        player = envelope.rows["placements"][0]["player"]
        binding = EvidenceOutputBinding(
            requirement_kind="task", requirement_id=None,
            output_id="PLAYER_NAME", node_id="mvp_winner",
            evidence_id=envelope.evidence_id, selector="rows[0].player",
            value={"kind": "string", "value": player},
            unit={"kind": "unitless"},
            domain="award_results")
        return DraftReport(
            sections=["MVP"],
            claims=[Claim(
                text=f"{player} won the {envelope.season} MVP.",
                kind=ClaimKind.OBSERVED,
                evidence_ids=[envelope.evidence_id],
                output_bindings=[binding])])


class WinnerSemantic:
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


def test_the_flat_selector_the_synthesizer_is_taught_reaches_a_nested_row(
        awards_warehouse, monkeypatch, tmp_path):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from v2.adapters.core import ToolCapability
    from v2.api import routes
    from v2.projects.service import ProjectStore
    from v2.runtime import PlanExecutor, Runtime
    from v2.runtime.assembly import MechanicalVerifier
    from v2.runtime.ledger import RunLedger

    runtime = Runtime(
        intake=WinnerIntake(), planner=WinnerPlanner(),
        executor=PlanExecutor(
            {"award_results": ToolCapability("award_results")}),
        synthesizer=WinnerSynthesizer(),
        mechanical_verifier=MechanicalVerifier(),
        semantic_verifier=WinnerSemantic())

    def build(**kwargs):
        return runtime, RunLedger(kwargs["run_id"])

    monkeypatch.setenv("DIME_RUNTIME_V2", "on")
    monkeypatch.setattr("shared.providers.resolve_model_id",
                        lambda value: ("openrouter", "fixture"))
    monkeypatch.setattr("v2.runtime.assembly.build_runtime", build)
    monkeypatch.setattr(routes, "_PROJECTS", ProjectStore(tmp_path / "p.sqlite"))
    routes._CHAT_HITS.clear()
    app = FastAPI()
    app.include_router(routes.router, prefix="/api")
    response = TestClient(app).post(
        "/api/v2/chat/stream",
        json={"q": "Who won the 2008-09 MVP?"})
    assert response.status_code == 200

    custom = _event(response.text, "custom_data")
    cited = custom["tables"]
    final = _event(response.text, "final_answer")
    assert [row["output_id"] for row in cited] == ["PLAYER_NAME"]
    assert cited[0]["value"] == "LeBron James"
    assert cited[0]["provenance"]["capability"] == "award_results"
    assert cited[0]["provenance"]["origin"] == "warehouse"
    assert custom["unverified_numbers"] == []
    assert "I could not verify a publishable answer" not in final["text"]
    assert final["carry"]["verified_claims"] == 1
    assert "rows[0].player" not in response.text
    assert "placements" not in response.text


RECORDED_WINNERS = {
    "2008-09": {"award": "MVP", "player": "LeBron James"},
    "2023-24": {"award": "DPOY", "player": "Rudy Gobert"},
}
AWARD_OUTPUTS = ["PLAYER_NAME"]
OFF_BOARD_PLAYER = "Ada Vega"
REFUSAL = "I could not verify a publishable answer"


class WinnersIntake:
    def __init__(self, season: str, award: str) -> None:
        from v2.contracts import RunMode, SeasonRef, TaskSpec

        label = {"MVP": "MVP", "DPOY": "Defensive Player of the Year"}[award]
        self._task = TaskSpec(
            goal=f"Who won the {season} {label}?",
            mode=RunMode.QUICK,
            deliverable="the winner",
            requested_outputs=list(AWARD_OUTPUTS),
            season=SeasonRef(value=season, source="user", confidence=1.0))

    async def understand(self, request: str, context=()):
        return self._task


class WinnersPlanner:
    def __init__(self, award: str) -> None:
        self._award = award

    async def plan(self, task, failure_context=None):
        from v2.contracts import Plan, PlanNode

        return Plan(nodes=[PlanNode(
            id="award_winner", description="official award winner",
            capability_hints=["award_results"],
            arguments={"view": "winner", "award": self._award})])


def _admitted_value(raw):
    if isinstance(raw, bool):
        return {"kind": "boolean", "value": raw}
    if isinstance(raw, int):
        return {"kind": "integer", "value": raw}
    if isinstance(raw, float):
        return {"kind": "float", "value": raw}
    return {"kind": "string", "value": str(raw)}


def _award_binding(output_id, node_id, envelope, column, value):
    from v2.contracts import EvidenceOutputBinding

    unit = envelope.units.get(column)
    return EvidenceOutputBinding(
        requirement_kind="task", requirement_id=None, output_id=output_id,
        node_id=node_id, evidence_id=envelope.evidence_id,
        selector=f"rows[0].{column}", value=value,
        unit=({"kind": "declared", "value": unit} if unit
              else {"kind": "unitless"}),
        domain="award_results")


class WinnersSynthesizer:
    def __init__(self, winner_name: str | None = None) -> None:
        self._winner_name = winner_name

    async def synthesize(self, task, evidence):
        from v2.contracts import Claim, ClaimKind, DraftReport

        envelope = next(iter(evidence))
        winner = envelope.rows["placements"][0]
        named = self._winner_name or winner["player"]
        return DraftReport(
            sections=["Awards"],
            claims=[Claim(
                text=(f"{named} won the {winner['award']} in "
                      f"{envelope.season}."),
                kind=ClaimKind.OBSERVED,
                evidence_ids=[envelope.evidence_id],
                output_bindings=[
                    _award_binding("PLAYER_NAME", "award_winner",
                                   envelope, "player",
                                   _admitted_value(named)),
                ])])


def _winners_stream(season, award, monkeypatch, tmp_path, *, winner_name=None):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from v2.adapters.core import ToolCapability
    from v2.api import routes
    from v2.projects.service import ProjectStore
    from v2.runtime import PlanExecutor, Runtime
    from v2.runtime.assembly import MechanicalVerifier
    from v2.runtime.ledger import RunLedger

    runtime = Runtime(
        intake=WinnersIntake(season, award), planner=WinnersPlanner(award),
        executor=PlanExecutor(
            {"award_results": ToolCapability("award_results")}),
        synthesizer=WinnersSynthesizer(winner_name=winner_name),
        mechanical_verifier=MechanicalVerifier(),
        semantic_verifier=WinnerSemantic())

    def build(**kwargs):
        return runtime, RunLedger(kwargs["run_id"])

    monkeypatch.setenv("DIME_RUNTIME_V2", "on")
    monkeypatch.setattr("shared.providers.resolve_model_id",
                        lambda value: ("openrouter", "fixture"))
    monkeypatch.setattr("v2.runtime.assembly.build_runtime", build)
    monkeypatch.setattr(routes, "_PROJECTS", ProjectStore(tmp_path / "p.sqlite"))
    app = FastAPI()
    app.include_router(routes.router, prefix="/api")
    label = {"MVP": "MVP", "DPOY": "Defensive Player of the Year"}[award]
    response = TestClient(app).post(
        "/api/v2/chat/stream",
        json={"q": f"Who won the {season} {label}?"})
    assert response.status_code == 200
    return (_event(response.text, "custom_data"),
            _event(response.text, "final_answer"))


def _authority(custom, final):
    return ([(item["output_id"], item["status"])
             for item in final["carry"]["output_statuses"]],
            {row["output_id"]: row["value"] for row in custom["tables"]})


@pytest.mark.parametrize("season", sorted(RECORDED_WINNERS))
def test_an_award_question_binds_the_recorded_winner(
        awards_warehouse, monkeypatch, tmp_path, season):
    expected = RECORDED_WINNERS[season]
    custom, final = _winners_stream(
        season, expected["award"], monkeypatch, tmp_path)

    statuses, cited = _authority(custom, final)
    assert ("PLAYER_NAME", "complete") in statuses
    assert cited["PLAYER_NAME"] == expected["player"]
    assert {row["provenance"]["capability"] for row in custom["tables"]} == {
        "award_results"}
    assert custom["unverified_numbers"] == []
    assert REFUSAL not in final["text"]


def test_an_award_binding_naming_a_player_off_the_board_is_rejected(
        awards_warehouse, monkeypatch, tmp_path):
    from v2.adapters import call_capability

    winners = call_capability("award_results", {
        "view": "winner", "award": "MVP", "season": "2008-09"})
    assert OFF_BOARD_PLAYER not in {
        row["player"] for row in winners.rows["placements"]}

    custom, final = _winners_stream(
        "2008-09", "MVP", monkeypatch, tmp_path, winner_name=OFF_BOARD_PLAYER)

    statuses, cited = _authority(custom, final)
    assert ("PLAYER_NAME", "rejected") in statuses
    assert "PLAYER_NAME could not be verified (rejected)." in final["text"]


def test_a_coach_award_fails_loudly_end_to_end(awards_warehouse):
    from v2.adapters import call_capability
    from v2.adapters.core import AdapterError

    with pytest.raises(AdapterError) as excinfo:
        call_capability("award_results", {
            "view": "winner", "award": "COY", "season": "2008-09"})
    message = str(excinfo.value)
    assert "get_award_results" in message
    assert "Coach of the Year" in message
    assert "players only" in message


def test_an_award_a_player_never_won_fails_loudly_end_to_end(awards_warehouse):
    from v2.adapters import call_capability
    from v2.adapters.core import AdapterError

    with pytest.raises(AdapterError) as excinfo:
        call_capability("award_results", {
            "view": "player_awards", "award": "MVP", "season": "2023-24",
            "player": "Jamal Crawford"})
    message = str(excinfo.value)
    assert "MVP" in message
    assert "Jamal Crawford" in message
    assert "6MOY" in message


def test_a_season_with_no_recorded_winners_fails_loudly_end_to_end(
        awards_warehouse):
    from v2.adapters import call_capability
    from v2.adapters.core import AdapterError

    with pytest.raises(AdapterError) as excinfo:
        call_capability("award_results", {
            "view": "winner", "award": "MVP", "season": "1984-85"})
    assert "1984-85" in str(excinfo.value)


def test_the_tool_argument_is_rejected_on_an_award_view_end_to_end(
        awards_warehouse):
    from v2.adapters import call_capability
    from v2.adapters.core import AdapterError

    with pytest.raises(AdapterError) as excinfo:
        call_capability("award_results", {
            "view": "winner", "award": "MVP", "season": "2008-09",
            "player": "LeBron James"})
    assert "player_awards" in str(excinfo.value)


def test_intake_blames_the_awards_table_for_an_uncovered_award_season(
        awards_warehouse):
    from v2.adapters.capabilities import CAPABILITIES
    from v2.adapters.models import ModelIntake
    from v2.contracts import EvidenceRequirement, SeasonRef, TaskSpec

    def task(season: str) -> TaskSpec:
        return TaskSpec(
            goal="Who won the MVP?",
            mode="quick",
            deliverable="answer",
            season=SeasonRef(value=season, source="user", confidence=1.0),
            required_evidence=["award_results"],
            requirements=[EvidenceRequirement(
                id="awards",
                description="Award result",
                capability_options=["award_results"],
                capability_arguments={"season": season},
            )],
        )

    covered = ModelIntake._mark_uncovered_season(task("2008-09"))
    assert covered.open_questions == []
    assert covered.assumptions == []
    blocked = ModelIntake._mark_uncovered_season(task("1984-85"))
    joined = " ".join([*blocked.open_questions, *blocked.assumptions])
    assert "silver_award_winners" in joined
    assert "1984-85" in joined
    assert "2025-26" in joined
    assert CAPABILITIES["award_results"].task_season_scoped is True


def test_the_projection_and_the_result_declare_themselves_apart(
        awards_warehouse, monkeypatch):
    from shared.tools import awards as projection
    from v2.adapters.capabilities import CAPABILITIES

    monkeypatch.setattr(projection, "clamp_season", lambda season: season)
    monkeypatch.setattr(projection, "_missing_table", lambda: None)
    monkeypatch.setattr(projection, "_standings_for", lambda season: {
        "table": "silver_standings", "coverage": "current"})
    monkeypatch.setattr(projection, "_pool", lambda season: [
        {"player": "A", "team": "AAA", "gp": 50, "mins": 1500,
         "ppg": 20, "eff_pg": 20, "apg": 5, "rpg": 7, "age": 20},
        {"player": "B", "team": "BBB", "gp": 50, "mins": 1500,
         "ppg": 10, "eff_pg": 10, "apg": 2, "rpg": 3, "age": 20},
    ])
    race = projection.get_award_race.invoke({"award": "ROY", "season": "2025-26"})
    assert race["meta"]["results_tool"] == "get_award_results"
    assert "not points, probability, vote share" in race["meta"]["score_definition"]
    assert CAPABILITIES["award_results"].tool_name != "get_award_race"


GOLDEN_CALLS = {
    "award-mvp-winner": ({"view": "winner", "award": "MVP"}, "answer"),
    "award-dpoy-winner": ({"view": "winner", "award": "DPOY"}, "answer"),
    "award-sixth-man-winner": ({"view": "winner", "award": "6MOY"}, "answer"),
    "award-mvp-no-recorded-winner": (
        {"view": "winner", "award": "MVP"}, "refuse"),
}


def _golden_scenarios():
    from v2.tests.compatibility.harness import load_pack

    pack = load_pack(Path(__file__).resolve().parent
                     / "compatibility" / "fixtures" / "scenarios.json")
    return [scenario for scenario in pack["scenarios"]
            if scenario["id"] in GOLDEN_CALLS]


def test_the_pack_carries_a_golden_question_for_every_award_call_shape():
    assert {scenario["id"] for scenario in _golden_scenarios()} == set(
        GOLDEN_CALLS)
    for scenario in _golden_scenarios():
        assert "award" in scenario["tags"]
        assert scenario["budget"]["max_tool_calls"] <= 2


def test_every_golden_award_question_is_answered_by_the_recorded_table(
        awards_warehouse):
    from v2.adapters import call_capability
    from v2.adapters.core import AdapterError
    from v2.domain.evidence import iter_values

    for scenario in _golden_scenarios():
        arguments, expected = GOLDEN_CALLS[scenario["id"]]
        call = {**arguments, "season": scenario["season"]}
        question = scenario["chain"][0]
        if expected == "refuse":
            with pytest.raises(AdapterError) as excinfo:
                call_capability("award_results", call)
            assert scenario["season"] in str(excinfo.value), question
            continue
        envelope = call_capability("award_results", call)
        assert envelope.season == scenario["season"], question
        values = {
            str(item.value).replace(",", "")
            for item in iter_values(envelope) if item.value is not None
        }
        requirement = scenario.get("evidence_requirement", {})
        assert "award_results" in requirement["any_capability"], question
        for needle in requirement["required_values"]:
            assert needle.replace(",", "") in values, (question, needle)
        for needle in requirement.get("metric_definitions_contain", []):
            assert any(needle in value
                       for value in envelope.metric_definitions.values()), (
                           question, needle)


def test_the_golden_winner_scenarios_answer_from_winners_not_a_race(
        awards_warehouse):
    from v2.adapters import call_capability

    envelope = call_capability("award_results", {
        "view": "winner", "award": "MVP", "season": "2008-09"})
    assert {row["rank"] for row in envelope.rows["placements"]} == {1}
    assert {row["rank_label"] for row in envelope.rows["placements"]} == {"1"}
