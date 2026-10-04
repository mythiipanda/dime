import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_team_clutch_fails_closed_without_team_rows():
    from shared.tools.league import get_clutch
    out = get_clutch.invoke({"scope": "team", "season": "2025-26"})
    assert out["ok"] is False
    assert out["rows"] == []
    assert "team-level" in out["error"]
