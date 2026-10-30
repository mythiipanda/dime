import hashlib
import json
from datetime import UTC, datetime

import pytest
from pydantic import BaseModel

from shared.config import settings

from v2.contracts import EvidenceEnvelope, TaskSpec, RequirementReview
from v2.arguments import PlannerOutputWire, RequirementReviewWire, SLOTS


class StubModel:
    def __init__(self, values):
        self.values = iter(values)
        self.calls = []

    @staticmethod
    def _wire_entry(key, value):
        if value is None: kind,slot='null','value'
        elif type(value) is bool: kind,slot='bool','bool_value'
        elif type(value) is int: kind,slot='int','int_value'
        elif type(value) is float: kind,slot='number','number_value'
        elif type(value) is str: kind,slot='string','string_value'
        elif type(value) is list and (not value or all(type(x) is str for x in value)): kind,slot='string_list','string_list_value'
        else: raise ValueError(f'fixture cannot encode {key}')
        slots={name:None for name in SLOTS.values()};slots[slot]=value
        return {'key':key,'kind':kind,**slots}
    @classmethod
    def _migrate_fixture(cls, schema, value):
        if schema is PlannerOutputWire:
            for n in value.get('nodes',[]):
                if len(n.get('capability_hints') or []) > 1:
                    raise ValueError(f"fixture node {n['id']!r} has several capability_hints; the wire takes one capability")
            return {'nodes':[{'id':n['id'],'description':n['description'],'depends_on':n.get('depends_on'),
             'capability':(n.get('capability_hints') or [n.get('capability')])[0],
             'covers_requirement_ids':n.get('covers_requirement_ids'),'arguments':{'entries':[cls._wire_entry(k,v) for k,v in n.get('arguments',{}).items()]},
             'max_attempts':n.get('max_attempts'),'status':n.get('status')} for n in value.get('nodes',[])]}
        if schema is RequirementReviewWire:
            rows=[]
            for r in value.get('requirements',[]):
                options=r['capability_options'];shared=r.get('capability_arguments',{})
                sets=r.get('capability_argument_sets') or [{'capability_id':c,'arguments':shared} for c in options]
                rows.append({'id':r['id'],'description':r['description'],'capability_options':options,
                 'capability_argument_sets':[{'capability_id':x['capability_id'],'arguments':{'entries':[cls._wire_entry(k,v) for k,v in x.get('arguments',{}).items()]}} for x in sets],
                 'metric_ids':r.get('metric_ids'),'requested_outputs':r.get('requested_outputs')})
            return {'requirements':rows,'calculation_requirements':value.get('calculation_requirements'),
             'missing_subquestions':value.get('missing_subquestions'),'missing_skills':value.get('missing_skills')}
        return value
    async def generate(self, **call):
        self.calls.append(call);value=next(self.values)
        return call["schema"].model_validate(self._migrate_fixture(call['schema'],value))


@pytest.mark.anyio
async def test_tool_capability_binds_dependency_lineage() -> None:
    from v2.adapters import ToolCapability
    from v2.contracts import EvidenceEnvelope, TaskSpec, PlanNode

    class Args(BaseModel):
        a: str
        b: str
    class CompareTool:
        name = "get_compare"
        args_schema = Args
        async def ainvoke(self, arguments):
            return {"ok": True, "rows": {"a": arguments["a"], "b": arguments["b"]},
                    "meta": {"source": "fixture"}}

    parent = EvidenceEnvelope(
        evidence_id="parent", capability="entity_resolution", source="fixture",
        observed_at=datetime.now(UTC), rows={"player": "Jaylen Brown"})
    result = await ToolCapability(
        "player_comparison", tools={"get_compare": CompareTool()}).execute(
            PlanNode(id="compare", description="compare",
                     capability_hints=["player_comparison"],
                     arguments={"a": "Jaylen Brown", "b": "Paul George"}),
            TaskSpec(goal="compare", mode="quick", deliverable="answer"), [parent])
    assert result.lineage == ["parent"]


@pytest.mark.parametrize("field", ["metric_ids", "requested_outputs"])
@pytest.mark.parametrize("bad", ["def_rating", "", "1PTS", "A" * 129])
def test_requirement_wire_rejects_malformed_dimension_ids(field, bad):
    from pydantic import ValidationError
    from v2.arguments import CalculationRequirementWire, RequirementWire
    base = {"id": "r", "description": "d", "metric_ids": None, "requested_outputs": None}
    evidence = {**base, "capability_options": ["team_ratings"],
                "capability_argument_sets": [{"capability_id": "team_ratings",
                                              "arguments": {"entries": []}}]}
    for model, row in ((RequirementWire, evidence), (CalculationRequirementWire, base)):
        model.model_validate({**row, field: ["DEF_RATING"]})
        with pytest.raises(ValidationError):
            model.model_validate({**row, field: [bad]})


