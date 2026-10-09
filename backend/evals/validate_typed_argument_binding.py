import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from v2.arguments import PlannerArguments, encode_argument, migrate_legacy_arguments
from v2.adapters.models import ModelPlanner, PlannerArgumentError, ranked_team_arguments_error
from v2.contracts import EvidenceRequirement
from v2.runtime.assembly import capability_catalog
from jsonschema import Draft202012Validator

CATALOG = capability_catalog()
SCHEMA = CATALOG["team_ratings"]["arguments"]


def _flat(arguments):
    if "entries" not in arguments:
        return dict(arguments)
    out = {}
    for entry in arguments["entries"]:
        value = entry.get("value")
        for key, item in entry.items():
            if key.endswith("_value") and item is not None:
                value = item
        out[entry["key"]] = value
    return out


def _probe(arguments):
    """Return the observed rejection stage for a flat argument dict."""
    flat = _flat(arguments)
    stages = {}
    errors = list(Draft202012Validator(SCHEMA).iter_errors(flat))
    stages["jsonschema"] = "reject" if errors else "accept"
    try:
        migrate_legacy_arguments("team_ratings", flat, SCHEMA, target="planner")
        stages["migrate_legacy_arguments"] = "accept"
    except ValueError:
        stages["migrate_legacy_arguments"] = "reject"
    ranked = ranked_team_arguments_error("team_ratings", flat)
    stages["ranked_team_arguments_error"] = "reject" if ranked else "accept"
    try:
        PlannerArguments.model_validate(arguments)
        stages["typed_pydantic"] = "accept"
    except ValueError:
        stages["typed_pydantic"] = "reject"
    return stages


def _typed(flat):
    return PlannerArguments.model_validate(
        {"entries": [encode_argument(key, value) for key, value in flat.items()]})


def _requirement(metric_ids):
    return EvidenceRequirement(
        id="reqdef", description="best defense",
        capability_options=["team_ratings"],
        capability_arguments={}, metric_ids=metric_ids)


def check_binding_case(row):
    """A binding case passes when its wrong_arguments are rejected by at least one stage."""
    stages = _probe(row["wrong_arguments"])
    rejected = any(stage == "reject" for stage in stages.values())
    return {
        "task_id": row["task_id"],
        "kind": "binding",
        "pass": rejected if row["rejection_signal"] else not rejected,
        "stages": stages,
        "declared_signal": row["rejection_signal"],
    }


def check_requirement_case(row):
    """A typed-metric_ids case passes when the planner agreement check matches its expectation."""
    requirement = _requirement(row["requirement"]["metric_ids"])
    node_args = _typed(_flat(row["planner_node"]["arguments"]))
    node = type("Node", (), {
        "id": row["planner_node"]["id"], "capability": row["planner_node"]["capability"],
        "covers_requirement_ids": ["reqdef"], "arguments": node_args})()
    planner = ModelPlanner(None, provider="stub", model_name="stub", capability_catalog=CATALOG)
    try:
        planner._check_ranked_requirement_agreement(node, node_args, {"reqdef": requirement})
        agreement = "accept"
    except PlannerArgumentError as exc:
        agreement = "reject: %s" % exc
    ranked = ranked_team_arguments_error(row["planner_node"]["capability"],
                                         _flat(row["planner_node"]["arguments"]))
    blocked = agreement.startswith("reject") or ranked is not None
    return {
        "task_id": row["task_id"],
        "kind": "requirement_agreement",
        "pass": (row["expected"] == "refuse") == blocked,
        "observed": agreement,
        "ranked_rule": ranked,
        "expected": row["expected"],
    }


def main(path):
    results = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        if "requirement" in row:
            results.append(check_requirement_case(row))
        elif "wrong_arguments" in row:
            results.append(check_binding_case(row))
    failed = [r for r in results if not r["pass"]]
    for r in results:
        if not r["pass"]:
            print("FAIL", json.dumps(r))
    print("checked=%d passed=%d failed=%d" % (len(results), len(results) - len(failed), len(failed)))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1]))
