import pytest
from pydantic import ValidationError
from v2.arguments import RequirementArguments,ProviderWireArguments,provider_to_source,migrate_legacy_arguments,RequirementV3,RequirementReviewWire,PlannerOutputWire
from v2.argument_schemas import compile_capability_catalog,normalize_provider_wire_schema

def entries_map():return {'entries':[{'key':'x','kind':'int','int_value':1}]}
def test_v3_models_reject_raw_maps_and_canonicalize_entries():
 with pytest.raises(ValidationError):RequirementArguments.model_validate({'x':1})
 x=RequirementArguments.model_validate({'entries':[{'key':'z','kind':'int','int_value':2},{'key':'a','kind':'string','string_value':'x'}]});assert list(x)==['a','z']
def test_legacy_adapter_requires_capability_schema():
 schema={'type':'object','additionalProperties':False,'properties':{'x':{'type':'integer'}},'required':['x']}
 assert migrate_legacy_arguments('cap',{'x':1},schema,target='planner')=={'x':1}
 with pytest.raises(ValueError):migrate_legacy_arguments('cap',{'bad':1},schema,target='planner')
def test_provider_schema_has_no_legacy_union():
 schema=ProviderWireArguments.model_json_schema();assert 'LegacyArgumentMap' not in str(schema)
def test_provider_semantic_boundary():
 row={'key':'x','kind':'int','value':None,'bool_value':None,'int_value':1,'number_value':None,'decimal_value':None,'string_value':None,'bool_list_value':None,'int_list_value':None,'number_list_value':None,'decimal_list_value':None,'string_list_value':None}
 assert provider_to_source(ProviderWireArguments(entries=[row]),'planner')=={'x':1};row['string_value']='bad'
 with pytest.raises(ValueError):provider_to_source(ProviderWireArguments(entries=[row]),'planner')
def test_capability_local_sets_exact():
 r=RequirementV3(id='r',description='r',capability_options=['a','b'],capability_argument_sets=[{'capability_id':'a','arguments':entries_map()},{'capability_id':'b','arguments':{'entries':[]}}]);assert r.select('a')=={'x':1}
def test_explicit_wire_normalizer_inlines_refs_closes_objects_and_reports_no_loss():
 source={'$defs':{'S':{'type':'string','maxLength':4}},'type':'object','additionalProperties':False,'properties':{'required':{'$ref':'#/$defs/S'},'optional':{'type':'integer','default':2}},'required':['required']}
 candidate,report=normalize_provider_wire_schema(source);assert '$defs' not in str(candidate) and candidate['required']==['optional','required']
 assert candidate['properties']['optional']=={'type':'integer','default':2}
 assert report['losses']==[] and len(report['source_schema_sha256'])==64
@pytest.mark.parametrize('wire',[RequirementReviewWire,PlannerOutputWire])
def test_live_wire_schemas_survive_provider_normalization(wire):
 candidate,_=normalize_provider_wire_schema(wire.model_json_schema());assert candidate['type']=='object'
@pytest.mark.parametrize('bad',[{'$defs':{'X':{'$ref':'#/$defs/X'}},'$ref':'#/$defs/X'},{'$defs':{'X':{'type':'string'}},'$ref':'#/$defs/X','description':'sibling'}])
def test_normalizer_rejects_ref_cycle_and_siblings(bad):
 with pytest.raises(ValueError):normalize_provider_wire_schema(bad)
def test_compiler_rejects_nested_array_and_records_constraints_injection():
 catalog={'good':{'arguments':{'type':'object','additionalProperties':False,'properties':{'x':{'anyOf':[{'type':'string','enum':['a']},{'type':'null'}],'maxLength':4}},'required':['x']},'dependent_entity_arguments':{'x':'player'}},'bad':{'arguments':{'type':'object','additionalProperties':False,'properties':{'x':{'type':'array','items':{'type':'object'}}}}}}
 out=compile_capability_catalog(catalog);by={x['capability_id']:x for x in out['capabilities']};assert by['bad']['status']=='UNREPRESENTABLE';assert by['good']['properties'][0]['nullable'] and by['good']['dependent_entity_arguments']=={'x':'player'}

def test_compiler_preserves_branch_local_constraints_and_decimal_metadata():
 catalog={'c':{'arguments':{'type':'object','additionalProperties':False,'properties':{
  'x':{'anyOf':[{'type':'integer','minimum':1,'maximum':3},{'type':'string','enum':['a'],'minLength':1}]},
  'scalar':{'type':'number','x-dime-exact-decimal':True},
  'items':{'type':'array','items':{'type':'number','x-dime-exact-decimal':True}}}}}}
 row=compile_capability_catalog(catalog)['capabilities'][0];by={p['property']:p for p in row['properties']}
 assert by['x']['branches'][0]['constraints']=={'minimum':1,'maximum':3}
 assert by['x']['branches'][1]['constraints']=={'enum':['a'],'minLength':1}
 assert by['scalar']['scalar_exact_decimal'] and not by['scalar']['list_item_exact_decimal']
 assert by['items']['list_item_exact_decimal'] and not by['items']['scalar_exact_decimal']

def test_defs_removal_is_schema_container_scoped_and_bad_pointers_are_typed():
 from v2.argument_schemas import SchemaCompileError
 source={'$defs':{'S':{'type':'string'}},'type':'object','additionalProperties':False,'properties':{'$defs':{'type':'string'},'x':{'$ref':'#/$defs/S'}},'required':['$defs','x']}
 candidate,_=normalize_provider_wire_schema(source);assert '$defs' in candidate['properties'] and '$defs' not in candidate
 for pointer,code in [('#/$defs/Missing','unresolved_json_pointer'),('#/$defs/~2bad','invalid_json_pointer_escape'),('https://x','unsupported_json_pointer')]:
  with pytest.raises(SchemaCompileError) as exc:normalize_provider_wire_schema({'$ref':pointer})
  assert exc.value.code==code


def test_array_branch_records_item_constraints():
 out=compile_capability_catalog({'c':{'arguments':{'type':'object','additionalProperties':False,'properties':{'xs':{'type':'array','minItems':1,'items':{'type':'string','enum':['a'],'minLength':1}}}}}})
 branch=out['capabilities'][0]['properties'][0]['branches'][0]
 assert branch['constraints']=={'minItems':1}
 assert branch['item_constraints']=={'enum':['a'],'minLength':1}
@pytest.mark.parametrize('wire',[RequirementReviewWire,PlannerOutputWire])
def test_live_wire_schemas_survive_provider_normalization(wire):
 candidate,_=normalize_provider_wire_schema(wire.model_json_schema());assert candidate['type']=='object'
 found=set()
 def walk(node):
  if isinstance(node,dict):
   if '$ref' in node:raise AssertionError('unresolved ref survives normalization')
   if node.get('type')=='object':
    props=node.get('properties',{})
    assert set(node.get('required',[]))>=set(props)
   for key in ('minLength','maxLength','minimum','maximum','pattern','enum'):
    if key in node:found.add(key)
   for value in node.values():walk(value)
  elif isinstance(node,list):
   for value in node:walk(value)
 walk(candidate)
 assert {'minLength','maxLength','pattern','enum'}<=found
