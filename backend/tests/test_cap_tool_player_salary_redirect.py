from backend.shared.tools.league import cba_cap


def test_cap_ledger_redirects_player_salary_asks():
    d = cba_cap.get_cap_ledger.description
    assert "no player salaries" in d
    assert "silver_salaries" in d
    assert "get_trade_check" in d


def test_cap_table_redirects_player_salary_asks():
    d = cba_cap.get_cap_table.description
    assert "no player salaries" in d
    assert "get_trade_check" in d
