
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.tools import _core, player


def _run(monkeypatch, rows, n=3):
    monkeypatch.setattr(_core, "last_completed_season", lambda: "2025-26")
    monkeypatch.setattr(
        player, "_warehouse_or_live",
        lambda *a, **k: (list(rows), {"source": "synthetic"}))
    return player.get_last_x.invoke(
        {"player_id": 123, "n": n, "season": "2025-26"})


def _iso_rows(days=(1, 2, 3, 4, 5), reverse=False):
    start = date(2026, 1, 1)
    rows = [{"GAME_DATE": (start + timedelta(days=d - 1)).isoformat(),
             "MATCHUP": "AAA vs. BBB", "PTS": d * 10}
            for d in days]
    return list(reversed(rows)) if reverse else rows


def _long_rows(days=(1, 2, 3, 4, 5), reverse=False):
    start = date(2026, 1, 1)
    rows = [{"GAME_DATE": (start + timedelta(days=d - 1)).strftime("%b %d, %Y"),
             "MATCHUP": "AAA vs. BBB", "PTS": d * 10}
            for d in days]
    return list(reversed(rows)) if reverse else rows


def _assert_recent(res, dates, pts):
    assert res["ok"] is True
    out = res["rows"]
    assert [r["GAME_DATE"] for r in out] == dates
    assert [r["PTS"] for r in out] == pts
    assert sum(r["PTS"] for r in out) == sum(pts)
    assert all("_d" not in r for r in out)


def test_iso_descending_selects_most_recent(monkeypatch):
    res = _run(monkeypatch, _iso_rows(reverse=True), n=3)
    _assert_recent(res, ["2026-01-05", "2026-01-04", "2026-01-03"], [50, 40, 30])
    assert sum(r["PTS"] for r in res["rows"]) == 120


def test_iso_ascending_selects_most_recent(monkeypatch):
    res = _run(monkeypatch, _iso_rows(), n=3)
    _assert_recent(res, ["2026-01-05", "2026-01-04", "2026-01-03"], [50, 40, 30])


def test_long_descending_selects_most_recent(monkeypatch):
    res = _run(monkeypatch, _long_rows(reverse=True), n=3)
    _assert_recent(res, ["Jan 05, 2026", "Jan 04, 2026", "Jan 03, 2026"], [50, 40, 30])


def test_long_ascending_selects_most_recent(monkeypatch):
    res = _run(monkeypatch, _long_rows(), n=3)
    _assert_recent(res, ["Jan 05, 2026", "Jan 04, 2026", "Jan 03, 2026"], [50, 40, 30])


def test_mixed_permuted_selects_most_recent(monkeypatch):
    rows = [
        {"GAME_DATE": "2026-01-02", "MATCHUP": "AAA vs. BBB", "PTS": 20},
        {"GAME_DATE": "Jan 05, 2026", "MATCHUP": "AAA vs. BBB", "PTS": 50},
        {"GAME_DATE": "2026-01-01", "MATCHUP": "AAA vs. BBB", "PTS": 10},
        {"GAME_DATE": "Jan 04, 2026", "MATCHUP": "AAA vs. BBB", "PTS": 40},
        {"GAME_DATE": "2026-01-03", "MATCHUP": "AAA vs. BBB", "PTS": 30},
    ]
    res = _run(monkeypatch, rows, n=3)
    _assert_recent(res, ["Jan 05, 2026", "Jan 04, 2026", "2026-01-03"], [50, 40, 30])
    res5 = _run(monkeypatch, rows, n=5)
    _assert_recent(res5, ["Jan 05, 2026", "Jan 04, 2026", "2026-01-03",
                          "2026-01-02", "2026-01-01"], [50, 40, 30, 20, 10])


def test_malformed_date_preserves_original_reverse_fallback(monkeypatch):
    rows = [
        {"GAME_DATE": "Jan 01, 2026", "MATCHUP": "AAA vs. BBB", "PTS": 10},
        {"GAME_DATE": "Jan 02, 2026", "MATCHUP": "AAA vs. BBB", "PTS": 20},
        {"GAME_DATE": "bad", "MATCHUP": "AAA vs. BBB", "PTS": 99},
        {"GAME_DATE": "Jan 03, 2026", "MATCHUP": "AAA vs. BBB", "PTS": 30},
        {"GAME_DATE": "Jan 04, 2026", "MATCHUP": "AAA vs. BBB", "PTS": 40},
        {"GAME_DATE": "Jan 05, 2026", "MATCHUP": "AAA vs. BBB", "PTS": 50},
    ]
    res = _run(monkeypatch, rows, n=3)
    _assert_recent(res, ["Jan 05, 2026", "Jan 04, 2026", "Jan 03, 2026"], [50, 40, 30])


def test_n_boundaries_clamp_low(monkeypatch):
    rows = _iso_rows(reverse=True)
    _assert_recent(_run(monkeypatch, rows, n=1), ["2026-01-05"], [50])
    _assert_recent(_run(monkeypatch, rows, n=0), ["2026-01-05"], [50])
    _assert_recent(_run(monkeypatch, rows, n=-4), ["2026-01-05"], [50])


def test_n_clamps_at_25_with_more_than_25_rows(monkeypatch):
    start = date(2026, 1, 1)
    rows = [{"GAME_DATE": (start + timedelta(days=d - 1)).isoformat(),
             "MATCHUP": "AAA vs. BBB", "PTS": d}
            for d in range(1, 31)]
    rows = list(reversed(rows))
    for n in (25, 100):
        res = _run(monkeypatch, rows, n=n)
        assert res["ok"] is True
        out = res["rows"]
        assert len(out) == 25
        assert out[0]["GAME_DATE"] == "2026-01-30"
        assert out[-1]["GAME_DATE"] == "2026-01-06"
        assert [r["PTS"] for r in out] == list(range(30, 5, -1))
        assert sum(r["PTS"] for r in out) == 450
