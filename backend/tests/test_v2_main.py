import pytest

def _stub_shared(monkeypatch, store_stub=None, **module_stubs):
    import sys
    import types

    shared = types.ModuleType("shared")
    if store_stub is not None:
        shared.store = store_stub
    monkeypatch.setitem(sys.modules, "shared", shared)
    for name, mod in module_stubs.items():
        monkeypatch.setitem(sys.modules, f"shared.{name}", mod)
    return shared

def _stub_store(**fns):
    import types

    return types.SimpleNamespace(**fns)

def test_v2_datasets_freshness_ttl_cache(monkeypatch):
    from analyst import dataset_engine as routes

    calls = []

    def fake_payload():
        calls.append(1)
        return {"ok": True, "rows": []}

    monkeypatch.setattr(routes, "_datasets_freshness_payload", fake_payload)
    routes._DATASETS_FRESHNESS_CACHE.update(at=0.0, payload=None)
    try:
        first = routes.datasets_freshness()
        second = routes.datasets_freshness()
        assert first == {"ok": True, "rows": []}
        assert second is first
        assert len(calls) == 1
    finally:
        routes._DATASETS_FRESHNESS_CACHE.update(at=0.0, payload=None)

def test_v2_dataset_unknown_name():
    from analyst.dataset_engine import dataset as dataset_view

    out = dataset_view("bogus")
    assert out["ok"] is False
    assert "unknown dataset" in out["error"]
    assert "standings" in out["error"]

def test_v2_dataset_wowy_path(monkeypatch):
    import types

    def fake_invoke(payload):
        assert payload["player_a"] == "LeBron James"
        assert payload["team_id"] == 14
        return {"ok": True, "rows": [{"x": 1}], "verdict": "v", "meta": {"m": 1}}

    player_mod = types.ModuleType("shared.tools.player")
    player_mod.get_wowy = types.SimpleNamespace(invoke=fake_invoke)
    tools_mod = types.ModuleType("shared.tools")
    _stub_shared(monkeypatch, **{"tools": tools_mod, "tools.player": player_mod})

    from analyst.dataset_engine import dataset as dataset_view

    out = dataset_view("wowy", player_a="LeBron James", team_id=14)
    assert out["ok"] is True
    assert out["data"] == [{"x": 1}]
    assert out["verdict"] == "v"
