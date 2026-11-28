import duckdb
import pytest


def _write_vintaged_picks(con, picks):
    con.execute(
        "CREATE TABLE silver_future_picks (DRAFT_YEAR INTEGER, "
        "ROUND INTEGER, ORIG_TEAM VARCHAR, STATUS VARCHAR, "
        "HELD_BY VARCHAR, PROTECTION VARCHAR, POOLED BOOLEAN, "
        "CONDITIONAL BOOLEAN, SUMMARY VARCHAR, LAST_EDITED VARCHAR, "
        "_source VARCHAR, _season VARCHAR, _fetched_at VARCHAR, "
        "_entity VARCHAR)")
    for row in picks:
        season = row[5] if len(row) > 5 else "2026-27"
        con.execute(
            "INSERT INTO silver_future_picks VALUES (?, ?, ?, ?, ?, "
            "'', false, false, '', '', 'thedraftday:picks', ?, "
            "'2026-10-01T00:00:00+00:00', '')",
            list(row[:5]) + [season])


def _write_legacy_picks(con, picks):
    con.execute(
        "CREATE TABLE silver_future_picks (DRAFT_YEAR INTEGER, "
        "ROUND INTEGER, ORIG_TEAM VARCHAR, STATUS VARCHAR, "
        "HELD_BY VARCHAR, PROTECTION VARCHAR, POOLED BOOLEAN, "
        "CONDITIONAL BOOLEAN, SUMMARY VARCHAR, LAST_EDITED VARCHAR)")
    for row in picks:
        con.execute(
            "INSERT INTO silver_future_picks VALUES (?, ?, ?, ?, ?, "
            "'', false, false, '', '')", list(row[:5]))


def _seed(monkeypatch, tmp_path, salaries, picks=None, legacy_picks=False):
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
        con.execute(
            "CREATE TABLE silver_cap_room (CAP_SEASON VARCHAR, "
            "PROJECTED_CAP BIGINT, PROJECTED_TAX BIGINT, "
            "PROJECTED_APRON1 BIGINT, PROJECTED_APRON2 BIGINT)")
        con.execute(
            "INSERT INTO silver_cap_room VALUES "
            "('2026-27', 164961000, 200428000, 209015000, 221686000)")
        if picks is not None:
            if legacy_picks:
                _write_legacy_picks(con, picks)
            else:
                _write_vintaged_picks(con, picks)
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


def test_trade_legality_surfaces_conditional_tpe_creation(monkeypatch, tmp_path):
    from shared.tools import get_trade_legality
    _seed(monkeypatch, tmp_path,
          _roster("BOS", 200_000_000, [("Alpha One", 30_000_000)])
          + _roster("MIA", 130_000_000, [("Beta Two", 20_000_000)]))
    out = get_trade_legality.invoke({
        "legs": '[{"from":"BOS","to":"MIA","players":"Alpha One"},'
                '{"from":"MIA","to":"BOS","players":"Beta Two"}]',
        "season": "2026-27",
    })
    bos = next(r for r in out["rows"] if r["team"] == "BOS")
    creation = bos.get("tpe_creation")
    assert creation is not None, "BOS sends out 30M and takes back 20M — creation must surface"
    assert creation["amount"] == 10_000_000
    assert "non-simultaneous" in creation["condition"]
    assert "forfeit" in creation["condition"]
    mia = next(r for r in out["rows"] if r["team"] == "MIA")
    assert mia.get("tpe_creation") is None


def test_trade_legality_no_creation_when_balanced_or_under_cap(monkeypatch, tmp_path):
    from shared.tools import get_trade_legality
    _seed(monkeypatch, tmp_path,
          _roster("BOS", 150_000_000, [("Alpha One", 30_000_000)])
          + _roster("MIA", 150_000_000, [("Beta Two", 28_000_000)]))
    out = get_trade_legality.invoke({
        "legs": '[{"from":"BOS","to":"MIA","players":"Alpha One"},'
                '{"from":"MIA","to":"BOS","players":"Beta Two"}]',
        "season": "2026-27",
    })
    for row in out["rows"]:
        assert row.get("tpe_creation") is None


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


