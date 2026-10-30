import hashlib,json,pytest
from v2.arguments import RequirementReviewWire,PlannerOutputWire
from v2.contracts import TaskSpec


def _req_args(values):
 from v2.arguments import RequirementArguments,encode_argument
 return RequirementArguments.model_validate({'entries':[encode_argument(k,v) for k,v in values.items()]})


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
