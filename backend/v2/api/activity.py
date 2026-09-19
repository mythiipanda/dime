from __future__ import annotations
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from typing import Literal, Union
import os,re
from pydantic import BaseModel, ConfigDict, Field, StrictInt, TypeAdapter, field_validator

Phase=Literal['understand','plan','execute','verify']
Status=Literal['running','complete','failed','pass','partial','repair']
Title=Literal['Request understood','Plan accepted','Tool running','Tool complete','Tool failed','Evidence admitted','Evidence rejected','Verification updated']
Transition=Literal['started','completed','failed','succeeded','admitted','rejected','snapshot']
class Safe(BaseModel):model_config=ConfigDict(extra='forbid',frozen=True)
class StageData(Safe):
 mode:Literal['quick','deep']|None=None;season:str|None=Field(default=None,pattern=r'^\d{4}-\d{2}$');entity_count:StrictInt=Field(ge=0);requirement_count:StrictInt=Field(ge=0);calculation_count:StrictInt=Field(ge=0)
class PlanData(Safe):
 node_count:StrictInt=Field(ge=0);capabilities:list[str]=Field(max_length=64);unknown_capability_count:StrictInt=Field(ge=0)
 @field_validator('capabilities')
 @classmethod
 def safe_caps(cls,v):
  if any(not re.fullmatch(r'[a-z][a-z0-9_]{0,63}',x) for x in v):raise ValueError('invalid capability')
  return v
class ToolCallData(Safe):
 name:str=Field(pattern=r'^[a-z][a-z0-9_]{0,63}$');argument_count:StrictInt=Field(ge=0);unknown_argument_count:StrictInt=Field(ge=0)
class ToolResultData(Safe):
 name:str=Field(pattern=r'^[a-z][a-z0-9_]{0,63}$');rows:StrictInt|None=Field(default=None,ge=0)
class EvidenceData(Safe):
 capability:str=Field(pattern=r'^[a-z][a-z0-9_]{0,63}$');season:str|None=Field(default=None,pattern=r'^\d{4}-\d{2}$');as_of:str|None=Field(default=None,pattern=r'^\d{4}-\d{2}-\d{2}$');observed_at:datetime;rows:StrictInt|None=Field(default=None,ge=0);qualification:Literal['present','missing'];coverage:Literal['present','missing'];warning_count:StrictInt=Field(ge=0)
class VerificationData(Safe):
 round:Literal['initial','repair:1','repair:2','reverify:1','reverify:2'];supported_count:StrictInt=Field(ge=0);claim_count:StrictInt=Field(ge=0);missing_count:StrictInt=Field(ge=0);contradiction_count:StrictInt=Field(ge=0);repair_count:StrictInt=Field(ge=0)
SafeData=Union[StageData,PlanData,ToolCallData,ToolResultData,EvidenceData,VerificationData]
ADAPTERS={'stage_summary':TypeAdapter(StageData),'plan_update':TypeAdapter(PlanData),'tool_call':TypeAdapter(ToolCallData),'tool_result':TypeAdapter(ToolResultData),'evidence_update':TypeAdapter(EvidenceData),'verification_update':TypeAdapter(VerificationData)}
ActivityKind=Literal['stage_summary','plan_update','tool_call','tool_result','evidence_update','verification_update']
class ActivityEvent(BaseModel):
 model_config=ConfigDict(extra='forbid',frozen=True)
 event_id:str=Field(pattern=r'^[A-Za-z0-9_-]+:\d+$');sequence:StrictInt=Field(ge=1);emitted_at:datetime;phase:Phase;status:Status;title:Title;kind:ActivityKind;correlation_id:str|None=Field(default=None,pattern=r'^activity-\d+$');transition:Transition;duration_ms:StrictInt|None=Field(default=None,ge=0);data:SafeData
class ActivityJournal:
 def __init__(self,path:Path,run_id:str):self.path=path;self.run_id=run_id;self._lock=Lock();path.parent.mkdir(parents=True,exist_ok=True)
 def read(self)->list[ActivityEvent]:
  if not self.path.exists():return []
  lines=self.path.read_bytes().splitlines(keepends=True);rows=[]
  for i,line in enumerate(lines):
   if not line.endswith(b'\n'):
    if i==len(lines)-1:break
    raise ValueError('corrupt activity journal line')
   rows.append(ActivityEvent.model_validate_json(line))
  if [x.sequence for x in rows]!=list(range(1,len(rows)+1)):raise ValueError('activity sequence must be contiguous')
  if any(x.event_id != f'{self.run_id}:{x.sequence}' for x in rows):raise ValueError('activity event identity mismatch')
  return rows
 def append(self,*,kind,phase,status,title,transition,correlation_id=None,duration_ms=None,data=None,summary=None):
  del summary;safe=ADAPTERS[kind].validate_python(data or {})
  with self._lock:
   rows=self.read();seq=len(rows)+1;event=ActivityEvent(event_id=f'{self.run_id}:{seq}',sequence=seq,emitted_at=datetime.now(UTC),phase=phase,status=status,title=title,kind=kind,correlation_id=correlation_id,transition=transition,duration_ms=duration_ms,data=safe)
   if self.path.exists() and not self.path.read_bytes().endswith(b'\n'):
    raw=self.path.read_bytes();self.path.write_bytes(raw[:raw.rfind(b'\n')+1])
   with self.path.open('a',encoding='utf-8') as h:h.write(event.model_dump_json()+'\n');h.flush();os.fsync(h.fileno())
   return event
