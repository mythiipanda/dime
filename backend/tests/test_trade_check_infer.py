
from shared.tools import get_trade_check

def test_teams_inferred_from_player_names():
    out = get_trade_check.invoke({
        "team_a": "", "players_a": "Jalen Brunson",
        "team_b": "", "players_b": "Victor Wembanyama",
        "season": "2026-27"})
    assert out["ok"] is True
    rows = out["rows"]
    assert rows["team_a"]["team"] == "NYK"
    assert rows["team_b"]["team"] == "SAS"
    assert "legal" in rows

def test_still_errors_when_nothing_resolves():
    out = get_trade_check.invoke({
        "team_a": "", "players_a": "", "team_b": "", "players_b": ""})
    assert out["ok"] is False
    assert "two teams needed" in out["error"]
