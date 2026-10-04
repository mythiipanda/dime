import json
import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

FIXTURES = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "bbref_awards"

RECORDED = (
    (1977, "1976-77"),
    (1998, "1997-98"),
    (2015, "2014-15"),
    (2024, "2023-24"),
    (2026, "2025-26"),
)


def _page(year: int):
    def transport(url: str) -> str:
        return (FIXTURES / f"awards_{year}.html").read_text(encoding="utf-8")

    return transport


@pytest.fixture(scope="module")
def recorded_awards(tmp_path_factory):
    import seed_bbref_awards as seed
    from shared import store

    root = tmp_path_factory.mktemp("v2_recorded_awards")
    recorded = root / "recorded.duckdb"
    original = (store.DB_PATH, store.LOCK_PATH)
    store.DB_PATH = recorded
    store.LOCK_PATH = root / ".write.lock"
    try:
        for year, season in RECORDED:
            seed.seed_season(
                season, transport=_page(year), min_interval_s=0.0)
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


def test_the_capability_names_its_tool_and_its_coverage_table():
    from shared.tools import v1_tools
    from v2.adapters.capabilities import CAPABILITIES
    from v2.adapters.coverage import tables_for_capability
    from v2.runtime.assembly import capability_catalog

    spec = CAPABILITIES["award_results"]
    assert spec.tool_name == "get_award_results"
    assert spec.tool_name in {tool.name for tool in v1_tools}
    assert tables_for_capability("award_results", {}) == ("silver_bbref_awards",)
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
    from v2.adapters.capabilities import BALLOT_POINTS, CAPABILITIES, COUNT, FRACTION

    units = CAPABILITIES["award_results"].units
    assert units == {
        "award_share": FRACTION,
        "points_won": BALLOT_POINTS,
        "points_max": BALLOT_POINTS,
        "votes_first": COUNT,
        "votes_second": COUNT,
        "votes_third": COUNT,
        "age": "years",
    }
    definitions = CAPABILITIES["award_results"].metric_definitions
    assert "fraction scale 0-1" in definitions["award_share"]
    assert "points_max" in definitions["points_won"]


def test_the_capability_description_separates_a_result_from_a_race():
    from v2.adapters.capabilities import CAPABILITY_DESCRIPTIONS

    description = CAPABILITY_DESCRIPTIONS["award_results"]
    assert "Official NBA award results" in description
    assert "never a model score" in description


def test_a_real_season_through_the_capability_returns_the_published_winner(
        awards_warehouse):
    from v2.adapters import call_capability

    envelope = call_capability(
        "award_results", {"view": "winner", "award": "MVP", "season": "2023-24"})
    assert envelope.capability == "award_results"
    assert envelope.season == "2023-24"
    assert envelope.rows["placements"] == [{
        "season": "2023-24",
        "award": "MVP",
        "player": "Nikola Jokić",
        "coach": None,
        "team": "DEN",
        "age": 28,
        "rank": 1,
        "rank_label": "1",
        "tied": False,
        "award_share": 0.935,
        "points_won": 926,
        "points_max": 990,
        "votes_first": 79,
        "votes_second": None,
        "votes_third": None,
    }]
    assert envelope.units == {
        "award_share": "fraction_0_1",
        "points_won": "ballot_points",
        "points_max": "ballot_points",
        "votes_first": "count",
        "votes_second": "count",
        "votes_third": "count",
        "age": "years",
    }
    assert "recorded outcome, never a model score" in envelope.coverage
    assert "ORV" in envelope.coverage or "ORV" in envelope.qualification
    assert envelope.source_identity.kind == "warehouse"
    assert envelope.source == "v1:get_award_results:warehouse"
    assert envelope.as_of is not None


def test_every_declared_unit_reaches_a_row_the_verifier_can_find(
        awards_warehouse):
    from v2.adapters import call_capability
    from v2.adapters.capabilities import CAPABILITIES
    from v2.domain.evidence import iter_values

    envelope = call_capability("award_results", {
        "view": "field", "award": "ALL_NBA", "season": "2023-24"})
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
            goal="Who won the 2023-24 MVP?",
            mode=RunMode.QUICK,
            deliverable="the winner and the share of the vote",
            requested_outputs=["AWARD_SHARE"],
            season=SeasonRef(value="2023-24", source="user", confidence=1.0))

    async def understand(self, request: str, context=()):
        return self._task


