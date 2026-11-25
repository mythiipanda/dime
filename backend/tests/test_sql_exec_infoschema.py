def test_information_schema_queries_pass_validation():
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from shared.tools.league.sql_schema import _validate_readonly_sql
    sql, used = _validate_readonly_sql(
        "SELECT column_name FROM information_schema.columns WHERE table_name = 'silver_hist_shots'",
        {"silver_hist_shots"})
    assert "information_schema" in sql

def test_foreign_qualified_tables_still_rejected():
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from shared.tools.league.sql_schema import _validate_readonly_sql
    import pytest
    with pytest.raises(ValueError):
        _validate_readonly_sql("SELECT * FROM other_db.silver_hist_shots", {"silver_hist_shots"})
