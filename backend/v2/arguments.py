"""Closed typed argument contracts and schema-aware migration codecs."""
from __future__ import annotations
from collections.abc import Iterator, Mapping
from decimal import Decimal
import math,re
from typing import Annotated, Any, Literal, Union
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictFloat, StrictInt, StrictStr, model_validator
KEY=Annotated[StrictStr,Field(min_length=1,max_length=128,pattern=r'^[A-Za-z_][A-Za-z0-9_]*$')]
TEXT=Annotated[StrictStr,Field(max_length=2048)]
DIMENSION_ID=Annotated[StrictStr,Field(min_length=1,max_length=128,pattern=r'^[A-Z][A-Z0-9_]*$')]
DECIMAL_TEXT=Annotated[StrictStr,Field(min_length=1,max_length=128,pattern=r'^-?(0|[1-9][0-9]*)(\.[0-9]+)?$')]
FINITE=Annotated[StrictFloat,Field(allow_inf_nan=False)]
class Closed(BaseModel):model_config=ConfigDict(extra='forbid')
class NullArg(Closed):key:KEY;kind:Literal['null'];value:None
class BoolArg(Closed):key:KEY;kind:Literal['bool'];bool_value:StrictBool
class IntArg(Closed):key:KEY;kind:Literal['int'];int_value:StrictInt
class NumberArg(Closed):key:KEY;kind:Literal['number'];number_value:FINITE
class DecimalArg(Closed):key:KEY;kind:Literal['decimal'];decimal_value:DECIMAL_TEXT
class StringArg(Closed):key:KEY;kind:Literal['string'];string_value:TEXT
class BoolListArg(Closed):key:KEY;kind:Literal['bool_list'];bool_list_value:list[StrictBool]=Field(max_length=32)
class IntListArg(Closed):key:KEY;kind:Literal['int_list'];int_list_value:list[StrictInt]=Field(max_length=32)
class NumberListArg(Closed):key:KEY;kind:Literal['number_list'];number_list_value:list[FINITE]=Field(max_length=32)
class DecimalListArg(Closed):key:KEY;kind:Literal['decimal_list'];decimal_list_value:list[DECIMAL_TEXT]=Field(max_length=32)
class StringListArg(Closed):key:KEY;kind:Literal['string_list'];string_list_value:list[TEXT]=Field(max_length=32)
ArgumentEntry=Annotated[Union[NullArg,BoolArg,IntArg,NumberArg,DecimalArg,StringArg,BoolListArg,IntListArg,NumberListArg,DecimalListArg,StringListArg],Field(discriminator='kind')]
SLOTS={k:('value' if k=='null' else k+'_value') for k in ('null','bool','int','number','decimal','string','bool_list','int_list','number_list','decimal_list','string_list')}

def encode_argument(key:str,value:Any,schema:dict[str,Any]|None=None)->dict[str,Any]:
 schema=schema or {};exact=schema.get('x-dime-exact-decimal') is True;items=schema.get('items',{});exact_list=items.get('x-dime-exact-decimal') is True or schema.get('x-dime-exact-decimal-list') is True
 pattern=r'-?(0|[1-9][0-9]*)(\.[0-9]+)?'
 if exact:
  if type(value) is not str or re.fullmatch(pattern,value) is None:raise ValueError('unrepresentable exact decimal')
  return {'key':key,'kind':'decimal','decimal_value':value}
 if exact_list:
  if type(value) is not list or any(type(x) is not str or re.fullmatch(pattern,x) is None for x in value):raise ValueError('unrepresentable exact decimal list')
  return {'key':key,'kind':'decimal_list','decimal_list_value':value}
 if value is None:return {'key':key,'kind':'null','value':None}
 if type(value) is bool:return {'key':key,'kind':'bool','bool_value':value}
 if type(value) is int:return {'key':key,'kind':'int','int_value':value}
 if type(value) is float:
  if not math.isfinite(value):raise ValueError('number must be finite')
  return {'key':key,'kind':'number','number_value':value}
 if type(value) is Decimal:
  if not value.is_finite():raise ValueError('decimal must be finite')
  return {'key':key,'kind':'decimal','decimal_value':str(value)}
 if type(value) is str:return {'key':key,'kind':'string','string_value':value}
 if type(value) is list:
  if not value:
   branches=schema.get('anyOf') or [schema];types={x.get('items',{}).get('type') for x in branches if x.get('type')=='array'};kind={'boolean':'bool_list','integer':'int_list','number':'number_list','string':'string_list'}.get(next(iter(types)) if len(types)==1 else None)
   if kind is None:raise ValueError('empty list item type is ambiguous')
   return {'key':key,'kind':kind,kind+'_value':[]}
  types={type(x) for x in value}
  if len(types)!=1 or next(iter(types)) not in {bool,int,float,str}:raise ValueError('only homogeneous scalar lists are supported')
  typ=next(iter(types));kind={bool:'bool_list',int:'int_list',float:'number_list',str:'string_list'}[typ]
  if typ is float and any(not math.isfinite(x) for x in value):raise ValueError('numbers must be finite')
  return {'key':key,'kind':kind,kind+'_value':value}
 raise ValueError('unsupported argument value')

