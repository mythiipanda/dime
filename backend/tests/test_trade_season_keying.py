import duckdb

CAP_2026 = {"cap": 164_961_000, "tax": 200_428_000,
            "apron1": 209_015_000, "apron2": 221_686_000}
CAP_2027 = {"cap": 181_457_100, "tax": 220_470_800,
            "apron1": 229_916_500, "apron2": 243_854_600}


def _seed(monkeypatch, tmp_path, salaries, cap_rows=None):
    from shared import store

    path = tmp_path / "season-keying.duckdb"
    con = duckdb.connect(str(path))
    try:
        con.execute(
            "CREATE TABLE silver_salaries (PLAYER_NAME VARCHAR, TEAM VARCHAR, "
            "SALARY_2026_27 INTEGER, SALARY_2027_28 INTEGER, "
            "SALARY_2028_29 INTEGER, _season VARCHAR, _fetched_at VARCHAR)")
        for name, team, salary in salaries:
            con.execute(
                "INSERT INTO silver_salaries VALUES (?, ?, ?, ?, ?, '2026-27', "
                "'2026-10-01')", [name, team, salary, salary, salary])
        con.execute(
            "CREATE TABLE silver_cap_room (CAP_SEASON VARCHAR, "
            "PROJECTED_CAP BIGINT, PROJECTED_TAX BIGINT, "
            "PROJECTED_APRON1 BIGINT, PROJECTED_APRON2 BIGINT)")
        rows = CAP_2026 if cap_rows is None else cap_rows
        for season, lines in rows.items():
            con.execute(
                "INSERT INTO silver_cap_room VALUES (?, ?, ?, ?, ?)",
                [season, lines["cap"], lines["tax"], lines["apron1"],
                 lines["apron2"]])
    finally:
        con.close()
    monkeypatch.setattr(store, "DB_PATH", path)
    monkeypatch.setattr(store, "LOCK_PATH", tmp_path / ".write.lock")
    store.warehouse_tables_cache_clear()
    store.warehouse_pool_clear()


def _roster(team, payroll, stars):
    rows = [(name, team, salary) for name, salary in stars]
    filler = payroll - sum(salary for _, salary in stars)
    per, remainder = divmod(filler, 10)
    filler_rows = [(f"{team} Filler {index}", team, per) for index in range(10)]
    first = filler_rows[0]
    filler_rows[0] = (first[0], first[1], first[2] + remainder)
    return rows + filler_rows


def _boundary_rosters(payroll):
    return (_roster("BOS", payroll,
                    [("Alpha One", 15_000_000), ("Beta Two", 15_000_000)])
            + _roster("MIA", 150_000_000, [("Gamma Three", 30_000_000)]))


def _boundary_trade(season):
    return {
        "legs": '[{"from":"BOS","to":"MIA",'
                '"players":"Alpha One, Beta Two"},'
                '{"from":"MIA","to":"BOS","players":"Gamma Three"}]',
        "season": season,
    }


def _team(out, team):
    return next(row for row in out["rows"] if row["team"] == team)


def test_trade_legality_uses_projected_2027_28_apron2_exact_boundary(
        monkeypatch, tmp_path):
    from shared.tools import get_trade_legality

    _seed(monkeypatch, tmp_path, _boundary_rosters(CAP_2027["apron2"]),
          {"2026-27": CAP_2026, "2027-28": CAP_2027})
    out = get_trade_legality.invoke(_boundary_trade("2027-28"))
    assert out["ok"] is True
    bos = _team(out, "BOS")
    assert bos["payroll_after"] == 243_854_600
    assert bos["over_apron2"] is False
    assert bos["room_apron2"] == 0
    assert bos["hard_cap_violations"] == []
    assert out["legal"] is True, out["issues"]
    assert out["meta"]["cap_lines"]["apron2"] == 243_854_600
    assert out["meta"]["cap_lines_source"] == "silver_cap_room"


def test_trade_legality_rejects_one_dollar_over_projected_2027_28_apron2(
        monkeypatch, tmp_path):
    from shared.tools import get_trade_legality

    _seed(monkeypatch, tmp_path, _boundary_rosters(CAP_2027["apron2"] + 1),
          {"2026-27": CAP_2026, "2027-28": CAP_2027})
    out = get_trade_legality.invoke(_boundary_trade("2027-28"))
    assert out["ok"] is True
    bos = _team(out, "BOS")
    assert bos["payroll_after"] == 243_854_601
    assert bos["over_apron2"] is True
    assert bos["room_apron2"] == -1
    assert bos["hard_cap_violations"] == ["second apron"]
    assert out["legal"] is False
    assert any("$243,854,600" in issue for issue in out["issues"])


