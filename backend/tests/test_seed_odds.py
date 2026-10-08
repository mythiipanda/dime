import os
import sys
from pathlib import Path

import polars as pl
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import seed_odds as seed
from shared import store


def _payload():
    base = {
        "game_date": "2024-04-20",
        "sport_key": "basketball_nba",
        "home_team": "Los Angeles Lakers",
        "away_team": "Denver Nuggets",
        "commence_time": "2024-04-21T02:00:00Z",
    }
    return [
        dict(base, bookmaker="pinnacle", market_key="h2h",
             outcome="Denver Nuggets", price=-150),
        dict(base, bookmaker="pinnacle", market_key="totals",
             line=224.5, over_odds=-110, under_odds=-110),
        dict(base, bookmaker="draftkings", market_key="spreads",
             outcome="Los Angeles Lakers", price=-110, line=-4.5),
    ]


def _scratch(monkeypatch, tmp_path):
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "warehouse.duckdb")
    monkeypatch.setattr(store, "LOCK_PATH", tmp_path / ".write.lock")


def test_mapper_flat_rows_to_expected_columns():
    frame = seed.map_closing_odds(_payload(), "2024-04-20")
    assert frame.height == 4
    assert frame.columns == ["game_date", "commence_time", "home_team",
                             "away_team", "book", "market", "outcome",
                             "price", "point"]


def test_mapper_abbreviates_teams_and_expands_totals():
    frame = seed.map_closing_odds(_payload(), "2024-04-20")
    assert frame["home_team"].unique().to_list() == ["LAL"]
    assert frame["away_team"].unique().to_list() == ["DEN"]
    totals = frame.filter(pl.col("market") == "totals").sort("outcome")
    assert totals["outcome"].to_list() == ["Over", "Under"]
    assert totals["price"].to_list() == [-110, -110]
    assert totals["point"].to_list() == [224.5, 224.5]
    spreads = frame.filter(pl.col("market") == "spreads")
    assert spreads["point"].to_list() == [-4.5]


def test_mapper_rejects_non_list_payload():
    with pytest.raises(ValueError):
        seed.map_closing_odds({"data": []}, "2024-04-20")


def test_mapper_rejects_unrecognized_row_shape():
    with pytest.raises(ValueError):
        seed.map_closing_odds([{"game_date": "2024-04-20"}], "2024-04-20")


def test_seed_writes_provenance(tmp_path, monkeypatch):
    _scratch(monkeypatch, tmp_path)
    n = seed.seed_date("2024-04-20", "2023-24",
                       fetch_fn=lambda date: _payload())
    assert n == 4
    back = store.read_frame("silver_odds")
    assert back.height == 4
    for col in ["_source", "_season", "_fetched_at", "_entity"]:
        assert back[col].null_count() == 0
    assert back["_source"].unique().to_list() == ["parlay"]
    assert back["_season"].unique().to_list() == ["2023-24"]
    assert back["_entity"].unique().to_list() == ["closing:2024-04-20"]


def test_seed_resumes_on_watermark(tmp_path, monkeypatch):
    _scratch(monkeypatch, tmp_path)
    calls = []
    first = seed.seed_date("2024-04-20", "2023-24",
                           fetch_fn=lambda date: calls.append(date) or _payload())
    second = seed.seed_date("2024-04-20", "2023-24",
                            fetch_fn=lambda date: calls.append(date) or _payload())
    assert (first, second) == (4, 0)
    assert calls == ["2024-04-20"]
    assert store.last_fetch("silver_odds", "2023-24",
                            "closing:2024-04-20") != ""


def test_seed_empty_payload_writes_nothing(tmp_path, monkeypatch):
    _scratch(monkeypatch, tmp_path)
    calls = []
    first = seed.seed_date("2024-04-20", "2023-24",
                           fetch_fn=lambda date: calls.append(date) or [])
    second = seed.seed_date("2024-04-20", "2023-24",
                            fetch_fn=lambda date: calls.append(date) or [])
    assert (first, second) == (0, 0)
    assert calls == ["2024-04-20", "2024-04-20"]


def _counts(path):
    import duckdb
    con = duckdb.connect(str(path), read_only=True)
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        rows = con.execute("SELECT COUNT(*) FROM silver_odds").fetchone()[0] \
            if "silver_odds" in tables else 0
        logs = con.execute("SELECT COUNT(*) FROM fetch_log").fetchone()[0] \
            if "fetch_log" in tables else 0
        return rows, logs
    finally:
        con.close()


def _boom(date):
    raise RuntimeError("HTTP 401: bad key")


def test_seed_fail_closed_leaves_table_and_log_unchanged(tmp_path, monkeypatch):
    _scratch(monkeypatch, tmp_path)
    path = tmp_path / "warehouse.duckdb"
    assert seed.seed_date("2024-04-20", "2023-24",
                          fetch_fn=lambda date: _payload()) == 4
    before = _counts(path)
    assert before == (4, 1)
    with pytest.raises(RuntimeError):
        seed.seed_date("2024-04-21", "2023-24", fetch_fn=_boom)
    assert _counts(path) == before


def test_seed_malformed_payload_writes_nothing(tmp_path, monkeypatch):
    _scratch(monkeypatch, tmp_path)
    path = tmp_path / "warehouse.duckdb"
    assert not path.exists()
    with pytest.raises(ValueError):
        seed.seed_date("2024-04-20", "2023-24",
                       fetch_fn=lambda date: {"unexpected": "shape"})
    assert not path.exists()


def _fake_run_factory(outputs):
    calls = {"n": 0}

    class Proc:
        def __init__(self, out):
            self.stdout = out
            self.returncode = 0

    def fake_run(*args, **kwargs):
        out = outputs[min(calls["n"], len(outputs) - 1)]
        calls["n"] += 1
        return Proc(out)

    return fake_run


def test_transport_retries_then_returns_body(monkeypatch):
    import subprocess
    monkeypatch.setattr(subprocess, "run", _fake_run_factory(
        [b"{}\n500", b"[]\n200"]))
    sleeps = []
    monkeypatch.setattr("seed_odds._sleep", lambda s: sleeps.append(s))
    body = seed._curl_transport("https://x", {}, {}, attempts=3)
    assert body == "[]"
    assert sleeps == [2]


def test_transport_raises_after_retries(monkeypatch):
    import subprocess
    monkeypatch.setattr(subprocess, "run",
                        _fake_run_factory([b"denied\n500"]))
    monkeypatch.setattr("seed_odds._sleep", lambda s: None)
    with pytest.raises(RuntimeError, match="500"):
        seed._curl_transport("https://x", {}, {}, attempts=2)


def test_main_fails_closed_without_key(tmp_path, monkeypatch):
    _scratch(monkeypatch, tmp_path)
    monkeypatch.delenv("PARLAY_API_KEY", raising=False)
    assert seed.main(["--date", "2024-04-20", "--season", "2023-24"]) == 1
    assert not (tmp_path / "warehouse.duckdb").exists()


def test_season_derivation():
    assert seed.season_for_date("2024-04-20") == "2023-24"
    assert seed.season_for_date("2024-10-22") == "2024-25"
    assert seed.season_for_date("2025-01-15") == "2024-25"
