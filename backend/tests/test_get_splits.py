
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.tools import _core, player


def _row(date, pts):
    return {"GAME_DATE": date, "MATCHUP": "AAA vs. BBB", "WL": "W",
            "PTS": pts, "FG_PCT": 0.5, "REB": 5, "AST": 5}


def _long(day):
    return f"Jan {day:02d}, 2026"


def _iso(day):
    return f"2026-01-{day:02d}"


def _run(monkeypatch, rows):
    monkeypatch.setattr(_core, "last_completed_season", lambda: "2025-26")
    monkeypatch.setattr(player, "_opp_tier_splits", lambda frame, season: [])
    monkeypatch.setattr(
        player, "_warehouse_or_live",
        lambda *a, **k: (list(rows),
                         {"source": "synthetic",
                          "fetched_at": "2026-01-01T00:00:00",
                          "rows": len(rows)}))
    return player.get_splits.invoke({"player_id": 123, "season": "2025-26"})


def _last10(res):
    assert res["ok"] is True
    for r in res["rows"]:
        if r.get("split") == "last10":
            return r
    raise AssertionError("missing last10 split")


def _assert_last10(res, ppg, gp=10):
    row = _last10(res)
    assert row["GP"] == gp
    assert row["PPG"] == ppg


def test_iso_ascending_selects_most_recent(monkeypatch):
    rows = [_row(_iso(d), d * 10) for d in range(1, 13)]
    _assert_last10(_run(monkeypatch, rows), 75.0)


def test_iso_descending_selects_most_recent(monkeypatch):
    rows = [_row(_iso(d), d * 10) for d in range(12, 0, -1)]
    _assert_last10(_run(monkeypatch, rows), 75.0)


def test_long_ascending_parity(monkeypatch):
    rows = [_row(_long(d), d * 10) for d in range(1, 13)]
    _assert_last10(_run(monkeypatch, rows), 75.0)


def test_mixed_permuted_selects_most_recent(monkeypatch):
    seen = set()
    order = [7, 2, 12, 1, 9, 4, 11, 3, 10, 5, 8, 6]
    rows = []
    for d in order:
        seen.add(d)
        rows.append(_row(_iso(d) if d % 2 else _long(d), d * 10))
    assert len(seen) == 12
    _assert_last10(_run(monkeypatch, rows), 75.0)


def test_mixed_iso_old_long_new_selects_most_recent(monkeypatch):
    rows = ([_row(_iso(1), 10), _row(_iso(2), 20)]
            + [_row(_long(d), d * 10) for d in range(3, 13)])
    _assert_last10(_run(monkeypatch, rows), 75.0)


def test_fewer_than_ten_rows_uses_all(monkeypatch):
    rows = [_row(_iso(d), d * 10) for d in range(1, 6)]
    _assert_last10(_run(monkeypatch, rows), 30.0, gp=5)


def test_empty_rows_returns_error(monkeypatch):
    res = _run(monkeypatch, [])
    assert res["ok"] is False
    assert "error" in res


def test_malformed_preserves_baseline(monkeypatch):
    rows = ([_row(_long(d), d * 10) for d in range(1, 11)]
            + [_row("not-a-date", 99), _row(_long(11), 110),
               _row(_long(12), 120)])
    _assert_last10(_run(monkeypatch, rows), 81.9)


def test_null_preserves_baseline(monkeypatch):
    rows = ([_row(_long(d), d * 10) for d in range(1, 11)]
            + [_row(None, 88), _row(_long(11), 110),
               _row(_long(12), 120)])
    _assert_last10(_run(monkeypatch, rows), 80.8)