class TypedArguments(Closed,Mapping[str,Any]):
 entries:list[ArgumentEntry]=Field(default_factory=list,max_length=64)
 @model_validator(mode='after')
 def canonical(self):
  keys=[x.key for x in self.entries]
  if len(keys)!=len(set(keys)):raise ValueError('duplicate argument key')
  self.entries.sort(key=lambda x:x.key);return self
 def as_dict(self):return {x.key:getattr(x,SLOTS[x.kind]) for x in self.entries}
 def __getitem__(self,k):return self.as_dict()[k]
 def __iter__(self)->Iterator[str]:return iter(self.as_dict())
 def __len__(self):return len(self.entries)
 def get(self,k,d=None):return self.as_dict().get(k,d)
 def __eq__(self,other):
  if isinstance(other,Mapping):return self.as_dict()==dict(other)
  return super().__eq__(other)
 def model_dump(self,*a,legacy:bool=False,**kw):return self.as_dict() if legacy else super().model_dump(*a,**kw)
class LegacyArgumentMap(Closed):
 values:dict[str,Any]=Field(default_factory=dict,max_length=64)

def migrate_legacy_arguments(capability_id:str,values:dict[str,Any],schema:dict[str,Any],*,target:Literal['requirement','planner']):
 if schema.get('type')!='object':raise ValueError(f'{capability_id}: argument schema must be object')
 props=schema.get('properties',{})
 unknown=set(values)-set(props)
 if unknown:raise ValueError(f'{capability_id}: unknown arguments {sorted(unknown)}')
 from jsonschema import Draft202012Validator
 effective=dict(schema)
 if target=='requirement':effective.pop('required',None)
 errors=list(Draft202012Validator(effective).iter_errors(values))
 if errors:raise ValueError(f'{capability_id}: invalid arguments: {errors[0].message}')
 rows=[encode_argument(k,v,props[k]) for k,v in values.items()]
 return (RequirementArguments if target=='requirement' else PlannerArguments).model_validate({'entries':rows})

class RequirementArguments(TypedArguments):entries:list[ArgumentEntry]=Field(default_factory=list,max_length=32)
class PlannerArguments(TypedArguments):entries:list[ArgumentEntry]=Field(default_factory=list,max_length=64)
class ProviderWireEntry(Closed):
 key:KEY
 kind:Literal[tuple(SLOTS)]
 value:None
 bool_value:StrictBool|None
 int_value:StrictInt|None
 number_value:FINITE|None
 decimal_value:DECIMAL_TEXT|None
 string_value:TEXT|None
 bool_list_value:list[StrictBool]|None=Field(max_length=32)
 int_list_value:list[StrictInt]|None=Field(max_length=32)
 number_list_value:list[FINITE]|None=Field(max_length=32)
 decimal_list_value:list[DECIMAL_TEXT]|None=Field(max_length=32)
 string_list_value:list[TEXT]|None=Field(max_length=32)
class ProviderWireArguments(Closed):
 entries:list[ProviderWireEntry]|None=Field(max_length=64)
def _wire_prop_nullable(prop:dict[str,Any])->bool:
 t=prop.get('type')
 if t=='null' or (isinstance(t,list) and 'null' in t):return True
 for branch in prop.get('anyOf') or []:
  if not isinstance(branch,dict):continue
  bt=branch.get('type')
  if bt=='null' or (isinstance(bt,list) and 'null' in bt):return True
 return False
def _null_is_omitted(key:str,schema:dict[str,Any])->bool:
 prop=(schema.get('properties') or {}).get(key)
 if not isinstance(prop,dict):return False
 if _wire_prop_nullable(prop):return False
 if key in (schema.get('required') or []):return False
 return 'default' in prop
