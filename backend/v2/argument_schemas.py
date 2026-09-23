"""Offline compiler and explicit provider-wire schema normalizer."""
from __future__ import annotations
import copy,hashlib,json,re
from typing import Any

def canonical_hash(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':')).encode()).hexdigest()
class SchemaCompileError(ValueError):
 def __init__(self,code,path='$'):
  self.code=code;self.path=path;super().__init__(f'{code} at {path}')
def _resolve_pointer(root,pointer):
 if not isinstance(pointer,str) or not pointer.startswith('#/'):
  raise SchemaCompileError('unsupported_json_pointer',str(pointer))
 parts=pointer[2:].split('/')
 if any(re.search(r'~(?![01])',raw) for raw in parts):
  raise SchemaCompileError('invalid_json_pointer_escape',pointer)
 value=root
 try:
  for raw in parts:
   part=raw.replace('~1','/').replace('~0','~');value=value[part]
 except (KeyError,TypeError,IndexError):raise SchemaCompileError('unresolved_json_pointer',pointer)
 return copy.deepcopy(value)
def _inline(value,root,stack,path):
 if isinstance(value,list):return [_inline(x,root,stack,path+'[]') for x in value]
 if not isinstance(value,dict):return value
 if '$ref' in value:
  if len(value)!=1:raise ValueError(f'ref siblings at {path}')
  ref=value['$ref']
  if ref in stack:raise ValueError(f'ref cycle at {path}')
  return _inline(_resolve_pointer(root,ref),root,stack+(ref,),path)
 return {k:_inline(v,root,stack,f'{path}.{k}') for k,v in value.items() if not (k=='$defs' and path=='$')}
def _nullable(schema):
 branches=schema.get('anyOf')
 if branches and any(x.get('type')=='null' for x in branches):return schema
 return {'anyOf':[schema,{'type':'null'}]}
def normalize_provider_wire_schema(source):
 """Normalize only an explicit all-slots provider wire codec, never arbitrary domain schemas."""
 inlined=_inline(copy.deepcopy(source),source,(),'$');losses=[]
 def walk(v,path='$'):
  if isinstance(v,list):return [walk(x,path+'[]') for x in v]
  if not isinstance(v,dict):return v
  out={k:walk(x,f'{path}.{k}') for k,x in v.items() if k not in {'title','description'}}
  if out.get('type')=='object':
   if out.get('additionalProperties',False) is not False:raise ValueError(f'free-form object at {path}')
   props=out.get('properties',{});original=set(out.get('required',[]))
   for key in props:
    if key not in original:
     default=props[key].get('default')
     props[key]=_nullable(props[key]);props[key]['default']=default
     losses.append({'path':f'{path}.properties.{key}','classification':'optional-materialized-nullable','default':default})
   out['required']=sorted(props)
  return out
 candidate=walk(inlined)
 return candidate,{'source_schema_sha256':canonical_hash(source),'candidate_schema_sha256':canonical_hash(candidate),'hash_canonicalization':'UTF-8 sorted-key compact JSON','losses':losses}

def _kinds(schema):
 out=[]
 for branch in schema.get('anyOf') or [schema]:
  t=branch.get('type')
  if t in {'null','boolean','integer','number','string'}:out.append({'null':'null','boolean':'bool','integer':'int','number':'decimal' if branch.get('x-dime-exact-decimal') else 'number','string':'decimal' if branch.get('x-dime-exact-decimal') else 'string'}[t]);continue
  if t=='array':
   items=branch.get('items')
   if not isinstance(items,dict) or any(x in branch for x in ('prefixItems','contains')):raise ValueError('tuple/mixed arrays unsupported')
   ks=_kinds(items)
   if len(ks)!=1 or ks[0]=='null' or ks[0].endswith('_list'):raise ValueError('nested/mixed arrays unsupported')
   out.append(ks[0]+'_list');continue
  raise ValueError(f'unsupported type {t!r}')
 return out
def compile_capability_catalog(catalog):
 rows=[]
 for cap,entry in sorted(catalog.items()):
  schema=entry.get('arguments',{});props=schema.get('properties',{});compiled=[];reasons=[]
  if schema.get('type')!='object' or schema.get('additionalProperties',False) is not False:reasons.append('arguments must be closed object')
  for name,prop in sorted(props.items()):
   try:kinds=_kinds(prop)
   except ValueError as exc:kinds=[];reasons.append(f'{name}: {exc}')
   branches=[]
   for branch in prop.get('anyOf') or [prop]:
    try:branch_kinds=_kinds(branch)
    except ValueError:branch_kinds=[]
    constraints={key:branch[key] for key in ('enum','minimum','maximum','exclusiveMinimum','exclusiveMaximum','multipleOf','minLength','maxLength','pattern','minItems','maxItems') if key in branch}
    item_schema=branch.get('items') if isinstance(branch.get('items'),dict) else {}
    item_constraints={key:item_schema[key] for key in ('enum','minimum','maximum','exclusiveMinimum','exclusiveMaximum','multipleOf','minLength','maxLength','pattern') if key in item_schema}
    branches.append({'compiled_kinds':branch_kinds,'constraints':constraints,'item_constraints':item_constraints,
     'scalar_exact_decimal':branch.get('x-dime-exact-decimal',False),
     'list_item_exact_decimal':(branch.get('items',{}).get('x-dime-exact-decimal',False) if isinstance(branch.get('items'),dict) else False),
     'schema_sha256':canonical_hash(branch)})
   compiled.append({'property':name,'required':name in schema.get('required',[]),'default_present':'default' in prop,'default':prop.get('default'),'nullable':'null' in kinds,'compiled_kinds':kinds,'branches':branches,'scalar_exact_decimal':prop.get('x-dime-exact-decimal',False),'list_item_exact_decimal':(prop.get('items',{}).get('x-dime-exact-decimal',False) if isinstance(prop.get('items'),dict) else False),'schema_sha256':canonical_hash(prop)})
  rows.append({'capability_id':cap,'status':'UNREPRESENTABLE' if reasons else 'REPRESENTABLE','reasons':reasons,'properties':compiled,'dependent_entity_arguments':entry.get('dependent_entity_arguments',{}),'schema_sha256':canonical_hash(schema)})
 return {'catalog_sha256':canonical_hash(catalog),'capabilities':rows}
