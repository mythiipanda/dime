import json

import duckdb
import pytest

STANDARD_MATCH_RULE = ("standard TPE matching: 100% of outgoing salary plus "
                       "applicable cushion")
AGGREGATED_STANDARD_MATCH_RULE = (
    "aggregated standard TPE matching: 100% of aggregated outgoing salary "
    "plus applicable cushion")
DECLARED_TPE_MATCH_RULE = (
    "declared TPE capacity: separate non-combined exception bin")
CAP_ROOM_MATCH_RULE = "cap room plus outgoing salary plus $250k (under the cap)"


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


def test_trade_check_crossing_first_apron_uses_post_trade_strict_matching(
        monkeypatch, tmp_path):
    from shared.tools import get_trade_check

    _seed(monkeypatch, tmp_path,
          _roster("BOS", 205_000_000, [("Alpha One", 25_000_000)])
          + _roster("MIA", 150_000_000, [("Beta Two", 30_000_000)]))
    out = get_trade_check.invoke({
        "team_a": "BOS", "players_a": "Alpha One",
        "team_b": "MIA", "players_b": "Beta Two",
        "season": "2026-27",
    })
    assert out["ok"] is True
    rows = out["rows"]
    bos = rows["team_a"]
    assert bos["over_apron1"] is True
    assert bos["room_apron1"] == -985_000
    assert bos["allowed_in"] == 25_000_000
    assert bos["match_rule"] == "100% (above the first apron)"
    assert rows["legal"] is False
    assert any("BOS takes back too much" in issue for issue in rows["issues"])


def test_trade_check_dropping_below_first_apron_uses_post_trade_band(
        monkeypatch, tmp_path):
    from shared.tools import get_trade_check

    _seed(monkeypatch, tmp_path,
          _roster("BOS", 212_000_000, [("Alpha One", 30_000_000)])
          + _roster("MIA", 150_000_000, [("Beta Two", 25_000_000)]))
    out = get_trade_check.invoke({
        "team_a": "BOS", "players_a": "Alpha One",
        "team_b": "MIA", "players_b": "Beta Two",
        "season": "2026-27",
    })
    assert out["ok"] is True
    bos = out["rows"]["team_a"]
    assert bos["over_apron1"] is False
    assert bos["room_apron1"] == 2_015_000
    assert bos["allowed_in"] == 39_096_000
    assert bos["match_rule"] == STANDARD_MATCH_RULE


def test_trade_check_dropping_below_second_apron_clears_aggregation_ban(
        monkeypatch, tmp_path):
    from shared.tools import get_trade_check

    _seed(monkeypatch, tmp_path,
          _roster("BOS", 224_000_000,
                  [("Alpha One", 15_000_000), ("Beta Two", 15_000_000)])
          + _roster("MIA", 150_000_000, [("Gamma Three", 25_000_000)]))
    out = get_trade_check.invoke({
        "team_a": "BOS", "players_a": "Alpha One, Beta Two",
        "team_b": "MIA", "players_b": "Gamma Three",
        "season": "2026-27",
    })
    assert out["ok"] is True
    rows = out["rows"]
    bos = rows["team_a"]
    assert bos["over_apron2"] is False
    assert bos["room_apron2"] == 2_686_000
    assert rows["legal"] is True, rows["issues"]
    assert not any("cannot aggregate" in issue for issue in rows["issues"])


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


def _standard_band_legality(monkeypatch, tmp_path, bos_payroll, incoming):
    from shared.tools import get_trade_legality

    _seed(monkeypatch, tmp_path,
          _roster("BOS", bos_payroll, [("Alpha One", 20_000_000)])
          + _roster("MIA", 150_000_000, [("Beta Two", incoming)]))
    return get_trade_legality.invoke({
        "legs": '[{"from":"BOS","to":"MIA","players":"Alpha One"},'
                '{"from":"MIA","to":"BOS","players":"Beta Two"}]',
        "season": "2026-27",
    })


@pytest.mark.parametrize("incoming", [20_100_000, 20_250_000])
def test_standard_tpe_band_is_legal_without_hard_cap(
        monkeypatch, tmp_path, incoming):
    out = _standard_band_legality(
        monkeypatch, tmp_path, 195_000_000, incoming)
    assert out["ok"] is True
    assert out["legal"] is True, out["issues"]
    row = _team_rows(out)["BOS"]
    assert row["payroll_after"] == 195_000_000 - 20_000_000 + incoming
    assert row["matching_structure"] == "standard_simultaneous"
    assert row["matching_mechanisms"] == ["standard_simultaneous"]
    assert row["expanded_required"] is False
    assert row["hard_cap"] == ""
    assert row["allowed_incoming"] == 29_096_000
    assert row["match_rule"] == STANDARD_MATCH_RULE
    assert "$9.096M" not in row["match_rule"]
    assert "standard TPE" in row["matching_note"]
    assert "no expanded TPE" in row["matching_note"]
    salary_note = next(check["note"] for check in out["checks"]
                       if check["rule"] == "salary matching")
    assert f"BOS {STANDARD_MATCH_RULE}" in salary_note


def test_standard_tpe_exact_boundary_plus_one_requires_expanded(
        monkeypatch, tmp_path):
    out = _standard_band_legality(
        monkeypatch, tmp_path, 195_000_000, 20_250_001)
    assert out["ok"] is True
    assert out["legal"] is True, out["issues"]
    row = _team_rows(out)["BOS"]
    assert row["payroll_after"] == 195_250_001
    assert row["matching_structure"] == "expanded"
    assert row["matching_mechanisms"] == ["expanded"]
    assert row["expanded_required"] is True
    assert row["hard_cap"] == "first apron"
    assert row["hard_cap_violations"] == []


def test_above_first_apron_surplus_is_prohibited_expanded_use(
        monkeypatch, tmp_path):
    out = _standard_band_legality(
        monkeypatch, tmp_path, 209_000_000, 20_100_000)
    assert out["ok"] is True
    assert out["legal"] is False
    row = _team_rows(out)["BOS"]
    assert row["payroll_after"] == 209_100_000
    assert row["matching_structure"] == "expanded"
    assert row["matching_mechanisms"] == ["expanded"]
    assert row["expanded_required"] is True
    assert row["matching_note"]
    assert row["hard_cap"] == "first apron"
    assert row["hard_cap_violations"] == ["first apron"]
    assert any("cannot use the Expanded Traded Player Exception" in issue
               and "transaction is prohibited" in issue
               for issue in out["issues"])


def test_above_first_apron_exact_standard_match_is_legal_without_hard_cap(
        monkeypatch, tmp_path):
    out = _standard_band_legality(
        monkeypatch, tmp_path, 209_100_000, 20_000_000)
    assert out["ok"] is True
    assert out["legal"] is True, out["issues"]
    row = _team_rows(out)["BOS"]
    assert row["payroll_after"] == 209_100_000
    assert row["over_apron1"] is True
    assert row["matching_structure"] == "standard_simultaneous"
    assert row["expanded_required"] is False
    assert row["hard_cap"] == ""


def _standard_band_check(monkeypatch, tmp_path, bos_payroll, incoming):
    from shared.tools import get_trade_check

    _seed(monkeypatch, tmp_path,
          _roster("BOS", bos_payroll, [("Alpha One", 20_000_000)])
          + _roster("MIA", 150_000_000, [("Beta Two", incoming)]))
    return get_trade_check.invoke({
        "team_a": "BOS", "players_a": "Alpha One",
        "team_b": "MIA", "players_b": "Beta Two",
        "season": "2026-27",
    })


@pytest.mark.parametrize(
    "payroll,incoming,legal,structure,expanded,hard_cap",
    [
        (195_000_000, 20_100_000, True, "standard_simultaneous", False, ""),
        (195_000_000, 20_250_000, True, "standard_simultaneous", False, ""),
        (195_000_000, 20_250_001, True, "expanded", True, "first apron"),
        (209_000_000, 20_100_000, False, "expanded", True, "first apron"),
        (209_100_000, 20_000_000, True, "standard_simultaneous", False, ""),
    ])
