"""Regression for Instinct's 2026-09-23 schema-codec verdict.

normalize_provider_wire_schema() must strip title/description only as schema
annotations on nodes — never as keys of a properties map, where they are real
field names (RequirementWire, CalculationRequirementWire and PlannerNodeWire
all require `description` in pydantic but lost it on the wire).
"""
import v2.arguments as _arguments
from v2.argument_schemas import normalize_provider_wire_schema

_WIRE_MODELS=sorted(
 (name,model) for name,model in vars(_arguments).items()
 if name.endswith('Wire') and isinstance(model,type)
)

def test_all_wire_models_keep_every_declared_property():
 assert _WIRE_MODELS, 'no *Wire models found — enumeration broken'
 for name,model in _WIRE_MODELS:
  source=model.model_json_schema()
  candidate,_=normalize_provider_wire_schema(source)
  want=set(source.get('properties',{}));got=set(candidate.get('properties',{}))
  assert want==got,f'{name}: properties keys lost on the wire: {sorted(want-got)}'

def test_description_field_survives_on_requirement_wires():
 from v2.arguments import RequirementWire,CalculationRequirementWire,PlannerNodeWire
 for model in (RequirementWire,CalculationRequirementWire,PlannerNodeWire):
  candidate,_=normalize_provider_wire_schema(model.model_json_schema())
  assert 'description' in candidate['properties'],f'{model.__name__}: description stripped'
  assert 'description' in candidate['required'],f'{model.__name__}: description dropped from required'

def test_node_level_annotations_still_stripped():
 source={'title':'Root title','description':'Root description','type':'object',
  'additionalProperties':False,
  'properties':{'description':{'type':'string','description':'annotation on the field schema'},
                'title':{'type':'string','title':'annotation on the field schema'}},
  'required':['description','title']}
 candidate,_=normalize_provider_wire_schema(source)
 assert 'title' not in candidate and 'description' not in candidate
 assert set(candidate['properties'])=={'description','title'}
 for prop in candidate['properties'].values():
  assert 'title' not in prop and 'description' not in prop

def test_nested_property_maps_keep_field_names():
 source={'type':'object','additionalProperties':False,
  'properties':{'nested':{'type':'object','additionalProperties':False,
   'properties':{'description':{'type':'string'}},'required':['description']}},
  'required':['nested']}
 candidate,_=normalize_provider_wire_schema(source)
 nested=candidate['properties']['nested']
 assert 'description' in nested['properties']
 assert 'description' in nested['required']