def _balanced_pick_trade(monkeypatch, tmp_path, picks, declared_picks,
                         pick_sender="BOS", legacy_picks=False):
    from shared.tools import get_trade_legality
    _seed(monkeypatch, tmp_path,
          _roster("BOS", 150_000_000, [("Alpha One", 30_000_000)])
          + _roster("MIA", 150_000_000, [("Beta Two", 30_000_000)]),
          picks=picks, legacy_picks=legacy_picks)
    if pick_sender == "BOS":
        legs = ('[{"from":"BOS","to":"MIA","players":"Alpha One",'
                f'"picks":{declared_picks}}},'
                '{"from":"MIA","to":"BOS","players":"Beta Two"}]')
    else:
        legs = ('[{"from":"MIA","to":"BOS","players":"Beta Two",'
                f'"picks":{declared_picks}}},'
                '{"from":"BOS","to":"MIA","players":"Alpha One"}]')
    return get_trade_legality.invoke({
        "legs": legs,
        "season": "2026-27",
    })


def test_trade_legality_owned_pick_remains_valid(monkeypatch, tmp_path):
    out = _balanced_pick_trade(
        monkeypatch, tmp_path, _all_firsts("BOS") + _all_firsts("MIA"),
        '[{"year":2028,"round":1}]')
    assert out["ok"] is True
    assert out["legal"] is True, out["issues"]
    check = next(row for row in out["checks"]
                 if row["rule"] == "pick ownership")
    assert check["checked"] is True
    limitation = ("same-year multiple firsts are validated only at year grain "
                  "because the leg input does not identify the original team "
                  "of a same-year first")
    assert "pooled/conditional picks are not modeled" in check["note"]
    assert limitation in check["note"]
    assert "pooled/conditional picks are not modeled" in out["meta"]["disclaimer"]
    assert limitation in out["meta"]["disclaimer"]
    assert out["meta"]["pick_vintage_basis"] == "warehouse_vintage"
    assert out["meta"]["pick_vintage_season"] == "2026-27"


def test_trade_legality_unvintaged_pick_inventory_falls_back(
        monkeypatch, tmp_path):
    out = _balanced_pick_trade(
        monkeypatch, tmp_path, _all_firsts("BOS") + _all_firsts("MIA"),
        '[{"year":2028,"round":1}]', legacy_picks=True)
    assert out["ok"] is True
    assert out["legal"] is True, out["issues"]
    assert out["meta"]["pick_vintage_basis"] == "unvintaged_fallback"
    assert "pick_vintage_season" not in out["meta"]


def test_trade_legality_rejects_pick_team_does_not_own(
        monkeypatch, tmp_path):
    bos_picks = [(y, 1, "BOS", "own", "BOS")
                 for y in range(2027, 2034) if y != 2028]
    bos_picks.append((2028, 1, "BOS", "traded", "MIA"))
    out = _balanced_pick_trade(
        monkeypatch, tmp_path, bos_picks + _all_firsts("MIA"),
        '[{"year":2028,"round":1}]')
    assert out["ok"] is False
    assert ("cannot declare a 2028 first-round pick it does not own"
            in out["error"])


def test_trade_legality_latest_pick_vintage_rejects_stale_own(
        monkeypatch, tmp_path):
    bos_picks = [(y, 1, "BOS", "own", "BOS")
                 for y in range(2027, 2034) if y != 2028]
    bos_picks += [
        (2028, 1, "BOS", "own", "BOS", "2025-26"),
        (2028, 1, "BOS", "traded", "MIA", "2026-27"),
    ]
    out = _balanced_pick_trade(
        monkeypatch, tmp_path, bos_picks + _all_firsts("MIA"),
        '[{"year":2028,"round":1}]')
    assert out["ok"] is False
    assert ("BOS cannot declare a 2028 first-round pick it does not own"
            in out["error"])


