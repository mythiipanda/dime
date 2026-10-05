import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

RUNTIME_WAREHOUSE = BACKEND / "data" / "warehouse-runtime.duckdb"

pytestmark = pytest.mark.skipif(
    not RUNTIME_WAREHOUSE.exists(),
    reason=f"the runtime warehouse is absent at {RUNTIME_WAREHOUSE}")


@pytest.fixture
def runtime_awards(monkeypatch):
    from shared import store
    from shared.tools import _core
    from v2.adapters import coverage

    connect = store.connect
    monkeypatch.setattr(store, "DB_PATH", RUNTIME_WAREHOUSE)
    monkeypatch.setattr(store, "connect",
                        lambda read_only=True: connect(read_only=True))
    store.warehouse_tables_cache_clear()
    store.warehouse_pool_clear()
    store.warehouse_identity_cache_clear()
    _core.last_completed_season_cache_clear()
    coverage.coverage_cache_clear()
    yield RUNTIME_WAREHOUSE
    store.warehouse_tables_cache_clear()
    store.warehouse_pool_clear()
    store.warehouse_identity_cache_clear()
    _core.last_completed_season_cache_clear()
    coverage.coverage_cache_clear()


def _results(**arguments):
    from shared.tools.award_results import get_award_results

    return get_award_results.invoke(arguments)


MVP_LEADERS = (
    ("2024-25", "Shai Gilgeous-Alexander", "OKC", 26, 913, 1000, 0.913, 71),
    ("2023-24", "Nikola Jokić", "DEN", 28, 926, 990, 0.935, 79),
    ("2019-20", "Giannis Antetokounmpo", "MIL", 25, 962, 1010, 0.952, 85),
)


@pytest.mark.parametrize(
    "season,player,team,age,won,maximum,share,votes",
    MVP_LEADERS,
)
def test_a_real_season_returns_the_real_winner_and_share(
        runtime_awards, season, player, team, age, won, maximum, share, votes):
    result = _results(view="winner", award="MVP", season=season)
    assert result["ok"] is True, result
    assert result["rows"] == [{
        "season": season,
        "award": "MVP",
        "player": player,
        "coach": None,
        "team": team,
        "age": age,
        "rank": 1,
        "rank_label": "1",
        "tied": False,
        "award_share": share,
        "points_won": won,
        "points_max": maximum,
        "votes_first": votes,
        "votes_second": None,
        "votes_third": None,
    }]
    assert result["meta"]["ballot"] is True
    assert result["meta"]["vote_columns"] == ["votes_first"]
    assert result["meta"]["dataset"] == "basketball-reference"


def test_a_coach_award_names_its_coach_and_its_votes(runtime_awards):
    result = _results(view="winner", award="COY", season="2015-16")
    assert result["ok"] is True, result
    assert result["rows"] == [{
        "season": "2015-16",
        "award": "COY",
        "player": None,
        "coach": "Steve Kerr",
        "team": "GSW",
        "age": None,
        "rank": 1,
        "rank_label": "1",
        "tied": False,
        "award_share": 0.586,
        "points_won": 381,
        "points_max": 650,
        "votes_first": 64,
        "votes_second": None,
        "votes_third": None,
    }]
    assert result["meta"]["award_subject"] == "coach"


def test_a_season_whose_ballot_never_existed_fails_loud_naming_the_season(
        runtime_awards):
    result = _results(view="winner", award="MVP", season="1981-82")
    assert result["ok"] is False
    assert result["rows"] == {}
    assert "1981-82" in result["error"]
    assert "1976-77" in result["error"]
    assert "2025-26" in result["error"]
    assert "never estimates" in result["error"]


def test_a_tied_rank_keeps_the_published_rank_and_marks_the_tie(runtime_awards):
    result = _results(view="field", award="DPOY", season="2024-25")
    assert result["ok"] is True, result
    tied = [row for row in result["rows"]
            if row["rank_label"] == "10T"]
    assert [row["player"] for row in tied] == [
        "Bam Adebayo", "Derrick White", "Shai Gilgeous-Alexander"]
    assert {row["rank"] for row in tied} == {10}
    assert {row["tied"] for row in tied} == {True}
    assert {row["award_share"] for row in tied} == {0.006}


