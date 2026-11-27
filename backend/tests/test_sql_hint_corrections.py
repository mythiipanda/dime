import pytest

from analyst.tools import sql_hints


@pytest.fixture(autouse=True)
def _columns(monkeypatch):
    monkeypatch.setattr(sql_hints, "_warehouse_columns", lambda: {
        "silver_salaries": {"PLAYER_NAME": "text", "TEAM": "text",
                            "SALARY_2026_27": "numeric"},
        "silver_leaders_pts": {"PLAYER_NAME": "text", "PTS": "numeric"},
        "silver_advanced": {"PLAYER_NAME": "text", "NET_RATING": "numeric"},
        "silver_hist_shots": {"x_legacy": "numeric", "y_legacy": "numeric",
                              "shot_distance": "numeric", "season_type_id": "numeric"},
    })


def _fail(error):
    return {"tool": "sql_exec", "ok": False, "error": error}


def test_unknown_table_gets_similar_names():
    res = _fail('Catalog Error: Table with name "silver_salary" does not exist!')
    hint = sql_hints.schema_hint_for_sql_failure("select * from silver_salary", res)
    assert hint["unknown_tables"] == ["silver_salary"]
    assert "silver_salaries" in hint["similar_tables"]


def test_missing_column_gets_matches():
    res = _fail('Binder Error: Referenced column "PLAER_NAME" not found in FROM clause!')
    hint = sql_hints.schema_hint_for_sql_failure("select PLAER_NAME from silver_salaries", res)
    assert hint["missing_column"] == "PLAER_NAME"
    assert "silver_salaries.PLAYER_NAME" in hint["tables_with_column"]


def test_unbound_parameter_error_gets_inline_literal_fix():
    res = _fail("Binder Error: Values were not provided for parameter 1")
    hint = sql_hints.schema_hint_for_sql_failure(
        "select * from silver_salaries where TEAM = ?", res)
    fix = hint["parameter_error"]
    assert "raw SQL string" in fix["rule"]
    assert "literal" in fix["fix"]
    assert "sql_exec(" in fix["example"]


def test_syntax_error_extracts_offending_token_and_clause():
    sql = "select TEAM, SALARY_2026_27 from silver_salaries whre TEAM = 'BOS'"
    res = _fail('Parser Error: syntax error at or near "whre"')
    hint = sql_hints.schema_hint_for_sql_failure(sql, res)
    err = hint["syntax_error"]
    assert err["offending_token"] == "whre"
    assert "whre TEAM" in err["clause"]
    assert err["fix"]


def test_syntax_error_without_token_still_gives_fix():
    res = _fail('Parser Error: syntax error at or near "),"')
    hint = sql_hints.schema_hint_for_sql_failure("select a, from t", res)
    assert hint["syntax_error"]["offending_token"] == "),"


def test_success_returns_none():
    assert sql_hints.schema_hint_for_sql_failure(
        "select 1", {"ok": True}) is None


def test_unrelated_error_returns_none_when_no_match():
    res = _fail("out of memory")
    assert sql_hints.schema_hint_for_sql_failure("select 1", res) is None


def test_failure_on_constant_table_seeds_constants():
    res = _fail('Binder Error: Referenced column "LOCX" not found in FROM clause!')
    hint = sql_hints.schema_hint_for_sql_failure(
        "select LOCX from silver_hist_shots where season_type_id = 2", res)
    assert "silver_hist_shots" in hint["table_constants"]
    assert "corner_3" in hint["table_constants"]["silver_hist_shots"]
    assert "season_type_id" in hint["table_constants"]["silver_hist_shots"]


def test_empty_result_seeds_columns_and_constants():
    res = {"tool": "sql_exec", "ok": True, "rows": [], "row_count": 0}
    hint = sql_hints.schema_hint_for_sql_empty(
        "select * from silver_hist_shots where season_type_id = 9", res)
    assert hint["empty_result"]
    assert "silver_hist_shots" in hint["referenced_tables"]
    assert "silver_hist_shots" in hint["table_constants"]


def test_empty_result_without_table_returns_none():
    res = {"tool": "sql_exec", "ok": True, "rows": [], "row_count": 0}
    assert sql_hints.schema_hint_for_sql_empty("select 1", res) is None


def test_nonempty_result_returns_none_for_empty_hint():
    res = {"tool": "sql_exec", "ok": True, "rows": [{"a": 1}], "row_count": 1}
    assert sql_hints.schema_hint_for_sql_empty(
        "select * from silver_hist_shots", res) is None


def test_silver_lineups_constants_document_measure_multiplex_and_group_columns():
    consts = sql_hints._TABLE_CONSTANTS["silver_lineups"]
    assert "MEASURE" in consts
    assert "advanced" in consts["MEASURE"]
    assert "GROUP_ID" in consts
    assert "no lineup_id" in consts["GROUP_ID"]
    assert "multiplexed" in consts["shape"]
