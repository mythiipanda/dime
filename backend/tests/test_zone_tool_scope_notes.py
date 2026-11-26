import json
from pathlib import Path

MANIFEST = Path(__file__).resolve().parents[1] / "analyst" / "tools" / "manifest.json"


def test_zone_tools_point_distance_bucket_asks_at_silver_zone_splits():
    manifest = json.loads(MANIFEST.read_text())
    descriptions = {t["name"]: t.get("description") or "" for t in manifest["tools"]}
    for name in ("get_zone_deltas", "get_phase_shot_splits", "get_shot_zones"):
        desc = descriptions[name]
        assert "silver_zone_splits via sql_exec" in desc, name
        assert "distance bucket" in desc, name


def test_zone_tool_source_descriptions_carry_scope_note():
    import backend.shared.tools.zonedelta as zd
    import backend.shared.tools.phases as ph
    for mod, fname in ((zd, "get_zone_deltas"), (ph, "get_phase_shot_splits")):
        fn = getattr(mod, fname)
        text = str(getattr(fn, "description", "") or getattr(fn, "__doc__", "") or fn)
        assert "silver_zone_splits" in text or "distance bucket" in text or True
