import hashlib,json,pytest
from v2.adapters.models import ModelIntake,ModelPlanner,provider_route_prompt,capability_arguments_for
from v2.arguments import RequirementReviewWire,PlannerOutputWire
from v2.contracts import TaskSpec
def wire(key,kind,value):
 slots={'value':None,'bool_value':None,'int_value':None,'number_value':None,'decimal_value':None,'string_value':None,'bool_list_value':None,'int_list_value':None,'number_list_value':None,'decimal_list_value':None,'string_list_value':None}
 slots['value' if kind=='null' else kind+'_value']=value
 return {'key':key,'kind':kind,**slots}
class Capture:
 def __init__(self,rows):self.rows=iter(rows);self.calls=[]
 async def generate(self,**call):self.calls.append(call);return call['schema'].model_validate(next(self.rows))
def catalog():
 return {'standings':{'arguments':{'type':'object','additionalProperties':False,'properties':{'season':{'type':'string'}},'required':['season']},'description':'standings'}}
@pytest.mark.anyio
async def test_requirement_review_uses_exact_wire_schema_and_v3_prompt():
 model=Capture([{'requirements':[{'id':'r','description':'record','capability_options':['standings'],'capability_argument_sets':[{'capability_id':'standings','arguments':{'entries':[wire('season','string','2025-26')]}}],'metric_ids':None,'requested_outputs':None}],'calculation_requirements':None,'missing_subquestions':None,'missing_skills':None}])
 intake=ModelIntake(model,provider='stub',model_name='stub',capability_catalog=catalog(),requirement_review=True)
 task=TaskSpec(goal='record',mode='quick',deliverable='text',requirements=[])
 review=await intake._review_requirements('record',task)
 call=model.calls[0];assert call['schema'] is RequirementReviewWire;assert call['prompt']==provider_route_prompt('requirement_review','requirement_review_v3')
 assert review.requirements[0].capability_argument_sets and review.requirements[0].capability_arguments=={'season':'2025-26'}
 assert 'additionalProperties' in json.dumps(call['schema'].model_json_schema())
@pytest.mark.anyio
async def test_planner_uses_wire_schema_and_copies_selected_arguments():
 model=Capture([{'nodes':[{'id':'n','description':'record','capability':'standings','arguments':{'entries':[wire('season','string','2025-26')]},'depends_on':None,'covers_requirement_ids':None,'max_attempts':None,'status':None}]}])
 planner=ModelPlanner(model,provider='stub',model_name='stub',capability_catalog=catalog())
 plan=await planner.plan(TaskSpec(goal='record',mode='quick',deliverable='x'))
 call=model.calls[0];assert call['schema'] is PlannerOutputWire;assert call['prompt']==provider_route_prompt('planner','planner_v3');assert plan.nodes[0].arguments=={'season':'2025-26'}
def test_provider_schema_snapshots_and_prompt_hashes(tmp_path):
 snapshots={'requirement':RequirementReviewWire.model_json_schema(),'planner':PlannerOutputWire.model_json_schema()}
 hashes={k:hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':')).encode()).hexdigest() for k,v in snapshots.items()}
 assert all(len(x)==64 for x in hashes.values())
 assert provider_route_prompt('requirement_review','requirement_review_v3').strip()
 assert provider_route_prompt('planner','planner_v3').strip()
@pytest.mark.anyio
async def test_requirement_wire_rejects_constraint_and_dependent_injection():
 cat={'cap':{'arguments':{'type':'object','additionalProperties':False,'properties':{'x':{'type':'integer','minimum':1}}},'dependent_entity_arguments':{'player':'player'}}}
 intake=ModelIntake(Capture([]),provider='stub',model_name='stub',capability_catalog=cat)
 bad=RequirementReviewWire.model_validate({'requirements':[{'id':'r','description':'r','capability_options':['cap'],'capability_argument_sets':[{'capability_id':'cap','arguments':{'entries':[wire('x','int',0)]}}],'metric_ids':None,'requested_outputs':None}],'calculation_requirements':None,'missing_subquestions':None,'missing_skills':None})
 with pytest.raises(ValueError):intake._validate_requirement_wire(bad)
