"""get_game_prediction tests. Pure math is hermetic; warehouse tests
prove the ratings/injury/schedule wiring against the real warehouse."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.tools import get_game_prediction
from app.tools.prediction import (
    STATUS_PENALTY,
    _injury_penalty,
    _simulate,
)


class _FakeCon:
    def __init__(self, tables, rows):
        self._tables = tables
        self._rows = rows

    def execute(self, query, params=None):
        q = str(query).strip().upper()
        if q.startswith("SHOW TABLES"):
            return _FakeRows([(t,) for t in self._tables])
        return _FakeRows(self._rows)


class _FakeRows:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows


def _injuries_blob(items):
    return str([{
        "id": str(i),
        "status": status,
        "athlete": {"displayName": name},
    } for i, (name, status) in enumerate(items)])


def test_sim_seed_deterministic():
    first = _simulate(115.0, 110.0, 5_000, 7)
    second = _simulate(115.0, 110.0, 5_000, 7)
    assert first == second


def test_sim_favorite_beats_underdog():
    assert _simulate(120.0, 100.0, 5_000, 7)["p_home"] > 0.6
    assert _simulate(100.0, 120.0, 5_000, 7)["p_home"] < 0.4


def test_sim_intervals_ordered_and_contain_mean():
    s = _simulate(112.0, 108.0, 5_000, 7)
    lo, hi = s["total_ci90"]
    assert lo <= s["total_mean"] <= hi
    mlo, mhi = s["margin_ci90"]
    assert mlo <= s["home_mean"] - s["away_mean"] <= mhi
    clo, chi = s["p_home_ci90"]
    assert clo <= s["p_home"] <= chi
    assert 0.0 <= clo and chi <= 1.0


def test_injury_status_weights():
    con = _FakeCon(["silver_injuries"], [
        (_injuries_blob([("Star A", "Out"), ("Role B", "Doubtful"),
                         ("Deep C", "Day-To-Day"), ("Active D", "Active")]),
         "2026-09-09T00:00:00+00:00"),
    ])
    out = _injury_penalty(con, "Test Team", "2025-26")
    expected = STATUS_PENALTY["OUT"] + STATUS_PENALTY["DOUBTFUL"] + \
        STATUS_PENALTY["DAY-TO-DAY"]
    assert out["penalty"] == round(expected, 2)
    assert [p["player"] for p in out["players"]] == \
        ["Star A", "Role B", "Deep C"]


def test_injury_penalty_capped():
    con = _FakeCon(["silver_injuries"], [
        (_injuries_blob([(f"P{i}", "Out") for i in range(6)]),
         "2026-09-09T00:00:00+00:00"),
    ])
    out = _injury_penalty(con, "Test Team", "2025-26")
    assert out["penalty"] == 3.0


def test_injury_missing_table_degrades():
    out = _injury_penalty(_FakeCon([], []), "Test Team", "2025-26")
    assert out["penalty"] == 0.0
    assert "no injury data" in out["note"]


def test_injury_unparseable_blob_degrades():
    con = _FakeCon(["silver_injuries"], [("not-a-list", None)])
    out = _injury_penalty(con, "Test Team", "2025-26")
    assert out["penalty"] == 0.0
    assert "unparseable" in out["note"]


def test_tool_unknown_team_errors():
    out = get_game_prediction.invoke({"a": "ZZZ", "b": "BOS"})
    assert out["ok"] is False
    assert "unknown team" in out["error"]


def test_tool_same_team_errors():
    out = get_game_prediction.invoke({"a": "BOS", "b": "Boston Celtics"})
    assert out["ok"] is False
    assert "different teams" in out["error"]


def test_tool_missing_ratings_degrades(monkeypatch):
    import app.tools.prediction as pred
    monkeypatch.setattr(pred, "_rating_row", lambda con, tid, season: None)
    out = get_game_prediction.invoke({"a": "BOS", "b": "NYK", "n_sims": 1_000})
    assert out["ok"] is False
    assert "ratings missing" in out["error"]


def test_tool_warehouse_integration():
    out = get_game_prediction.invoke(
        {"a": "BOS", "b": "NYK", "n_sims": 5_000, "seed": 7})
    assert out["ok"] is True
    est = out["estimate"]
    probs = est["win_prob"]
    assert abs(sum(probs.values()) - 1.0) < 0.01
    lo, hi = est["total_ci90"]
    assert lo <= est["projected_total"] <= hi
    assert out["methodology"] and out["limitations"]
    assert any("not betting picks" in line for line in out["limitations"])
    assert out["inputs"]["n_sims"] == 5_000
    assert out["inputs"]["seed"] == 7
    assert out["matchup"]["home"] in probs and out["matchup"]["away"] in probs


def test_tool_seed_deterministic_through_warehouse():
    args = {"a": "LAL", "b": "GSW", "n_sims": 5_000, "seed": 42}
    first = get_game_prediction.invoke(args)
    second = get_game_prediction.invoke(args)
    assert first["ok"] is True and second["ok"] is True
    assert first["estimate"] == second["estimate"]
