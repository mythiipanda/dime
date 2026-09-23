"""Offline exact v2/v3 persistence contracts. Live cutover is intentionally not wired."""
from __future__ import annotations
import hashlib,json
from typing import Any,Literal
from pydantic import BaseModel,ConfigDict,Field,StrictInt
from v2.arguments import TaskSpecV3,PlanV3,PlannerArguments
class Closed(BaseModel):model_config=ConfigDict(extra='forbid')
class ContractIdentity(Closed):argument_contract_version:Literal[3]=3;schema_sha256:str=Field(pattern=r'^[0-9a-f]{64}$');catalog_sha256:str=Field(pattern=r'^[0-9a-f]{64}$')
class OriginIdentity(Closed):origin_version:Literal[2,3];origin_content_sha256:str=Field(pattern=r'^[0-9a-f]{64}$');request_context_hash:str=Field(pattern=r'^[0-9a-f]{64}$')
class CheckpointV3(Closed):version:Literal[3]=3;run_id:str;contract:ContractIdentity;origin:OriginIdentity;task:TaskSpecV3;plan:PlanV3;evidence_by_node:dict[str,dict]=Field(default_factory=dict,max_length=32);attempts:dict[str,StrictInt]=Field(default_factory=dict,max_length=32);errors:dict[str,list[str]]=Field(default_factory=dict,max_length=32);error_codes:dict[str,list[str]]=Field(default_factory=dict,max_length=32)
class ToolCallPayloadV3(Closed):payload_contract_version:Literal[3]=3;capability:str;arguments:PlannerArguments;argument_schema_sha256:str=Field(pattern=r'^[0-9a-f]{64}$')
class PersistenceError(ValueError):
 def __init__(self,code):self.code=code;super().__init__(code)
def inspect_checkpoint_version(raw):
 try:value=json.loads(raw)
 except Exception:raise PersistenceError('invalid_checkpoint')
 if not isinstance(value,dict):raise PersistenceError('invalid_checkpoint')
 version=value.get('version')
 if version not in {2,3}:raise PersistenceError('unsupported_version')
 return {'version':version,'origin_content_sha256':hashlib.sha256(raw).hexdigest(),'document':value}
def validate_checkpoint_v3(raw,expected_schema_hash,expected_catalog_hash):
 inspected=inspect_checkpoint_version(raw)
 if inspected['version']!=3:raise PersistenceError('unsupported_version')
 try:value=CheckpointV3.model_validate(inspected['document'])
 except Exception:raise PersistenceError('invalid_v3_envelope')
 if value.contract.schema_sha256!=expected_schema_hash or value.contract.catalog_sha256!=expected_catalog_hash:raise PersistenceError('schema_hash_mismatch')
 return value
def project_requirement_v2(requirement):
 sets=[dict(x.arguments) for x in requirement.capability_argument_sets]
 if sets and any(x!=sets[0] for x in sets[1:]):raise PersistenceError('v2_projection_requires_v3')
 return {'id':requirement.id,'capability_options':requirement.capability_options,'capability_arguments':sets[0] if sets else {}}
