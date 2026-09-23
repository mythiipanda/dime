import pytest
from pydantic import ValidationError
from v2.arguments import RequirementArguments,PlannerArguments,ProviderWireArguments,provider_to_source,encode_argument,migrate_legacy_arguments,RequirementV3
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
def test_explicit_wire_normalizer_inlines_refs_materializes_optional_and_reports_loss():
 source={'$defs':{'S':{'type':'string','maxLength':4}},'type':'object','additionalProperties':False,'properties':{'required':{'$ref':'#/$defs/S'},'optional':{'type':'integer','default':2}},'required':['required']}
 candidate,report=normalize_provider_wire_schema(source);assert '$defs' not in str(candidate) and candidate['required']==['optional','required'];assert candidate['properties']['optional']['anyOf'][-1]=={'type':'null'};assert report['losses'] and len(report['source_schema_sha256'])==64
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

def _assert_snapshot_binding(root, live):
 import json,hashlib
 from v2.argument_schemas import canonical_hash
 source=json.loads((root/'catalog.source.json').read_text())
 aggregate=json.loads((root/'catalog.compiled.json').read_text())
 manifest=json.loads((root/'manifest.json').read_text())
 assert live==source
 actual=compile_capability_catalog(live);assert actual==aggregate
 assert manifest['catalog_canonical_sha256']==canonical_hash(live)==canonical_hash(source)
 assert manifest['compiled_canonical_sha256']==canonical_hash(actual)==canonical_hash(aggregate)
 rows={x['capability_id']:x for x in aggregate['capabilities']}
 assert len(rows)==manifest['count']==39
 files={p.stem:p for p in root.glob('*.json') if p.name not in {'catalog.source.json','catalog.compiled.json','manifest.json'}}
 assert set(rows)==set(files)
 assert all(json.loads(files[name].read_text())==row for name,row in rows.items())
 assert all(hashlib.sha256((root/name).read_bytes()).hexdigest()==digest for name,digest in manifest['files'].items())

def test_all_39_capability_snapshots_bind_live_source_aggregate_and_rows():
 import pathlib
 from v2.runtime.assembly import capability_catalog
 _assert_snapshot_binding(pathlib.Path(__file__).parents[2]/'capability_snapshots',capability_catalog())

def test_snapshot_binding_detects_description_only_source_drift(tmp_path):
 import pathlib,shutil,pytest
 from v2.runtime.assembly import capability_catalog
 root=pathlib.Path(__file__).parents[2]/'capability_snapshots';shutil.copytree(root,tmp_path/'s')
 live=capability_catalog();live['standings']['description']+=' drift'
 with pytest.raises(AssertionError):_assert_snapshot_binding(tmp_path/'s',live)

def test_snapshot_binding_detects_per_capability_row_drift(tmp_path):
 import pathlib,shutil,json,pytest
 from v2.runtime.assembly import capability_catalog
 root=pathlib.Path(__file__).parents[2]/'capability_snapshots';shutil.copytree(root,tmp_path/'s');p=tmp_path/'s'/'standings.json';row=json.loads(p.read_text());row['status']='DRIFT';p.write_text(json.dumps(row))
 with pytest.raises(AssertionError):_assert_snapshot_binding(tmp_path/'s',capability_catalog())

def test_array_branch_records_item_constraints():
 out=compile_capability_catalog({'c':{'arguments':{'type':'object','additionalProperties':False,'properties':{'xs':{'type':'array','minItems':1,'items':{'type':'string','enum':['a'],'minLength':1}}}}}})
 branch=out['capabilities'][0]['properties'][0]['branches'][0]
 assert branch['constraints']=={'minItems':1}
 assert branch['item_constraints']=={'enum':['a'],'minLength':1}
