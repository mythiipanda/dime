"""Planner typed-metric safety regression. No provider or warehouse needed.

The task and its covered requirement both carry DEF_RATING in typed metric_ids.
A schema-valid planner response must not substitute OFF_RATING/desc for that
requirement, even when capability-local ranking arguments are omitted. The
missing capability arguments are not authorization to override typed intent.
"""
import asyncio
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(BACKEND))

from v2.adapters.models import ModelPlanner, PlannerArgumentError  # noqa: E402
from v2.contracts import TaskSpec  # noqa: E402

sys.path.insert(0, str(BACKEND / "v2" / "tests" / "runtime"))
import importlib.util  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "existing_model_stage_tests", BACKEND / "v2" / "tests" / "runtime" / "test_model_stages.py"
)
existing = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(existing)


def _defense_task():
    return TaskSpec.model_validate({
        "goal": "Which team has the best defense?",
        "mode": "quick",
        "deliverable": "team and rating",
        "season": {"value": "2025-26", "source": "user", "confidence": 1},
        "required_evidence": ["team_ratings"],
        "metric_ids": ["DEF_RATING"],
        "requirements": [{
            "id": "rank",
            "description": "lowest defensive rating board",
            "capability_options": ["team_ratings"],
            "metric_ids": ["DEF_RATING"],
            "capability_arguments": {"team": "", "season": "2025-26"},
        }],
    })


def test_omitted_ranking_arguments_cannot_override_typed_metric():
    task = _defense_task()
    node = existing._planner_node(
        "n", "team_ratings", {"requested_metric": "OFF_RATING", "ranking_direction": "desc"}
    )
    model = existing.StubModel([{"nodes": [node]}])
    planner = ModelPlanner(
        model, provider="stub", model_name="stub", capability_catalog=existing._typed_catalog()
    )
    with pytest.raises(PlannerArgumentError):
        asyncio.run(planner.plan(task))


def test_matching_typed_metric_still_accepted():
    task = _defense_task()
    node = existing._planner_node(
        "n", "team_ratings", {"requested_metric": "DEF_RATING", "ranking_direction": "asc"}
    )
    model = existing.StubModel([{"nodes": [node]}])
    planner = ModelPlanner(
        model, provider="stub", model_name="stub", capability_catalog=existing._typed_catalog()
    )
    plan = asyncio.run(planner.plan(task))
    assert plan.nodes[0].arguments["requested_metric"] == "DEF_RATING"
    assert plan.nodes[0].covers_requirement_ids == ["rank"]
