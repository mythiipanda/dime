import duckdb
import pytest


def _seed(monkeypatch, tmp_path, salaries, picks=None):
    from shared import store

    path = tmp_path / "legality.duckdb"
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
        if picks is not None:
            con.execute(
                "CREATE TABLE silver_future_picks (DRAFT_YEAR INTEGER, "
                "ROUND INTEGER, ORIG_TEAM VARCHAR, STATUS VARCHAR, "
                "HELD_BY VARCHAR, PROTECTION VARCHAR, POOLED VARCHAR, "
                "CONDITIONAL VARCHAR, SUMMARY VARCHAR, LAST_EDITED VARCHAR, "
                "_season VARCHAR)")
            for row in picks:
                con.execute(
                    "INSERT INTO silver_future_picks VALUES (?, ?, ?, ?, ?, "
                    "'', '', '', '', '', '2026-27')", list(row))
    finally:
        con.close()
    monkeypatch.setattr(store, "DB_PATH", path)
    monkeypatch.setattr(store, "LOCK_PATH", tmp_path / ".write.lock")
    store.warehouse_tables_cache_clear()
    store.warehouse_pool_clear()


def _roster(team, base_salary, stars):
    rows = [(name, team, salary) for name, salary in stars]
    filler = base_salary - sum(s for _, s in stars)
    per = filler // 10
    rows += [(f"{team} Filler {i}", team, per) for i in range(10)]
    return rows


def _all_firsts(team):
    return [(y, 1, team, "own", team) for y in range(2027, 2034)]


def test_trade_legality_two_team_balanced(monkeypatch, tmp_path):
    from shared.tools import get_trade_legality
    _seed(monkeypatch, tmp_path,
          _roster("BOS", 150_000_000, [("Alpha One", 30_000_000)])
          + _roster("MIA", 150_000_000, [("Beta Two", 28_000_000)]))
    out = get_trade_legality.invoke({
        "legs": '[{"from":"BOS","to":"MIA","players":"Alpha One"},'
                '{"from":"MIA","to":"BOS","players":"Beta Two"}]',
        "season": "2026-27",
    })
    assert out["ok"] is True
    assert out["legal"] is True, out["issues"]
    assert len(out["rows"]) == 2


def test_trade_legality_rejects_unmatched_takeback(monkeypatch, tmp_path):
    from shared.tools import get_trade_legality
    _seed(monkeypatch, tmp_path,
          _roster("BOS", 150_000_000, [("Alpha One", 30_000_000)])
          + _roster("MIA", 150_000_000, [("Beta Two", 5_000_000)]))
    out = get_trade_legality.invoke({
        "legs": '[{"from":"MIA","to":"BOS","players":"Beta Two"},'
                '{"from":"BOS","to":"MIA","players":"Alpha One"}]',
        "season": "2026-27",
    })
    assert out["ok"] is True
    assert out["legal"] is False
    assert any("takes back too much" in i for i in out["issues"])


def test_trade_legality_stepien_consecutive_firsts(monkeypatch, tmp_path):
    from shared.tools import get_trade_legality
    _seed(monkeypatch, tmp_path,
          _roster("BOS", 150_000_000, [("Alpha One", 30_000_000)])
          + _roster("MIA", 150_000_000, [("Beta Two", 30_000_000)]),
          picks=_all_firsts("BOS") + _all_firsts("MIA"))
    out = get_trade_legality.invoke({
        "legs": '[{"from":"BOS","to":"MIA","players":"Alpha One",'
                '"picks":[{"year":2028,"round":1},{"year":2029,"round":1}]},'
                '{"from":"MIA","to":"BOS","players":"Beta Two"}]',
        "season": "2026-27",
    })
    assert out["ok"] is True
    assert out["legal"] is False
    assert any("Stepien" in i for i in out["issues"])


def test_trade_legality_pick_beyond_seven_years(monkeypatch, tmp_path):
    from shared.tools import get_trade_legality
    _seed(monkeypatch, tmp_path,
          _roster("BOS", 150_000_000, [("Alpha One", 30_000_000)])
          + _roster("MIA", 150_000_000, [("Beta Two", 30_000_000)]))
    out = get_trade_legality.invoke({
        "legs": '[{"from":"BOS","to":"MIA","players":"Alpha One",'
                '"picks":[{"year":2034,"round":1}]},'
                '{"from":"MIA","to":"BOS","players":"Beta Two"}]',
        "season": "2026-27",
    })
    assert out["ok"] is True
    assert out["legal"] is False
    assert any("7 drafts out" in i for i in out["issues"])


def test_trade_legality_second_apron_aggregation_ban(monkeypatch, tmp_path):
    from shared.tools import get_trade_legality
    _seed(monkeypatch, tmp_path,
          _roster("PHX", 240_000_000,
                  [("Alpha One", 5_000_000), ("Beta Two", 5_000_000)])
          + _roster("MIA", 150_000_000, [("Gamma Three", 10_000_000)]))
    out = get_trade_legality.invoke({
        "legs": '[{"from":"PHX","to":"MIA",'
                '"players":"Alpha One, Beta Two"},'
                '{"from":"MIA","to":"PHX","players":"Gamma Three"}]',
        "season": "2026-27",
    })
    assert out["ok"] is True
    assert out["legal"] is False
    assert any("aggregate" in i for i in out["issues"])


