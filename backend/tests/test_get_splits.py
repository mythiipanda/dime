
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


_NON_MONTHLY = {"home", "away", "wins", "losses", "last10", "starter", "bench"}

_MONTH_FACTS = [
    ("Aug 05, 2026", "2026-08-05", 10),
    ("Aug 10, 2026", "2026-08-10", 20),
    ("Aug 15, 2026", "2026-08-15", 30),
    ("Sep 05, 2026", "2026-09-05", 40),
    ("Sep 10, 2026", "2026-09-10", 50),
]

_MONTH_EXPECTED = [
    {"split": "Aug", "GP": 3, "PPG": 20.0, "FG_PCT": 0.5},
    {"split": "Sep", "GP": 2, "PPG": 45.0, "FG_PCT": 0.5},
]


def _monthly(res):
    assert res["ok"] is True
    return [r for r in res["rows"] if r.get("split") not in _NON_MONTHLY]


def test_monthly_iso_matches_long_control(monkeypatch):
    long_res = _run(monkeypatch, [_row(l, p) for l, _i, p in _MONTH_FACTS])
    iso_res = _run(monkeypatch, [_row(i, p) for _l, i, p in _MONTH_FACTS])
    assert _monthly(long_res) == _MONTH_EXPECTED
    assert _monthly(iso_res) == _MONTH_EXPECTED
    assert iso_res == long_res


def test_monthly_mixed_matches_long_control(monkeypatch):
    long_res = _run(monkeypatch, [_row(l, p) for l, _i, p in _MONTH_FACTS])
    mixed_res = _run(monkeypatch, [
        _row(l if k % 2 == 0 else i, p)
        for k, (l, i, p) in enumerate(_MONTH_FACTS)])
    assert _monthly(mixed_res) == _MONTH_EXPECTED
    assert mixed_res == long_res


def test_monthly_yearless_long_across_years(monkeypatch):
    rows = [_row("Aug 05, 2025", 10), _row("Aug 05, 2026", 30)]
    assert _monthly(_run(monkeypatch, rows)) == [
        {"split": "Aug", "GP": 2, "PPG": 20.0, "FG_PCT": 0.5}]


def test_monthly_null_malformed_fallback_matches_direct_helper_without_d(monkeypatch):
    import polars as pl

    rows = [_row("Aug 05, 2026", 10), _row("Aug 10, 2026", 20),
            _row("Foo 99, 9999", 40), _row(None, 99)]
    public_monthly = _monthly(_run(monkeypatch, rows))
    direct_monthly = player._monthly_splits(pl.DataFrame(rows))
    key = lambda r: str(r.get("split"))
    assert sorted(public_monthly, key=key) == sorted(direct_monthly, key=key)
    assert {"split": "Aug", "GP": 2, "PPG": 15.0, "FG_PCT": 0.5} in public_monthly
    assert {"split": "Foo", "GP": 1, "PPG": 40.0, "FG_PCT": 0.5} in public_monthly


def test_monthly_cap12_remains_and_iso_matches_long(monkeypatch):
    abbr = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct"]
    long_rows = [_row(f"{abbr[m - 1]} 05, 2026", m * 10) for m in range(1, 11)]
    iso_rows = [_row(f"2026-{m:02d}-05", m * 10) for m in range(1, 11)]
    long_res = _run(monkeypatch, long_rows)
    iso_res = _run(monkeypatch, iso_rows)
    assert len(long_res["rows"]) == 12
    assert len(iso_res["rows"]) == 12
    assert [r["split"] for r in _monthly(iso_res)] == abbr[:9]
    assert iso_res == long_res
