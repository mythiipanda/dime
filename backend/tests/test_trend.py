
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.tools import _core, player

DECAY = 0.94
WINDOW = 20


def _dates(n):
    start = date(2026, 1, 1)
    return [f"{(start + timedelta(days=i)):%b} {(start + timedelta(days=i)).day}, 2026"
            for i in range(n)]


def _rows(pts):
    return [{"GAME_DATE": d, "PTS": p} for d, p in zip(_dates(len(pts)), pts)]


def _expected(pts):
    recent = pts[-WINDOW:]
    weights = [DECAY ** (len(recent) - 1 - j) for j in range(len(recent))]
    form = sum(p * w for p, w in zip(recent, weights)) / sum(weights)
    base = sum(pts) / len(pts)
    direction = "up" if form > base + 1 else (
        "down" if form < base - 1 else "flat")
    return form, base, direction


def _run(monkeypatch, pts, reverse=False):
    rows = _rows(pts)
    if reverse:
        rows = list(reversed(rows))
    monkeypatch.setattr(_core, "last_completed_season", lambda: "2025-26")
    monkeypatch.setattr(
        player, "_warehouse_or_live",
        lambda *a, **k: (list(rows), {"source": "synthetic"}))
    return player.get_trend.invoke(
        {"player_id": 123, "season": "2025-26"})


def _assert_trend(res, pts):
    form, base, direction = _expected(pts)
    dates = _dates(len(pts))
    recent_dates = dates[-WINDOW:]
    assert res["ok"] is True
    out = res["rows"]
    assert out["games"] == len(pts)
    assert out["season_ppg"] == round(base, 1)
    assert out["form_ppg"] == round(form, 1)
    assert out["delta"] == round(form - base, 1)
    assert out["direction"] == direction
    assert out["form_games"] == len(recent_dates)
    assert out["form_from"] == recent_dates[0]
    assert out["log_from"] == dates[0]
    assert out["log_to"] == dates[-1]


def test_trend_hot_newest_weighted(monkeypatch):
    pts = [10] * 23 + [30, 30]
    res = _run(monkeypatch, pts)
    _assert_trend(res, pts)
    assert res["rows"]["season_ppg"] == 11.6
    assert res["rows"]["form_ppg"] == 13.3
    assert res["rows"]["direction"] == "up"


def test_trend_cold_newest_weighted(monkeypatch):
    pts = [30] * 23 + [10, 10]
    res = _run(monkeypatch, pts)
    _assert_trend(res, pts)
    assert res["rows"]["direction"] == "down"


def test_trend_constant(monkeypatch):
    pts = [20] * 12
    res = _run(monkeypatch, pts)
    _assert_trend(res, pts)
    assert res["rows"]["form_ppg"] == 20.0
    assert res["rows"]["delta"] == 0.0
    assert res["rows"]["direction"] == "flat"


def test_trend_five_game_boundary(monkeypatch):
    pts = [10, 10, 10, 10, 30]
    res = _run(monkeypatch, pts)
    _assert_trend(res, pts)
    assert res["rows"]["form_games"] == 5


def test_trend_twenty_game_boundary(monkeypatch):
    pts = [10] * 19 + [30]
    res = _run(monkeypatch, pts)
    _assert_trend(res, pts)
    assert res["rows"]["form_games"] == 20


def test_trend_over_twenty_window(monkeypatch):
    pts = [10] * 19 + [30, 30]
    res = _run(monkeypatch, pts)
    _assert_trend(res, pts)
    assert res["rows"]["games"] == 21
    assert res["rows"]["form_games"] == 20


def test_trend_ordering_ignores_input_order(monkeypatch):
    pts = [10] * 23 + [30, 30]
    forward = _run(monkeypatch, pts)
    reversed_res = _run(monkeypatch, pts, reverse=True)
    assert reversed_res["rows"] == forward["rows"]