def test_trade_check_standard_tpe_band_vectors(
        monkeypatch, tmp_path, payroll, incoming, legal, structure,
        expanded, hard_cap):
    out = _standard_band_check(monkeypatch, tmp_path, payroll, incoming)
    assert out["ok"] is True
    assert out["rows"]["legal"] is legal, out["rows"]["issues"]
    row = out["rows"]["team_a"]
    assert row["payroll"] == payroll
    assert row["matching_structure"] == structure
    assert row["matching_mechanisms"] == [structure]
    assert row["expanded_required"] is expanded
    assert row["hard_cap"] == hard_cap
    if structure == "standard_simultaneous":
        assert row["match_rule"] == STANDARD_MATCH_RULE
        assert "$9.096M" not in row["match_rule"]
    if payroll == 195_000_000 and structure == "expanded":
        assert row["match_rule"] == (
            "outgoing salary plus $9.096M (below the first apron)")
    assert out["meta"]["salary_basis"] == (
        "approximate_salary_ledger_not_exact_apron_team_salary")


def test_trade_legality_meta_discloses_payroll_proxy(monkeypatch, tmp_path):
    out = _standard_band_legality(
        monkeypatch, tmp_path, 195_000_000, 20_100_000)
    assert out["ok"] is True
    meta = out["meta"]
    assert meta["salary_basis"] == (
        "approximate_salary_ledger_not_exact_apron_team_salary")
    assert meta["ats_exact"] is False
    assert meta["ats_missing_inputs"] == [
        "performance_bonus_amounts_and_likelihood",
        "contract_component_and_protection_allocations",
        "actual_dead_money_and_stretch_elections",
        "rfa_offer_sheet_required_tender_and_free_agent_state",
        "exception_inventory_and_usage",
        "contract_subtype_timing_flags",
        "official_team_salary_reconciliation",
    ]
    assert meta["payroll_proxy_disclosure"] == (
        "Approximation, not exact Apron Team Salary: this result uses the "
        "warehouse salary ledger of listed player salaries only. It does not "
        "calculate exact ATS because performance bonuses (including unlikely "
        "bonuses counted for apron purposes), waived/stretched dead money, "
        "retired-player or grievance amounts, minimum-contract apron adjustments, "
        "restricted free-agent/offer-sheet/required-tender amounts, exception "
        "bookkeeping, two-way/conversion status, and offseason next-year "
        "assumptions are missing or estimated. Apron room, hard-cap, and TPE "
        "conclusions are screening estimates and can be wrong near either apron; "
        "do not represent this as a final CBA legality determination.")


def test_expanded_matching_below_first_apron_is_legal_hard_cap_trigger(
        monkeypatch, tmp_path):
    from shared.tools import get_trade_legality

    _seed(monkeypatch, tmp_path,
          _roster("BOS", 190_000_000, [("Alpha One", 20_000_000)])
          + _roster("MIA", 150_000_000, [("Beta Two", 28_000_000)]))
    out = get_trade_legality.invoke({
        "legs": '[{"from":"BOS","to":"MIA","players":"Alpha One"},'
                '{"from":"MIA","to":"BOS","players":"Beta Two"}]',
        "season": "2026-27",
    })
    assert out["ok"] is True
    assert out["legal"] is True, out["issues"]
    row = _team_rows(out)["BOS"]
    assert row["payroll_after"] == 198_000_000
    assert row["over_apron1"] is False
    assert row["hard_cap"] == "first apron"


def test_expanded_matching_cannot_finish_above_first_apron(
        monkeypatch, tmp_path):
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
    row = _team_rows(out)["BOS"]
    assert row["payroll_after"] == 210_000_000
    assert row["hard_cap"] == "first apron"
    assert any("cannot use the Expanded Traded Player Exception" in issue
               and "transaction is prohibited" in issue
               for issue in out["issues"])


def test_expanded_matching_can_be_required_alongside_disjoint_tpe(
        monkeypatch, tmp_path):
    from shared.tools import get_trade_legality

    _seed(monkeypatch, tmp_path,
          _roster("BOS", 190_000_000, [("Alpha One", 10_000_000)])
          + _roster("MIA", 150_000_000,
                    [("Beta Two", 12_000_000),
                     ("Gamma Three", 11_000_000)]))
    out = get_trade_legality.invoke({
        "legs": '[{"from":"BOS","to":"MIA","players":"Alpha One"},'
                '{"from":"MIA","to":"BOS",'
                '"players":"Beta Two, Gamma Three"}]',
        "tpe": '[{"team":"BOS","amount":11000000,"kind":"ordinary",'
               '"origin_season":"2026-27"}]',
        "season": "2026-27",
    })
    assert out["ok"] is True
    assert out["legal"] is True, out["issues"]
    row = _team_rows(out)["BOS"]
    assert row["payroll_after"] == 203_000_000
    assert row["matching_ok"] is True
    assert row["hard_cap"] == "first apron"


def test_trade_check_expanded_matching_surfaces_first_apron_hard_cap(
        monkeypatch, tmp_path):
    from shared.tools import get_trade_check

    _seed(monkeypatch, tmp_path,
          _roster("BOS", 190_000_000, [("Alpha One", 20_000_000)])
          + _roster("MIA", 150_000_000, [("Beta Two", 28_000_000)]))
    out = get_trade_check.invoke({
        "team_a": "BOS", "players_a": "Alpha One",
        "team_b": "MIA", "players_b": "Beta Two",
        "season": "2026-27",
    })
    assert out["ok"] is True
    rows = out["rows"]
    assert rows["legal"] is True, rows["issues"]
    assert rows["team_a"]["hard_cap"] == "first apron"
    assert rows["team_b"]["hard_cap"] == ""


def test_trade_check_expanded_matching_over_first_apron_issue(
        monkeypatch, tmp_path):
    from shared.tools import get_trade_check

    _seed(monkeypatch, tmp_path,
          _roster("BOS", 205_000_000, [("Alpha One", 25_000_000)])
          + _roster("MIA", 150_000_000, [("Beta Two", 30_000_000)]))
    out = get_trade_check.invoke({
        "team_a": "BOS", "players_a": "Alpha One",
        "team_b": "MIA", "players_b": "Beta Two",
        "season": "2026-27",
    })
    assert out["ok"] is True
    rows = out["rows"]
    assert rows["legal"] is False
    assert rows["team_a"]["hard_cap"] == "first apron"
    assert any("cannot use the Expanded Traded Player Exception" in issue
               and "transaction is prohibited" in issue
               for issue in rows["issues"])


