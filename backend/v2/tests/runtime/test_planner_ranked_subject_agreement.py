from types import SimpleNamespace

import pytest

from v2.adapters.models import ModelPlanner, PlannerArgumentError
from v2.contracts import EvidenceRequirement


def _planner():
    return ModelPlanner(
        None, provider="stub", model_name="stub-model",
        capability_catalog={"team_ratings": {}},
    )


def _node(arguments):
    return SimpleNamespace(
        id="n1", capability="team_ratings",
        covers_requirement_ids=["req-def"], arguments=arguments,
    )


def _requirement(entries):
    return EvidenceRequirement(
        id="reqdef", description="best defense",
        capability_options=["team_ratings"],
        capability_argument_sets=[{
            "capability_id": "team_ratings",
            "arguments": {"entries": entries},
        }],
    )


def _entry(key, value):
    return {"key": key, "kind": "string", "string_value": value}


def test_planner_rejects_team_drift_from_requirement():
    planner = _planner()
    node = _node({
        "team": "LAL",
        "requested_metric": "DEF_RATING",
        "ranking_direction": "asc",
    })
    requirements = {"req-def": _requirement([
        _entry("team", "BOS"),
        _entry("requested_metric", "DEF_RATING"),
        _entry("ranking_direction", "asc"),
    ])}
    with pytest.raises(PlannerArgumentError, match="team"):
        planner._check_ranked_requirement_agreement(
            node, node.arguments, requirements)


def test_planner_accepts_team_matching_requirement():
    planner = _planner()
    node = _node({
        "team": "BOS",
        "requested_metric": "DEF_RATING",
        "ranking_direction": "asc",
    })
    requirements = {"req-def": _requirement([
        _entry("team", "BOS"),
        _entry("requested_metric", "DEF_RATING"),
        _entry("ranking_direction", "asc"),
    ])}
    planner._check_ranked_requirement_agreement(
        node, node.arguments, requirements)


def test_requirement_without_team_leaves_the_node_free():
    planner = _planner()
    node = _node({
        "team": "LAL",
        "requested_metric": "DEF_RATING",
        "ranking_direction": "asc",
    })
    requirements = {"req-def": _requirement([
        _entry("requested_metric", "DEF_RATING"),
        _entry("ranking_direction", "asc"),
    ])}
    planner._check_ranked_requirement_agreement(
        node, node.arguments, requirements)
