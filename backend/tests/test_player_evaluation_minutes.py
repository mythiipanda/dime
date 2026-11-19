import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import polars as pl

from shared import tools
from shared.sources.base import FetchMeta, FetchResult
from shared.tools import league
from shared.tools import player as player_module

SEASON = "2025-26"


class _FakeTool:
    def __init__(self, out):
        self.out = out

    def invoke(self, args):
        return self.out


def _run_evaluation(monkeypatch, gp, total_min, pie_rank=1000,
                    usage_rank=1000, ts_rank=1000):
    monkeypatch.setattr(player_module, "_read_df", lambda *a, **k: [])
    monkeypatch.setattr(player_module.store, "save_frame",
                        lambda *a, **k: 0)
    frame = pl.DataFrame({
        "PLAYER_ID": [2544],
        "PLAYER_NAME": ["Synthetic Probe"],
        "TEAM_ABBREVIATION": ["SYN"],
        "GP": [gp],
        "MIN": [float(total_min)],
        "USG_PCT": [0.30],
        "TS_PCT": [0.58],
        "EFG_PCT": [0.55],
        "AST_PCT": [0.20],
        "TM_TOV_PCT": [0.10],
        "PIE": [0.12],
        "OFF_RATING": [110.0],
        "DEF_RATING": [108.0],
        "NET_RATING": [2.0],
        "USG_PCT_RANK": [usage_rank],
        "TS_PCT_RANK": [ts_rank],
        "PIE_RANK": [pie_rank],
        "NET_RATING_RANK": [1000],
    })
    fake_res = FetchResult(
        frame=frame,
        meta=FetchMeta(source="fake_endpoint_synthetic", season=SEASON),
        ok=True,
        error="",
    )
    monkeypatch.setattr(player_module.nba_stats, "player_advanced",
                        lambda season: fake_res)
    monkeypatch.setattr(
        league, "get_contract_value",
        _FakeTool({"tool": "get_contract_value", "ok": True,
                   "rows": [], "meta": {}}))
    monkeypatch.setattr(
        player_module, "get_comps",
        _FakeTool({"tool": "get_comps", "ok": True,
                   "rows": [], "meta": {}}))
    return tools.get_player_evaluation.invoke(
        {"player": 2544, "season": SEASON})


def test_totals_min_converted_to_mpg(monkeypatch):
    res = _run_evaluation(monkeypatch, gp=40, total_min=400)
    assert res["ok"] is True
    rows = res["rows"]
    assert rows["profile"]["minutes"] == pytest.approx(10.0)
    assert rows["tier"] == "role player"


def test_exact_25_mpg_boundary_is_starter(monkeypatch):
    res = _run_evaluation(monkeypatch, gp=40, total_min=1000)
    assert res["ok"] is True
    rows = res["rows"]
    assert rows["profile"]["minutes"] == pytest.approx(25.0)
    assert rows["tier"] == "starter"


def test_just_below_25_mpg_is_role_player(monkeypatch):
    res = _run_evaluation(monkeypatch, gp=40, total_min=999)
    assert res["ok"] is True
    rows = res["rows"]
    assert rows["profile"]["minutes"] == pytest.approx(24.975)
    assert rows["tier"] == "role player"


def test_25_mpg_with_under_20_gp_is_role_player(monkeypatch):
    res = _run_evaluation(monkeypatch, gp=19, total_min=475)
    assert res["ok"] is True
    rows = res["rows"]
    assert rows["profile"]["minutes"] == pytest.approx(25.0)
    assert rows["tier"] == "role player"


def test_zero_gp_no_division_error(monkeypatch):
    res = _run_evaluation(monkeypatch, gp=0, total_min=0)
    assert res["ok"] is True
    rows = res["rows"]
    assert rows["profile"]["minutes"] == 0.0
    assert rows["tier"] == "role player"


def test_star_tier_unaffected_by_minutes_unit(monkeypatch):
    res = _run_evaluation(monkeypatch, gp=45, total_min=900,
                          pie_rank=10, usage_rank=30)
    assert res["ok"] is True
    assert res["rows"]["tier"] == "star"
