from app.tools import get_trade_check


def test_trade_check_fails_closed_on_salary_vintage_mismatch():
    out = get_trade_check.invoke({
        "team_a": "LAL", "players_a": "LeBron James",
        "team_b": "MIA", "players_b": "Giannis Antetokounmpo",
        "season": "2025-26",
    })
    assert out["ok"] is False
    assert "salary data is for 2026-27, not 2025-26" in out["error"]
    assert "not calculated" in out["error"]
