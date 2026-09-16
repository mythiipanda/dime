"""Today-page movers route: snapshot-pending must read as honest empty."""
import asyncio

from app.routes import api_movers


def test_movers_route_translates_snapshot_pending_to_empty():
    # Warehouse here has <2 leaderboard_snapshots dates, so the tool
    # errors; the UI route must return ok:true with empty lists so the
    # panel renders "No movers yet" instead of a failure message.
    out = asyncio.run(api_movers(season="2025-26", days=7))
    assert out["ok"] is True
    rows = out["rows"]
    assert rows == {"climbers": [], "fallers": [], "new_entries": []}
    assert out["meta"]["reason"] == "snapshots_pending"


def test_today_and_movers_share_empty_projection(monkeypatch):
    from app.tools.today import _movers_from_delta, normalize_movers
    failed = {"ok": False, "error": "not enough snapshots (need at least 2 dates)"}
    assert _movers_from_delta(failed, "2025-26") == []
    assert normalize_movers(failed, "2025-26")["rows"] == {
        "climbers": [], "fallers": [], "new_entries": []}


def test_today_and_movers_share_movement_projection():
    from app.tools.today import _movers_from_delta, normalize_movers
    delta = {"ok": True, "rows": {"climbers": [
        {"player": "A", "team": "BOS", "rank_change": 2, "pts_change": 3.1}],
        "fallers": [], "new_entries": []}}
    normalized = normalize_movers(delta, "2025-26")
    today = _movers_from_delta(delta, "2025-26")
    assert normalized["rows"]["climbers"][0]["player"] == today[0]["PLAYER"]
    assert today[0]["RANK_CHANGE"] == "+2"
