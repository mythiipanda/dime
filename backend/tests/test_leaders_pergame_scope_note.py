import json
from pathlib import Path

MANIFEST = Path(__file__).resolve().parents[1] / "analyst" / "tools" / "manifest.json"


def test_get_leaders_manifest_description_points_pergame_asks_at_sql_exec():
    manifest = json.loads(MANIFEST.read_text())
    desc = {t["name"]: t.get("description") or "" for t in manifest["tools"]}["get_leaders"]
    assert "silver_hist_player_seasons" in desc
    assert "per-game" in desc
    assert "season totals" in desc


def test_get_leaders_source_description_carries_pergame_scope_note():
    from backend.shared.tools.league.leaders import get_leaders
    text = str(getattr(get_leaders, "description", "") or "")
    assert "silver_hist_player_seasons" in text
    assert "per-game" in text
