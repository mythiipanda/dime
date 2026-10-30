import pytest
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

def test_loss_snapshots_carry_live_provenance_hashes():
 import json,pathlib
 from v2.arguments import RequirementReviewWire,PlannerOutputWire
 from v2.argument_schemas import normalize_provider_wire_schema,canonical_hash
 root=pathlib.Path(__file__).parents[2]/'schema_snapshots'
 for name,model in (('requirement_review',RequirementReviewWire),('planner',PlannerOutputWire)):
  source=model.model_json_schema();candidate,_=normalize_provider_wire_schema(source)
  stored=json.loads((root/f'{name}.loss.json').read_text())
  assert stored['source_schema_sha256']==canonical_hash(source),f'{name}: stale source provenance hash'
  assert stored['candidate_schema_sha256']==canonical_hash(candidate),f'{name}: stale candidate provenance hash'

def _null_arg_schema():
 return {'type':'object','additionalProperties':False,
  'properties':{'req':{'type':'string'},
   'opt_default':{'type':'string','default':'dflt'},
   'opt_nodefault':{'type':'string'},
   'nullable':{'type':['string','null']}},
  'required':['req']}

def _null_wire(key):
 return {'entries':[{'key':key,'kind':'null','value':None,'bool_value':None,
  'int_value':None,'number_value':None,'decimal_value':None,'string_value':None,
  'bool_list_value':None,'int_list_value':None,'number_list_value':None,
  'decimal_list_value':None,'string_list_value':None}]}

def _decode_null(key,target='planner'):
 from v2.arguments import ProviderWireArguments,provider_to_source
 wire=ProviderWireArguments.model_validate(_null_wire(key));drops=[]
 out=provider_to_source(wire,target,route=target,capability_id='cap',
  argument_schema=_null_arg_schema(),drops=drops)
 return dict(out),drops

def test_null_on_optional_with_default_is_omitted_and_logged():
 out,drops=_decode_null('opt_default')
 assert out=={}
 assert drops==[{'route':'planner','capability_id':'cap','key':'opt_default','rule':'null-as-omitted'}]

def test_null_on_nullable_stays_null():
 out,drops=_decode_null('nullable')
 assert out=={'nullable':None} and drops==[]

def test_null_on_required_and_optional_without_default_stays_invalid():
 from jsonschema import Draft202012Validator
 schema=_null_arg_schema()
 for key in ('req','opt_nodefault'):
  out,drops=_decode_null(key)
  assert out=={key:None} and drops==[]
  assert list(Draft202012Validator(schema).iter_errors(out)),f'{key}: null must still fail validation'
