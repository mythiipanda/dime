from pathlib import Path
import pytest
from v2.api.activity import ActivityJournal
from v2.api.events import EVENT_ADAPTER
from v2.api.sse import encode_event

def stage(j):return j.append(kind='stage_summary',phase='understand',status='complete',title='Request understood',transition='completed',correlation_id='activity-1',data={'mode':'quick','season':None,'entity_count':0,'requirement_count':0,'calculation_count':0})
def test_identity_and_crash_tail(tmp_path):
 p=tmp_path/'r';j=ActivityJournal(p,'r');stage(j);p.open('ab').write(b'{"partial"');assert len(j.read())==1
 j.append(kind='plan_update',phase='plan',status='complete',title='Plan accepted',transition='completed',correlation_id='activity-2',data={'capabilities':['team_ratings'],'node_count':1,'unknown_capability_count':1});assert len(j.read())==2
 p.write_bytes(b'bad\n'+p.read_bytes())
 with pytest.raises(Exception):j.read()
def test_canaries_rejected_and_sse_typed(tmp_path):
 c='CANARY_PRIVATE_SECRET';j=ActivityJournal(tmp_path/'r','r');e=stage(j)
 for kw in [dict(kind='plan_update',phase='plan',status='complete',title='Plan accepted',transition='completed',correlation_id='activity-2',data={'capabilities':[c],'node_count':1,'unknown_capability_count':0}),dict(kind='tool_call',phase='execute',status='running',title='Tool running',transition='started',correlation_id='activity-2',data={'name':'team_ratings','argument_count':1,'unknown_argument_count':0,'step_id':c})]:
  with pytest.raises(Exception):j.append(**kw)
 assert c not in (tmp_path/'r').read_text()
 wire=encode_event(EVENT_ADAPTER.validate_python({'type':e.kind,**e.model_dump(mode='json',exclude={'kind'})}));assert c not in wire and 'entity_count' in wire
 with pytest.raises(Exception):EVENT_ADAPTER.validate_python({'type':'stage_summary','event_id':'r:2','sequence':2,'emitted_at':'2026-01-01T00:00:00Z','phase':'understand','status':'complete','title':'Request understood','transition':'completed','data':{'mode':'quick','season':None,'entity_count':0,'requirement_count':0,'calculation_count':0,'extra':c}})

def test_foreign_event_identity_rejected(tmp_path):
 j=ActivityJournal(tmp_path/'r','r');stage(j)
 text=(tmp_path/'r').read_text().replace('"event_id":"r:1"','"event_id":"other:1"');(tmp_path/'r').write_text(text)
 with pytest.raises(ValueError,match='identity'):j.read()

def test_recorded_capability_live_pair_safe_and_correlated():
 import asyncio
 from datetime import UTC,datetime
 from v2.runtime.recording import RecordedCapability
 from v2.runtime.ledger import RunLedger
 from v2.contracts import EvidenceEnvelope,PlanNode,TaskSpec
 seen=[]
 class Cap:
  name='team_ratings';task_season_scoped=True
  async def execute(self,node,task,evidence):return EvidenceEnvelope(evidence_id='private-id',capability=self.name,source='fixture',observed_at=datetime.now(UTC),rows=[])
 cap=RecordedCapability(Cap(),RunLedger('r'),turn_id='r',activity=seen.append)
 asyncio.run(cap.execute(PlanNode(id='CANARY_STEP',description='CANARY_DESC',capability_hints=['team_ratings'],arguments={'CANARY_KEY':'secret'}),TaskSpec(goal='g',mode='quick',deliverable='d'),[]))
 assert [x['kind'] for x in seen]==['tool_call','tool_result']
 assert seen[0]['correlation_id']==seen[1]['correlation_id']
 assert seen[0]['data']=={'name':'team_ratings','argument_count':1,'unknown_argument_count':1}
 assert 'CANARY' not in str([item['data'] for item in seen])

def test_recorded_capability_observer_failures_never_interfere():
 import asyncio
 from datetime import UTC,datetime
 from v2.runtime.recording import RecordedCapability
 from v2.runtime.ledger import RunLedger
 from v2.contracts import EvidenceEnvelope,PlanNode,TaskSpec
 class Cap:
  name='team_ratings';task_season_scoped=True;calls=0
  async def execute(self,node,task,evidence):self.calls+=1;return EvidenceEnvelope(evidence_id='e',capability=self.name,source='f',observed_at=datetime.now(UTC),rows=[])
 class Boom:
  def __call__(self,p):raise OSError('disk full')
 cap=Cap();wrapped=RecordedCapability(cap,RunLedger('r'),turn_id='r',activity=Boom());result=asyncio.run(wrapped.execute(PlanNode(id='n',description='n',capability_hints=['team_ratings']),TaskSpec(goal='g',mode='quick',deliverable='d'),[]));assert cap.calls==1 and result.evidence_id=='e'

def test_recorded_capability_preserves_original_failure_when_observer_raises():
 import asyncio
 from v2.runtime.recording import RecordedCapability
 from v2.runtime.ledger import RunLedger
 from v2.contracts import PlanNode,TaskSpec
 original=RuntimeError('original')
 class Cap:
  name='team_ratings';task_season_scoped=True
  async def execute(self,*args):raise original
 def boom(p):raise OSError('observer')
 with pytest.raises(RuntimeError) as caught:asyncio.run(RecordedCapability(Cap(),RunLedger('r'),turn_id='r',activity=boom).execute(PlanNode(id='n',description='n',capability_hints=['team_ratings']),TaskSpec(goal='g',mode='quick',deliverable='d'),[]))
 assert caught.value is original

def test_executor_evidence_observer_failure_preserves_success():
 import asyncio
 from datetime import UTC,datetime
 from v2.runtime.executor import PlanExecutor
 from v2.contracts import EvidenceEnvelope,Plan,PlanNode,TaskSpec
 class Cap:
  name='team_ratings';task_season_scoped=True
  async def execute(self,*args):return EvidenceEnvelope(evidence_id='e',capability=self.name,source='f',observed_at=datetime.now(UTC),rows=[])
 def boom(p):raise ValueError('bad as_of shape')
 plan=Plan(nodes=[PlanNode(id='n',description='n',capability_hints=['team_ratings'])]);result=asyncio.run(PlanExecutor({'team_ratings':Cap()},evidence_activity=boom).execute(TaskSpec(goal='g',mode='quick',deliverable='d'),plan));assert result.plan.nodes[0].status.value=='complete' and result.evidence[0].evidence_id=='e'
