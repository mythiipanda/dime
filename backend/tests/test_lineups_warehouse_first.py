import inspect
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import polars as pl
from app import datasets as _ds
from shared import store as _store
from shared.sources import nba_stats as _nba
from shared.sources.base import FetchResult, FetchMeta


def _row(gid, team_id, abbr, name, season="2024-25", pts=110.0, pm=10.0, mn=48.0):
    return {
        "GROUP_ID": gid, "GROUP_NAME": name,
        "TEAM_ID": team_id, "TEAM_ABBREVIATION": abbr,
        "PTS": pts, "PLUS_MINUS": pm, "FGA": 90.0, "OREB": 10.0,
        "TOV": 15.0, "FTA": 20.0, "MIN": mn, "GP": 5,
        "_source": "nba_api", "_season": season,
        "_fetched_at": "2025-01-01T00:00:00+00:00",
        "_entity": "lineups:2024-25",
    }


def _endpoint():
    return _ds.dataset.__wrapped__ if hasattr(_ds.dataset, "__wrapped__") else _ds.dataset


def test_team_lineups_serves_warehouse_despite_live_timeout(monkeypatch):
    warehouse_rows = pl.DataFrame([
        _row("1-2-3-4-5", 14, "BOS", "starters"),
        _row("6-7-8-9-10", 14, "BOS", "bench"),
    ])
    calls = {"live": 0}

    def fake_read(table, where=None, params=None):
        assert table == "silver_lineups"
        if where is not None and "_entity" in where:
            return pl.DataFrame([])
        return warehouse_rows

    def fake_lineups(team_id, season):
        calls["live"] += 1
        return FetchResult(
            frame=pl.DataFrame([]),
            meta=FetchMeta(source="nba_api", season=season),
            ok=False,
            error="HTTPSConnectionPool(host='stats.nba.com',port=443): Read timed out.",
        )

    monkeypatch.setattr(_store, "read_frame", fake_read)
    monkeypatch.setattr(_nba, "lineups", fake_lineups)
    out = _endpoint()("lineups", season="2024-25", team_id=14)
    assert out.get("ok") is True, f"warehouse had rows but endpoint failed: {out}"
    assert calls["live"] == 0, f"live was called {calls['live']}x despite warehouse rows"
    assert out["meta"]["cached"] is True
    assert out["meta"]["season"] == "2024-25"
    assert len(out["data"]) == 2
    assert out["data"][0]["SAMPLE_TIER"] == "small"
    assert out["data"][0]["EST_POSS"] == 96


def test_team_lineups_falls_back_to_live_when_warehouse_empty(monkeypatch):
    live_rows = pl.DataFrame([_row("1-2-3-4-5", 14, "BOS", "starters")])
    calls = {"live": 0, "save": 0}
    live_meta = FetchMeta(source="nba_api", season="2024-25")

    def fake_read(table, where=None, params=None):
        assert table == "silver_lineups"
        if where is not None and "TEAM_ID" in where:
            return pl.DataFrame([])
        if where is not None and "_entity" in where:
            return pl.DataFrame([])
        if where is not None and "_fetched_at" in where:
            return live_rows
        return pl.DataFrame([])

    def fake_lineups(team_id, season):
        calls["live"] += 1
        assert team_id == 14
        assert season == "2024-25"
        return FetchResult(frame=live_rows, meta=live_meta, ok=True, error="")

    def fake_save(table, result, entity=""):
        calls["save"] += 1
        return 1

    monkeypatch.setattr(_store, "read_frame", fake_read)
    monkeypatch.setattr(_store, "save_frame", fake_save)
    monkeypatch.setattr(_nba, "lineups", fake_lineups)
    out = _endpoint()("lineups", season="2024-25", team_id=14)
    assert out.get("ok") is True
    assert calls["live"] == 1
    assert calls["save"] == 1
    assert out["data"][0]["GROUP_NAME"] == "starters"


def test_team_lineups_both_fail_returns_sanitized_error(monkeypatch):
    def fake_read(table, where=None, params=None):
        return pl.DataFrame([])

    def fake_lineups(team_id, season):
        return FetchResult(
            frame=pl.DataFrame([]),
            meta=FetchMeta(source="nba_api", season=season),
            ok=False,
            error="HTTPSConnectionPool(host='stats.nba.com',port=443): Read timed out.",
        )

    monkeypatch.setattr(_store, "read_frame", fake_read)
    monkeypatch.setattr(_nba, "lineups", fake_lineups)
    out = _endpoint()("lineups", season="2024-25", team_id=14)
    assert out.get("ok") is False
    assert "HTTPSConnectionPool" not in out["error"]
    assert "443" not in out["error"]
    assert "timed out" in out["error"].lower()
    assert "no cached rows" in out["error"].lower()


def test_default_season_resolves_without_literal_and_explicit_preserved(monkeypatch):
    assert "2025-26" not in inspect.getsource(_ds.dataset)
    import shared.tools._core as _core
    seen = {}

    def fake_resolve(season=None, table=None):
        assert season is None
        return "2024-25"

    def fake_read(table, where=None, params=None):
        seen["params"] = params
        return pl.DataFrame([_row("1-2-3-4-5", 14, "BOS", "starters")])

    monkeypatch.setattr(_core, "resolve_season", fake_resolve)
    monkeypatch.setattr(_store, "read_frame", fake_read)
    out = _endpoint()("lineups", team_id=14)
    assert out.get("ok") is True
    assert out["meta"]["season"] == "2024-25"
    assert "2024-25" in (seen["params"] or [])


def test_explicit_season_never_substituted(monkeypatch):
    def fake_read(table, where=None, params=None):
        assert params is not None and "2023-24" in params
        return pl.DataFrame([_row("1-2-3-4-5", 14, "BOS", "starters", season="2023-24")])

    monkeypatch.setattr(_store, "read_frame", fake_read)
    out = _endpoint()("lineups", season="2023-24", team_id=14)
    assert out.get("ok") is True
    assert out["meta"]["season"] == "2023-24"


def test_shared_aggregation_sums_stints_with_hand_literals(monkeypatch):
    rows = [
        {"GROUP_ID": "1-2-3-4-5", "GROUP_NAME": "early", "TEAM_ABBREVIATION": "BOS",
         "PTS": 50.0, "PLUS_MINUS": 5.0, "FGA": 40.0, "OREB": 5.0,
         "TOV": 8.0, "FTA": 10.0, "MIN": 20.0},
        {"GROUP_ID": "1-2-3-4-5", "GROUP_NAME": "late", "TEAM_ABBREVIATION": "BOS",
         "PTS": 60.0, "PLUS_MINUS": -2.0, "FGA": 45.0, "OREB": 6.0,
         "TOV": 9.0, "FTA": 10.0, "MIN": 25.0},
    ]
    out = _ds._aggregate_lineup_rows(rows)
    assert len(out) == 1
    gid, team, name, vals, poss = out[0]
    assert gid == "1-2-3-4-5"
    assert team == "BOS"
    assert name == "late"
    assert vals["PTS"] == 110.0
    assert vals["MIN"] == 45.0
    assert poss == 85 - 11 + 17 + 0.44 * 20