NULL_AS_OMITTED='null-as-omitted'
def provider_to_source(value:ProviderWireArguments|None,target:Literal['requirement','planner'],*,route:str|None=None,capability_id:str|None=None,argument_schema:dict[str,Any]|None=None,drops:list[dict[str,Any]]|None=None):
 rows=[]
 for item in (value.entries if value is not None and value.entries is not None else []):
  raw=item.model_dump();active=SLOTS[item.kind]
  if item.kind!='null' and raw[active] is None:raise ValueError('kind payload mismatch')
  if any(raw[x] is not None for x in set(SLOTS.values())-{active}):raise ValueError('inactive payload non-null')
  if item.kind=='null' and argument_schema is not None and _null_is_omitted(item.key,argument_schema):
   if drops is not None and route is not None and capability_id is not None:
    drops.append({'route':route,'capability_id':capability_id,'key':item.key,'rule':NULL_AS_OMITTED})
   continue
  rows.append({'key':item.key,'kind':item.kind,active:raw[active]})
 return (RequirementArguments if target=='requirement' else PlannerArguments).model_validate({'entries':rows})

CAPABILITY_ID=Annotated[StrictStr,Field(min_length=1,max_length=64,pattern=r'^[a-z][a-z0-9_]*$')]
class CapabilityArgumentSet(Closed):
 capability_id:CAPABILITY_ID
 arguments:RequirementArguments=Field(default_factory=RequirementArguments)
class RequirementV3(Closed):
 description:TEXT
 id:Annotated[StrictStr,Field(min_length=1,max_length=64,pattern=r'^[a-z][a-z0-9_]*$')]
 capability_options:list[CAPABILITY_ID]=Field(min_length=1,max_length=8)
 capability_argument_sets:list[CapabilityArgumentSet]=Field(min_length=1,max_length=8)
 @model_validator(mode='after')
 def exact_sets(self):
  if len(self.capability_options)!=len(set(self.capability_options)):raise ValueError('duplicate capability option')
  ids=[x.capability_id for x in self.capability_argument_sets]
  if len(ids)!=len(set(ids)):raise ValueError('duplicate capability argument set')
  if set(ids)!=set(self.capability_options):raise ValueError('capability argument sets must exactly cover options')
  self.capability_argument_sets.sort(key=lambda x:x.capability_id);return self
 def select(self,capability_id:str)->PlannerArguments:
  if capability_id not in self.capability_options:raise ValueError('planner capability not allowed')
  source=next(x.arguments for x in self.capability_argument_sets if x.capability_id==capability_id)
  return PlannerArguments.model_validate(source.model_dump())
class TaskSpecV3(Closed):contract_version:Literal[3]=3;requirements:list[RequirementV3]=Field(max_length=32)
class PlannerNodeV3(Closed):id:StrictStr;capability:CAPABILITY_ID;arguments:PlannerArguments=Field(default_factory=PlannerArguments)
class PlanV3(Closed):contract_version:Literal[3]=3;nodes:list[PlannerNodeV3]=Field(max_length=64)
class CapabilityArgumentSetWire(Closed):
 capability_id:CAPABILITY_ID
 arguments:ProviderWireArguments|None
class RequirementWire(Closed):
 description:TEXT
 id:Annotated[StrictStr,Field(min_length=1,max_length=64,pattern=r'^[a-z][a-z0-9_]*$')]
 capability_options:list[CAPABILITY_ID]=Field(min_length=1,max_length=8)
 capability_argument_sets:list[CapabilityArgumentSetWire]=Field(min_length=1,max_length=8)
 metric_ids:list[DIMENSION_ID]|None=Field(max_length=16)
 requested_outputs:list[DIMENSION_ID]|None=Field(max_length=16)
class CalculationRequirementWire(Closed):
 id:Annotated[StrictStr,Field(min_length=1,max_length=64,pattern=r'^[a-z][a-z0-9_]*$')]
 description:TEXT
 metric_ids:list[DIMENSION_ID]|None=Field(max_length=16)
 requested_outputs:list[DIMENSION_ID]|None=Field(max_length=16)
class RequirementReviewWire(Closed):
 requirements:list[RequirementWire]|None=Field(max_length=32)
 calculation_requirements:list[CalculationRequirementWire]|None=Field(max_length=32)
 missing_subquestions:list[str]|None=Field(max_length=32)
 missing_skills:list[str]|None=Field(max_length=16)
class PlannerNodeWire(Closed):
 id:StrictStr
 description:TEXT
 depends_on:list[str]|None=Field(max_length=32)
 capability:CAPABILITY_ID
 covers_requirement_ids:list[str]|None=Field(max_length=32)
 arguments:ProviderWireArguments|None
 max_attempts:StrictInt|None=Field(ge=1,le=5)
 status:Literal['pending','running','complete','failed','skipped']|None
class PlannerOutputWire(Closed):
 nodes:list[PlannerNodeWire]|None=Field(max_length=32)
