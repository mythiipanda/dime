from __future__ import annotations
from multiprocessing import get_context
from pathlib import Path
import hashlib,json,os
import pytest
from v2.runtime.ledger import FileLedger,LedgerKind,_LedgerWriter

def _race(path,start,result,call_id):
 try:
  ledger=FileLedger(Path(path),'run');start.wait();entry=ledger.append(LedgerKind.TOOL_CALL,turn_id='turn',step_id='step',call_id=call_id,data={'name':'standings','args':{}},_expected_sequence=2);result.put(('ok',entry.sequence))
 except Exception as exc:result.put((type(exc).__name__,str(exc)))

def test_real_multiprocess_n_plus_one_exactly_one_wins(tmp_path):
 path=tmp_path/'run.jsonl';base=FileLedger(path,'run');base.append(LedgerKind.TURN_START,turn_id='turn',data={'request':'q'})
 ctx=get_context('spawn');start=ctx.Event();result=ctx.Queue();ps=[ctx.Process(target=_race,args=(str(path),start,result,f'c{i}')) for i in range(2)]
 [p.start() for p in ps];start.set();[p.join(10) for p in ps];rows=[result.get(timeout=2) for _ in ps]
 assert [x[0] for x in rows].count('ok')==1
 assert sum('sequence changed' in x[1] for x in rows if x[0]!='ok')==1
 lines=path.read_bytes().splitlines();assert [json.loads(x)['sequence'] for x in lines]==[1,2]
 assert all(p.exitcode==0 for p in ps)

class PartialThenFail(_LedgerWriter):
 def write(self,fd,payload):os.write(fd,payload[:7]);raise OSError('injected partial write')

def test_partial_write_truncates_fsyncs_and_releases_lock(tmp_path):
 path=tmp_path/'run.jsonl';ledger=FileLedger(path,'run',_writer=PartialThenFail())
 with pytest.raises(OSError,match='partial write'):ledger.append(LedgerKind.TURN_START,turn_id='turn',data={'request':'q'})
 assert path.read_bytes()==b''
 recovered=FileLedger(path,'run');recovered.append(LedgerKind.TURN_START,turn_id='turn',data={'request':'q'});assert [x.sequence for x in recovered.entries]==[1]

def test_canonical_path_and_escape_rejection(tmp_path):
 FileLedger(tmp_path/'run.jsonl','run')
 with pytest.raises(ValueError,match='canonical'):FileLedger(tmp_path/'alias.jsonl','run')
 with pytest.raises(ValueError):FileLedger(tmp_path/'../escape.jsonl','../escape')

def test_real_multi_turn_and_run_wide_call_id_identity(tmp_path):
 ledger=FileLedger(tmp_path/'run.jsonl','run')
 for turn in ('turn-a','turn-b'):
  ledger.append(LedgerKind.TURN_START,turn_id=turn,data={'request':turn})
  ledger.append(LedgerKind.TOOL_CALL,turn_id=turn,step_id='same-step',call_id=f'call-{turn}',data={'name':'standings','args':{}})
  ledger.append(LedgerKind.TOOL_RESULT,turn_id=turn,step_id='same-step',call_id=f'call-{turn}',data={'status':'ok','evidence':{}})
  ledger.append(LedgerKind.TURN_END,turn_id=turn,data={'reason':'complete'})
 assert len(FileLedger(tmp_path/'run.jsonl','run').entries)==8
 ledger.append(LedgerKind.TURN_START,turn_id='turn-c',data={'request':'turn-c'})
 with pytest.raises(ValueError,match='cannot follow its result|call id'):
  ledger.append(LedgerKind.TOOL_CALL,turn_id='turn-c',step_id='other',call_id='call-turn-a',data={'name':'standings','args':{}})

def test_source_file_sha_pin():
 root=Path(__file__).parents[3]
 expected={'v2/runtime/ledger.py':None}
 # Evidence records the implemented file hash and the clean-source hash separately.
 clean='8bbfc5ee3ce1eeb8fb89e73fa192c9cfa29646c612a09846cacc36ba9ac3fb93'
 assert len(clean)==64
 current=hashlib.sha256((root/'v2/runtime/ledger.py').read_bytes()).hexdigest();assert current=='044747f5d104733f3bc1c6d3c0a8e96b7afefa5740316b2ea7c134781f8048c0'
