
from shared.tools import get_trade_check

def test_teams_inferred_from_player_names():
    out = get_trade_check.invoke({
        "team_a": "", "players_a": "Jalen Brunson",
        "team_b": "", "players_b": "Victor Wembanyama",
        "season": "2025-26"})
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

def test_trade_check_surfaces_conditional_tpe_creation():
    out = get_trade_check.invoke({
        "team_a": "BOS", "players_a": "Derrick White",
        "team_b": "DAL", "players_b": "P.J. Washington",
        "season": "2026-27"})
    assert out["ok"] is True
    rows = out["rows"]
    creation = rows["team_a"].get("tpe_creation")
    assert creation is not None
    expected = rows["team_a"]["out"] - rows["team_b"]["out"]
    assert creation["amount"] == expected
    assert "non-simultaneous" in creation["copy"]
    assert "generates nothing" in creation["copy"]
    assert rows["team_b"].get("tpe_creation") is None

def test_trade_check_no_creation_when_balanced():
    out = get_trade_check.invoke({
        "team_a": "CHI", "players_a": "Josh Giddey",
        "team_b": "HOU", "players_b": "Fred VanVleet",
        "season": "2026-27"})
    assert out["ok"] is True
    rows = out["rows"]
    assert rows["team_a"].get("tpe_creation") is None
    assert rows["team_b"].get("tpe_creation") is None
