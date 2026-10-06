import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.tools.lineup import get_lineup_stats
from shared.tools.player import get_on_off, get_wowy
from shared.tools.team import get_lineups

BOS = 1610612738
TATUM = 1628369
BROWN = 1627759
SEASON = "2022-23"
TOP_UNIT = "A. Horford - M. Smart - J. Brown - J. Tatum - D. White"
TOP_MIN = 432.4

def test_get_lineup_stats_hist_season_returns_rows():
    res = get_lineup_stats.invoke(
        {"team": "BOS", "season": SEASON, "min_possessions": 100})
    assert res["ok"] is True
    assert len(res["rows"]) > 0
    assert res["best_net_unit"] is not None
    assert res["meta"].get("coverage") == "historical_lineups"

def test_get_lineup_stats_hist_floor_hides_everything_when_absurd():
    res = get_lineup_stats.invoke(
        {"team": "BOS", "season": SEASON, "min_possessions": 100000})
    assert res["ok"] is True
    assert res["rows"] == []
    assert "hidden" in res["meta"].get("data_note", "")

def test_get_lineup_stats_hist_uses_real_minutes_without_play_data(monkeypatch):
    import shared.tools.lineup as _lineup

    fixture = [{"GROUP_ID": "1-2-3-4-5", "GROUP_NAME": "starters",
                "GP": 35, "MIN": 432.4, "PTS": 1138.0, "PLUS_MINUS": 103.0,
                "FGA": 801.0, "OREB": 57.0, "TOV": 98.0, "FTA": 187.0,
                "TEAM_ID": BOS, "TEAM_ABBREVIATION": "BOS"}]
    monkeypatch.setattr(_lineup, "_warehouse_or_live",
                        lambda *a, **k: ([], {"source": "warehouse"}))
    monkeypatch.setattr(_lineup, "_possession_aggs", lambda *a: None)
    import shared.tools.team as _team
    monkeypatch.setattr(_team, "_hist_lineup_rows", lambda *a: list(fixture))
    res = get_lineup_stats.invoke(
        {"team": "BOS", "season": SEASON, "min_possessions": 10})
    assert res["ok"] is True
    assert res["rows"][0]["EST_MIN"] == 432.4
    assert any("estimated-possessions" in f
               for f in res["rows"][0]["flags"])
    assert "clock minutes" in res["meta"].get("data_note", "")

def test_get_lineups_hist_season_returns_rows_sorted_by_min():
    res = get_lineups.invoke({"team_id": "BOS", "season": SEASON})
    assert res["ok"] is True
    assert len(res["rows"]) > 10
    assert res["rows"][0]["GROUP_NAME"] == TOP_UNIT
    assert round(float(res["rows"][0]["MIN"]), 1) == TOP_MIN
    assert res["rows"][0]["SAMPLE_TIER"] == "large"
    mins = [float(r.get("MIN") or 0) for r in res["rows"]]
    assert mins == sorted(mins, reverse=True)

def test_get_wowy_hist_season_uses_real_minutes():
    res = get_wowy.invoke({"player_a": str(TATUM), "player_b": str(BROWN),
                           "team_id": "BOS", "season": SEASON})
    assert res["ok"] is True
    both = next(r for r in res["rows"] if r["split"] == "Both ON")
    assert both["minutes"] == 1433.6
    assert res["meta"].get("source") == "silver_hist_lineups"

def test_get_on_off_hist_season_returns_rows():
    res = get_on_off.invoke({"player_id": str(TATUM),
                             "team_id": "BOS", "season": SEASON})
    assert res["ok"] is True
    stats = [r["Stat"] for r in res["rows"]]
    assert "Net Rating" in stats

def test_get_lineup_stats_current_season_still_serves_warehouse():
    res = get_lineup_stats.invoke({"team": "BOS", "season": "2025-26"})
    assert res["ok"] is True
    assert len(res["rows"]) > 0
    assert res["meta"].get("coverage") != "historical_lineups"