def test_a_row_that_made_no_team_keeps_a_null_rank_and_its_published_label(
        runtime_awards):
    result = _results(view="field", award="ALL_NBA", season="2024-25")
    assert result["ok"] is True, result
    placements = result["rows"]
    other = [row for row in placements if row["rank_label"] == "ORV"]
    assert len(other) == 9
    assert {row["rank"] for row in other} == {None}
    assert {row["tied"] for row in other} == {False}
    ranked = [row for row in placements if row["rank"] is not None]
    assert min(row["rank"] for row in ranked) == 1
    assert placements[-1]["rank"] is None


def test_a_tied_first_team_keeps_every_leading_player(runtime_awards):
    result = _results(view="winner", award="ALL_NBA", season="2024-25")
    assert result["ok"] is True, result
    placements = result["rows"]
    assert {row["rank"] for row in placements} == {1}
    assert {row["rank_label"] for row in placements} == {"1T"}
    assert {row["tied"] for row in placements} == {True}
    assert {row["player"] for row in placements} == {
        "Giannis Antetokounmpo", "Shai Gilgeous-Alexander", "Nikola Jokić",
        "Jayson Tatum", "Donovan Mitchell"}
    assert result["meta"]["honors_teams"] == 3


def test_a_team_award_is_not_reported_as_a_tie(runtime_awards):
    result = _results(view="winner", award="ALL_DEFENSE", season="2024-25")
    assert result["ok"] is True, result
    placements = result["rows"]
    assert {row["rank_label"] for row in placements} == {"1st"}
    assert {row["tied"] for row in placements} == {False}
    assert result["meta"]["ballot"] is False
    assert result["meta"]["vote_columns"] == []


def test_the_runtime_warehouse_answers_every_season_it_records(
        runtime_awards):
    from shared.tools.award_results import (
        TABLE,
        AwardResultError,
        _season_guard,
    )
    from v2.adapters.coverage import table_seasons

    answerable = sorted(table_seasons(TABLE))
    assert len(answerable) == 47
    assert answerable[0] == "1976-77"
    assert answerable[-1] == "2025-26"
    assert all(_season_guard(season) == season for season in answerable)
    for season in ("1981-82", "1982-83", "1984-85"):
        with pytest.raises(AwardResultError) as excinfo:
            _season_guard(season)
        assert season in str(excinfo.value)


def test_the_coverage_registry_names_the_table_the_awards_tool_reads(
        runtime_awards):
    from shared.tools.award_results import TABLE
    from v2.adapters.capabilities import CAPABILITIES
    from v2.adapters.coverage import (
        absent_tables_for_capability,
        declared_tables_for_capability,
        warehouse_tables,
    )

    assert declared_tables_for_capability("award_results", {}) == (TABLE,)
    assert absent_tables_for_capability("award_results", {}) == ()
    assert TABLE in warehouse_tables()
    coverage_text = CAPABILITIES["award_results"].coverage
    assert "Basketball-Reference" in coverage_text
    assert "nba_api" not in coverage_text


def test_intake_accepts_every_award_season_the_runtime_warehouse_records(
        runtime_awards):
    from v2.adapters.models import ModelIntake
    from v2.contracts import EvidenceRequirement, SeasonRef, TaskSpec

    def task(season: str, award: str) -> TaskSpec:
        return TaskSpec(
            goal=f"Who won the {season} {award}?",
            mode="quick",
            deliverable="answer",
            season=SeasonRef(value=season, source="user", confidence=1.0),
            required_evidence=["award_results"],
            requirements=[EvidenceRequirement(
                id="awards",
                description="Award result",
                capability_options=["award_results"],
                capability_arguments={"season": season, "award": award},
            )],
        )

    for season, award in (("2024-25", "MVP"), ("2019-20", "MVP"),
                          ("2015-16", "COY"), ("2023-24", "ALL_NBA")):
        marked = ModelIntake._mark_uncovered_season(task(season, award))
        assert list(marked.open_questions) == [], (season, award)
        assert list(marked.assumptions) == [], (season, award)

    refused = ModelIntake._mark_uncovered_season(task("1981-82", "MVP"))
    joined = " ".join([*refused.open_questions, *refused.assumptions])
    assert "1981-82" in joined
    assert "silver_bbref_awards" in joined


def test_a_wrong_subject_fails_loud_through_the_capability_end_to_end(
        runtime_awards):
    from v2.adapters import call_capability
    from v2.adapters.core import AdapterError

    with pytest.raises(AdapterError) as excinfo:
        call_capability("award_results", {
            "view": "player_awards", "award": "MVP", "season": "2024-25",
            "player": "Ada Vega"})
    message = str(excinfo.value)
    assert "get_award_results" in message
    assert "Ada Vega" in message
    assert "2024-25" in message


