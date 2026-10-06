import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from shared.tools.zone import get_team_shot_zones

def test_corner_three_leader_zone_share_contract():
    out = get_team_shot_zones.invoke({"teams": "league", "season": "2025-26"})
    assert out["ok"] is True
    rows = out["rows"]
    assert len(rows) >= 2
    lead = max(rows, key=lambda r: r["corner_3_share"])
    assert lead["team"]
    assert all(0 <= r["corner_3_share"] <= 1 for r in rows)
    assert lead["corner_3_share"] >= sum(
        r["corner_3_share"] for r in rows) / len(rows)
