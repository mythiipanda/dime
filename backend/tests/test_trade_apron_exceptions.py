import duckdb


def _seed(monkeypatch, tmp_path, salaries):
    from shared import store

    path = tmp_path / "apron_exceptions.duckdb"
    con = duckdb.connect(str(path))
    try:
        con.execute(
            "CREATE TABLE silver_salaries (PLAYER_NAME VARCHAR, "
            "TEAM VARCHAR, SALARY_2026_27 INTEGER, _season VARCHAR, "
            "_fetched_at VARCHAR)")
        for name, team, salary in salaries:
            con.execute(
                "INSERT INTO silver_salaries VALUES (?, ?, ?, '2026-27', "
                "'2026-10-01')", [name, team, salary])
    finally:
        con.close()
    monkeypatch.setattr(store, "DB_PATH", path)
    monkeypatch.setattr(store, "LOCK_PATH", tmp_path / ".write.lock")
    store.warehouse_tables_cache_clear()
    store.warehouse_pool_clear()


def _roster(team, payroll, stars):
    rows = [(name, team, salary) for name, salary in stars]
    filler = payroll - sum(salary for _, salary in stars)
    per = filler // 10
    rows += [(f"{team} Filler {i}", team, per) for i in range(10)]
    return rows


def _team_rows(out):
    return {row["team"]: row for row in out["rows"]}


def test_first_apron_matching_is_dollar_for_dollar_and_ignores_cap_room():
    from shared.tools.league.cba_cap import _allowed_incoming, _outgoing_needed

    allow, rule = _allowed_incoming(20_000_000, True, 10_000_000)
    assert allow == 20_000_000
    assert rule == "100% (above the first apron)"
    assert _outgoing_needed(20_000_000, True, 10_000_000) == 20_000_000


def test_high_band_inverse_is_continuous_at_29m_boundary():
    from shared.tools.league.cba_cap import _allowed_incoming, _outgoing_needed

    assert _allowed_incoming(29_000_000, False, 0)[0] == 36_500_000
    assert _allowed_incoming(29_000_001, False, 0)[0] == 36_500_001
    assert _outgoing_needed(36_500_000, False, 0) == 29_000_000
    assert _outgoing_needed(36_500_001, False, 0) == 29_000_001


def test_crossing_first_apron_uses_post_trade_strict_matching(monkeypatch, tmp_path):
    from shared.tools import get_trade_legality

    _seed(monkeypatch, tmp_path,
          _roster("BOS", 205_000_000, [("Alpha One", 25_000_000)])
          + _roster("MIA", 150_000_000, [("Beta Two", 30_000_000)]))
    out = get_trade_legality.invoke({
        "legs": '[{"from":"BOS","to":"MIA","players":"Alpha One"},'
                '{"from":"MIA","to":"BOS","players":"Beta Two"}]',
        "season": "2026-27",
    })
    assert out["ok"] is True
    assert out["legal"] is False
    rows = _team_rows(out)
    bos = rows["BOS"]
    assert bos["payroll_before"] == 205_000_000
    assert bos["payroll_after"] == 210_000_000
    assert bos["over_apron1_before"] is False
    assert bos["over_apron1"] is True
    assert bos["allowed_incoming"] == 25_000_000
    assert bos["match_rule"] == "100% (above the first apron)"
    assert any("BOS takes back too much" in issue for issue in out["issues"])


def test_aggregation_below_second_apron_is_legal_hard_cap_trigger(
        monkeypatch, tmp_path):
    from shared.tools import get_trade_legality

    _seed(monkeypatch, tmp_path,
          _roster("BOS", 190_000_000,
                  [("Alpha One", 15_000_000), ("Beta Two", 15_000_000)])
          + _roster("MIA", 150_000_000, [("Gamma Three", 25_000_000)]))
    out = get_trade_legality.invoke({
        "legs": '[{"from":"BOS","to":"MIA",'
                '"players":"Alpha One, Beta Two"},'
                '{"from":"MIA","to":"BOS","players":"Gamma Three"}]',
        "season": "2026-27",
    })
    assert out["ok"] is True
    assert out["legal"] is True, out["issues"]
    rows = _team_rows(out)
    assert rows["BOS"]["payroll_after"] == 185_000_000
    assert rows["MIA"]["payroll_after"] == 155_000_000
    assert rows["BOS"]["aggregates"] is True
    assert rows["BOS"]["hard_cap"] == "second apron"
    assert rows["BOS"]["matching_ok"] is True
    assert rows["MIA"]["matching_ok"] is True