def test_a_missing_table_is_a_loud_absence_naming_the_table(runtime_awards,
                                                          tmp_path,
                                                          monkeypatch):
    import duckdb

    from shared import store
    from shared.tools import award_results
    from v2.adapters import coverage

    empty = tmp_path / "empty.duckdb"
    duckdb.connect(str(empty)).close()
    monkeypatch.setattr(store, "DB_PATH", empty)
    store.warehouse_tables_cache_clear()
    store.warehouse_pool_clear()
    coverage.coverage_cache_clear()

    result = _results(view="winner", award="MVP", season="2024-25")
    assert result["ok"] is False
    assert result["rows"] == {}
    assert award_results.TABLE in result["error"]
    assert "missing" in result["error"]

    from v2.adapters.coverage import absent_tables_for_capability

    assert absent_tables_for_capability("award_results", {}) == (
        award_results.TABLE,)


def test_a_wrong_subject_fails_loud_through_the_chat_stream(runtime_awards,
                                                           monkeypatch,
                                                           tmp_path):
    import json

    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from v2.adapters.core import ToolCapability
    from v2.api import routes
    from v2.contracts import (
        DraftReport,
        Plan,
        PlanNode,
        RunMode,
        SeasonRef,
        TaskSpec,
        VerificationReport,
        VerificationStatus,
    )
    from v2.projects.service import ProjectStore
    from v2.runtime import PlanExecutor, Runtime
    from v2.runtime.assembly import MechanicalVerifier
    from v2.runtime.ledger import RunLedger

    task = TaskSpec(
        goal="What awards did Ada Vega win in 2024-25?",
        mode=RunMode.QUICK,
        deliverable="the award record",
        requested_outputs=["PLAYER_NAME"],
        season=SeasonRef(value="2024-25", source="user", confidence=1.0))

    class Intake:
        async def understand(self, request: str, context=()):
            return task

    class Planner:
        async def plan(self, task, failure_context=None):
            return Plan(nodes=[PlanNode(
                id="award_record", description="published award record",
                capability_hints=["award_results"],
                arguments={"view": "player_awards", "season": "2024-25",
                           "player": "Ada Vega"})])

    class Synthesizer:
        async def synthesize(self, task, evidence):
            return DraftReport(sections=["Awards"], claims=[])

    class Semantic:
        async def verify(self, task, draft, evidence):
            return VerificationReport(
                status=VerificationStatus.PASS,
                claim_results=[{"claim_index": index,
                               "supported": True}
                              for index, _ in enumerate(draft.claims)])

    runtime = Runtime(
        intake=Intake(), planner=Planner(),
        executor=PlanExecutor(
            {"award_results": ToolCapability("award_results")}),
        synthesizer=Synthesizer(),
        mechanical_verifier=MechanicalVerifier(),
        semantic_verifier=Semantic())

    monkeypatch.setenv("DIME_RUNTIME_V2", "on")
    monkeypatch.setattr("shared.providers.resolve_model_id",
                        lambda value: ("openrouter", "fixture"))
    monkeypatch.setattr("v2.runtime.assembly.build_runtime",
                        lambda **kwargs: (runtime, RunLedger(kwargs["run_id"])))
    monkeypatch.setattr(routes, "_PROJECTS",
                        ProjectStore(tmp_path / "p.sqlite"))
    routes._CHAT_HITS.clear()
    app = FastAPI()
    app.include_router(routes.router, prefix="/api")
    response = TestClient(app).post(
        "/api/v2/chat/stream",
        json={"q": "What awards did Ada Vega win in 2024-25?"})
    routes._CHAT_HITS.clear()
    assert response.status_code == 200

    def event(name: str) -> dict:
        payloads = [chunk.split("data: ", 1)[1]
                    for chunk in response.text.split("\n\n")
                    if chunk.startswith(f"event: {name}\n")]
        assert payloads, name
        return json.loads(payloads[-1])

    final = event("final_answer")
    assert "PLAYER_NAME could not be verified (missing)." in final["text"]
    assert final["carry"]["output_statuses"] == [{
        "requirement_kind": "task",
        "requirement_id": None,
        "output_id": "PLAYER_NAME",
        "status": "missing",
    }]
    assert {gap["kind"] for gap in final["carry"]["gaps"]} == {
        "execution_failure"}
    assert {block for gap in final["carry"]["gaps"]
            for block in gap["blocks"]} == {
                "node:award_record", "node:award_record-replan2"}
    assert "Ada Vega" in response.text