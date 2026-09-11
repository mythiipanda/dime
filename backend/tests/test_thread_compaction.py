"""Thread compaction: long threads fold into one summary memo row."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import providers as providers_mod
from app import store


class _FakeLLM:
    def __init__(self, calls, fail=False):
        self._calls = calls
        self._fail = fail

    def invoke(self, messages):
        if self._fail:
            raise RuntimeError("llm down")
        prompt = ""
        try:
            prompt = str(messages[-1].content)
        except Exception:
            prompt = ""
        self._calls.append(prompt)
        return type("Resp", (), {"content": "MEMO :: " + prompt})()


def _isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "thread.duckdb")
    monkeypatch.setattr(store, "LOCK_PATH", tmp_path / ".write.lock")


def _seed(thread, n):
    for i in range(n):
        role = "human" if i % 2 == 0 else "ai"
        store.save_chat(thread, role, f"turn-{i} asks about Player{i}")


def _rows(thread):
    con = store.connect()
    try:
        return con.execute(
            """SELECT role, text FROM chat_history
            WHERE thread = ? ORDER BY created_at, rowid""",
            [thread],
        ).fetchall()
    finally:
        con.close()


def _fake_provider(monkeypatch, calls, fail=False):
    monkeypatch.setattr(
        providers_mod, "get_llm", lambda primary, model=None: _FakeLLM(calls, fail))


def test_below_threshold_untouched(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _fake_provider(monkeypatch, [])
    _seed("t1", 11)
    out = store.compact_thread("t1")
    assert out == {"compacted": False, "kept": 11, "dropped": 0}
    assert len(_rows("t1")) == 11


def test_compacts_to_summary_plus_recent(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    calls: list = []
    _fake_provider(monkeypatch, calls)
    _seed("t2", 13)
    out = store.compact_thread("t2")
    assert out == {"compacted": True, "kept": 4, "dropped": 9}
    rows = _rows("t2")
    assert len(rows) == 5
    assert rows[-1][0] == "summary"
    assert rows[-1][1].startswith("THREAD SUMMARY: ")
    assert "turn-0" in rows[-1][1]
    assert [r[1] for r in rows[:-1]] == [
        f"turn-{i} asks about Player{i}" for i in (9, 10, 11, 12)]
    assert len(calls) == 1


def test_second_compact_preserves_old_memo(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _fake_provider(monkeypatch, [])
    _seed("t3", 13)
    first = store.compact_thread("t3")
    assert first["compacted"] is True
    memo1 = _rows("t3")[-1][1]
    assert "turn-0" in memo1
    for i in range(13, 23):
        store.save_chat("t3", "human" if i % 2 else "ai",
                        f"turn-{i} asks about Player{i}")
    second = store.compact_thread("t3")
    assert second["compacted"] is True
    rows = _rows("t3")
    assert len(rows) == 5
    summaries = [r for r in rows if r[0] == "summary"]
    assert len(summaries) == 1
    assert "turn-0" in summaries[0][1]
    assert "turn-13" in summaries[0][1]


def test_llm_failure_leaves_history_untouched(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _fake_provider(monkeypatch, [], fail=True)
    _seed("t4", 13)
    out = store.compact_thread("t4")
    assert out == {"compacted": False, "kept": 13, "dropped": 0}
    assert len(_rows("t4")) == 13
