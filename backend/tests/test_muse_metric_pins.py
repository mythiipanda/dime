import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from shared.tools import get_young_player_usage

def test_young_usage_current_qualified_board():
    out = get_young_player_usage.invoke({})
    assert out["ok"] is True
    assert out["meta"]["min_minutes"] == 1000
    assert "1,000+ total minutes" in out["meta"]["deterministic_answer"]
    lead = out["rows"][0]
    assert lead["PLAYER"]
    assert all(r["USG_PCT"] <= lead["USG_PCT"] for r in out["rows"])
    assert lead["PLAYER"] in out["meta"]["deterministic_answer"]
