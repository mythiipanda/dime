import json, os, sqlite3, sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from workspaces.service import WorkspaceStore

root = Path(os.environ['DIME_PI_TEST_ROOT'])
conv_path = root / 'cross-conversations.sqlite'
proj_path = root / 'cross-projects.sqlite'
workspaces = WorkspaceStore(root / 'cross-workspaces.sqlite')


def _conv_connect():
    con = sqlite3.connect(conv_path)
    con.execute(
        'CREATE TABLE IF NOT EXISTS conversations ('
        'owner TEXT NOT NULL, thread TEXT NOT NULL, '
        'sequence INTEGER NOT NULL, turn TEXT NOT NULL, '
        'run_id TEXT, turn_id TEXT, '
        'PRIMARY KEY(owner, thread, sequence))'
    )
    return con


def _proj_connect():
    con = sqlite3.connect(proj_path)
    con.execute('CREATE TABLE IF NOT EXISTS projects (id TEXT PRIMARY KEY, data TEXT NOT NULL)')
    return con


def _read_turns(owner, thread):
    with _conv_connect() as con:
        rows = con.execute(
            'SELECT turn FROM conversations WHERE owner=? AND thread=? ORDER BY sequence',
            (owner, thread),
        ).fetchall()
    return [json.loads(r[0])['content'] for r in rows]


def _get_project(pid):
    with _proj_connect() as con:
        row = con.execute('SELECT data FROM projects WHERE id=?', (pid,)).fetchone()
    return json.loads(row[0]) if row else None


if sys.argv[1] == 'prepare':
    with _conv_connect() as con:
        run_id = 'run-' + 'a' * 32
        con.execute(
            'INSERT INTO conversations(owner, thread, sequence, turn, run_id, turn_id) VALUES(?,?,?,?,?,?)',
            ('fixture', 'thread', 1, json.dumps({'role': 'user', 'content': 'old question'}), run_id, run_id),
        )
        con.execute(
            'INSERT INTO conversations(owner, thread, sequence, turn, run_id, turn_id) VALUES(?,?,?,?,?,?)',
            ('fixture', 'thread', 2, json.dumps({'role': 'assistant', 'content': 'old answer'}), run_id, run_id),
        )
        con.commit()
    pid = uuid4().hex
    now = datetime.now(timezone.utc).isoformat()
    project = {
        'id': pid,
        'goal': 'Old Python project',
        'status': 'pending',
        'run_id': f'project-{pid}',
        'created_at': now,
        'updated_at': now,
        'result': None,
        'error': None,
    }
    with _proj_connect() as con:
        con.execute('INSERT INTO projects(id, data) VALUES(?, ?)', (pid, json.dumps(project)))
        con.commit()
    workspace, token = workspaces.create('Old Python workspace', 'fixture')
    workspaces.update_members(workspace.id, add_thread_ids=['old-thread'], add_brief_ids=['old-brief'])
    (root / 'cross-expected.json').write_text(json.dumps({
        'project': project,
        'workspace': workspaces.get(workspace.id).model_dump(mode='json'),
        'token': token,
    }))
else:
    expected = json.loads((root / 'cross-expected.json').read_text())
    assert _read_turns('fixture', 'thread') == ['old question', 'old answer', 'Node question', 'Node answer']
    assert _read_turns('wrong', 'thread') == []
    assert _get_project(expected['project']['id'])['goal'] == 'Old Python project'
    workspace = workspaces.get(expected['workspace']['id'])
    assert workspace.member_thread_ids == ['new-thread'] and workspace.member_brief_ids == ['old-brief']
    assert workspaces.verify_owner(workspace.id, expected['token'])
    created = json.loads((root / 'cross-node-created.json').read_text())
    assert _get_project(created['project'])['goal'] == 'Node project'
    assert workspaces.get(created['workspace']).owner == 'node-owner'
    assert workspaces.verify_owner(created['workspace'], created['token'])
    print('Python reads Node writes in existing SQLite formats; owner/token boundaries preserved')
