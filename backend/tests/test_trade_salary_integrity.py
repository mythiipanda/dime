from shared.tools import get_trade_check

def test_trade_check_fails_closed_on_salary_vintage_mismatch(
        monkeypatch, tmp_path):
    import duckdb

    from shared import store

    path = tmp_path / "vintage.duckdb"
    con = duckdb.connect(str(path))
    try:
        con.execute(
            "CREATE TABLE silver_salaries (PLAYER_NAME VARCHAR, "
            "TEAM VARCHAR, SALARY INTEGER, _season VARCHAR, "
            "_fetched_at VARCHAR)")
        con.execute(
            "INSERT INTO silver_salaries VALUES ('LeBron James', 'LAL', "
            "50000000, '2026-27', NULL)")
        con.execute(
            "INSERT INTO silver_salaries VALUES "
            "('Giannis Antetokounmpo', 'MIA', 40000000, '2026-27', NULL)")
    finally:
        con.close()
    monkeypatch.setattr(store, "DB_PATH", path)
    monkeypatch.setattr(store, "LOCK_PATH", tmp_path / ".write.lock")
    store.warehouse_tables_cache_clear()
    store.warehouse_pool_clear()
    out = get_trade_check.invoke({
        "team_a": "LAL", "players_a": "LeBron James",
        "team_b": "MIA", "players_b": "Giannis Antetokounmpo",
        "season": "2025-26",
    })
    assert out["ok"] is False
    assert "salary data is for 2026-27, not 2025-26" in out["error"]
    assert "not calculated" in out["error"]


def test_trade_check_serves_season_column_under_later_vintage_label(
        monkeypatch, tmp_path):
    import duckdb

    from shared import store

    path = tmp_path / "vintage.duckdb"
    con = duckdb.connect(str(path))
    try:
        con.execute(
            "CREATE TABLE silver_salaries (PLAYER_NAME VARCHAR, "
            "TEAM VARCHAR, SALARY_2025_26 INTEGER, _season VARCHAR, "
            "_fetched_at VARCHAR)")
        con.execute(
            "INSERT INTO silver_salaries VALUES ('LeBron James', 'LAL', "
            "50000000, '2026-27', NULL)")
        con.execute(
            "INSERT INTO silver_salaries VALUES "
            "('Giannis Antetokounmpo', 'MIA', 40000000, '2026-27', NULL)")
    finally:
        con.close()
    monkeypatch.setattr(store, "DB_PATH", path)
    monkeypatch.setattr(store, "LOCK_PATH", tmp_path / ".write.lock")
    store.warehouse_tables_cache_clear()
    store.warehouse_pool_clear()
    out = get_trade_check.invoke({
        "team_a": "LAL", "players_a": "LeBron James",
        "team_b": "MIA", "players_b": "Giannis Antetokounmpo",
        "season": "2025-26",
    })
    assert out["ok"] is True


def test_trade_check_refuses_season_with_no_salary_column(
        monkeypatch, tmp_path):
    import duckdb

    from shared import store

    path = tmp_path / "vintage.duckdb"
    con = duckdb.connect(str(path))
    try:
        con.execute(
            "CREATE TABLE silver_salaries (PLAYER_NAME VARCHAR, "
            "TEAM VARCHAR, SALARY_2025_26 INTEGER, _season VARCHAR, "
            "_fetched_at VARCHAR)")
        con.execute(
            "INSERT INTO silver_salaries VALUES ('LeBron James', 'LAL', "
            "50000000, '2026-27', NULL)")
        con.execute(
            "INSERT INTO silver_salaries VALUES "
            "('Giannis Antetokounmpo', 'MIA', 40000000, '2026-27', NULL)")
    finally:
        con.close()
    monkeypatch.setattr(store, "DB_PATH", path)
    monkeypatch.setattr(store, "LOCK_PATH", tmp_path / ".write.lock")
    store.warehouse_tables_cache_clear()
    store.warehouse_pool_clear()
    out = get_trade_check.invoke({
        "team_a": "LAL", "players_a": "LeBron James",
        "team_b": "MIA", "players_b": "Giannis Antetokounmpo",
        "season": "2026-27",
    })
    assert out["ok"] is False
    assert "covers 2025-26, not 2026-27" in out["error"]
    assert "not calculated" in out["error"]


