"""Ranked planner nodes must keep the requirement's typed metric identity.

Three properties must hold at once for a ranked node covering a requirement:

  1. An OFF_RATING/desc node must not cover a requirement whose typed
     metric_ids are [DEF_RATING] (the d2235fa4 unsafe substitution).
  2. A node must not contradict the requirement's explicit requested_metric /
     ranking_direction when the requirement declares them, regardless of
     whether the rest of capability_arguments is empty or populated.
  3. A node must not drop the requirement's explicit requested_metric /
     ranking_direction by leaving them blank.

Property 1 is the typed-metric identity guard. Properties 2 and 3 are the
per-key equality check. Both must run for every covered ranked node; neither
is a substitute for the other. Tests drive the real validator directly, so no
provider, network or warehouse is involved.
"""
import importlib.util
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(BACKEND))

from v2.adapters.models import ModelPlanner, PlannerArgumentError  # noqa: E402
from v2.arguments import PlannerNodeWire  # noqa: E402
from v2.contracts import TaskSpec  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "existing_model_stage_tests", BACKEND / "v2" / "tests" / "runtime" / "test_model_stages.py"
)
existing = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(existing)


def _task(metric_ids, capability_arguments):
    return TaskSpec.model_validate({
        "goal": "Which team has the best defense?",
        "mode": "quick",
        "deliverable": "team and rating",
        "season": {"value": "2025-26", "source": "user", "confidence": 1},
        "required_evidence": ["team_ratings"],
        "metric_ids": metric_ids,
        "requirements": [{
            "id": "rank",
            "description": "lowest defensive rating board",
            "capability_options": ["team_ratings"],
            "metric_ids": metric_ids,
            "capability_arguments": capability_arguments,
        }],
    })


def _check(node_args, metric_ids, capability_arguments):
    """Run the real ranked-agreement validator and return the rejection or None."""
    task = _task(metric_ids, capability_arguments)
    planner = ModelPlanner(
        None, provider="stub", model_name="stub",
        capability_catalog=existing._typed_catalog(),
    )
    wire_node = PlannerNodeWire.model_validate({
        "id": "n",
        "description": "team ratings node",
        "capability": "team_ratings",
        "covers_requirement_ids": ["rank"],
        "depends_on": None,
        "arguments": None,
        "max_attempts": None,
        "status": None,
    })
    requirements = {r.id: r for r in task.requirements}
    try:
        planner._check_ranked_requirement_agreement(wire_node, dict(node_args), requirements)
    except PlannerArgumentError as exc:
        return str(exc)
    return None


def test_typed_metric_identity_guards_offensive_substitution():
    """Property 1: OFF_RATING must not cover a DEF_RATING-typed requirement.

    No capability arguments are declared on the requirement, which is exactly
    the case the d2235fa4 hold exposed.
    """
    rejected = _check(
        {"requested_metric": "OFF_RATING", "ranking_direction": "desc"},
        ["DEF_RATING"],
        {"team": "", "season": "2025-26"},
    )
    assert rejected is not None, (
        "an OFF_RATING/desc node covering a DEF_RATING-typed requirement was accepted"
    )
    assert "OFF_RATING" in rejected


def test_nonempty_expected_arguments_still_bind_requested_metric():
    """Property 2: explicit requirement metric wins with other args present.

    The requirement explicitly asks for DEF_RATING/asc and also carries normal
    capability arguments. An OFF_RATING/desc node contradicts it and must be
    rejected - the presence of unrelated arguments is not permission to
    override the typed intent.
    """
    expected = {
        "team": "", "season": "2025-26",
        "requested_metric": "DEF_RATING", "ranking_direction": "asc",
    }
    rejected = _check(
        {"requested_metric": "OFF_RATING", "ranking_direction": "desc"},
        ["OFF_RATING"],
        expected,
    )
    assert rejected is not None, (
        "an OFF_RATING/desc node was accepted against a requirement whose explicit "
        "requested_metric is DEF_RATING with ranking_direction asc"
    )
    assert "DEF_RATING" in rejected


def test_blank_ranking_fields_cannot_drop_explicit_intent():
    """Property 3: blank node fields cannot silently drop explicit intent.

    The requirement explicitly declares requested_metric/ranking_direction but
    no typed metric_ids. A node that leaves both fields blank must be rejected
    rather than accepted as if the intent never existed.
    """
    expected = {
        "team": "", "season": "2025-26",
        "requested_metric": "DEF_RATING", "ranking_direction": "asc",
    }
    rejected = _check({}, [], expected)
    assert rejected is not None, (
        "a node with blank requested_metric/ranking_direction was accepted against a "
        "requirement that explicitly declares them"
    )
    assert "DEF_RATING" in rejected


def test_agreeing_node_still_accepted_with_nonempty_arguments():
    """Control: an agreeing node must not become over-rejected.

    The equality guard must not start rejecting schema-valid nodes that honour
    the requirement's explicit typed intent.
    """
    expected = {
        "team": "", "season": "2025-26",
        "requested_metric": "DEF_RATING", "ranking_direction": "asc",
    }
    rejected = _check(
        {"requested_metric": "DEF_RATING", "ranking_direction": "asc"},
        [],
        expected,
    )
    assert rejected is None, f"an agreeing node was rejected: {rejected}"


def test_typed_defense_rating_node_still_accepted():
    """Control: the safe DEF_RATING node must remain acceptable end to end."""
    task = _task(["DEF_RATING"], {"team": "", "season": "2025-26"})
    node = existing._planner_node(
        "n", "team_ratings", {"requested_metric": "DEF_RATING", "ranking_direction": "asc"}
    )
    model = existing.StubModel([{"nodes": [node]}])
    planner = ModelPlanner(
        model, provider="stub", model_name="stub", capability_catalog=existing._typed_catalog()
    )
    import asyncio

    plan = asyncio.run(planner.plan(task))
    assert plan.nodes[0].arguments["requested_metric"] == "DEF_RATING"
    assert plan.nodes[0].covers_requirement_ids == ["rank"]