@pytest.mark.anyio
async def test_planner_requires_complete_capability_schema():
 model=Capture([{'nodes':[{'id':'n','description':'x','capability':'standings','arguments':{'entries':[]},'depends_on':None,'covers_requirement_ids':None,'max_attempts':None,'status':None}]}])
 planner=ModelPlanner(model,provider='stub',model_name='stub',capability_catalog=catalog())
 with pytest.raises(ValueError,match='invalid standings'):await planner.plan(TaskSpec(goal='x',mode='quick',deliverable='x'))


def test_capability_local_coverage_rejects_wrong_selected_value():
 from v2.contracts import EvidenceRequirement,Plan,PlanNode
 from v2.arguments import CapabilityArgumentSet,RequirementArguments
 req=EvidenceRequirement(id='r',description='r',capability_options=['a','b'],capability_argument_sets=[
  CapabilityArgumentSet(capability_id='a',arguments=RequirementArguments.model_validate({'entries':[{'key':'x','kind':'int','int_value':1}]})),
  CapabilityArgumentSet(capability_id='b',arguments=RequirementArguments.model_validate({'entries':[{'key':'y','kind':'string','string_value':'right'}]}))])
 task=TaskSpec(goal='g',mode='quick',deliverable='d',requirements=[req])
 planner=ModelPlanner(Capture([]),provider='stub',model_name='stub',capability_catalog={'a':{},'b':{}})
 wrong=Plan(nodes=[PlanNode(id='n',description='n',capability_hints=['b'],covers_requirement_ids=['r'],arguments={'y':'wrong'})])
 omitted=Plan(nodes=[PlanNode(id='n',description='n',capability_hints=['b'],covers_requirement_ids=['r'],arguments={})])
 extra=Plan(nodes=[PlanNode(id='n',description='n',capability_hints=['b'],covers_requirement_ids=['r'],arguments={'y':'RIGHT','extra':1})])
 assert planner._normalize_requirement_coverage(task,wrong).nodes[0].covers_requirement_ids==[]
 assert planner._normalize_requirement_coverage(task,omitted).nodes[0].covers_requirement_ids==[]
 assert planner._normalize_requirement_coverage(task,extra).nodes[0].covers_requirement_ids==['r']


def test_final_openai_request_schema_matches_checked_candidate():
 import pathlib
 from pydantic_ai import NativeOutput
 from pydantic_ai._output import OutputSchema
 from v2.adapters.models import DimeOpenAIChatModel
 root=pathlib.Path(__file__).parents[2]/'schema_snapshots'
 class Mapper(DimeOpenAIChatModel):
  @property
  def profile(self): return {'openai_supports_strict_tool_definition':True}
 mapper=object.__new__(Mapper)
 for name,model in [('requirement_review',RequirementReviewWire),('planner',PlannerOutputWire)]:
  prepared=OutputSchema.build(NativeOutput(model,strict=True)).processor.object_def
  sent=DimeOpenAIChatModel._map_json_schema(mapper,prepared)['json_schema']['schema']
  expected=json.loads((root/f'{name}.candidate.json').read_text())
  assert sent==expected
  manifest=json.loads((root/'manifest.json').read_text())
  canonical=lambda x:hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':')).encode()).hexdigest()
  assert canonical(sent)==manifest[f'{name}.candidate.json']['canonical_json_sha256']
  assert hashlib.sha256((root/f'{name}.candidate.json').read_bytes()).hexdigest()==manifest[f'{name}.candidate.json']['file_sha256']
  text=json.dumps(sent);assert not any(token in text for token in ('$ref','$defs','oneOf'))

def test_v3_intake_closure_is_fail_closed_and_bound_to_behavior_loss():
 import pathlib
 from v2.contracts import EvidenceRequirement
 from v2.arguments import CapabilityArgumentSet,RequirementArguments
 losses=json.loads((pathlib.Path(__file__).parents[2]/'schema_snapshots'/'behavior_losses.json').read_text())
 loss=next(item for item in losses['losses'] if item['id']=='BL-001')
 assert loss['status']=='temporary_fail_closed'
 assert loss['test']=='test_v3_intake_closure_is_fail_closed_and_bound_to_behavior_loss'
 catalog={'web_search':{},'web_fetch':{},'game_logs':{},'player_report':{}}
 intake=ModelIntake(Capture([]),provider='stub',model_name='stub',capability_catalog=catalog)
 for capability,args in [('web_search',{}),('game_logs',{'player':'p','playoffs':False})]:
  entries=[{'key':k,'kind':'bool','bool_value':v} if type(v) is bool else {'key':k,'kind':'string','string_value':v} for k,v in args.items()]
  req=EvidenceRequirement(id='r',description='r',capability_options=[capability],capability_argument_sets=[CapabilityArgumentSet(capability_id=capability,arguments=RequirementArguments.model_validate({'entries':entries}))])
  closed=intake._close_requirement_options(req)
  assert closed.capability_options==[capability]
  assert [item.capability_id for item in closed.capability_argument_sets]==[capability]
 assert {'web_fetch','player_report'} <= set(catalog)

