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
