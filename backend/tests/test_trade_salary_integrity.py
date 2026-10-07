from shared.tools import get_trade_check

def test_trade_check_fails_closed_on_salary_vintage_mismatch():
    out = get_trade_check.invoke({
        "team_a": "LAL", "players_a": "LeBron James",
        "team_b": "MIA", "players_b": "Giannis Antetokounmpo",
        "season": "2025-26",
    })
    assert out["ok"] is False
    assert "salary data is for 2026-27, not 2025-26" in out["error"]
    assert "not calculated" in out["error"]


def test_unknown_player_typed_reason_on_versioned_salary_schema(
        monkeypatch, tmp_path):
    import duckdb

    from shared import store
    from shared.tools import league as league_mod

    path = tmp_path / "vintaged.duckdb"
    con = duckdb.connect(str(path))
    try:
        con.execute(
            "CREATE TABLE silver_salaries (PLAYER_NAME VARCHAR, "
            "TEAM VARCHAR, SALARY_2025_26 INTEGER, _season VARCHAR)")
        con.execute(
            "INSERT INTO silver_salaries VALUES ('LeBron James', 'LAL', "
            "50000000, '2025-26')")
    finally:
        con.close()
    monkeypatch.setattr(store, "DB_PATH", path)
    monkeypatch.setattr(store, "LOCK_PATH", tmp_path / ".write.lock")
    store.warehouse_tables_cache_clear()
    store.warehouse_pool_clear()
    out = league_mod.get_trade_value.invoke(
        {"team_a": "LAL", "players_a": "Zzx Notaplayer",
         "team_b": "MIA", "players_b": "LeBron James"})
    assert out["ok"] is False
    assert out["reason"] == "unknown_players"
