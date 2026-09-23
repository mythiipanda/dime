import hashlib,json,pytest
from v2.versioned_persistence import *
from v2.arguments import RequirementV3
def test_inspector_only_identifies_and_hashes_v2():
 raw=b'{"version":2,"run_id":"r"}\n';x=inspect_checkpoint_version(raw);assert x['version']==2 and x['origin_content_sha256']==hashlib.sha256(raw).hexdigest()
def test_v3_validation_and_hash_taxonomy():
 with pytest.raises(PersistenceError) as e:validate_checkpoint_v3(b'{"version":3}','1'*64,'2'*64)
 assert e.value.code=='invalid_v3_envelope'
def test_v2_projection_disagreement():
 r=RequirementV3(id='r',description='r',capability_options=['a','b'],capability_argument_sets=[{'capability_id':'a','arguments':{'entries':[{'key':'x','kind':'int','int_value':1}]}},{'capability_id':'b','arguments':{'entries':[{'key':'x','kind':'int','int_value':2}]}}])
 with pytest.raises(PersistenceError) as e:project_requirement_v2(r)
 assert e.value.code=='v2_projection_requires_v3'

def test_inspect_checkpoint_rejects_non_object_json():
 from v2.versioned_persistence import PersistenceError
 import pytest
 for raw in (b'[]',b'null',b'1',b'"x"'):
  with pytest.raises(PersistenceError) as exc:inspect_checkpoint_version(raw)
  assert exc.value.code=='invalid_checkpoint'
