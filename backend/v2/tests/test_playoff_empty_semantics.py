from types import SimpleNamespace


def test_playoffs_does_not_convert_missing_source_to_zero(monkeypatch):
    from app.tools import league

    monkeypatch.setattr(
        league, "_warehouse_or_live",
        lambda *args, **kwargs: ([], {"source": "warehouse",
                                     "error": "no seeded rows"}),
    )
    result = league.get_playoffs.invoke({"season": "2024-25"})
    assert result == {"tool": "get_playoffs", "ok": False,
                      "error": "no seeded rows"}


def test_playoffs_preserves_verified_empty_population(monkeypatch):
    from app.tools import league

    monkeypatch.setattr(
        league, "_warehouse_or_live",
        lambda *args, **kwargs: ([], {"source": "fixture", "rows": 0}),
    )
    result = league.get_playoffs.invoke({"season": "2025-26"})
    assert result["ok"] is True
    assert result["rows"]["games_total"] == 0