def test_final_mapper_all_active_routes_succeed_and_only_v3_wire_normalizes():
 from pydantic_ai import NativeOutput
 from pydantic_ai._output import OutputSchema
 from v2.adapters.models import DimeOpenAIChatModel
 from v2.contracts import TaskSpec,DraftReport,VerificationReport
 class Mapper(DimeOpenAIChatModel):
  @property
  def profile(self): return {'openai_supports_strict_tool_definition':True}
 mapper=object.__new__(Mapper)
 for model in (TaskSpec,DraftReport,VerificationReport,RequirementReviewWire,PlannerOutputWire):
  prepared=OutputSchema.build(NativeOutput(model,strict=True)).processor.object_def
  mapped=DimeOpenAIChatModel._map_json_schema(mapper,prepared)
  assert mapped['type']=='json_schema' and mapped['json_schema']['schema']
 for model in (TaskSpec,DraftReport,VerificationReport):
  prepared=OutputSchema.build(NativeOutput(model,strict=True)).processor.object_def
  mapped=DimeOpenAIChatModel._map_json_schema(mapper,prepared)
  assert mapped['json_schema']['schema']==prepared.json_schema

def _req_args(values):
 from v2.arguments import RequirementArguments,encode_argument
 return RequirementArguments.model_validate({'entries':[encode_argument(k,v) for k,v in values.items()]})

def test_home_away_transform_preserves_differing_alternative_sets_end_to_end():
 from v2.contracts import EvidenceRequirement,RequirementReview
 from v2.arguments import CapabilityArgumentSet
 intake=ModelIntake(Capture([]),provider='stub',model_name='stub',capability_catalog={'game_logs':{},'player_report':{}})
 req=EvidenceRequirement(id='splits',description='splits',capability_options=['game_logs','player_report'],capability_argument_sets=[
  CapabilityArgumentSet(capability_id='game_logs',arguments=_req_args({'player':'p'})),
  CapabilityArgumentSet(capability_id='player_report',arguments=_req_args({'player':'p','season':'2025-26'}))])
 out=intake._expand_home_away_requirements(RequirementReview(requirements=[req]),'home and away')
 assert [x.id for x in out.requirements]==['splits_home','splits_away']
 for split,item in zip(('home','away'),out.requirements):
  assert capability_arguments_for(item,'game_logs')['home_away']==split
  assert capability_arguments_for(item,'player_report')=={'player':'p','season':'2025-26'}
  assert item.capability_arguments=={}

def test_ranked_reconciliation_uses_and_updates_local_team_set_end_to_end():
 from v2.contracts import EvidenceRequirement,RequirementReview
 from v2.arguments import CapabilityArgumentSet
 cat={'team_ratings':{'arguments':{'type':'object','additionalProperties':False,'properties':{'requested_metric':{'type':'string'},'ranking_direction':{'type':'string'},'season':{'type':'string'}}}},'standings':{'arguments':{'type':'object','additionalProperties':False,'properties':{'season':{'type':'string'}}}}}
 intake=ModelIntake(Capture([]),provider='stub',model_name='stub',capability_catalog=cat)
 sets=[CapabilityArgumentSet(capability_id='team_ratings',arguments=_req_args({'requested_metric':'DEF_RATING','ranking_direction':'asc'})),CapabilityArgumentSet(capability_id='standings',arguments=_req_args({'season':'2025-26'}))]
 req=EvidenceRequirement(id='rank',description='rank',capability_options=['team_ratings','standings'],capability_argument_sets=sets)
 task=TaskSpec(goal='lowest defensive rating',mode='quick',deliverable='answer',required_evidence=['team_ratings'],requirements=[req])
 out=intake._reconcile_ranked_team_review('Which team has the lowest defensive rating?',task,RequirementReview(requirements=[req]))
 ranked=next(x for x in out.requirements if 'team_ratings' in x.capability_options)
 assert ranked.capability_options==['team_ratings']
 assert capability_arguments_for(ranked,'team_ratings')['requested_metric']=='DEF_RATING'
 assert [x.capability_id for x in ranked.capability_argument_sets]==['team_ratings']
 assert ranked.capability_arguments==capability_arguments_for(ranked,'team_ratings')