def test_trade_legality_latest_pick_vintage_rejects_stale_traded_holder(
        monkeypatch, tmp_path):
    mia_picks = [(y, 1, "MIA", "own", "MIA")
                 for y in range(2027, 2034) if y != 2028]
    mia_picks.append((2028, 1, "MIA", "traded", "DEN", "2026-27"))
    picks = (_all_firsts("BOS") + mia_picks
             + [(2028, 1, "BOS", "traded", "MIA", "2025-26")])
    out = _balanced_pick_trade(
        monkeypatch, tmp_path, picks, '[{"year":2028,"round":1}]',
        pick_sender="MIA")
    assert out["ok"] is False
    assert ("MIA cannot declare a 2028 first-round pick it does not own"
            in out["error"])


def test_trade_legality_rejects_duplicate_pick_without_inventory(
        monkeypatch, tmp_path):
    out = _balanced_pick_trade(
        monkeypatch, tmp_path, None,
        '[{"year":2028,"round":1},{"year":2028,"round":1}]')
    assert out["ok"] is False
    assert "more than once" in out["error"]


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


def test_trade_legality_snt_discloses_unvalidated_first_year_guarantee(
        monkeypatch, tmp_path):
    out = _snt_legality(monkeypatch, tmp_path, 3)
    disclosure = ("first-season full guarantee required by 2023 CBA Art. VII "
                  "sec. 8(e)(1) is not validated")
    assert out["ok"] is True
    assert out["legal"] is True, out["issues"]
    snt_check = next(check for check in out["checks"]
                     if check["rule"] == "sign-and-trade")
    assert disclosure in snt_check["note"]
    assert disclosure in out["meta"]["disclaimer"]


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


def _cash_legality(monkeypatch, tmp_path, cash):
    from shared.tools import get_trade_legality
    _seed(monkeypatch, tmp_path,
          _roster("BOS", 150_000_000, [("Alpha One", 30_000_000)])
          + _roster("MIA", 150_000_000, [("Beta Two", 30_000_000)]))
    return get_trade_legality.invoke({
        "legs": '[{"from":"BOS","to":"MIA","players":"Alpha One"},'
                '{"from":"MIA","to":"BOS","players":"Beta Two"}]',
        "cash": cash,
        "season": "2026-27",
    })


def test_trade_legality_valid_cash_between_parties(monkeypatch, tmp_path):
    out = _cash_legality(
        monkeypatch, tmp_path,
        '[{"from":"BOS","to":"MIA","amount":1000000}]')
    assert out["ok"] is True
    assert out["legal"] is True, out["issues"]
    rows = {row["team"]: row for row in out["rows"]}
    assert rows["BOS"]["cash_out"] == 1_000_000
    assert rows["MIA"]["cash_in"] == 1_000_000


@pytest.mark.parametrize("amount", [-1_000_000, 0])
def test_trade_legality_rejects_nonpositive_cash(
        monkeypatch, tmp_path, amount):
    out = _cash_legality(
        monkeypatch, tmp_path,
        f'[{{"from":"BOS","to":"MIA","amount":{amount}}}]')
    assert out["ok"] is False
    assert "positive integer" in out["error"]


def test_trade_legality_rejects_cash_outside_trade_parties(
        monkeypatch, tmp_path):
    out = _cash_legality(
        monkeypatch, tmp_path,
        '[{"from":"LAL","to":"BOS","amount":1000000}]')
    assert out["ok"] is False
    assert "not a trade party" in out["error"]


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


