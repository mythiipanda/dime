import json
from datetime import UTC,datetime
import pytest
from v2.contracts import EvidenceEnvelope,PlanNode,TaskSpec
from v2.runtime.ledger import FileLedger
from v2.runtime.recording import RecordedCapability

@pytest.mark.anyio
async def test_recorded_root_evidence_persists_typed_source_identity(tmp_path):
    class C:
        name='team_ratings';task_season_scoped=True
        async def execute(self,node,task,evidence):
            # Synthetic fixture identity only; this is not benchmark data.
            return EvidenceEnvelope(evidence_id='e',capability='team_ratings',source='fixture',observed_at=datetime.now(UTC),rows=[{'TEAM_NAME':'Oklahoma City Thunder'}],source_identity={'kind':'warehouse','warehouse_id':'frozen-eval','sha256':'f'*64})
    ledger=FileLedger(tmp_path/'run.jsonl','run');cap=RecordedCapability(C(),ledger,turn_id='run')
    await cap.execute(PlanNode(id='n',description='ratings',capability_hints=['team_ratings']),TaskSpec(goal='g',mode='quick',deliverable='d'),[])
    payload=[json.loads(x) for x in (tmp_path/'run.jsonl').read_text().splitlines() if json.loads(x)['kind']=='tool/result'][0]['data']['evidence']
    assert payload['source_identity']=={'kind':'warehouse','warehouse_id':'frozen-eval','sha256':'f'*64}
    assert payload['lineage']==[]

@pytest.mark.anyio
async def test_dependent_source_identity_and_replay_remain_independent(tmp_path):
    from v2.runtime.projections import replay_turn
    parent=EvidenceEnvelope(evidence_id='parent',capability='x',source='fixture',observed_at=datetime.now(UTC),rows=[])
    class C:
        name='team_ratings';task_season_scoped=True
        async def execute(self,node,task,evidence):
            return EvidenceEnvelope(evidence_id='child',capability='team_ratings',source='fixture',observed_at=datetime.now(UTC),rows=[],lineage=['parent'],source_identity={'kind':'live','source':'nba_api'})
    ledger=FileLedger(tmp_path/'run.jsonl','run');cap=RecordedCapability(C(),ledger,turn_id='run')
    await cap.execute(PlanNode(id='n',description='x',capability_hints=['team_ratings']),TaskSpec(goal='g',mode='quick',deliverable='d'),[parent])
    entries=[]
    from v2.runtime.ledger import LedgerEntry
    for line in (tmp_path/'run.jsonl').read_text().splitlines():
        raw=json.loads(line)
        if raw['kind']=='tool/result': raw['data'].pop('duration_ms',None)
        entries.append(LedgerEntry.model_validate(raw))
    evidence=replay_turn(entries)['evidence'][0]
    assert evidence['lineage']==['parent'] and evidence['source_identity']=={'kind':'live','source':'nba_api'}
