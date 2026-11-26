import duckdb

from shared.tools import _core
from shared.tools.league import cba_cap, fa_plan, free_agents, trade_targets
from shared.tools.league import value_contracts


def test_defunct_abbreviation_names_successor():
    msg = _core.team_error_message("SEA")
    assert "SuperSonics" in msg
    assert "OKC" in msg
    assert "unknown team" not in msg


def test_defunct_city_and_nickname():
    assert "SuperSonics" in _core.team_error_message("seattle")
    assert "SuperSonics" in _core.team_error_message("Sonics")
    assert "BKN" in _core.team_error_message("New Jersey Nets")
    assert "MEM" in _core.team_error_message("Vancouver")


def test_unknown_team_suggests_closest():
    msg = _core.team_error_message("Bostin")
    assert msg.startswith("unknown team:")
    assert "BOS" in msg
    assert "BOS" in msg.split("Closest current teams:")[1] \
        if "Closest current teams:" in msg else True


def test_coerce_team_id_defunct():
    try:
        _core.coerce_team_id("SEA")
    except ValueError as exc:
        assert "OKC" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_coerce_team_id_unknown_still_guides():
    try:
        _core.coerce_team_id("zzz-not-a-team")
    except ValueError as exc:
        assert "unknown team" in str(exc)
        assert "BOS" in str(exc) or "team_id" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_season_rows_error_lists_coverage():
    con = duckdb.connect()
    try:
        con.execute("CREATE TABLE t (_season TEXT)")
        con.execute("INSERT INTO t VALUES ('2024-25'), ('2025-26')")
        msg = _core.season_rows_error(con, "t", "2099-00", "CHI")
    finally:
        con.close()
    assert "no rows for CHI 2099-00 in t" in msg
    assert "2024-25" in msg and "2025-26" in msg


def test_season_rows_error_missing_table():
    con = duckdb.connect()
    try:
        msg = _core.season_rows_error(con, "nope", "2099-00", "SEA")
    finally:
        con.close()
    assert msg == "no rows for SEA 2099-00 in nope"


def test_cap_ledger_defunct_team():
    res = cba_cap.get_cap_ledger.invoke({"team": "SEA"})
    assert res["ok"] is False
    assert "SuperSonics" in res["error"]
    assert "team needed" not in res["error"]


def test_value_contracts_defunct_vs_empty():
    res = value_contracts.get_value_contracts.invoke({"team": "SEA"})
    assert res["ok"] is False
    assert "OKC" in res["error"]
    res = value_contracts.get_value_contracts.invoke({"team": ""})
    assert "team needed" not in str(res.get("error") or "")


def test_fa_plan_and_free_agents_unresolvable():
    res = fa_plan.get_fa_plan.invoke({"team": "NJN"})
    assert res["ok"] is False
    assert "BKN" in res["error"]
    res = free_agents.get_free_agents.invoke({"team": "sea"})
    assert res["ok"] is False
    assert "SuperSonics" in res["error"]


def test_trade_targets_keeps_row_contract():
    res = trade_targets.get_trade_targets.invoke({"team": "SEA"})
    assert res["ok"] is False
    assert "OKC" in res["error"]
    assert res["rows"] == [] and "columns" in res
