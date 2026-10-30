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