def test_draft_validator_rejects_duplicate_requirement_ownership():
    from v2.contracts import DraftReport
    TaskSpec(goal="x",mode="quick",deliverable="x",
        calculation_requirements=[{"id":"same","description":"one"}])
    with pytest.raises(ValueError, match="must not duplicate requirement ids"):
        DraftReport.model_validate({"sections":[],"claims":[],"calculations":[
            {"calculation_id":"a","requirement_id":"same","operation":"mean",
             "inputs":[{"evidence_id":"e","path":"rows.x"}],"result":"1"},
            {"calculation_id":"b","requirement_id":"same","operation":"mean",
             "inputs":[{"evidence_id":"e","path":"rows.y"}],"result":"2"}]})


def test_calculation_validation_accepts_ordinary_rate_rounding_but_not_wrong_value():
    from v2.domain.calculations import Calculation, validate_calculation
    from v2.domain.evidence import EvidenceIndex
    ev=EvidenceEnvelope(evidence_id="rate",capability="leaders",source="fixture",observed_at=datetime.now(UTC),rows={"total":200,"gp":64})
    base={"calculation_id":"bpg","operation":"divide","inputs":[{"evidence_id":"rate","path":"rows.total"},{"evidence_id":"rate","path":"rows.gp"}]}
    rounded=Calculation.model_validate({**base,"result":"3.1"})
    wrong=Calculation.model_validate({**base,"result":"99"})
    index=EvidenceIndex([ev])
    assert validate_calculation(rounded,index) is None
    assert "does not recompute" in validate_calculation(wrong,index)


def test_admission_dimension_ids_reject_noncanonical_values_at_task_boundary():
    from pydantic import ValidationError
    for value in ("!!!", "A B", "ÉFG", "lower"):
        with pytest.raises(ValidationError):
            TaskSpec(goal="x",mode="quick",deliverable="x",metric_ids=[value])
        with pytest.raises(ValidationError):
            TaskSpec(goal="x",mode="quick",deliverable="x",requested_outputs=[value])

def test_evidence_and_calculation_requirement_ids_cannot_collide():
    from pydantic import ValidationError
    with pytest.raises(ValidationError,match="ids overlap"):
        TaskSpec(goal="x",mode="quick",deliverable="x",
            requirements=[{"id":"same","description":"e","capability_options":["standings"]}],
            calculation_requirements=[{"id":"same","description":"c"}])


def test_ranked_conflict_field_excluded_from_model_output_schemas():

    from v2.contracts import RequirementReview, TaskSpec
    for model in (TaskSpec, RequirementReview):
        assert "ranked_argument_conflicts" not in model.model_json_schema()["properties"]


def test_ranked_typed_functions_never_read_request_text_or_use_regex():
    import ast, pathlib
    root = pathlib.Path(__file__).parents[3]
    def check_ranked_function(name: str, node: ast.AST, path: str) -> None:
        for child in ast.walk(node):
            if isinstance(child, ast.Attribute) and child.attr in {
                    "goal", "description", "request", "subquestions"}:
                raise AssertionError(f"{path}:{name} reads .{child.attr} text")
            if isinstance(child, ast.Attribute) and isinstance(
                    child.value, ast.Name) and child.value.id == "re":
                raise AssertionError(f"{path}:{name} uses the re module")
            if isinstance(child, (ast.Import, ast.ImportFrom)):
                imported = [alias.name for alias in child.names]
                if isinstance(child, ast.ImportFrom) and child.module:
                    imported.append(child.module)
                assert "re" not in imported, f"{path}:{name} imports re"
            if isinstance(child, ast.Compare) and any(
                    isinstance(op, (ast.In, ast.NotIn)) for op in child.ops):
                for comparator in child.comparators:
                    if (isinstance(child.left, ast.Constant)
                            and isinstance(child.left.value, str)
                            and isinstance(comparator, ast.Name)):
                        raise AssertionError(
                            f"{path}:{name} does substring matching on text")

    league = ast.parse((root / "shared" / "tools" / "league.py").read_text())
    get_ratings = next(node for node in ast.walk(league)
                       if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                       and node.name == "get_ratings")
    check_ranked_function("get_ratings", get_ratings, "shared/tools/league.py")

def test_no_request_text_regex_routes_ranked_arguments():
    import ast, pathlib
    for rel in ("shared/tools/league.py",):
        tree = ast.parse((pathlib.Path(__file__).parents[3] / rel).read_text())
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            name = node.name.lower()
            if "ranked" not in name and "rating" not in name:
                continue
            src = ast.get_source_segment(
                (pathlib.Path(__file__).parents[3] / rel).read_text(), node) or ""
            assert "import re" not in src and "re.compile" not in src, \
                f"{rel}:{node.name} uses regex for ranked argument routing"