def test_trade_check_cap_room_absorption_is_not_expanded_matching(
        monkeypatch, tmp_path):
    from shared.tools import get_trade_check

    _seed(monkeypatch, tmp_path,
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
    assert rows["team_a"]["hard_cap"] == ""


def test_below_cap_absorption_elects_cap_room_before_standard(
        monkeypatch, tmp_path):
    from shared.tools import get_cap_scenario, get_trade_check, get_trade_legality

    _seed(monkeypatch, tmp_path,
          _roster("BOS", 150_000_000, [("Alpha One", 20_000_000)])
          + _roster("MIA", 180_000_000, [("Beta Two", 20_100_000)]))
    legality = get_trade_legality.invoke({
        "legs": '[{"from":"BOS","to":"MIA","players":"Alpha One"},'
                '{"from":"MIA","to":"BOS","players":"Beta Two"}]',
        "season": "2026-27",
    })
    check = get_trade_check.invoke({
        "team_a": "BOS", "players_a": "Alpha One",
        "team_b": "MIA", "players_b": "Beta Two",
        "season": "2026-27",
    })
    scenario = get_cap_scenario.invoke({
        "team": "BOS", "trade_out_players": "Alpha One",
        "in_players": "Beta Two", "season": "2026-27",
    })
    assert legality["ok"] is True
    assert legality["legal"] is True, legality["issues"]
    assert check["ok"] is True
    assert check["rows"]["legal"] is True, check["rows"]["issues"]
    assert scenario["ok"] is True
    legality_row = _team_rows(legality)["BOS"]
    check_row = check["rows"]["team_a"]
    scenario_matching = scenario["matching"]
    for elected in (legality_row, check_row, scenario_matching):
        assert elected["matching_structure"] == "cap_room"
        assert elected["matching_mechanisms"] == ["cap_room"]
        assert elected["expanded_required"] is False
        assert elected["match_rule"] == CAP_ROOM_MATCH_RULE
    assert legality_row["allowed_incoming"] == 35_211_000
    assert check_row["allowed_in"] == 35_211_000
    assert scenario_matching["allowed_incoming"] == 35_211_000


@pytest.mark.parametrize("incoming", [1, 250_000, 250_001])
def test_trade_legality_zero_outgoing_without_room_rejects_small_incoming(
        monkeypatch, tmp_path, incoming):
    from shared.tools import get_trade_legality

    rows = [("Tiny One", "MIA", incoming)]
    rows += [(f"BOS Filler {index}", "BOS", 20_000_000)
             for index in range(10)]
    rows += [(f"MIA Filler {index}", "MIA", 15_000_000)
             for index in range(10)]
    _seed(monkeypatch, tmp_path, rows)
    out = get_trade_legality.invoke({
        "legs": '[{"from":"MIA","to":"BOS","players":"Tiny One"},'
                '{"from":"BOS","to":"MIA",'
                '"picks":[{"year":2028,"round":2}]}]',
        "season": "2026-27",
    })
    assert out["ok"] is True
    assert out["legal"] is False
    row = _team_rows(out)["BOS"]
    case = f"incoming={incoming!r} row={row!r} issues={out['issues']!r}"
    assert row["payroll_before"] == 200_000_000, case
    assert row["outgoing"] == 0, case
    assert row["incoming"] == incoming, case
    assert row["allowed_incoming"] == 0, case
    assert row["matching_ok"] is False, case
    assert row["matching_structure"] == "no_available_structure", case
    assert any(" vs $0 allowed under " in issue
               for issue in out["issues"]), case


def test_cap_scenario_standard_match_rule_describes_selected_mechanism(
        monkeypatch, tmp_path):
    from shared.tools import get_cap_scenario

    _seed(monkeypatch, tmp_path,
          _roster("BOS", 195_000_000, [("Alpha One", 20_000_000)])
          + _roster("MIA", 150_000_000, [("Beta Two", 20_100_000)]))
    out = get_cap_scenario.invoke({
        "team": "BOS", "trade_out_players": "Alpha One",
        "in_players": "Beta Two", "season": "2026-27",
    })
    assert out["ok"] is True
    matching = out["matching"]
    assert matching["legal"] is True
    assert matching["matching_structure"] == "standard_simultaneous"
    assert matching["matching_mechanisms"] == ["standard_simultaneous"]
    assert matching["expanded_required"] is False
    assert matching["allowed_incoming"] == 29_096_000
    assert matching["match_rule"] == STANDARD_MATCH_RULE
    assert "$9.096M" not in matching["match_rule"]


def test_cap_scenario_expanded_matching_surfaces_first_apron_hard_cap(
        monkeypatch, tmp_path):
    from shared.tools import get_cap_scenario

    _seed(monkeypatch, tmp_path,
          _roster("BOS", 190_000_000, [("Alpha One", 20_000_000)])
          + _roster("MIA", 150_000_000, [("Beta Two", 28_000_000)]))
    out = get_cap_scenario.invoke({
        "team": "BOS", "trade_out_players": "Alpha One",
        "in_players": "Beta Two", "season": "2026-27",
    })
    assert out["ok"] is True
    assert out["summary"]["payroll_after"] == 198_000_000
    assert out["summary"]["hard_cap"] == "first apron"
    assert out["matching"]["legal"] is True


def test_cap_scenario_expanded_matching_cannot_finish_above_first_apron(
        monkeypatch, tmp_path):
    from shared.tools import get_cap_scenario

    _seed(monkeypatch, tmp_path,
          _roster("BOS", 205_000_000, [("Alpha One", 25_000_000)])
          + _roster("MIA", 150_000_000, [("Beta Two", 30_000_000)]))
    out = get_cap_scenario.invoke({
        "team": "BOS", "trade_out_players": "Alpha One",
        "in_players": "Beta Two", "season": "2026-27",
    })
    assert out["ok"] is True
    assert out["summary"]["payroll_after"] == 210_000_000
    assert out["summary"]["hard_cap"] == "first apron"
    assert any("cannot use the Expanded Traded Player Exception" in issue
               and "transaction is prohibited" in issue
               for issue in out["issues"])


def test_trade_check_aggregation_without_expanded_matching_surfaces_hard_cap(
        monkeypatch, tmp_path):
    from shared.tools import get_trade_check

    _seed(monkeypatch, tmp_path,
          _roster("BOS", 190_000_000,
                  [("Alpha One", 15_000_000), ("Beta Two", 15_000_000)])
          + _roster("MIA", 145_000_000, [("Gamma Three", 25_000_000)]))
    out = get_trade_check.invoke({
        "team_a": "BOS", "players_a": "Alpha One, Beta Two",
        "team_b": "MIA", "players_b": "Gamma Three",
        "season": "2026-27",
    })
    assert out["ok"] is True
    rows = out["rows"]
    assert rows["legal"] is True, rows["issues"]
    assert rows["team_a"]["hard_cap"] == "second apron"
    assert rows["team_b"]["hard_cap"] == ""


def test_cap_scenario_aggregation_without_expanded_matching_surfaces_hard_cap(
        monkeypatch, tmp_path):
    from shared.tools import get_cap_scenario

    _seed(monkeypatch, tmp_path,
          _roster("BOS", 190_000_000,
                  [("Alpha One", 15_000_000), ("Beta Two", 15_000_000)])
          + _roster("MIA", 145_000_000, [("Gamma Three", 25_000_000)]))
    out = get_cap_scenario.invoke({
        "team": "BOS", "trade_out_players": "Alpha One, Beta Two",
        "in_players": "Gamma Three", "season": "2026-27",
    })
    assert out["ok"] is True
    assert out["summary"]["payroll_after"] == 185_000_000
    assert out["summary"]["hard_cap"] == "second apron"
    assert out["matching"]["legal"] is True


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


def test_aggregated_standard_probe_match_rule_consistent_across_consumers(
        monkeypatch, tmp_path):
    from shared.tools import get_cap_scenario, get_trade_check, get_trade_legality

    _seed(monkeypatch, tmp_path,
          _roster("BOS", 190_000_000,
                  [("Alpha One", 15_000_000), ("Beta Two", 15_000_000)])
          + _roster("MIA", 150_000_000, [("Gamma Three", 30_100_000)]))
    legality = get_trade_legality.invoke({
        "legs": '[{"from":"BOS","to":"MIA",'
                '"players":"Alpha One, Beta Two"},'
                '{"from":"MIA","to":"BOS","players":"Gamma Three"}]',
        "season": "2026-27",
    })
    check = get_trade_check.invoke({
        "team_a": "BOS", "players_a": "Alpha One, Beta Two",
        "team_b": "MIA", "players_b": "Gamma Three",
        "season": "2026-27",
    })
    scenario = get_cap_scenario.invoke({
        "team": "BOS", "trade_out_players": "Alpha One, Beta Two",
        "in_players": "Gamma Three", "season": "2026-27",
    })
    assert legality["ok"] is True
    assert legality["legal"] is True, legality["issues"]
    assert check["ok"] is True
    assert check["rows"]["legal"] is True, check["rows"]["issues"]
    assert scenario["ok"] is True

    legality_row = _team_rows(legality)["BOS"]
    check_row = check["rows"]["team_a"]
    scenario_matching = scenario["matching"]
    for elected in (legality_row, check_row, scenario_matching):
        assert elected["matching_structure"] == "aggregated_standard"
        assert elected["matching_mechanisms"] == ["aggregated_standard"]
        assert elected["match_rule"] == AGGREGATED_STANDARD_MATCH_RULE
        assert "aggregated standard TPE" in elected["match_rule"]
        assert "$9.096M" not in elected["match_rule"]
        assert "expanded" not in elected["match_rule"].lower()
    assert legality_row["allowed_incoming"] == 39_096_000
    assert check_row["allowed_in"] == 39_096_000
    assert scenario_matching["allowed_incoming"] == 39_096_000
    salary_note = next(item["note"] for item in legality["checks"]
                       if item["rule"] == "salary matching")
    assert f"BOS {AGGREGATED_STANDARD_MATCH_RULE}" in salary_note
    assert "$9.096M" not in salary_note
    assert "expanded" not in salary_note.lower()


def test_second_apron_receiver_multiple_incoming_is_not_aggregation(
        monkeypatch, tmp_path):
    from shared.tools import get_trade_legality

    _seed(monkeypatch, tmp_path,
          _roster("PHX", 230_000_000, [("Alpha One", 30_000_000)])
          + _roster("MIA", 150_000_000,
                    [("Beta Two", 15_000_000),
                     ("Gamma Three", 15_000_000)]))
    out = get_trade_legality.invoke({
        "legs": '[{"from":"PHX","to":"MIA","players":"Alpha One"},'
                '{"from":"MIA","to":"PHX","players":"Beta Two, Gamma Three"}]',
        "season": "2026-27",
    })
    assert out["ok"] is True
    assert out["legal"] is True, out["issues"]
    rows = _team_rows(out)
    phx = rows["PHX"]
    assert phx["payroll_after"] == 230_000_000
    assert phx["over_apron2"] is True
    assert phx["matching_ok"] is True
    assert phx["aggregates"] is False
    assert phx["hard_cap"] == ""
    assert not any("aggregate incoming" in issue for issue in out["issues"])


def test_multiple_outgoing_players_remain_aggregation(
        monkeypatch, tmp_path):
    from shared.tools import get_trade_legality

    _seed(monkeypatch, tmp_path,
          _roster("PHX", 230_000_000, [("Alpha One", 30_000_000)])
          + _roster("MIA", 150_000_000,
                    [("Beta Two", 15_000_000),
                     ("Gamma Three", 15_000_000)]))
    out = get_trade_legality.invoke({
        "legs": '[{"from":"PHX","to":"MIA","players":"Alpha One"},'
                '{"from":"MIA","to":"PHX","players":"Beta Two, Gamma Three"}]',
        "season": "2026-27",
    })
    assert out["ok"] is True
    rows = _team_rows(out)
    assert rows["MIA"]["aggregates"] is True
    assert rows["MIA"]["hard_cap"] == "second apron"


def test_sign_and_trade_byc_reduces_outgoing_and_stays_legal(
        monkeypatch, tmp_path):
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
    assert bos["matching_ok"] is True
    assert mia["incoming"] == 30_000_000
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
    assert any("cannot use a sign-and-trade acquisition" in issue
               and "transaction is prohibited" in issue
               for issue in out["issues"])
    assert not any("takes back too much" in issue for issue in out["issues"])


def test_second_apron_cash_is_rejected(monkeypatch, tmp_path):
    from shared.tools import get_trade_legality

    _seed(monkeypatch, tmp_path,
          _roster("BOS", 230_000_000, [("Alpha One", 20_000_000)])
          + _roster("MIA", 150_000_000, [("Beta Two", 30_000_000)]))
    out = get_trade_legality.invoke({
        "legs": '[{"from":"BOS","to":"MIA","players":"Alpha One"},'
                '{"from":"MIA","to":"BOS","players":"Beta Two"}]',
        "cash": '[{"from":"BOS","to":"MIA","amount":1000000}]',
        "season": "2026-27",
    })
    assert out["ok"] is True
    assert out["legal"] is False
    rows = _team_rows(out)
    assert rows["BOS"]["payroll_after"] == 240_000_000
    assert rows["BOS"]["cash_out"] == 1_000_000
    assert any("cannot send cash above the second apron" in issue
               for issue in out["issues"])
    assert any("cannot use cash in a trade" in issue
               and "transaction is prohibited" in issue
               for issue in out["issues"])


def test_current_year_ordinary_tpe_usable_above_second_apron(
        monkeypatch, tmp_path):
    from shared.tools import get_trade_legality

    _seed(monkeypatch, tmp_path,
          _roster("BOS", 225_000_000, [])
          + _roster("MIA", 150_000_000, [("Alpha One", 8_000_000)]))
    out = get_trade_legality.invoke({
        "legs": '[{"from":"MIA","to":"BOS","players":"Alpha One"}]',
        "tpe": '[{"team":"BOS","amount":8000000,"kind":"ordinary",'
               '"origin_season":"2026-27"}]',
        "season": "2026-27",
    })
    assert out["ok"] is True
    assert out["legal"] is True, out["issues"]
    row = _team_rows(out)["BOS"]
    assert row["payroll_after"] == 233_000_000
    assert row["over_apron2"] is True
    assert row["hard_cap"] == ""
    assert row["tpe_used"] == 8_000_000
    assert row["matching_ok"] is True


def test_prior_year_ordinary_tpe_hard_caps_at_first_apron(
        monkeypatch, tmp_path):
    from shared.tools import get_trade_legality

    _seed(monkeypatch, tmp_path,
          _roster("BOS", 203_000_000, [])
          + _roster("MIA", 150_000_000, [("Alpha One", 8_000_000)]))
    out = get_trade_legality.invoke({
        "legs": '[{"from":"MIA","to":"BOS","players":"Alpha One"}]',
        "tpe": '[{"team":"BOS","amount":8000000,"kind":"ordinary",'
               '"origin_season":"2025-26"}]',
        "season": "2026-27",
    })
    assert out["ok"] is True
    assert out["legal"] is False
    row = _team_rows(out)["BOS"]
    assert row["payroll_after"] == 211_000_000
    assert row["over_apron1"] is True
    assert row["over_apron2"] is False
    assert row["hard_cap"] == "first apron"
    assert any("cannot use the prior-year traded player exception" in issue
               and "transaction is prohibited" in issue
               for issue in out["issues"])


def test_prior_year_ordinary_tpe_below_first_apron_is_legal_trigger(
        monkeypatch, tmp_path):
    from shared.tools import get_trade_legality

    _seed(monkeypatch, tmp_path,
          _roster("BOS", 198_000_000, [])
          + _roster("MIA", 150_000_000, [("Alpha One", 8_000_000)]))
    out = get_trade_legality.invoke({
        "legs": '[{"from":"MIA","to":"BOS","players":"Alpha One"}]',
        "tpe": '[{"team":"BOS","amount":8000000,"kind":"ordinary",'
               '"origin_season":"2025-26"}]',
        "season": "2026-27",
    })
    assert out["ok"] is True
    assert out["legal"] is True, out["issues"]
    row = _team_rows(out)["BOS"]
    assert row["payroll_after"] == 206_000_000
    assert row["hard_cap"] == "first apron"


def test_sign_and_trade_tpe_hard_caps_second_apron(
        monkeypatch, tmp_path):
    from shared.tools import get_trade_legality

    _seed(monkeypatch, tmp_path,
          _roster("BOS", 203_000_000, [])
          + _roster("MIA", 150_000_000, [("Alpha One", 8_000_000)]))
    out = get_trade_legality.invoke({
        "legs": '[{"from":"MIA","to":"BOS","players":"Alpha One"}]',
        "tpe": '[{"team":"BOS","amount":8000000,"kind":"sign_and_trade",'
               '"origin_season":"2026-27"}]',
        "season": "2026-27",
    })
    assert out["ok"] is True
    assert out["legal"] is True, out["issues"]
    row = _team_rows(out)["BOS"]
    assert row["payroll_after"] == 211_000_000
    assert row["hard_cap"] == "second apron"


def test_expired_tpe_cannot_be_used(monkeypatch, tmp_path):
    from shared.tools import get_trade_legality

    _seed(monkeypatch, tmp_path,
          _roster("BOS", 170_000_000, [])
          + _roster("MIA", 150_000_000, [("Alpha One", 8_000_000)]))
    out = get_trade_legality.invoke({
        "legs": '[{"from":"MIA","to":"BOS","players":"Alpha One"}]',
        "tpe": '[{"team":"BOS","amount":8000000,"kind":"ordinary",'
               '"origin_season":"2024-25"}]',
        "season": "2026-27",
    })
    assert out["ok"] is True
    assert out["legal"] is False
    assert any("expired" in issue and "traded player exception" in issue
               for issue in out["issues"])


def test_tpe_absorbs_to_amount_plus_cushion(monkeypatch, tmp_path):
    from shared.tools import get_trade_legality

    _seed(monkeypatch, tmp_path,
          _roster("BOS", 170_000_000, [])
          + _roster("MIA", 150_000_000, [("Alpha One", 8_200_000)]))
    out = get_trade_legality.invoke({
        "legs": '[{"from":"MIA","to":"BOS","players":"Alpha One"}]',
        "tpe": '[{"team":"BOS","amount":8000000,"kind":"ordinary",'
               '"origin_season":"2026-27"}]',
        "season": "2026-27",
    })
    assert out["ok"] is True
    assert out["legal"] is True, out["issues"]
    row = _team_rows(out)["BOS"]
    assert row["matching_structure"] == "declared_tpe"
    assert row["matching_mechanisms"] == ["declared_tpe"]
    assert row["match_rule"] == DECLARED_TPE_MATCH_RULE
    assert "$9.096M" not in row["match_rule"]
    assert "200%" not in row["match_rule"]
    assert "expanded" not in row["match_rule"].lower()


def test_tpe_amount_cap_rejects_salary_above_cushion(monkeypatch, tmp_path):
    from shared.tools import get_trade_legality

    _seed(monkeypatch, tmp_path,
          _roster("BOS", 170_000_000, [])
          + _roster("MIA", 150_000_000, [("Alpha One", 8_300_000)]))
    out = get_trade_legality.invoke({
        "legs": '[{"from":"MIA","to":"BOS","players":"Alpha One"}]',
        "tpe": '[{"team":"BOS","amount":8000000,"kind":"ordinary",'
               '"origin_season":"2026-27"}]',
        "season": "2026-27",
    })
    assert out["ok"] is True
    assert out["legal"] is False
    assert any("cannot be combined" in issue for issue in out["issues"])


def test_tpe_cannot_combine_with_matching_for_one_acquisition(
        monkeypatch, tmp_path):
    from shared.tools import get_trade_legality

    _seed(monkeypatch, tmp_path,
          _roster("BOS", 180_000_000, [("Alpha One", 20_000_000)])
          + _roster("MIA", 180_000_000, [("Beta Two", 32_000_000)]))
    out = get_trade_legality.invoke({
        "legs": '[{"from":"BOS","to":"MIA","players":"Alpha One"},'
                '{"from":"MIA","to":"BOS","players":"Beta Two"}]',
        "tpe": '[{"team":"BOS","amount":4000000,"kind":"ordinary",'
               '"origin_season":"2026-27"}]',
        "season": "2026-27",
    })
    assert out["ok"] is True
    assert out["legal"] is False
    assert any("cannot be combined" in issue for issue in out["issues"])


def test_multiple_tpes_cannot_combine_for_one_acquisition(
        monkeypatch, tmp_path):
    from shared.tools import get_trade_legality

    _seed(monkeypatch, tmp_path,
          _roster("BOS", 170_000_000, [])
          + _roster("MIA", 150_000_000, [("Alpha One", 8_000_000)]))
    out = get_trade_legality.invoke({
        "legs": '[{"from":"MIA","to":"BOS","players":"Alpha One"}]',
        "tpe": '[{"team":"BOS","amount":4000000,"kind":"ordinary",'
               '"origin_season":"2026-27"},'
               '{"team":"BOS","amount":4000000,"kind":"ordinary",'
               '"origin_season":"2026-27"}]',
        "season": "2026-27",
    })
    assert out["ok"] is True
    assert out["legal"] is False
    assert any("cannot be combined" in issue for issue in out["issues"])


def test_multiple_tpes_can_cover_disjoint_incoming_players(
        monkeypatch, tmp_path):
    from shared.tools import get_trade_legality

    _seed(monkeypatch, tmp_path,
          _roster("BOS", 170_000_000, [])
          + _roster("MIA", 150_000_000,
                    [("Alpha One", 4_000_000),
                     ("Beta Two", 4_000_000)]))
    out = get_trade_legality.invoke({
        "legs": '[{"from":"MIA","to":"BOS","players":"Alpha One, Beta Two"}]',
        "tpe": '[{"team":"BOS","amount":4000000,"kind":"ordinary",'
               '"origin_season":"2026-27"},'
               '{"team":"BOS","amount":4000000,"kind":"ordinary",'
               '"origin_season":"2026-27"}]',
        "season": "2026-27",
    })
    assert out["ok"] is True
    assert out["legal"] is True, out["issues"]


def test_required_tpe_bins_are_not_deduped_with_matching(
        monkeypatch, tmp_path):
    from shared.tools import get_trade_legality

    _seed(monkeypatch, tmp_path,
          _roster("BOS", 208_100_000, [("Alpha One", 5_000_000)])
          + _roster("MIA", 150_000_000,
                    [("Beta Two", 3_000_000),
                     ("Gamma Three", 3_000_000)]))
    out = get_trade_legality.invoke({
        "legs": '[{"from":"BOS","to":"MIA","players":"Alpha One"},'
                '{"from":"MIA","to":"BOS",'
                '"players":"Beta Two, Gamma Three"}]',
        "tpe": '[{"team":"BOS","amount":5000000,"kind":"ordinary",'
               '"origin_season":"2026-27"},'
               '{"team":"BOS","amount":4000000,"kind":"ordinary",'
               '"origin_season":"2026-27"}]',
        "season": "2026-27",
    })
    assert out["ok"] is True
    assert out["legal"] is True, out["issues"]
    row = _team_rows(out)["BOS"]
    assert row["allowed_incoming"] == 5_000_000
    assert row["matching_ok"] is True


def test_matching_plus_one_tpe_covers_disjoint_review_shape(
        monkeypatch, tmp_path):
    from shared.tools import get_trade_legality

    _seed(monkeypatch, tmp_path,
          _roster("BOS", 208_100_000, [("Alpha One", 14_000_000)])
          + _roster("MIA", 150_000_000,
                    [("Beta Two", 8_000_000),
                     ("Gamma Three", 6_000_000),
                     ("Delta Four", 1_000_000)]))
    out = get_trade_legality.invoke({
        "legs": '[{"from":"BOS","to":"MIA","players":"Alpha One"},'
                '{"from":"MIA","to":"BOS",'
                '"players":"Beta Two, Gamma Three, Delta Four"}]',
        "tpe": '[{"team":"BOS","amount":6000000,"kind":"ordinary",'
               '"origin_season":"2026-27"}]',
        "season": "2026-27",
    })
    assert out["ok"] is True
    assert out["legal"] is True, out["issues"]
    row = _team_rows(out)["BOS"]
    assert row["allowed_incoming"] == 14_000_000
    assert row["matching_ok"] is True
    assert row["matching_structure"] == "standard_simultaneous+declared_tpe"
    assert row["matching_mechanisms"] == [
        "standard_simultaneous", "declared_tpe"]
    assert row["match_rule"] == STANDARD_MATCH_RULE
    assert "$9.096M" not in row["match_rule"]
    assert "expanded" not in row["match_rule"].lower()
    assert "separate non-combined capacity bins" in row["matching_note"]


def test_prior_year_sign_and_trade_tpe_keeps_first_apron_timing(
        monkeypatch, tmp_path):
    from shared.tools import get_trade_legality

    _seed(monkeypatch, tmp_path,
          _roster("BOS", 203_000_000, [])
          + _roster("MIA", 150_000_000, [("Alpha One", 8_000_000)]))
    out = get_trade_legality.invoke({
        "legs": '[{"from":"MIA","to":"BOS","players":"Alpha One"}]',
        "tpe": '[{"team":"BOS","amount":8000000,"kind":"sign_and_trade",'
               '"origin_season":"2025-26"}]',
        "season": "2026-27",
    })
    assert out["ok"] is True
    assert out["legal"] is False
    row = _team_rows(out)["BOS"]
    assert row["hard_cap"] == "first apron+second apron"
    assert any("prior-year traded player exception" in issue
               for issue in out["issues"])


def test_legacy_amount_only_tpe_defaults_to_current_ordinary(
        monkeypatch, tmp_path):
    from shared.tools import get_trade_legality

    _seed(monkeypatch, tmp_path,
          _roster("BOS", 170_000_000, [])
          + _roster("MIA", 150_000_000, [("Alpha One", 8_000_000)]))
    out = get_trade_legality.invoke({
        "legs": '[{"from":"MIA","to":"BOS","players":"Alpha One"}]',
        "tpe": '[{"team":"BOS","amount":8000000}]',
        "season": "2026-27",
    })
    assert out["ok"] is True
    assert out["legal"] is True, out["issues"]
    detail = _team_rows(out)["BOS"]["tpe_details"][0]
    assert detail["kind"] == "ordinary"
    assert detail["origin_year"] == 2026
    assert detail["status"] == "current_year"
    assert detail["legacy_defaults"] is True
    assert detail["timing_basis"] == "season_approximate"
    assert detail["expiry_date"] is None
    note = next(row["note"] for row in out["checks"]
                if row["rule"] == "traded player exceptions")
    assert "approximate legacy season bins" in note


def _dated_tpe_out(monkeypatch, tmp_path, row,
                   evaluation_date="2026-10-01"):
    from shared.tools import get_trade_legality

    _seed(monkeypatch, tmp_path,
          _roster("BOS", 170_000_000, [])
          + _roster("MIA", 150_000_000, [("Alpha One", 8_000_000)]))
    return get_trade_legality.invoke({
        "legs": '[{"from":"MIA","to":"BOS","players":"Alpha One"}]',
        "tpe": json.dumps([row]),
        "evaluation_date": evaluation_date,
        "season": "2026-27",
    })


def test_exact_date_prior_year_tpe_active_before_expiry(
        monkeypatch, tmp_path):
    out = _dated_tpe_out(monkeypatch, tmp_path, {
        "team": "BOS", "amount": 8_000_000, "kind": "ordinary",
        "origin_date": "2025-12-15", "expiry_date": "2026-12-15",
    })
    assert out["ok"] is True
    assert out["legal"] is True, out["issues"]
    detail = _team_rows(out)["BOS"]["tpe_details"][0]
    assert detail["status"] == "prior_year"
    assert detail["timing_basis"] == "exact_date"
    assert detail["as_of_date"] == "2026-10-01"
    assert detail["origin_year"] == 2025
    assert detail["origin_season"] == "2025-26"
    assert detail["expiry_date"] == "2026-12-15"
    assert detail["expiry_date_derived"] is False


def test_exact_expiry_date_remains_usable_on_as_of_date(
        monkeypatch, tmp_path):
    out = _dated_tpe_out(monkeypatch, tmp_path, {
        "team": "BOS", "amount": 8_000_000, "kind": "ordinary",
        "origin_season": "2025-26", "expiry_date": "2026-10-01",
    })
    assert out["ok"] is True
    assert out["legal"] is True, out["issues"]
    detail = _team_rows(out)["BOS"]["tpe_details"][0]
    assert detail["status"] == "prior_year"
    assert detail["timing_basis"] == "exact_date"
    assert detail["as_of_date"] == "2026-10-01"
    assert detail["expiry_date"] == "2026-10-01"
    assert detail["effective_expiry_date"] == "2026-10-01"


def test_origin_date_derives_exact_one_year_expiry(monkeypatch, tmp_path):
    out = _dated_tpe_out(monkeypatch, tmp_path, {
        "team": "BOS", "amount": 8_000_000, "kind": "ordinary",
        "origin_date": "2025-09-15",
    })
    assert out["ok"] is True
    assert out["legal"] is False
    detail = _team_rows(out)["BOS"]["tpe_details"][0]
    assert detail["status"] == "expired"
    assert detail["expiry_date"] == "2026-09-15"
    assert detail["effective_expiry_date"] == "2026-09-15"
    assert detail["expiry_date_derived"] is True


def test_derived_anniversary_date_remains_usable(monkeypatch, tmp_path):
    out = _dated_tpe_out(monkeypatch, tmp_path, {
        "team": "BOS", "amount": 8_000_000, "kind": "ordinary",
        "origin_date": "2025-10-01",
    })
    assert out["ok"] is True
    assert out["legal"] is True, out["issues"]
    detail = _team_rows(out)["BOS"]["tpe_details"][0]
    assert detail["status"] == "prior_year"
    assert detail["as_of_date"] == "2026-10-01"
    assert detail["expiry_date"] == "2026-10-01"
    assert detail["effective_expiry_date"] == "2026-10-01"
    assert detail["expiry_date_derived"] is True


def test_day_after_derived_anniversary_expires(monkeypatch, tmp_path):
    out = _dated_tpe_out(monkeypatch, tmp_path, {
        "team": "BOS", "amount": 8_000_000, "kind": "ordinary",
        "origin_date": "2025-10-01",
    }, evaluation_date="2026-10-02")
    assert out["ok"] is True
    assert out["legal"] is False
    detail = _team_rows(out)["BOS"]["tpe_details"][0]
    assert detail["status"] == "expired"
    assert detail["as_of_date"] == "2026-10-02"
    assert any("effective expiry date 2026-10-01 passed before" in issue
               for issue in out["issues"])


def test_weekend_anniversary_rolls_to_next_business_day(
        monkeypatch, tmp_path):
    out = _dated_tpe_out(monkeypatch, tmp_path, {
        "team": "BOS", "amount": 8_000_000, "kind": "ordinary",
        "origin_date": "2025-10-04",
    }, evaluation_date="2026-10-05")
    assert out["ok"] is True
    assert out["legal"] is True, out["issues"]
    detail = _team_rows(out)["BOS"]["tpe_details"][0]
    assert detail["expiry_date"] == "2026-10-04"
    assert detail["effective_expiry_date"] == "2026-10-05"
    assert detail["status"] == "prior_year"


def test_day_after_weekend_anniversary_rollover_expires(
        monkeypatch, tmp_path):
    out = _dated_tpe_out(monkeypatch, tmp_path, {
        "team": "BOS", "amount": 8_000_000, "kind": "ordinary",
        "origin_date": "2025-10-04",
    }, evaluation_date="2026-10-06")
    assert out["ok"] is True
    assert out["legal"] is False
    detail = _team_rows(out)["BOS"]["tpe_details"][0]
    assert detail["status"] == "expired"
    assert detail["effective_expiry_date"] == "2026-10-05"


def test_federal_holiday_anniversary_rolls_to_next_business_day(
        monkeypatch, tmp_path):
    out = _dated_tpe_out(monkeypatch, tmp_path, {
        "team": "BOS", "amount": 8_000_000, "kind": "ordinary",
        "origin_date": "2025-12-25",
    }, evaluation_date="2026-12-28")
    assert out["ok"] is True
    assert out["legal"] is True, out["issues"]
    detail = _team_rows(out)["BOS"]["tpe_details"][0]
    assert detail["expiry_date"] == "2026-12-25"
    assert detail["effective_expiry_date"] == "2026-12-28"
    assert detail["status"] == "prior_year"


def test_day_after_holiday_anniversary_rollover_expires(
        monkeypatch, tmp_path):
    out = _dated_tpe_out(monkeypatch, tmp_path, {
        "team": "BOS", "amount": 8_000_000, "kind": "ordinary",
        "origin_date": "2025-12-25",
    }, evaluation_date="2026-12-29")
    assert out["ok"] is True
    assert out["legal"] is False
    detail = _team_rows(out)["BOS"]["tpe_details"][0]
    assert detail["status"] == "expired"
    assert detail["effective_expiry_date"] == "2026-12-28"


def test_future_origin_date_makes_tpe_unavailable(monkeypatch, tmp_path):
    out = _dated_tpe_out(monkeypatch, tmp_path, {
        "team": "BOS", "amount": 8_000_000, "kind": "ordinary",
        "origin_date": "2026-12-01",
    })
    assert out["ok"] is True
    assert out["legal"] is False
    detail = _team_rows(out)["BOS"]["tpe_details"][0]
    assert detail["status"] == "future"
    assert detail["timing_basis"] == "exact_date"
    assert any("not yet available" in issue for issue in out["issues"])


def test_tpe_rejects_unknown_kind():
    from shared.tools import get_trade_legality

    out = get_trade_legality.invoke({
        "legs": '[{"from":"MIA","to":"BOS","players":"Alpha One"}]',
        "tpe": '[{"team":"BOS","amount":8000000,"kind":"mystery",'
               '"origin_season":"2026-27"}]',
        "season": "2026-27",
    })
    assert out["ok"] is False
    assert "ordinary or sign_and_trade" in out["error"]


def _tpe_validation_out(row):
    from shared.tools import get_trade_legality

    return get_trade_legality.invoke({
        "legs": '[{"from":"MIA","to":"BOS","players":"Alpha One"}]',
        "tpe": json.dumps([row]),
        "season": "2026-27",
    })


@pytest.mark.parametrize("value", ["10/01/2026", "2026-02-30"])
def test_trade_legality_rejects_malformed_evaluation_date(value):
    from shared.tools import get_trade_legality

    out = get_trade_legality.invoke({
        "legs": '[{"from":"MIA","to":"BOS","players":"Alpha One"}]',
        "evaluation_date": value,
        "season": "2026-27",
    })
    assert out["ok"] is False
    assert "evaluation_date must be YYYY-MM-DD" in out["error"]


@pytest.mark.parametrize("origin_season", ["2026-99", "2026 garbage"])
def test_tpe_rejects_invalid_origin_season(origin_season):
    out = _tpe_validation_out({
        "team": "BOS", "amount": 8_000_000, "kind": "ordinary",
        "origin_season": origin_season,
    })
    assert out["ok"] is False
    assert "origin_season must be YYYY-YY with consecutive years" in out["error"]


@pytest.mark.parametrize("row", [
    {"team": "BOS", "amount": 8_000_000.9, "kind": "ordinary",
     "origin_season": "2026-27"},
    {"team": "BOS", "amount": True, "kind": "ordinary",
     "origin_season": "2026-27"},
    {"team": "BOS", "amount": 8_000_000, "kind": "ordinary",
     "origin_year": True},
])
def test_tpe_rejects_non_integer_numeric_values(row):
    out = _tpe_validation_out(row)
    assert out["ok"] is False
    assert "integer" in out["error"]


@pytest.mark.parametrize("key", [
    "amount", "kind", "origin_year", "origin_season", "origin_date",
    "expiry_date",
])
def test_tpe_rejects_explicit_null_typed_keys(key):
    row = {"team": "BOS", "amount": 8_000_000, "kind": "ordinary",
           "origin_season": "2026-27", key: None}
    out = _tpe_validation_out(row)
    assert out["ok"] is False
    assert "explicit null" in out["error"]


@pytest.mark.parametrize("key,value", [
    ("origin_date", "12/15/2025"),
    ("origin_date", "2025-02-30"),
    ("expiry_date", "2026-02-30"),
    ("expiry_date", 20261215),
])
def test_tpe_rejects_malformed_exact_dates(key, value):
    row = {"team": "BOS", "amount": 8_000_000, "kind": "ordinary",
           "origin_season": "2025-26", key: value}
    out = _tpe_validation_out(row)
    assert out["ok"] is False
    assert f"{key} must be YYYY-MM-DD" in out["error"]


def test_tpe_rejects_expiry_before_origin():
    out = _tpe_validation_out({
        "team": "BOS", "amount": 8_000_000, "kind": "ordinary",
        "origin_date": "2025-12-15", "expiry_date": "2025-12-15",
    })
    assert out["ok"] is False
    assert "expiry_date must be after origin_date" in out["error"]


def test_tpe_rejects_origin_date_mismatched_with_origin_season():
    out = _tpe_validation_out({
        "team": "BOS", "amount": 8_000_000, "kind": "ordinary",
        "origin_season": "2026-27", "origin_date": "2025-12-15",
    })
    assert out["ok"] is False
    assert "origin_date does not match origin_year/origin_season" in out["error"]


def test_cap_scenario_crossing_first_apron_uses_post_move_strict_matching(
        monkeypatch, tmp_path):
    from shared.tools import get_cap_scenario

    _seed(monkeypatch, tmp_path,
          _roster("BOS", 205_000_000, [("Alpha One", 25_000_000)])
          + _roster("MIA", 150_000_000, [("Beta Two", 30_000_000)]))
    out = get_cap_scenario.invoke({
        "team": "BOS", "trade_out_players": "Alpha One",
        "in_players": "Beta Two", "season": "2026-27",
    })
    assert out["ok"] is True
    assert out["summary"]["payroll_after"] == 210_000_000
    assert out["summary"]["over_apron1"] is True
    assert out["matching"]["allowed_incoming"] == 25_000_000
    assert out["matching"]["match_rule"] == "100% (above the first apron)"
    assert out["matching"]["legal"] is False
    assert any("takes back too much" in issue for issue in out["issues"])


def test_cap_scenario_dropping_below_first_apron_uses_post_move_band(
        monkeypatch, tmp_path):
    from shared.tools import get_cap_scenario

    _seed(monkeypatch, tmp_path,
          _roster("BOS", 212_000_000, [("Alpha One", 30_000_000)])
          + _roster("MIA", 150_000_000, [("Beta Two", 25_000_000)]))
    out = get_cap_scenario.invoke({
        "team": "BOS", "trade_out_players": "Alpha One",
        "in_players": "Beta Two", "season": "2026-27",
    })
    assert out["ok"] is True
    assert out["summary"]["payroll_after"] == 207_000_000
    assert out["summary"]["over_apron1"] is False
    assert out["matching"]["allowed_incoming"] == 39_096_000
    assert out["matching"]["match_rule"] == STANDARD_MATCH_RULE
    assert out["matching"]["legal"] is True


def _split_even(total):
    high = total // 2 + total % 2
    return high, total - high


def _boundary_seed_rows(payroll, outgoing_stars, incoming_stars, anchor_count):
    anchors = [(f"Anchor {index}", 1_000_000)
               for index in range(4, 4 + anchor_count)]
    return (_roster("PHX", payroll, outgoing_stars + anchors)
            + _roster("MIA", 150_000_000, incoming_stars))


@pytest.mark.parametrize("offset", [-1, 0, 1])
def test_cap_scenario_multiple_incoming_second_apron_boundary_not_aggregation(
        monkeypatch, tmp_path, offset):
    from shared.tools import get_cap_scenario
    from shared.tools.cap_rules import CAP

    payroll = CAP["apron2"] + offset
    outgoing = 30_000_000 + offset
    first_in, second_in = _split_even(outgoing)
    _seed(monkeypatch, tmp_path,
          _boundary_seed_rows(
              payroll, [("Alpha One", outgoing)],
              [("Beta Two", first_in), ("Gamma Three", second_in)], 3))
    out = get_cap_scenario.invoke({
        "team": "PHX", "trade_out_players": "Alpha One",
        "in_players": "Beta Two, Gamma Three", "season": "2026-27",
    })
    assert out["ok"] is True
    assert out["summary"]["payroll_after"] == payroll
    assert out["summary"]["room_apron2"] == -offset
    assert out["summary"]["over_apron2"] == (offset == 1)
    assert out["summary"]["hard_cap"] == ""
    assert out["matching"]["incoming"] == outgoing
    assert out["matching"]["outgoing"] == outgoing
    assert out["matching"]["legal"] is True
    assert not any("aggregate" in issue or "aggregation" in issue
                   for issue in out["issues"])


@pytest.mark.parametrize(
    "offset,legal,match_rule",
    [(-1, True, AGGREGATED_STANDARD_MATCH_RULE),
     (0, True, AGGREGATED_STANDARD_MATCH_RULE),
     (1, False, "no aggregation (above the second apron)")])
def test_cap_scenario_multiple_outgoing_second_apron_boundary_aggregates(
        monkeypatch, tmp_path, offset, legal, match_rule):
    from shared.tools import get_cap_scenario
    from shared.tools.cap_rules import CAP

    payroll = CAP["apron2"] + offset
    outgoing = 30_000_000 + offset
    first_out, second_out = _split_even(outgoing)
    _seed(monkeypatch, tmp_path,
          _boundary_seed_rows(
              payroll,
              [("Alpha One", first_out), ("Delta Four", second_out)],
              [("Beta Two", outgoing)], 4))
    out = get_cap_scenario.invoke({
        "team": "PHX", "trade_out_players": "Alpha One, Delta Four",
        "in_players": "Beta Two", "season": "2026-27",
    })
    assert out["ok"] is True
    assert out["summary"]["payroll_after"] == payroll
    assert out["summary"]["room_apron2"] == -offset
    assert out["summary"]["over_apron2"] == (offset == 1)
    assert out["summary"]["hard_cap"] == "second apron"
    assert out["matching"]["incoming"] == outgoing
    assert out["matching"]["outgoing"] == outgoing
    assert out["matching"]["legal"] is legal
    assert out["matching"]["match_rule"] == match_rule
    assert out["matching"]["allowed_incoming"] == (outgoing if legal else 0)
    aggregation_ban = any("cannot aggregate salaries above the second apron"
                          in issue for issue in out["issues"])
    assert aggregation_ban is (offset == 1)


def test_cap_scenario_second_apron_receiver_multiple_incoming_is_not_aggregation(
        monkeypatch, tmp_path):
    from shared.tools import get_cap_scenario

    _seed(monkeypatch, tmp_path,
          _roster("PHX", 230_000_000,
                  [("Alpha One", 30_000_000),
                   ("Anchor Four", 1_000_000),
                   ("Anchor Five", 1_000_000)])
          + _roster("MIA", 150_000_000,
                    [("Beta Two", 15_000_000),
                     ("Gamma Three", 15_000_000)]))
    out = get_cap_scenario.invoke({
        "team": "PHX", "trade_out_players": "Alpha One",
        "in_players": "Beta Two, Gamma Three", "season": "2026-27",
    })
    assert out["ok"] is True
    assert out["summary"]["payroll_after"] == 230_000_000
    assert out["summary"]["over_apron2"] is True
    assert out["matching"]["allowed_incoming"] == 30_000_000
    assert out["matching"]["match_rule"] == STANDARD_MATCH_RULE
    assert out["matching"]["legal"] is True
    assert not any("aggregate" in issue or "aggregation" in issue
                   for issue in out["issues"])


def test_cap_scenario_multiple_outgoing_players_remain_conservative(
        monkeypatch, tmp_path):
    from shared.tools import get_cap_scenario

    _seed(monkeypatch, tmp_path,
          _roster("PHX", 230_000_000,
                  [("Alpha One", 15_000_000),
                   ("Delta Four", 15_000_000),
                   ("Anchor Five", 1_000_000),
                   ("Anchor Six", 1_000_000)])
          + _roster("MIA", 150_000_000, [("Beta Two", 25_000_000)]))
    out = get_cap_scenario.invoke({
        "team": "PHX", "trade_out_players": "Alpha One, Delta Four",
        "in_players": "Beta Two", "season": "2026-27",
    })
    assert out["ok"] is True
    assert out["summary"]["payroll_after"] == 225_000_000
    assert out["summary"]["over_apron2"] is True
    assert out["matching"]["legal"] is False
    assert out["matching"]["match_rule"] == (
        "no aggregation (above the second apron)")
    assert any("cannot aggregate salaries above the second apron" in issue
               for issue in out["issues"])


def test_cap_scenario_dropping_below_second_apron_clears_aggregation_ban(
        monkeypatch, tmp_path):
    from shared.tools import get_cap_scenario

    _seed(monkeypatch, tmp_path,
          _roster("BOS", 224_000_000,
                  [("Alpha One", 15_000_000), ("Beta Two", 15_000_000)])
          + _roster("MIA", 150_000_000, [("Gamma Three", 25_000_000)]))
    out = get_cap_scenario.invoke({
        "team": "BOS", "trade_out_players": "Alpha One, Beta Two",
        "in_players": "Gamma Three", "season": "2026-27",
    })
    assert out["ok"] is True
    assert out["summary"]["payroll_after"] == 219_000_000
    assert out["summary"]["over_apron2"] is False
    assert out["matching"]["legal"] is True
    assert not any("cannot aggregate" in issue for issue in out["issues"])


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


def test_trade_partners_crossing_first_apron_drops_over_apron_packages(
        monkeypatch, tmp_path):
    from shared.tools import get_trade_partners

    _seed(monkeypatch, tmp_path,
          _roster("BOS", 205_000_000, [("Alpha One", 25_000_000)])
          + _roster("MIA", 150_000_000, [("Beta Two", 30_000_000)]))
    out = get_trade_partners.invoke({
        "player": "Alpha One", "teams": "MIA", "season": "2026-27",
    })
    assert out["ok"] is True
    rows = out["rows"]
    assert not any(r["players"] == "Beta Two" for r in rows)
    assert all(r["package_salary"] <= 29_015_000 for r in rows)
    assert out["meta"]["max_return_salary"] == 29_015_000
    assert out["meta"]["match_rule_in"] == (
        "outgoing salary plus $9.096M (below the first apron)")


def test_trade_partners_dropping_below_second_apron_allows_aggregation(
        monkeypatch, tmp_path):
    from shared.tools import get_trade_partners

    _seed(monkeypatch, tmp_path,
          _roster("BOS", 150_000_000, [("Alpha One", 25_000_000)])
          + _roster("MIA", 224_000_000,
                    [("Beta Two", 15_000_000), ("Gamma Three", 15_000_000)]))
    out = get_trade_partners.invoke({
        "player": "Alpha One", "teams": "MIA", "season": "2026-27",
    })
    assert out["ok"] is True
    rows = [r for r in out["rows"] if r["team"] == "MIA"]
    pair = [r for r in rows if r["players"] == "Beta Two, Gamma Three"]
    assert pair, rows
    assert pair[0]["package_salary"] == 30_000_000
    assert pair[0]["over_apron2"] is False
    assert pair[0]["legal"] is True
