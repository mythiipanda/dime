import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import polars as pl

from app import datasets as _ds
from shared import store as _store
from shared.tools.zone import zone_of

_LABEL_BY_KEY = {
    "rim": "Rim (<8 ft)",
    "corner_3": "Corner 3",
    "atb_3": "Above-Break 3",
    "short_mid": "Short Mid (8-14 ft)",
    "long_mid": "Long Mid (14 ft+)",
}


def _lu(gid, team, name, pts, pm, fga, oreb, tov, fta, mn):
    return {
        "GROUP_ID": gid, "GROUP_NAME": name, "TEAM_ABBREVIATION": team,
        "PTS": pts, "PLUS_MINUS": pm, "FGA": fga, "OREB": oreb,
        "TOV": tov, "FTA": fta, "MIN": mn,
    }


def _fake_reader(frames):
    def fake(table, where=None, params=None):
        if table not in frames:
            raise ValueError(f"no stub for {table}")
        return frames[table]
    return fake


def test_lineup_rating_math(monkeypatch):
    frames = {
        "silver_lineups": pl.DataFrame([
            _lu("1-2-3-4-5", "BOS", "starters", 110, 10, 90, 10, 15, 20, 48.0),
            _lu("6-7-8-9-10", "BOS", "bench", 90, -4, 90, 10, 15, 20, 40.0),
        ])
    }
    monkeypatch.setattr(_store, "read_frame", _fake_reader(frames))
    res = _ds._lineup_leaders("2024-25", 0)
    assert res["ok"] is True
    assert [r["lineup"] for r in res["data"]] == ["starters", "bench"]
    top = res["data"][0]
    assert top["possessions"] == round(90 - 10 + 15 + 0.44 * 20, 1)
    assert top["OFF_RTG"] == 106.0
    assert top["NET_RTG"] == 9.6
    assert top["DEF_RTG"] == round(106.0 - 9.6, 1)
    assert res["meta"]["min_poss"] == 0
    assert "estimated" in res["meta"]["method"]
    assert "derived" in res["meta"]["method"]


def test_lineup_aggregates_stints_per_lineup(monkeypatch):
    frames = {
        "silver_lineups": pl.DataFrame([
            _lu("1-2-3-4-5", "BOS", "early", 50, 5, 40, 5, 8, 10, 20.0),
            _lu("1-2-3-4-5", "BOS", "late", 60, -2, 45, 6, 9, 10, 25.0),
        ])
    }
    monkeypatch.setattr(_store, "read_frame", _fake_reader(frames))
    res = _ds._lineup_leaders("2024-25", 0)
    assert res["ok"] is True
    assert len(res["data"]) == 1
    row = res["data"][0]
    assert row["lineup"] == "late"
    assert row["MIN"] == 45.0
    assert row["possessions"] == round(85 - 11 + 17 + 0.44 * 20, 1)
    assert row["OFF_RTG"] == round(100.0 * 110 / 99.8, 1)
    assert row["NET_RTG"] == round(100.0 * 3 / 99.8, 1)
    assert row["DEF_RTG"] == round(row["OFF_RTG"] - row["NET_RTG"], 1)


def test_lineup_min_poss_filtering(monkeypatch):
    frames = {
        "silver_lineups": pl.DataFrame([
            _lu("1-2-3-4-5", "BOS", "starters", 110, 10, 90, 10, 15, 20, 48.0),
            _lu("6-7-8-9-10", "BOS", "bench", 900, 80, 700, 80, 120, 160, 400.0),
        ])
    }
    monkeypatch.setattr(_store, "read_frame", _fake_reader(frames))
    res = _ds._lineup_leaders("2024-25", 200)
    assert res["ok"] is True
    assert [r["lineup"] for r in res["data"]] == ["bench"]


def test_lineup_skips_non_fiveman_and_null_pts(monkeypatch):
    frames = {
        "silver_lineups": pl.DataFrame([
            _lu("1-2-3-4", "BOS", "four", 110, 10, 90, 10, 15, 20, 48.0),
            _lu("1-2-3-4-5", "BOS", "broken", None, 10, 90, 10, 15, 20, 48.0),
            _lu("6-7-8-9-10", "BOS", "bench", 90, 4, 90, 10, 15, 20, 40.0),
        ])
    }
    monkeypatch.setattr(_store, "read_frame", _fake_reader(frames))
    res = _ds._lineup_leaders("2024-25", 0)
    assert res["ok"] is True
    assert [r["lineup"] for r in res["data"]] == ["bench"]


def test_lineup_empty_frame_errors(monkeypatch):
    monkeypatch.setattr(_store, "read_frame", _fake_reader(
        {"silver_lineups": pl.DataFrame([])}))
    res = _ds._lineup_leaders("2024-25", 0)
    assert res["ok"] is False
    assert "silver_lineups" in res["error"]


def test_lineup_warehouse_failure_errors(monkeypatch):
    def boom(table, where=None, params=None):
        raise RuntimeError("db gone")
    monkeypatch.setattr(_store, "read_frame", boom)
    res = _ds._lineup_leaders("2024-25", 0)
    assert res["ok"] is False
    assert "warehouse read failed" in res["error"]


