import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "scripts"))

import dab_run


SS_SAMPLE = """\
State    Recv-Q   Send-Q     Local Address:Port      Peer Address:Port   Process
LISTEN   0        511              0.0.0.0:8062           0.0.0.0:*       users:(("MainThread",pid=1293107,fd=22))
"""


def test_port_owner_pid_parses_ss(monkeypatch):
    class FakeProc:
        stdout = SS_SAMPLE
        returncode = 0

    monkeypatch.setattr(dab_run.subprocess, "run", lambda *a, **k: FakeProc())
    assert dab_run.port_owner_pid(8062) == 1293107


def test_port_owner_pid_none_when_unmatched(monkeypatch):
    class FakeProc:
        stdout = ""
        returncode = 1

    monkeypatch.setattr(dab_run.subprocess, "run", lambda *a, **k: FakeProc())
    assert dab_run.port_owner_pid(8062) is None


def test_host_matches_worktree(monkeypatch):
    monkeypatch.setattr(dab_run, "proc_cwd", lambda pid: dab_run.ROOT)
    assert dab_run.host_matches_worktree(1234) is True
    monkeypatch.setattr(dab_run, "proc_cwd", lambda pid: Path("/other/worktree"))
    assert dab_run.host_matches_worktree(1234) is False
    monkeypatch.setattr(dab_run, "proc_cwd", lambda pid: None)
    assert dab_run.host_matches_worktree(1234) is False


def test_pid_is_descendant(monkeypatch):
    stats = {
        "/proc/300/stat": "300 (node) S 200 100 100 0 -1 4194304",
        "/proc/200/stat": "200 (bash) S 1 100 100 0 -1 4194304",
    }

    class FakePath(type(Path())):
        def read_text(self, *a, **k):
            try:
                return stats[str(self)]
            except KeyError:
                raise FileNotFoundError(str(self))

    monkeypatch.setattr(dab_run, "Path", FakePath)
    assert dab_run.pid_is_descendant(300, 200) is True
    assert dab_run.pid_is_descendant(200, 300) is False
    assert dab_run.pid_is_descendant(300, 999) is False


def test_main_reuses_same_worktree_host(monkeypatch, capsys):
    spawned = {}

    monkeypatch.setattr(dab_run, "listener_pid", lambda port: "777")
    monkeypatch.setattr(dab_run, "port_owner_pid", lambda port: 777)
    monkeypatch.setattr(dab_run, "host_matches_worktree", lambda pid: True)
    monkeypatch.setattr(dab_run, "verify_runtime_warehouse", lambda: ([], 10))
    monkeypatch.setattr(dab_run, "warehouse_metadata", lambda: {})
    monkeypatch.setattr(dab_run, "generate_manifest", lambda env, path: True)
    monkeypatch.setattr(dab_run, "load_env", lambda path: {})
    monkeypatch.setattr(
        dab_run,
        "boot_host",
        lambda env, log: spawned.setdefault("host", object()),
    )
    monkeypatch.setattr(dab_run, "wait_health", lambda port, host, log: {"amd": True})
    monkeypatch.setattr(dab_run, "run_eval", lambda cmd, env: 0)
    monkeypatch.setattr(dab_run, "report_results", lambda args: True)

    rc = dab_run.main(["--model", "amd:X", "--port", "8062", "--out-name", "t"])
    assert rc == 0
    assert "host" not in spawned
    assert "reusing it" in capsys.readouterr().out


def test_main_remaps_foreign_host(monkeypatch, capsys):
    owners = {8062: 555, 8063: 4242}
    seen_ports = []

    monkeypatch.setattr(dab_run, "listener_pid", lambda port: "555")
    monkeypatch.setattr(dab_run, "port_owner_pid", lambda port: owners.get(port))
    monkeypatch.setattr(dab_run, "host_matches_worktree", lambda pid: False)
    monkeypatch.setattr(dab_run, "proc_cwd", lambda pid: Path("/foreign"))
    monkeypatch.setattr(dab_run, "free_port", lambda start: 8063)
    monkeypatch.setattr(dab_run, "verify_runtime_warehouse", lambda: ([], 10))
    monkeypatch.setattr(dab_run, "warehouse_metadata", lambda: {})
    monkeypatch.setattr(dab_run, "generate_manifest", lambda env, path: True)
    monkeypatch.setattr(dab_run, "load_env", lambda path: {})

    class FakeHost:
        pid = 4242

        def poll(self):
            return None

    monkeypatch.setattr(dab_run, "boot_host", lambda env, log: FakeHost())

    def fake_health(port, host, log):
        seen_ports.append(port)
        return {"amd": True}

    monkeypatch.setattr(dab_run, "wait_health", fake_health)
    monkeypatch.setattr(dab_run, "pid_is_descendant", lambda pid, anc: False)

    def fake_eval(cmd, env):
        assert "http://127.0.0.1:8063" in cmd
        return 0

    monkeypatch.setattr(dab_run, "run_eval", fake_eval)
    monkeypatch.setattr(dab_run, "report_results", lambda args: True)
    monkeypatch.setattr(dab_run, "terminate_host", lambda host, keep: None)

    rc = dab_run.main(["--model", "amd:X", "--port", "8062", "--out-name", "t"])
    assert rc == 0
    assert seen_ports == [8063]


def test_main_refuses_foreign_owner_after_health(monkeypatch, capsys):
    monkeypatch.setattr(dab_run, "listener_pid", lambda port: None)
    monkeypatch.setattr(dab_run, "verify_runtime_warehouse", lambda: ([], 10))
    monkeypatch.setattr(dab_run, "warehouse_metadata", lambda: {})
    monkeypatch.setattr(dab_run, "generate_manifest", lambda env, path: True)
    monkeypatch.setattr(dab_run, "load_env", lambda path: {})

    class FakeHost:
        pid = 4242

        def poll(self):
            return None

        def terminate(self):
            pass

        def wait(self, timeout=None):
            return 0

    monkeypatch.setattr(dab_run, "boot_host", lambda env, log: FakeHost())
    monkeypatch.setattr(dab_run, "wait_health", lambda port, host, log: {"amd": True})
    monkeypatch.setattr(dab_run, "port_owner_pid", lambda port: 999)
    monkeypatch.setattr(dab_run, "proc_cwd", lambda pid: Path("/foreign/wt"))
    monkeypatch.setattr(dab_run, "pid_is_descendant", lambda pid, anc: False)

    rc = dab_run.main(["--model", "amd:X", "--port", "8062", "--out-name", "t"])
    assert rc == 1
    assert "refusing to evaluate" in capsys.readouterr().err
