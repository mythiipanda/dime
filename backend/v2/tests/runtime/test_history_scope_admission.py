from __future__ import annotations

import asyncio

import pytest

from shared.tools.award_results import get_award_results
from shared.tools.league import get_standings
from v2.adapters.core import AdapterError, ToolCapability
from v2.contracts import EntityRef, PlanNode, RunMode, SeasonRef, TaskSpec
from v2.domain.evidence import post_result_denials


class _AwardTool:
    args_schema = get_award_results.args_schema

    def __init__(self, rows, *, season="2025-26", meta=None):
        self.rows = rows
        self.season = season
        self.meta = meta or {}
        self.arguments = None

    async def ainvoke(self, arguments):
        self.arguments = arguments
        return {
            "ok": True,
            "rows": self.rows,
            "meta": {"source": "fixture", "season": self.season, **self.meta},
        }


def _task(*, entity=None, season="2025-26"):
    return TaskSpec(
        goal="Read NBA award history",
        mode=RunMode.QUICK,
        deliverable="Winner rows",
        entities=[entity] if entity else [],
        season=(SeasonRef(value=season, source="default", confidence=1)
                if season is not None else None),
    )


def _node(view="winner_history", **arguments):
    return PlanNode(
        id="awards",
        description="Read award rows",
        capability_hints=["award_results"],
        arguments={"award": "MVP", "view": view, **arguments},
    )


def _row(season, player="LeBron James"):
    return {
        "season": season,
        "award": "MVP",
        "player": player,
        "winner": player,
        "team": "CLE",
        "rank": 1,
        "points_won": 100,
    }


def _execute(tool, task, node=None, capability="award_results"):
    if capability == "standings":
        tool.args_schema = get_standings.args_schema
    executor = ToolCapability(
        capability,
        tools={
            "get_award_results" if capability == "award_results"
            else "get_standings": tool,
        },
    )
    return asyncio.run(executor.execute(node or _node(), task, []))


def test_history_admits_old_rows_through_inclusive_endpoint():
    tool = _AwardTool([_row("1976-77"), _row("2025-26")])
    task = _task(entity=EntityRef(
        id="league", type="league", display_name="NBA"))

    envelope = _execute(tool, task)

    assert envelope.season == "2025-26"
    assert envelope.season_scope == "at_or_before"
    assert envelope.population_scope == EntityRef(
        id="league", type="league", display_name="NBA")
    assert post_result_denials(task, envelope) == []


def test_history_rejects_row_after_endpoint():
    task = _task()
    envelope = _execute(_AwardTool([_row("2026-27")]), task)

    assert [item.check for item in post_result_denials(task, envelope)] == [
        "row_season_mismatch"]


def test_history_uses_envelope_endpoint_when_task_has_no_season():
    task = _task(season=None)
    envelope = _execute(_AwardTool([_row("2026-27")]), task)

    assert envelope.season == "2025-26"
    assert [item.check for item in post_result_denials(task, envelope)] == [
        "row_season_mismatch"]


def test_history_rejects_response_with_wrong_endpoint():
    with pytest.raises(AdapterError, match="response season"):
        _execute(_AwardTool([_row("2025-26")], season="2024-25"), _task())


def test_single_season_view_keeps_exact_row_season_check():
    task = _task(entity=EntityRef(
        id="league", type="league", display_name="NBA"))
    envelope = _execute(
        _AwardTool([_row("1976-77")]), task, _node(view="winner"))

    assert envelope.season_scope == "exact"
    assert envelope.population_scope is None
    assert {item.check for item in post_result_denials(task, envelope)} == {
        "row_season_mismatch", "entity_mismatch"}


def test_history_keeps_explicit_player_membership_check():
    task = _task(entity=EntityRef(
        id="Michael Jordan", type="player", display_name="Michael Jordan"))
    envelope = _execute(_AwardTool([_row("1995-96")]), task)

    assert envelope.population_scope is not None
    assert "entity_mismatch" in {
        item.check for item in post_result_denials(task, envelope)}


def test_player_history_is_admitted_when_filtered_to_that_player():
    player = EntityRef(
        id="LeBron James", type="player", display_name="LeBron James")
    task = _task(entity=player)
    tool = _AwardTool([_row("2024-25")])
    envelope = _execute(tool, task, _node(player="LeBron James"))

    assert tool.arguments["player"] == "LeBron James"
    assert envelope.population_scope is None
    assert post_result_denials(task, envelope) == []


def test_scope_does_not_leak_to_other_view_or_capability():
    league = EntityRef(id="league", type="league", display_name="NBA")
    task = _task(entity=league)
    history = _execute(_AwardTool([_row("2024-25")]), task)
    winner = _execute(
        _AwardTool([_row("2025-26")]), task, _node(view="winner"))
    standings = _execute(
        _AwardTool([{"season": "2025-26", "team": "BOS"}]),
        task,
        PlanNode(
            id="standings",
            description="Read standings",
            capability_hints=["standings"],
            arguments={"season": "2025-26"},
        ),
        capability="standings",
    )

    assert history.population_scope == league
    assert winner.population_scope is None
    assert standings.population_scope is None
    assert standings.season_scope == "exact"


def test_model_result_metadata_cannot_override_adapter_scope():
    task = _task(entity=EntityRef(
        id="league", type="league", display_name="NBA"))
    tool = _AwardTool(
        [_row("1976-77")],
        meta={
            "season_scope": "exact",
            "population_scope": {"id": "other", "type": "league",
                                "display_name": "Other"},
        },
    )
    envelope = _execute(tool, task)

    assert envelope.season_scope == "at_or_before"
    assert envelope.population_scope == EntityRef(
        id="league", type="league", display_name="NBA")
    assert post_result_denials(task, envelope) == []
