import pytest

from analyst.tools import sql_hints


@pytest.fixture(autouse=True)
def _columns(monkeypatch):
    monkeypatch.setattr(sql_hints, "_warehouse_columns", lambda: {
        "silver_salaries": {"PLAYER_NAME": "text", "TEAM": "text",
                            "SALARY_2026_27": "numeric"},
        "silver_leaders_pts": {"PLAYER_NAME": "text", "PTS": "numeric"},
        "silver_advanced": {"PLAYER_NAME": "text", "NET_RATING": "numeric"},
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
