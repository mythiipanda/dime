import sys
from pathlib import Path

import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.tools.transactions import get_transactions


TXN_ROWS = [
    {
        "txn_date": "2025-07-02",
        "txn_type": "Signing",
        "player": "wayne-bruce",
        "player_id": 999000,
        "team": "LAL",
        "team_id": 1610612747,
        "detail": "Signed F Bruce Wayne",
    },
    {
        "txn_date": "2025-07-10",
        "txn_type": "Waive",
        "player": "doe-john",
        "player_id": 999001,
        "team": "LAL",
        "team_id": 1610612747,
        "detail": "Waived G John Doe",
    },
    {
        "txn_date": "2025-08-01",
        "txn_type": "Trade",
        "player": "smith-jane",
        "player_id": 999002,
        "team": "BOS",
        "team_id": 1610612738,
        "detail": "Acquired F Jane Smith",
    },
    {
        "txn_date": "2024-07-05",
        "txn_type": "Signing",
        "player": "roe-richard",
        "player_id": 999003,
        "team": "LAL",
        "team_id": 1610612747,
        "detail": "Signed C Richard Roe",
    },
]


def _frame(monkeypatch, rows=None):
    from shared import store

    data = TXN_ROWS if rows is None else rows
    frame = pl.DataFrame(data, strict=False)
    monkeypatch.setattr(store, "read_frame", lambda *a, **k: frame)
    monkeypatch.setattr(store, "warehouse_identity", lambda: {})


def _seasons(monkeypatch, seasons):
    import v2.adapters.coverage as coverage

    monkeypatch.setattr(coverage, "table_seasons", lambda *a, **k: set(seasons))


def test_shape_and_team_filter_orders_desc(monkeypatch):
    _frame(monkeypatch)
    _seasons(monkeypatch, {"2024-25", "2025-26"})
    out = get_transactions.invoke({"team": "LAL"})
    assert out["tool"] == "get_transactions"
    assert out["ok"] is True
    assert "error" not in out
    assert {k for k in ("tool", "ok", "rows", "meta")} <= set(out)
    assert len(out["rows"]) == 3
    dates = [r["txn_date"] for r in out["rows"]]
    assert dates == ["2025-07-10", "2025-07-02", "2024-07-05"]
    for row in out["rows"]:
        assert set(row) >= {"txn_date", "txn_type", "player", "player_id", "team", "team_id", "detail"}
        assert row["team"] == "LAL"
    assert out["meta"]["source"] == "warehouse:silver_transactions"


def test_date_range_filters_lexically(monkeypatch):
    _frame(monkeypatch)
    _seasons(monkeypatch, {"2024-25", "2025-26"})
    out = get_transactions.invoke({"team": "LAL", "start": "2025-07-05", "end": "2025-07-31"})
    assert out["ok"] is True
    assert [r["txn_date"] for r in out["rows"]] == ["2025-07-10"]
    assert out["meta"]["start"] == "2025-07-05"
    assert out["meta"]["end"] == "2025-07-31"


def test_txn_type_filter_and_unknown_names_valid(monkeypatch):
    _frame(monkeypatch)
    _seasons(monkeypatch, {"2024-25", "2025-26"})
    out = get_transactions.invoke({"txn_type": "waive"})
    assert out["ok"] is True
    assert len(out["rows"]) == 1
    assert out["rows"][0]["txn_type"] == "Waive"
    bad = get_transactions.invoke({"txn_type": "Release"})
    assert bad["ok"] is False
    assert bad["rows"] == []
    for name in ("Signing", "Waive", "Trade", "ContractConverted", "AwardOnWaivers"):
        assert name in bad["error"]


def test_unknown_team_refusal(monkeypatch):
    _frame(monkeypatch)
    _seasons(monkeypatch, {"2024-25", "2025-26"})
    out = get_transactions.invoke({"team": "ZZZ"})
    assert out["ok"] is False
    assert out["rows"] == []
    assert "unknown team: ZZZ" in out["error"]


def test_no_coverage_refusal_names_seasons(monkeypatch):
    _frame(monkeypatch)
    _seasons(monkeypatch, {"2024-25", "2025-26"})
    out = get_transactions.invoke({"start": "2020-01-01", "end": "2020-02-01"})
    assert out["ok"] is False
    assert out["rows"] == []
    assert "2024-25" in out["error"]
    assert "2025-26" in out["error"]
    assert out["meta"]["available_seasons"] == ["2024-25", "2025-26"]


def test_tool_registered():
    from shared import tools

    assert "get_transactions" in tools.TOOL_NAMES