def test_stepien_zero_pick_trade_passes_for_previolating_team(monkeypatch, tmp_path):
    from shared.tools import get_trade_legality
    bos_inventory = [(y, 1, "BOS", "own", "BOS") for y in range(2030, 2034)]
    _seed(monkeypatch, tmp_path,
          _roster("BOS", 150_000_000, [("Alpha One", 30_000_000)])
          + _roster("MIA", 150_000_000, [("Beta Two", 30_000_000)]),
          picks=bos_inventory + _all_firsts("MIA"))
    out = get_trade_legality.invoke({
        "legs": '[{"from":"BOS","to":"MIA","players":"Alpha One"},'
                '{"from":"MIA","to":"BOS","players":"Beta Two"}]',
        "season": "2026-27",
    })
    assert out["ok"] is True
    assert not any("Stepien" in i for i in out["issues"]), out["issues"]


def test_stepien_firsts_trade_fails_for_previolating_team(monkeypatch, tmp_path):
    from shared.tools import get_trade_legality
    bos_inventory = [(y, 1, "BOS", "own", "BOS") for y in range(2030, 2034)]
    _seed(monkeypatch, tmp_path,
          _roster("BOS", 150_000_000, [("Alpha One", 30_000_000)])
          + _roster("MIA", 150_000_000, [("Beta Two", 30_000_000)]),
          picks=bos_inventory + _all_firsts("MIA"))
    out = get_trade_legality.invoke({
        "legs": '[{"from":"BOS","to":"MIA","players":"Alpha One",'
                '"picks":[{"year":2030,"round":1}]},'
                '{"from":"MIA","to":"BOS","players":"Beta Two"}]',
        "season": "2026-27",
    })
    assert out["ok"] is True
    assert any("Stepien" in i for i in out["issues"])


def test_stepien_same_year_exchange_legal_in_both_leg_orderings(
        monkeypatch, tmp_path):
    from shared.tools import get_trade_legality
    bos_inventory = [(y, 1, "BOS", "own", "BOS")
                     for y in range(2027, 2034) if y != 2029]
    _seed(monkeypatch, tmp_path,
          _roster("BOS", 150_000_000, [("Alpha One", 30_000_000)])
          + _roster("MIA", 150_000_000, [("Beta Two", 30_000_000)]),
          picks=bos_inventory + _all_firsts("MIA"))
    bos_first = ('[{"from":"BOS","to":"MIA","players":"Alpha One",'
                 '"picks":[{"year":2028,"round":1}]},'
                 '{"from":"MIA","to":"BOS","players":"Beta Two",'
                 '"picks":[{"year":2028,"round":1}]}]')
    mia_first = ('[{"from":"MIA","to":"BOS","players":"Beta Two",'
                 '"picks":[{"year":2028,"round":1}]},'
                 '{"from":"BOS","to":"MIA","players":"Alpha One",'
                 '"picks":[{"year":2028,"round":1}]}]')
    for legs in (bos_first, mia_first):
        out = get_trade_legality.invoke({
            "legs": legs,
            "season": "2026-27",
        })
        assert out["ok"] is True
        assert out["legal"] is True, out["issues"]


def _cycle_legs(order):
    legs = {
        "bos": ('{"from":"BOS","to":"MIA","players":"Alpha One",'
                '"picks":[{"year":2028,"round":1}]}'),
        "mia": '{"from":"MIA","to":"DEN","players":"Beta Two"}',
        "den": ('{"from":"DEN","to":"BOS","players":"Gamma Three",'
                '"picks":[{"year":2028,"round":1}]}'),
    }
    return "[" + ",".join(legs[key] for key in order) + "]"