def test_trade_legality_keeps_2026_27_apron2_exact_boundary(
        monkeypatch, tmp_path):
    from shared.tools import get_trade_legality

    _seed(monkeypatch, tmp_path, _boundary_rosters(CAP_2026["apron2"]),
          {"2026-27": CAP_2026, "2027-28": CAP_2027})
    out = get_trade_legality.invoke(_boundary_trade("2026-27"))
    assert out["ok"] is True
    bos = _team(out, "BOS")
    assert bos["payroll_after"] == 221_686_000
    assert bos["over_apron2"] is False
    assert bos["room_apron2"] == 0
    assert out["legal"] is True, out["issues"]
    assert out["meta"]["cap_lines"]["apron2"] == 221_686_000


def test_trade_legality_missing_cap_line_season_errors_without_fallback(
        monkeypatch, tmp_path):
    from shared.tools import get_trade_legality

    _seed(monkeypatch, tmp_path, _boundary_rosters(150_000_000),
          {"2026-27": CAP_2026, "2027-28": CAP_2027})
    out = get_trade_legality.invoke(_boundary_trade("2028-29"))
    assert out["ok"] is False
    assert "cap-line data unavailable for 2028-29" in out["error"]
    assert "silver_cap_history" in out["error"]
    assert "silver_cap_room" in out["error"]


def test_cap_line_lookup_prefers_exact_history_before_projection():
    from shared.tools.league.cap_lines import resolve_cap_lines

    con = duckdb.connect(":memory:")
    try:
        con.execute(
            "CREATE TABLE silver_cap_history (season INTEGER, season_label VARCHAR, "
            "salary_cap DOUBLE, luxury_tax DOUBLE, apron_1 DOUBLE, apron_2 DOUBLE)")
        con.execute(
            "INSERT INTO silver_cap_history VALUES "
            "(2026, '2025-26', 100000000, 110000000, 120000000, 130000000)")
        con.execute(
            "CREATE TABLE silver_cap_room (CAP_SEASON VARCHAR, PROJECTED_CAP BIGINT, "
            "PROJECTED_TAX BIGINT, PROJECTED_APRON1 BIGINT, PROJECTED_APRON2 BIGINT)")
        con.execute(
            "INSERT INTO silver_cap_room VALUES "
            "('2025-26', 101000000, 111000000, 121000000, 131000000)")
        resolved = resolve_cap_lines(con, "2025-26")
    finally:
        con.close()
    assert resolved["ok"] is True
    assert resolved["source"] == "silver_cap_history"
    assert resolved["projected"] is False
    assert resolved["exact"] is True
    assert resolved["lines"] == {"cap": 100_000_000, "tax": 110_000_000,
                                 "apron1": 120_000_000, "apron2": 130_000_000}


def test_trade_check_uses_projected_2027_28_lines(monkeypatch, tmp_path):
    from shared.tools import get_trade_check

    _seed(monkeypatch, tmp_path, _boundary_rosters(CAP_2027["apron2"]),
          {"2026-27": CAP_2026, "2027-28": CAP_2027})
    out = get_trade_check.invoke({
        "team_a": "BOS", "players_a": "Alpha One, Beta Two",
        "team_b": "MIA", "players_b": "Gamma Three",
        "season": "2027-28"})
    assert out["ok"] is True
    assert out["meta"]["cap_lines"]["apron2"] == 243_854_600
    assert out["rows"]["team_a"]["over_apron2"] is False
    assert out["rows"]["team_a"]["room_apron2"] == 0


def test_cap_table_uses_projected_lines_for_requested_season(
        monkeypatch, tmp_path):
    from shared.tools.league import get_cap_table

    _seed(monkeypatch, tmp_path, _boundary_rosters(CAP_2027["apron2"]),
          {"2026-27": CAP_2026, "2027-28": CAP_2027})
    out = get_cap_table.invoke({"season": "2027-28"})
    assert out["ok"] is True
    assert out["meta"]["season"] == "2027-28"
    assert out["meta"]["cap_lines_source"] == "silver_cap_room"
    assert out["meta"]["apron2"] == 243_854_600
    bos = next(row for row in out["rows"] if row["team"] == "BOS")
    assert bos["over_apron2"] is False
    assert bos["room_under_apron2"] == 0


def test_cap_table_missing_cap_line_season_errors_without_fallback(
        monkeypatch, tmp_path):
    from shared.tools.league import get_cap_table

    _seed(monkeypatch, tmp_path, _boundary_rosters(150_000_000),
          {"2026-27": CAP_2026, "2027-28": CAP_2027})
    out = get_cap_table.invoke({"season": "2028-29"})
    assert out["ok"] is False
    assert out["reason"] == "cap_lines_unavailable"
    assert "cap-line data unavailable for 2028-29" in out["error"]
