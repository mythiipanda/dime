import pytest
from types import SimpleNamespace
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


def _requirement(metric_ids):
    return EvidenceRequirement(
        id="reqdef", description="best defense",
        capability_options=["team_ratings"],
        capability_arguments={}, metric_ids=metric_ids,
    )


def test_planner_rejects_metric_absent_from_requirement_typed_ids():
    planner = _planner()
    node = _node({"requested_metric": "OFF_RATING", "ranking_direction": "desc"})
    requirements = {"req-def": _requirement(["DEF_RATING"])}
    with pytest.raises(PlannerArgumentError, match="OFF_RATING"):
        planner._check_ranked_requirement_agreement(node, node.arguments, requirements)


def test_planner_accepts_metric_matching_requirement_typed_ids():
    planner = _planner()
    node = _node({"requested_metric": "DEF_RATING", "ranking_direction": "desc"})
    requirements = {"req-def": _requirement(["DEF_RATING"])}
    planner._check_ranked_requirement_agreement(node, node.arguments, requirements)


def test_planner_accepts_omitted_metric_when_requirement_declares_typed_ids():
    planner = _planner()
    node = _node({"ranking_direction": "desc"})
    requirements = {"req-def": _requirement(["DEF_RATING"])}
    planner._check_ranked_requirement_agreement(node, node.arguments, requirements)