def test_trade_legality_three_team(monkeypatch, tmp_path):
    from shared.tools import get_trade_legality
    _seed(monkeypatch, tmp_path,
          _roster("BOS", 150_000_000, [("Alpha One", 30_000_000)])
          + _roster("MIA", 150_000_000, [("Beta Two", 30_000_000)])
          + _roster("DEN", 150_000_000, [("Gamma Three", 30_000_000)]))
    out = get_trade_legality.invoke({
        "legs": '[{"from":"BOS","to":"MIA","players":"Alpha One"},'
                '{"from":"MIA","to":"DEN","players":"Beta Two"},'
                '{"from":"DEN","to":"BOS","players":"Gamma Three"}]',
        "season": "2026-27",
    })
    assert out["ok"] is True
    assert len(out["rows"]) == 3
    assert out["legal"] is True, out["issues"]


def _snt_legality(monkeypatch, tmp_path, years):
    from shared.tools import get_trade_legality
    _seed(monkeypatch, tmp_path,
          _roster("BOS", 140_000_000, [("Alpha One", 10_000_000)])
          + _roster("MIA", 140_000_000, [("Beta Two", 15_000_000)]))
    return get_trade_legality.invoke({
        "legs": '[{"from":"BOS","to":"MIA","players":"Alpha One"},'
                '{"from":"MIA","to":"BOS","players":"Beta Two"}]',
        "sign_and_trade": '{"player":"Alpha One","new_salary":15000000,'
                          f'"years":{years}}}',
        "season": "2026-27",
    })


def test_trade_legality_snt_minimum_years(monkeypatch, tmp_path):
    out = _snt_legality(monkeypatch, tmp_path, 2)
    assert out["ok"] is True
    assert out["legal"] is False
    assert any("3 seasons" in i for i in out["issues"])


def test_trade_legality_snt_maximum_years(monkeypatch, tmp_path):
    out = _snt_legality(monkeypatch, tmp_path, 5)
    assert out["ok"] is True
    assert out["legal"] is False
    assert any("cannot exceed 4 seasons" in i for i in out["issues"])


def test_trade_legality_snt_four_years_remain_valid(monkeypatch, tmp_path):
    out = _snt_legality(monkeypatch, tmp_path, 4)
    assert out["ok"] is True
    assert out["legal"] is True, out["issues"]


@pytest.mark.parametrize(("payload", "message"), [
    ('[]', "JSON object"),
    ('{"player":"Alpha One","years":3}', "missing new_salary"),
    ('{"player":"Alpha One","new_salary":0,"years":3}', "positive integer"),
    ('{"player":"Alpha One","new_salary":-1,"years":3}', "positive integer"),
    ('{"player":"Alpha One","new_salary":15000000.5,"years":3}',
     "positive integer"),
    ('{"player":"Alpha One","new_salary":15000000,"years":0}',
     "positive integer"),
])
def test_trade_legality_snt_input_validation(payload, message):
    from shared.tools import get_trade_legality
    out = get_trade_legality.invoke({
        "legs": '[{"from":"BOS","to":"MIA","players":"Alpha One"},'
                '{"from":"MIA","to":"BOS","players":"Beta Two"}]',
        "sign_and_trade": payload,
        "season": "2026-27",
    })
    assert out["ok"] is False
    assert message in out["error"]


def test_trade_legality_same_team_leg_rejected():
    from shared.tools import get_trade_legality
    out = get_trade_legality.invoke({
        "legs": '[{"from":"BOS","to":"BOS","players":"Alpha One"}]'})
    assert out["ok"] is False
    assert "same team" in out["error"]


def test_trade_legality_bad_legs_json():
    from shared.tools import get_trade_legality
    out = get_trade_legality.invoke({"legs": "not json"})
    assert out["ok"] is False
    assert "JSON" in out["error"]


def test_stepien_issue_windows():
    from shared.tools.league.trade_legality import _stepien_issues
    assert _stepien_issues("BOS", set(range(2027, 2034)), 2026) == []
    assert _stepien_issues("BOS", {2027, 2029, 2031, 2033}, 2026) == []
    gaps = _stepien_issues("BOS", {2027, 2030, 2031, 2032, 2033}, 2026)
    assert len(gaps) == 1 and "2028" in gaps[0] and "2029" in gaps[0]


def test_frozen_pick_excludes_final_tradable_draft(monkeypatch, tmp_path):
    from shared.tools import get_trade_legality
    _seed(monkeypatch, tmp_path,
          _roster("BOS", 230_000_000, [("Alpha One", 30_000_000)])
          + _roster("MIA", 230_000_000, [("Beta Two", 30_000_000)]))
    out = get_trade_legality.invoke({
        "legs": '[{"from":"BOS","to":"MIA","players":"Alpha One",'
                '"picks":[{"year":2033,"round":1}]},'
                '{"from":"MIA","to":"BOS","players":"Beta Two"}]',
        "season": "2026-27",
    })
    assert out["ok"] is True
    assert not any("frozen" in issue for issue in out["issues"])
    assert out["legal"] is True, out["issues"]


def test_frozen_pick_includes_first_draft_after_seventh_season(
        monkeypatch, tmp_path):
    from shared.tools import get_trade_legality
    _seed(monkeypatch, tmp_path,
          _roster("BOS", 230_000_000, [("Alpha One", 30_000_000)])
          + _roster("MIA", 230_000_000, [("Beta Two", 30_000_000)]))
    out = get_trade_legality.invoke({
        "legs": '[{"from":"BOS","to":"MIA","players":"Alpha One",'
                '"picks":[{"year":2034,"round":1}]},'
                '{"from":"MIA","to":"BOS","players":"Beta Two"}]',
        "season": "2026-27",
    })
    assert out["ok"] is True
    assert any("2034 first-round pick is frozen" in issue
               for issue in out["issues"])
    assert any("2034 pick - more than 7 drafts out" in issue
               for issue in out["issues"])
