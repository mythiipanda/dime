"""Cross-language product persistence fixture using only explicit owned paths."""
import json,os,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from v2.conversations import ConversationStore
from v2.projects.service import ProjectStore
from workspaces.service import WorkspaceStore
root=Path(os.environ['DIME_PI_TEST_ROOT'])
conversations=ConversationStore(root/'cross-conversations.sqlite')
projects=ProjectStore(root/'cross-projects.sqlite')
workspaces=WorkspaceStore(root/'cross-workspaces.sqlite')
if sys.argv[1]=='prepare':
 conversations.append_exchange('fixture','thread','old question','old answer',run_id='run-'+'a'*32,turn_id='run-'+'a'*32)
 project=projects.create('Old Python project')
 workspace,token=workspaces.create('Old Python workspace','fixture')
 workspaces.update_members(workspace.id,add_thread_ids=['old-thread'],add_brief_ids=['old-brief'])
 (root/'cross-expected.json').write_text(json.dumps({'project':project.model_dump(mode='json'),'workspace':workspaces.get(workspace.id).model_dump(mode='json'),'token':token}))
else:
 expected=json.loads((root/'cross-expected.json').read_text())
 assert [turn.content for turn in conversations.read('fixture','thread')]==['old question','old answer','Node question','Node answer']
 assert conversations.read('wrong','thread')==[]
 assert projects.get(expected['project']['id']).goal=='Old Python project'
 workspace=workspaces.get(expected['workspace']['id'])
 assert workspace.member_thread_ids==['new-thread'] and workspace.member_brief_ids==['old-brief']
 assert workspaces.verify_owner(workspace.id,expected['token'])
 created=json.loads((root/'cross-node-created.json').read_text())
 assert projects.get(created['project']).goal=='Node project'
 assert workspaces.get(created['workspace']).owner=='node-owner'
 assert workspaces.verify_owner(created['workspace'],created['token'])
 print('Python reads Node writes in existing SQLite formats; owner/token boundaries preserved')