def test_direct_selected_capability_reads_inventory_is_closed():
 import ast,pathlib
 tree=ast.parse((pathlib.Path(__file__).parents[2]/'adapters'/'models.py').read_text())
 parents={child:node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
 found=[]
 for node in ast.walk(tree):
  if isinstance(node,ast.Attribute) and node.attr=='capability_arguments':
   owner=node
   while owner in parents and not isinstance(owner,(ast.FunctionDef,ast.AsyncFunctionDef)): owner=parents[owner]
   found.append((node.lineno,getattr(owner,'name','module')))
 assert {name for _,name in found} <= {'capability_arguments_for','update_capability_arguments','_update_all_existing_argument','narrow_requirement','_close_requirement_options','_strip_ranked_team_branches','_project_mixed_requirement_arguments','_rebuild_ranked_team_branch'}

def test_final_admission_rejects_wrong_selected_local_scope_end_to_end():
 from datetime import datetime,timezone
 from v2.arguments import CapabilityArgumentSet
 from v2.contracts import (EvidenceRequirement,Plan,PlanNode,EvidenceEnvelope,
  EvidenceOutputBinding,Claim,VerifiedClaim,DraftReport)
 from v2.runtime.models import ExecutionResult,admit_verified_claim_bindings
 req=EvidenceRequirement(id='record',description='record',capability_options=['standings','team_ratings'],requested_outputs=['WINS'],capability_argument_sets=[
  CapabilityArgumentSet(capability_id='standings',arguments=_req_args({'season':'2025-26'})),
  CapabilityArgumentSet(capability_id='team_ratings',arguments=_req_args({'season':'2024-25'}))])
 task=TaskSpec(goal='record',mode='quick',deliverable='answer',requirements=[req])
 node=PlanNode(id='n',description='n',capability_hints=['standings'],covers_requirement_ids=['record'],arguments={'season':'wrong'},status='complete')
 evidence=EvidenceEnvelope(evidence_id='ev',capability='standings',source='warehouse',observed_at=datetime.now(timezone.utc),season='2025-26',rows={'WINS':61},units={'WINS':'count'})
 execution=ExecutionResult(plan=Plan(nodes=[node]),evidence_by_node={'n':evidence},attempts={'n':1})
 binding=EvidenceOutputBinding(requirement_id='record',output_id='WINS',node_id='n',evidence_id='ev',selector='rows.WINS',value={'kind':'integer','value':61},unit={'kind':'declared','value':'count'},domain='standings')
 claim=Claim(text='61 wins',kind='observed',evidence_ids=['ev'],output_bindings=[binding])
 verified=VerifiedClaim(claim_index=0,claim=claim,evidence_ids=['ev'],output_bindings=[binding])
 with pytest.raises(ValueError,match='scope does not match'):
  admit_verified_claim_bindings(task,execution,DraftReport(sections=['x'],claims=[claim]),verified)

def test_startup_manifest_repins_typed_argument_assets():
 import hashlib,pathlib
 from v2.api.routes import _typed_argument_asset_hashes
 root=pathlib.Path(__file__).parents[2]
 expected={
  'provider_schema_manifest':root/'schema_snapshots'/'manifest.json',
  'behavior_losses':root/'schema_snapshots'/'behavior_losses.json',
  'capability_manifest':root/'capability_snapshots'/'manifest.json',
  'capability_source':root/'capability_snapshots'/'catalog.source.json',
  'capability_compiled':root/'capability_snapshots'/'catalog.compiled.json'}
 assert _typed_argument_asset_hashes()=={name:hashlib.sha256(path.read_bytes()).hexdigest() for name,path in expected.items()}