def _vintaged_warehouse(tmp_path, monkeypatch, columns, rows):
    import duckdb

    from shared import store

    path = tmp_path / "vintaged.duckdb"
    con = duckdb.connect(str(path))
    try:
        con.execute(
            "CREATE TABLE silver_salaries (PLAYER_NAME VARCHAR, "
            f"TEAM VARCHAR, {columns}, _season VARCHAR)")
        ncols = 3 + columns.count(",") + 1
        for row in rows:
            con.execute(
                "INSERT INTO silver_salaries VALUES (%s)" % ", ".join(
                    ["?"] * ncols), row)
    finally:
        con.close()
    monkeypatch.setattr(store, "DB_PATH", path)
    monkeypatch.setattr(store, "LOCK_PATH", tmp_path / ".write.lock")
    store.warehouse_tables_cache_clear()
    store.warehouse_pool_clear()
    return path


def test_unknown_player_typed_reason_on_canonical_salary_schema(
        monkeypatch, tmp_path):
    from shared.tools import league as league_mod

    _vintaged_warehouse(
        tmp_path, monkeypatch, "SALARY INTEGER",
        [("LeBron James", "LAL", 50000000, "2025-26")])
    out = league_mod.get_trade_value.invoke(
        {"team_a": "LAL", "players_a": "Zzx Notaplayer",
         "team_b": "MIA", "players_b": "LeBron James"})
    assert out["ok"] is False
    assert out["reason"] == "unknown_players"


def test_season_matched_column_wins_over_first_match(
        monkeypatch, tmp_path):
    from shared import store
    from shared.tools import league as league_mod

    _vintaged_warehouse(
        tmp_path, monkeypatch,
        "SALARY_2024_25 INTEGER, SALARY_2025_26 INTEGER",
        [("LeBron James", "LAL", 10, 20, "2025-26")])
    con = store.connect(read_only=True)
    try:
        total_2526, roster, _dead = league_mod._payroll(
            "LAL", con, season="2025-26")
        total_2425, _r, _d = league_mod._payroll("LAL", con, season="2024-25")
    finally:
        con.close()
    assert total_2526 == 20
    assert [p["salary"] for p in roster] == [20]
    assert total_2425 == 10


def test_unmatched_season_column_fails_loud_not_wrong_value(
        monkeypatch, tmp_path):
    from shared.tools import league as league_mod

    _vintaged_warehouse(
        tmp_path, monkeypatch,
        "SALARY_2025_26 INTEGER",
        [("LeBron James", "LAL", 20, "2025-26")])
    out = league_mod.get_trade_value.invoke(
        {"team_a": "LAL", "players_a": "LeBron James",
         "team_b": "MIA", "players_b": "LeBron James"})
    assert out["ok"] is False
    assert out["reason"] == "salary_column_unmatched"


def test_cap_ledger_vintage_only_schema_fails_typed(
        monkeypatch, tmp_path):
    from shared.tools import league as league_mod

    _vintaged_warehouse(
        tmp_path, monkeypatch,
        "SALARY_2024_25 INTEGER, SALARY_2025_26 INTEGER",
        [("LeBron James", "LAL", 10, 20, "2025-26")])
    out = league_mod.get_cap_ledger.invoke({"team": "LAL"})
    assert out["ok"] is False
    assert out["reason"] == "salary_column_unmatched"


def test_salary_vintage_prefers_the_newest_season(monkeypatch, tmp_path):
    import duckdb

    from shared import store
    from shared.tools.league import _salary_vintage

    path = tmp_path / "vintage_order.duckdb"
    con = duckdb.connect(str(path))
    try:
        con.execute(
            "CREATE TABLE silver_salaries (PLAYER_NAME VARCHAR, TEAM VARCHAR, "
            "SALARY INTEGER, _season VARCHAR, _fetched_at VARCHAR)")
        con.execute(
            "INSERT INTO silver_salaries VALUES "
            "('LeBron James', 'LAL', 50000000, '2025-26', '2026-01-01'), "
            "('Giannis Antetokounmpo', 'MIA', 40000000, '2025-26', "
            "'2026-01-01'), "
            "('Jayson Tatum', 'BOS', 58000000, '2026-27', '2026-09-01')")
    finally:
        con.close()
    monkeypatch.setattr(store, "DB_PATH", path)
    monkeypatch.setattr(store, "LOCK_PATH", tmp_path / ".write.lock")
    store.warehouse_tables_cache_clear()
    store.warehouse_pool_clear()
    season, rows, _ = _salary_vintage()
    assert season == "2026-27"
    assert rows == 1
