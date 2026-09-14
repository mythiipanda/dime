"""Player-named opponents in get_head_to_head resolve to their team."""
import asyncio

from app.tools.headtohead import get_head_to_head


def _run(args):
    return asyncio.run(get_head_to_head.ainvoke(args))


def test_player_opponent_resolves_to_team():
    r = _run({"player": "Luka Dončić",
              "opponent": "Shai Gilgeous-Alexander", "season": "2025-26"})
    assert r["ok"]
    assert r["rows"]["opponent"] == "OKC"
    assert "resolved to team OKC" in (r["rows"].get("note") or "")


def test_team_opponent_unchanged():
    r = _run({"player": "Luka Dončić", "opponent": "OKC",
              "season": "2025-26"})
    assert r["ok"] and r["rows"]["opponent"] == "OKC"
    assert "resolved to team" not in (r["rows"].get("note") or "")


def test_unknown_opponent_still_errors():
    r = _run({"player": "Luka Dončić", "opponent": "Zorblax Nine",
              "season": "2025-26"})
    assert not r["ok"]


def test_compare_different_teams_reports_meetings():
    from app.tools.player import get_compare
    r = asyncio.run(get_compare.ainvoke(
        {"a": "Luka Dončić", "b": "Shai Gilgeous-Alexander",
         "season": "2025-26"}))
    assert r["ok"]
    pair = r["rows"]["pair"]
    assert not pair["teammates"]
    meetings = pair.get("h2h_meetings") or []
    assert len(meetings) == 2
    assert "shared the floor in 2 game(s)" in pair["note"]
    assert "no shared court" not in pair["note"].lower()


def test_compare_no_meetings_says_teams_did_not_meet():
    from app.tools.player import _different_teams_pair
    pair = _different_teams_pair(
        {"player_id": 1629029, "team": "LAL", "name": "Luka Dončić"},
        {"player_id": 201939, "team": "GSW", "name": "Stephen Curry"},
        "2025-26")
    assert pair.get("h2h_meetings") is not None
