import asyncio
import sys
import types


def _op(name):
    from analyst import direct_data
    return getattr(direct_data, name)


def test_stamp_ok_adds_ok_to_bare_payloads():
    from analyst.direct_data import _stamp_ok
    assert _stamp_ok({"threads": []}) == {"threads": [], "ok": True}


def test_stamp_ok_preserves_explicit_failure():
    from analyst.direct_data import _stamp_ok
    failure = {"ok": False, "error": "boom"}
    assert _stamp_ok(dict(failure))["ok"] is False


def test_threads_and_runs_stamp_ok(monkeypatch):
    from shared import store
    monkeypatch.setattr(store, "list_threads", lambda owner="": [{"thread": "t1", "title": "x"}])
    monkeypatch.setattr(store, "list_runs", lambda thread, owner="": [])
    threads = _op("product_threads").invoke({"owner": "o"})
    assert threads["ok"] is True
    assert threads["threads"] == [{"thread": "t1", "title": "x"}]
    runs = _op("product_runs").invoke({"thread": "t", "owner": "o"})
    assert runs["ok"] is True
    assert runs["runs"] == []


def test_warehouse_identity_stamps_ok(monkeypatch):
    from shared import store

    class _Identity(dict):
        pass

    monkeypatch.setattr(store, "warehouse_identity", lambda: {"warehouse_id": "w", "warehouse_sha256": "s"})
    res = _op("product_warehouse_identity").invoke({})
    assert res["ok"] is True
    assert res["warehouse"]["warehouse_id"] == "w"


def test_delegate_wrapped_ops_stamp_ok(monkeypatch):
    import analyst.boards as boards
    import analyst.dataset_engine as engine
    monkeypatch.setattr(boards, "metrics", lambda: {"metrics": ["x"]})
    monkeypatch.setattr(engine, "home_snapshot", lambda: {"games": []})
    sys.modules.setdefault("analyst.boards", boards)
    res = _op("product_board_metrics").invoke({})
    assert res["ok"] is True
    home = _op("product_home").invoke({})
    assert home["ok"] is True


def test_delegate_failure_shape_survives_wrapping(monkeypatch):
    import analyst.boards as boards
    monkeypatch.setattr(boards, "fill", lambda payload: {"ok": False, "error": "bad board"})
    res = _op("product_board_fill").invoke({"payload": {}})
    assert res["ok"] is False
    assert res["error"] == "bad board"