class WinnerPlanner:
    async def plan(self, task, failure_context=None):
        from v2.contracts import Plan, PlanNode

        return Plan(nodes=[PlanNode(
            id="mvp_winner", description="official 2023-24 MVP result",
            capability_hints=["award_results"],
            arguments={"view": "winner", "award": "MVP"})])


class WinnerSynthesizer:
    async def synthesize(self, task, evidence):
        from v2.contracts import Claim, ClaimKind, DraftReport, EvidenceOutputBinding

        envelope = next(iter(evidence))
        share = envelope.rows["placements"][0]["award_share"]
        binding = EvidenceOutputBinding(
            requirement_kind="task", requirement_id=None,
            output_id="AWARD_SHARE", node_id="mvp_winner",
            evidence_id=envelope.evidence_id, selector="rows[0].award_share",
            value={"kind": "float", "value": share},
            unit={"kind": "declared", "value": "fraction_0_1"},
            domain="award_results")
        return DraftReport(
            sections=["MVP"],
            claims=[Claim(
                text=(f"{envelope.rows['placements'][0]['player']} won the "
                      f"{envelope.season} MVP, taking {share} of "
                      "first-place votes."),
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
        json={"q": "Who won the 2023-24 MVP?"})
    assert response.status_code == 200

    custom = _event(response.text, "custom_data")
    cited = custom["tables"]
    final = _event(response.text, "final_answer")
    assert [row["output_id"] for row in cited] == ["AWARD_SHARE"]
    assert cited[0]["value"] == "0.935"
    assert cited[0]["provenance"]["capability"] == "award_results"
    assert cited[0]["provenance"]["origin"] == "warehouse"
    assert custom["unverified_numbers"] == []
    assert "I could not verify a publishable answer" not in final["text"]
    assert final["carry"]["verified_claims"] == 1
    assert "rows[0].award_share" not in response.text
    assert "placements" not in response.text



def test_a_coach_asked_for_as_a_player_fails_loudly_end_to_end(awards_warehouse):
    from v2.adapters import call_capability
    from v2.adapters.core import AdapterError

    with pytest.raises(AdapterError) as excinfo:
        call_capability("award_results", {
            "view": "player_awards", "season": "1976-77", "player": "Larry Brown"})
    message = str(excinfo.value)
    assert "get_award_results" in message
    assert "Larry Brown" in message
    assert "coach, not a player" in message
    assert "COY" in message


def test_an_award_a_player_never_won_fails_loudly_end_to_end(awards_warehouse):
    from v2.adapters import call_capability
    from v2.adapters.core import AdapterError

    with pytest.raises(AdapterError) as excinfo:
        call_capability("award_results", {
            "view": "player_awards", "award": "COY", "season": "2023-24",
            "player": "Nikola Jokić"})
    message = str(excinfo.value)
    assert "COY" in message
    assert "Nikola Jokić" in message
    assert "MVP" in message and "ALL_NBA" in message


def test_a_season_whose_ballot_never_existed_fails_loudly_end_to_end(
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
            "view": "field", "award": "MVP", "season": "2023-24",
            "player": "Nikola Jokić"})
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

    covered = ModelIntake._mark_uncovered_season(task("2023-24"))
    assert covered.open_questions == []
    assert covered.assumptions == []
    blocked = ModelIntake._mark_uncovered_season(task("1984-85"))
    joined = " ".join([*blocked.open_questions, *blocked.assumptions])
    assert "silver_bbref_awards" in joined
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
    "award-coach-of-year-winner": ({"view": "winner", "award": "COY"}, "answer"),
    "award-all-nba-first-team": (
        {"view": "winner", "award": "ALL_NBA"}, "answer"),
    "award-mvp-no-published-ballot": (
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


def test_the_golden_winner_scenarios_are_not_a_race(awards_warehouse):
    from v2.adapters import call_capability

    envelope = call_capability("award_results", {
        "view": "winner", "award": "ALL_NBA", "season": "2023-24"})
    labels = {row["rank_label"] for row in envelope.rows["placements"]}
    assert labels == {"1T"}
    assert {row["rank"] for row in envelope.rows["placements"]} == {1}
    assert "never a model score" in envelope.coverage