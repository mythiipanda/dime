import json
from pathlib import Path

MANIFEST = Path(__file__).resolve().parents[1] / "analyst" / "tools" / "manifest.json"


def test_get_combine_manifest_description_scopes_cohort_asks_to_sql_exec():
    manifest = json.loads(MANIFEST.read_text())
    desc = {t["name"]: t.get("description") or "" for t in manifest["tools"]}["get_combine"]
    assert "silver_combine via sql_exec" in desc
    assert "at most 25 rows" in desc


def test_get_combine_source_description_and_truncation_meta():
    from backend.shared.tools.league.draft_contracts import get_combine
    text = str(getattr(get_combine, "description", "") or "")
    assert "silver_combine via sql_exec" in text
