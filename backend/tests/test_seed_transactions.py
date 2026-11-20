import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import seed_transactions as seed
from shared import store


def _row(date, kind, detail, team="celtics", player="sample-player"):
    return {
        "Transaction_Type": kind,
        "TRANSACTION_DATE": date + "T00:00:00",
        "TRANSACTION_DESCRIPTION": detail,
        "TEAM_ID": 1610612738.0,
        "TEAM_SLUG": team,
        "PLAYER_ID": 1641000.0,
        "PLAYER_SLUG": player,
        "Additional_Sort": 1.0,
        "GroupSort": "A",
    }


def _payload():
    return {"NBA_Player_Movement": {"rows": [
        _row("2024-04-11", "Signing", "Boston Celtics signed guard X."),
        _row("2024-10-22", "Signing", "Boston Celtics signed guard Y to a Two-Way Contract."),
        _row("2025-01-15", "Waive", "Boston Celtics waived guard Y."),
        _row("2024-09-27", "Trade", "Boston Celtics received guard Z from Chicago Bulls."),
    ]}}


def _scratch(monkeypatch, tmp_path):
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "warehouse.duckdb")
    monkeypatch.setattr(store, "LOCK_PATH", tmp_path / ".write.lock")


def test_mapper_rows_match_source_count():
    frame = seed.map_transactions(_payload())
    assert frame.height == 4
    assert frame.columns == ["txn_date", "txn_type", "player", "player_id",
                             "team", "team_id", "detail"]


def test_mapper_rejects_payload_without_rows():
    with pytest.raises(ValueError):
        seed.map_transactions({"NBA_Player_Movement": {"rows": None}})
    with pytest.raises(ValueError):
        seed.map_transactions({"something": "else"})


def test_partition_splits_seasons():
    parts = seed.partition_by_season(seed.map_transactions(_payload()))
    assert sorted(parts) == ["2023-24", "2024-25"]
    assert parts["2023-24"].height == 2
    assert parts["2024-25"].height == 2


def test_season_derivation():
    assert seed.season_for_date("2024-04-11") == "2023-24"
    assert seed.season_for_date("2024-10-22") == "2024-25"
    assert seed.season_for_date("2025-01-15") == "2024-25"
    assert seed.season_for_date("2015-07-01") == "2014-15"


def test_seed_all_writes_one_unit_per_season(tmp_path, monkeypatch):
    _scratch(monkeypatch, tmp_path)
    result = seed.seed_all(fetch_fn=lambda: _payload())
    assert result == {"2023-24": 2, "2024-25": 2}
    back = store.read_frame("silver_transactions")
    assert back.height == 4
    for col in ["_source", "_season", "_fetched_at", "_entity"]:
        assert back[col].null_count() == 0
    assert back["_source"].unique().to_list() == ["nba_official"]
    assert sorted(back["_season"].unique().to_list()) == ["2023-24", "2024-25"]
    assert sorted(back["_entity"].unique().to_list()) == [
        "season:2023-24", "season:2024-25"]
    assert store.last_fetch("silver_transactions", "2023-24",
                            "season:2023-24") != ""
    assert store.last_fetch("silver_transactions", "2024-25",
                            "season:2024-25") != ""


def _log_count(path):
    import duckdb
    con = duckdb.connect(str(path), read_only=True)
    try:
        return con.execute("SELECT COUNT(*) FROM fetch_log").fetchone()[0]
    finally:
        con.close()


def test_seed_all_resumes_per_season(tmp_path, monkeypatch):
    _scratch(monkeypatch, tmp_path)
    path = tmp_path / "warehouse.duckdb"
    assert seed.seed_all(fetch_fn=lambda: _payload()) == {
        "2023-24": 2, "2024-25": 2}
    assert _log_count(path) == 2
    assert seed.seed_all(fetch_fn=lambda: _payload()) == {
        "2023-24": 0, "2024-25": 0}
    assert _log_count(path) == 2
    assert store.read_frame("silver_transactions").height == 4


def test_seed_all_empty_writes_nothing(tmp_path, monkeypatch):
    _scratch(monkeypatch, tmp_path)
    assert seed.seed_all(
        fetch_fn=lambda: {"NBA_Player_Movement": {"rows": []}}) == {}
    assert not (tmp_path / "warehouse.duckdb").exists()


def test_seed_all_fail_closed_on_fetch_error(tmp_path, monkeypatch):
    _scratch(monkeypatch, tmp_path)

    def boom():
        raise RuntimeError("HTTP 500: upstream down")

    with pytest.raises(RuntimeError):
        seed.seed_all(fetch_fn=boom)
    assert not (tmp_path / "warehouse.duckdb").exists()


def test_seed_all_fail_closed_on_malformed_payload(tmp_path, monkeypatch):
    _scratch(monkeypatch, tmp_path)
    with pytest.raises(ValueError):
        seed.seed_all(fetch_fn=lambda: {"unexpected": "shape"})
    assert not (tmp_path / "warehouse.duckdb").exists()


def test_main_reports_counts(tmp_path, monkeypatch, capsys):
    _scratch(monkeypatch, tmp_path)
    assert seed.main([], fetch_fn=lambda: _payload()) == 0
    out = capsys.readouterr().out
    assert "2023-24" in out and "2024-25" in out


def test_main_returns_nonzero_on_failure(tmp_path, monkeypatch):
    _scratch(monkeypatch, tmp_path)

    def boom():
        raise RuntimeError("HTTP 500: upstream down")

    assert seed.main([], fetch_fn=boom) == 1