def test_stepien_multi_team_verdict_is_order_independent(monkeypatch, tmp_path):
    from shared.tools import get_trade_legality
    bos_inventory = [(y, 1, "BOS", "own", "BOS")
                     for y in range(2027, 2034) if y != 2029]
    _seed(monkeypatch, tmp_path,
          _roster("BOS", 150_000_000, [("Alpha One", 30_000_000)])
          + _roster("MIA", 150_000_000, [("Beta Two", 30_000_000)])
          + _roster("DEN", 150_000_000, [("Gamma Three", 30_000_000)]),
          picks=(bos_inventory + _all_firsts("MIA")
                 + _all_firsts("DEN")))
    outputs = []
    for order in (("bos", "mia", "den"), ("den", "bos", "mia")):
        outputs.append(get_trade_legality.invoke({
            "legs": _cycle_legs(order),
            "season": "2026-27",
        }))
    assert all(out["ok"] is True for out in outputs)
    assert outputs[0]["legal"] == outputs[1]["legal"]
    assert all(out["legal"] is True for out in outputs), outputs


def test_stepien_trade_created_violation_fails_in_both_leg_orderings(
        monkeypatch, tmp_path):
    from shared.tools import get_trade_legality
    _seed(monkeypatch, tmp_path,
          _roster("BOS", 150_000_000, [("Alpha One", 30_000_000)])
          + _roster("MIA", 150_000_000, [("Beta Two", 30_000_000)]),
          picks=_all_firsts("BOS") + _all_firsts("MIA"))
    bos_first = ('[{"from":"BOS","to":"MIA","players":"Alpha One",'
                 '"picks":[{"year":2028,"round":1},{"year":2029,"round":1}]},'
                 '{"from":"MIA","to":"BOS","players":"Beta Two"}]')
    mia_first = ('[{"from":"MIA","to":"BOS","players":"Beta Two"},'
                 '{"from":"BOS","to":"MIA","players":"Alpha One",'
                 '"picks":[{"year":2028,"round":1},{"year":2029,"round":1}]}]')
    for legs in (bos_first, mia_first):
        out = get_trade_legality.invoke({
            "legs": legs,
            "season": "2026-27",
        })
        assert out["ok"] is True
        assert out["legal"] is False
        assert any("Stepien" in issue for issue in out["issues"])


def test_stepien_out_of_window_incoming_first_does_not_trigger_previolation(
        monkeypatch, tmp_path):
    from shared.tools import get_trade_legality
    bos_inventory = [(y, 1, "BOS", "own", "BOS") for y in range(2030, 2034)]
    _seed(monkeypatch, tmp_path,
          _roster("BOS", 150_000_000, [("Alpha One", 30_000_000)])
          + _roster("MIA", 150_000_000, [("Beta Two", 30_000_000)]),
          picks=bos_inventory + _all_firsts("MIA"))
    out = get_trade_legality.invoke({
        "legs": '[{"from":"MIA","to":"BOS","players":"Beta Two",'
                '"picks":[{"year":2034,"round":1}]},'
                '{"from":"BOS","to":"MIA","players":"Alpha One"}]',
        "season": "2026-27",
    })
    assert out["ok"] is True
    assert any("7 drafts out" in issue for issue in out["issues"])
    assert not any("Stepien" in issue for issue in out["issues"])


def test_stepien_elapsed_incoming_first_does_not_trigger_previolation(
        monkeypatch, tmp_path):
    from shared.tools import get_trade_legality
    bos_inventory = [(y, 1, "BOS", "own", "BOS") for y in range(2030, 2034)]
    _seed(monkeypatch, tmp_path,
          _roster("BOS", 150_000_000, [("Alpha One", 30_000_000)])
          + _roster("MIA", 150_000_000, [("Beta Two", 30_000_000)]),
          picks=bos_inventory + _all_firsts("MIA"))
    out = get_trade_legality.invoke({
        "legs": '[{"from":"MIA","to":"BOS","players":"Beta Two",'
                '"picks":[{"year":2026,"round":1}]},'
                '{"from":"BOS","to":"MIA","players":"Alpha One"}]',
        "season": "2026-27",
    })
    assert out["ok"] is True
    assert out["legal"] is True, out["issues"]
    assert not any("Stepien" in issue for issue in out["issues"])


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
