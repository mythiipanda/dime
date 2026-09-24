"""Regression tests for the provider wire schema codec.

normalize_provider_wire_schema() must strip title/description only as schema
annotations on nodes — never as keys of a properties map, where they are real
field names (RequirementWire, CalculationRequirementWire and PlannerNodeWire
all require `description` in pydantic but lost it on the wire).
"""
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

def _capture(rows):
 class Capture:
  def __init__(self):self.rows=iter(rows);self.calls=[]
  async def generate(self,**call):self.calls.append(call);return call['schema'].model_validate(next(self.rows))
 return Capture()

@pytest.mark.anyio
async def test_planner_null_drop_lands_in_accepted_attempt_metadata():
 from v2.adapters.models import ModelPlanner,RecordedStructuredModel
 from v2.contracts import TaskSpec
 from v2.runtime import RunLedger
 from v2.runtime.ledger import LedgerKind
 def wire(key,kind,value):
  slots={'value':None,'bool_value':None,'int_value':None,'number_value':None,'decimal_value':None,
   'string_value':None,'bool_list_value':None,'int_list_value':None,'number_list_value':None,
   'decimal_list_value':None,'string_list_value':None}
  slots['value' if kind=='null' else kind+'_value']=value
  return {'key':key,'kind':kind,**slots}
 rows=[{'nodes':[{'id':'n','description':'d','capability':'cap','depends_on':None,
   'covers_requirement_ids':None,'max_attempts':None,'status':None,
   'arguments':{'entries':[wire('req','string','v'),wire('opt_default','null',None)]}}]}]
 ledger=RunLedger('run')
 planner=ModelPlanner(RecordedStructuredModel(_capture(rows),ledger,turn_id='t'),
  provider='stub',model_name='stub',
  capability_catalog={'cap':{'arguments':_null_arg_schema(),'description':'cap'}})
 plan=await planner.plan(TaskSpec(goal='g',mode='quick',deliverable='d'))
 assert plan.nodes[0].arguments=={'req':'v'}
 attempt=ledger.entries[-1].data
 assert attempt['status']=='accepted'
 assert attempt['null_as_omitted_drops']==[
  {'route':'planner','capability_id':'cap','key':'opt_default','rule':'null-as-omitted'}]
 assert attempt['model_requests']==1 and attempt['repaired'] is False

@pytest.mark.anyio
async def test_review_null_drop_lands_in_accepted_attempt_metadata():
 from v2.adapters.models import ModelIntake,RecordedStructuredModel
 from v2.contracts import TaskSpec
 from v2.runtime import RunLedger
 rows=[{'requirements':[{'id':'r','description':'r','capability_options':['cap'],
   'capability_argument_sets':[{'capability_id':'cap','arguments':_null_wire('opt_default')}],
   'metric_ids':None,'requested_outputs':None}],
  'calculation_requirements':None,'missing_subquestions':None,'missing_skills':None}]
 ledger=RunLedger('run')
 intake=ModelIntake(RecordedStructuredModel(_capture(rows),ledger,turn_id='t'),
  provider='stub',model_name='stub',
  capability_catalog={'cap':{'arguments':_null_arg_schema(),'description':'cap'}},
  requirement_review=True)
 review=await intake._review_requirements('g',TaskSpec(goal='g',mode='quick',deliverable='d'))
 assert review.requirements[0].capability_arguments=={}
 attempt=ledger.entries[-1].data
 assert attempt['null_as_omitted_drops']==[
  {'route':'requirement_review','capability_id':'cap','key':'opt_default','rule':'null-as-omitted'}]

@pytest.mark.anyio
async def test_accepted_attempt_records_model_requests_and_repaired():
 from v2.adapters.models import RecordedStructuredModel
 from v2.contracts import TaskSpec
 from v2.runtime import RequestEnvelope,RunLedger
 class M:
  last_provider='p';last_model='m';last_failures=[]
  async def generate(self,**call):return TaskSpec(goal='ok',mode='quick',deliverable='x')
 ledger=RunLedger('run');model=RecordedStructuredModel(M(),ledger,turn_id='t')
 def envelope(route):
  return RequestEnvelope.freeze(provider='p',model='m',route=route,prompt='p',
   context={},tool_schemas={},planner_version='v2')
 await model.generate(schema=TaskSpec,prompt='p',payload={},envelope=envelope('intake'))
 first=ledger.entries[-1].data
 assert first['model_requests']==1 and first['repaired'] is False
 await model.generate(schema=TaskSpec,prompt='p',payload={},envelope=envelope('repair'))
 second=ledger.entries[-1].data
 assert second['model_requests']==2 and second['repaired'] is True