def test_sign_and_trade_byc_exact_match_stays_legal(monkeypatch, tmp_path):
    from shared.tools import get_trade_legality

    _seed(monkeypatch, tmp_path,
          _roster("BOS", 170_000_000, [("Alpha One", 10_000_000)])
          + _roster("MIA", 170_000_000, [("Beta Two", 22_500_000)]))
    out = get_trade_legality.invoke({
        "legs": '[{"from":"BOS","to":"MIA","players":"Alpha One"},'
                '{"from":"MIA","to":"BOS","players":"Beta Two"}]',
        "sign_and_trade": '{"player":"Alpha One","new_salary":30000000,'
                          '"years":3}',
        "season": "2026-27",
    })
    assert out["ok"] is True
    assert out["legal"] is True, out["issues"]
    rows = _team_rows(out)
    bos = rows["BOS"]
    mia = rows["MIA"]
    assert bos["outgoing"] == 10_000_000
    assert bos["outgoing_matching"] == 15_000_000
    assert bos["byc_note"] == (
        "Alpha One counts at $15,000,000 outgoing under base-year compensation")
    assert bos["allowed_incoming"] == 22_500_000
    assert bos["matching_ok"] is True
    assert mia["incoming"] == 30_000_000
    assert mia["allowed_incoming"] == 30_000_000
    assert mia["matching_ok"] is True
    assert mia["hard_cap"] == "first apron"


def test_sign_and_trade_receiver_cannot_finish_above_first_apron(
        monkeypatch, tmp_path):
    from shared.tools import get_trade_legality

    _seed(monkeypatch, tmp_path,
          _roster("BOS", 170_000_000, [("Alpha One", 25_000_000)])
          + _roster("MIA", 215_000_000, [("Beta Two", 30_000_000)]))
    out = get_trade_legality.invoke({
        "legs": '[{"from":"BOS","to":"MIA","players":"Alpha One"},'
                '{"from":"MIA","to":"BOS","players":"Beta Two"}]',
        "sign_and_trade": '{"player":"Alpha One","new_salary":30000000,'
                          '"years":3}',
        "season": "2026-27",
    })
    assert out["ok"] is True
    assert out["legal"] is False
    rows = _team_rows(out)
    assert rows["MIA"]["matching_ok"] is True
    assert rows["MIA"]["payroll_after"] == 215_000_000
    assert rows["MIA"]["hard_cap"] == "first apron"
    assert any("hard-capped at the first apron" in issue
               for issue in out["issues"])
    assert not any("takes back too much" in issue for issue in out["issues"])


def test_second_apron_cash_and_tpe_combination_is_rejected(
        monkeypatch, tmp_path):
    from shared.tools import get_trade_legality

    _seed(monkeypatch, tmp_path,
          _roster("BOS", 230_000_000, [("Alpha One", 20_000_000)])
          + _roster("MIA", 150_000_000, [("Beta Two", 30_000_000)]))
    out = get_trade_legality.invoke({
        "legs": '[{"from":"BOS","to":"MIA","players":"Alpha One"},'
                '{"from":"MIA","to":"BOS","players":"Beta Two"}]',
        "cash": '[{"from":"BOS","to":"MIA","amount":1000000}]',
        "tpe": '[{"team":"BOS","amount":10000000}]',
        "season": "2026-27",
    })
    assert out["ok"] is True
    assert out["legal"] is False
    rows = _team_rows(out)
    assert rows["BOS"]["payroll_after"] == 240_000_000
    assert rows["BOS"]["cash_out"] == 1_000_000
    assert rows["BOS"]["tpe_used"] == 10_000_000
    assert any("cannot send cash above the second apron" in issue
               for issue in out["issues"])
    assert any("cannot use a traded player exception above the second apron" in issue
               for issue in out["issues"])
    assert any("hard-capped at the second apron" in issue
               for issue in out["issues"])


def test_cap_scenario_second_apron_freezes_seventh_following_draft(
        monkeypatch, tmp_path):
    from shared.tools import get_cap_scenario

    _seed(monkeypatch, tmp_path,
          _roster("BOS", 230_000_000, [("Alpha One", 30_000_000)]))
    out = get_cap_scenario.invoke({
        "team": "BOS",
        "signings": "Depth Piece=1m",
        "season": "2026-27",
    })
    assert out["ok"] is True
    assert out["summary"]["over_apron2"] is True
    assert any(row["threshold"] == "second apron"
               and "2034 first-round pick is frozen" in row["rule"]
               for row in out["restrictions"])