def test_hist_zone_boundaries():
    assert _ds._hist_zone(2, 7.9, 0) == "Rim (<8 ft)"
    assert _ds._hist_zone(2, 8.0, 0) == "Short Mid (8-14 ft)"
    assert _ds._hist_zone(2, 8.1, 0) == "Short Mid (8-14 ft)"
    assert _ds._hist_zone(2, 13.9, 0) == "Short Mid (8-14 ft)"
    assert _ds._hist_zone(2, 14.0, 0) == "Long Mid (14 ft+)"
    assert _ds._hist_zone(2, 30, 0) == "Long Mid (14 ft+)"
    assert _ds._hist_zone(3, 25, 230) == "Corner 3"
    assert _ds._hist_zone(3, 25, 220) == "Corner 3"
    assert _ds._hist_zone(3, 25, 219.9) == "Above-Break 3"
    assert _ds._hist_zone(3, 25, 0) == "Above-Break 3"
    assert _ds._hist_zone(3, 25, None) == "Above-Break 3"


def test_hist_zone_matches_zone_of():
    cases = [
        (0, 79, 2), (0, 80, 2), (0, 81, 2), (100, 100, 2),
        (0, 139, 2), (0, 140, 2), (0, 300, 2),
        (230, 30, 3), (220, 0, 3), (219, 0, 3), (0, 250, 3),
    ]
    for x, y, value in cases:
        dist = math.hypot(float(x), float(y)) / 10.0
        assert _ds._hist_zone(value, dist, x) == _LABEL_BY_KEY[zone_of(x, y, value)]


def test_zone_splits_hist_fallback_binning(monkeypatch):
    frames = {
        "silver_shots": pl.DataFrame([]),
        "silver_hist_shots": pl.DataFrame([
            {"shot_value": 2, "shot_distance": 5.0, "x_legacy": 10,
             "shot_result": "Made"},
            {"shot_value": 2, "shot_distance": 5.0, "x_legacy": 10,
             "shot_result": "Missed"},
            {"shot_value": 2, "shot_distance": 10.0, "x_legacy": 50,
             "shot_result": "Made"},
            {"shot_value": 3, "shot_distance": 24.0, "x_legacy": 230,
             "shot_result": "Made"},
            {"shot_value": 3, "shot_distance": 26.0, "x_legacy": 0,
             "shot_result": "Missed"},
        ]),
    }
    monkeypatch.setattr(_store, "read_frame", _fake_reader(frames))
    res = _ds._zone_splits("2024-25", 123)
    assert res["ok"] is True
    by_zone = {r["zone"]: r for r in res["data"]}
    assert by_zone["Rim (<8 ft)"] == {
        "zone": "Rim (<8 ft)", "FGM": 1, "FGA": 2, "FG_PCT": 0.5}
    assert by_zone["Short Mid (8-14 ft)"]["FGM"] == 1
    assert by_zone["Corner 3"]["FGM"] == 1
    assert by_zone["Above-Break 3"]["FGA"] == 1
    assert res["data"] == sorted(res["data"], key=lambda d: d["FGA"],
                                 reverse=True)
    assert "8 ft" in res["meta"]["zone_definition"]
    assert res["meta"]["sources"] == ["silver_hist_shots"]


def test_zone_splits_prefers_native_shot_zones(monkeypatch):
    frames = {
        "silver_shots": pl.DataFrame([
            {"SHOT_ZONE_BASIC": "Mid-Range", "SHOT_MADE_FLAG": "1"},
            {"SHOT_ZONE_BASIC": "Mid-Range", "SHOT_MADE_FLAG": "0"},
        ]),
    }
    monkeypatch.setattr(_store, "read_frame", _fake_reader(frames))
    res = _ds._zone_splits("2024-25", 123)
    assert res["ok"] is True
    assert res["data"] == [
        {"zone": "Mid-Range", "FGM": 1, "FGA": 2, "FG_PCT": 0.5}]
    assert res["meta"]["sources"] == ["silver_shots"]


def test_zone_splits_requires_player():
    res = _ds._zone_splits("2024-25", 0)
    assert res["ok"] is False
    assert "player_id" in res["error"]


def test_zone_splits_empty_errors(monkeypatch):
    monkeypatch.setattr(_store, "read_frame", _fake_reader(
        {"silver_shots": pl.DataFrame([]),
         "silver_hist_shots": pl.DataFrame([])}))
    res = _ds._zone_splits("2024-25", 123)
    assert res["ok"] is False
    assert "no shot rows" in res["error"]


def test_rapm_sorted_descending(monkeypatch):
    frames = {
        "silver_rapm": pl.DataFrame([
            {"PLAYER": "B", "rapm": 1.5},
            {"PLAYER": "A", "rapm": 3.0},
            {"PLAYER": "C", "rapm": -0.5},
        ])
    }
    monkeypatch.setattr(_store, "read_frame", _fake_reader(frames))
    res = _ds._table_leaders("silver_rapm", "2024-25", "rapm")
    assert res["ok"] is True
    assert [r["PLAYER"] for r in res["data"]] == ["A", "B", "C"]


def test_clutch_sorted_by_pts(monkeypatch):
    frames = {
        "silver_clutch": pl.DataFrame([
            {"PLAYER": "B", "PTS": 40},
            {"PLAYER": "A", "PTS": 90},
        ])
    }
    monkeypatch.setattr(_store, "read_frame", _fake_reader(frames))
    res = _ds._table_leaders("silver_clutch", "2024-25", "PTS")
    assert res["ok"] is True
    assert [r["PLAYER"] for r in res["data"]] == ["A", "B"]


def test_table_leaders_empty_errors(monkeypatch):
    monkeypatch.setattr(_store, "read_frame", _fake_reader(
        {"silver_rapm": pl.DataFrame([])}))
    res = _ds._table_leaders("silver_rapm", "2024-25", "rapm")
    assert res["ok"] is False
    assert "no rows" in res["error"]
