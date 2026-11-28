import duckdb

from shared import store


def _use_salary_warehouse(monkeypatch, tmp_path, rows):
    path = tmp_path / "trade_math.duckdb"
    con = duckdb.connect(str(path))
    try:
        con.execute(
            "CREATE TABLE silver_salaries (PLAYER_NAME VARCHAR, TEAM VARCHAR, "
            "PLAYER_ID BIGINT, SALARY_2026_27 BIGINT, _season VARCHAR, "
            "_fetched_at VARCHAR)")
        for row in rows:
            con.execute(
                "INSERT INTO silver_salaries VALUES (?, ?, ?, ?, '2026-27', "
                "'2026-10-01')", row)
        con.execute(
            "CREATE TABLE silver_cap_room (CAP_SEASON VARCHAR, "
            "PROJECTED_CAP BIGINT, PROJECTED_TAX BIGINT, "
            "PROJECTED_APRON1 BIGINT, PROJECTED_APRON2 BIGINT)")
        con.execute(
            "INSERT INTO silver_cap_room VALUES "
            "('2026-27', 164961000, 200428000, 209015000, 221686000)")
    finally:
        con.close()
    monkeypatch.setattr(store, "DB_PATH", path)
    monkeypatch.setattr(store, "LOCK_PATH", tmp_path / ".write.lock")
    store.warehouse_tables_cache_clear()
    store.warehouse_pool_clear()
    return path


def _roster(team, payroll, stars):
    rows = [(name, team, None, salary) for name, salary in stars]
    filler = payroll - sum(salary for _, salary in stars)
    rows.append((f"{team} Filler", team, None, filler))
    return rows


def test_under_cap_absorption_and_minimum_outgoing_are_tool_visible(
        monkeypatch, tmp_path):
    from shared.tools import get_trade_check

    _use_salary_warehouse(
        monkeypatch, tmp_path,
        _roster("BOS", 149_961_000, [("Alpha One", 20_000_000)])
        + _roster("MIA", 180_000_000, [("Beta Two", 35_250_000)]))
    out = get_trade_check.invoke({
        "team_a": "BOS", "players_a": "Alpha One",
        "team_b": "MIA", "players_b": "Beta Two",
        "season": "2026-27",
    })
    assert out["ok"] is True
    rows = out["rows"]
    assert rows["legal"] is True, rows["issues"]
    assert out["meta"]["season"] == "2026-27"
    assert out["meta"]["source"]
    assert rows["salary_date"] == "2026-10-01"
    side = rows["team_a"]
    assert side["allowed_in"] == 35_250_000
    assert side["match_rule"] == (
        "cap room plus outgoing salary plus $250k (under the cap)")
    assert side["outgoing_needed"] == 20_000_000


def test_mid_band_minimum_outgoing_is_inverted_exactly(monkeypatch, tmp_path):
    from shared.tools import get_trade_check

    _use_salary_warehouse(
        monkeypatch, tmp_path,
        _roster("BOS", 180_000_000, [("Alpha One", 20_000_000)])
        + _roster("MIA", 180_000_000, [("Beta Two", 29_096_000)]))
    out = get_trade_check.invoke({
        "team_a": "BOS", "players_a": "Alpha One",
        "team_b": "MIA", "players_b": "Beta Two",
        "season": "2026-27",
    })
    assert out["ok"] is True
    rows = out["rows"]
    assert rows["legal"] is True, rows["issues"]
    side = rows["team_a"]
    assert side["allowed_in"] == 29_096_000
    assert side["match_rule"] == (
        "outgoing salary plus $9.096M (below the first apron)")
    assert side["outgoing_needed"] == 20_000_000


def test_trade_value_norm_uses_contract_identity_normalization():
    from shared.tools.league.trade_value import _trade_value_norm

    assert _trade_value_norm("De'Aaron Fox") == _trade_value_norm("DeAaron Fox")
    assert _trade_value_norm("Luka Dončić") == _trade_value_norm("Luka Doncic")


def test_trade_value_joins_advanced_rows_by_player_identity(
        monkeypatch, tmp_path):
    import shared.tools.league as league_mod

    path = _use_salary_warehouse(
        monkeypatch, tmp_path,
        [("De'Aaron Fox", "BOS", 1, 20_000_000),
         ("Beta Two", "NYK", 2, 20_000_000)])
    con = duckdb.connect(str(path))
    try:
        con.execute(
            "CREATE TABLE silver_leaders_pts (PLAYER VARCHAR, TEAM VARCHAR, "
            "GP INTEGER, PTS DOUBLE, REB DOUBLE, AST DOUBLE, STL DOUBLE, "
            "BLK DOUBLE, TOV DOUBLE, FG3M DOUBLE, FG3_PCT DOUBLE, "
            "PLAYER_ID BIGINT, _season VARCHAR)")
        con.execute(
            "INSERT INTO silver_leaders_pts VALUES "
            "('De''Aaron Fox', 'BOS', 40, 1000, 160, 240, 50, 20, 80, "
            "100, 0.40, 1, '2025-26'), "
            "('Beta Two', 'NYK', 40, 1000, 160, 240, 50, 20, 80, "
            "100, 0.40, 2, '2025-26')")
        con.execute(
            "CREATE TABLE silver_advanced (PLAYER_ID BIGINT, "
            "PLAYER_NAME VARCHAR, AGE INTEGER, TS_PCT DOUBLE, USG_PCT DOUBLE, "
            "_season VARCHAR)")
        con.execute(
            "INSERT INTO silver_advanced VALUES "
            "(1, 'DeAaron Fox', 28, 0.61, 0.30, '2025-26'), "
            "(2, 'Beta Two', 27, 0.59, 0.25, '2025-26')")
    finally:
        con.close()
    monkeypatch.setattr(league_mod, "last_completed_season", lambda: "2025-26")
    out = league_mod.get_trade_value.invoke({
        "team_a": "BOS", "players_a": "De'Aaron Fox",
        "team_b": "NYK", "players_b": "Beta Two",
    })
    assert out["ok"] is True, out
    fox = out["rows"]["team_a"]["players"][0]
    assert fox["salary_26_27"] == 20_000_000
    assert fox["age"] == 28
    assert "efficient scorer" in fox["archetypes"]
    assert "high-usage creator" in fox["archetypes"]
