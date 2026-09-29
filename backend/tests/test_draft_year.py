
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.tools.league import _norm_draft_year, get_combine  # noqa: E402


def test_season_label_maps_to_draft_year():
    assert _norm_draft_year("2025-26") == "2025"
    assert _norm_draft_year("2025") == "2025"
    assert _norm_draft_year("") == ""


def test_combine_season_label_returns_rows():
    import asyncio
    r = asyncio.run(get_combine.ainvoke({"season": "2025-26"}))
    assert r["ok"] is True
    assert r["rows"], "2025 combine is seeded (79 rows)"


def test_combine_unknown_year_falls_back_with_note():
    import asyncio
    r = asyncio.run(get_combine.ainvoke({"season": "2026"}))
    assert r["ok"] is True
    assert r["rows"]
    assert "2025" in str((r.get("meta") or {}).get("note"))


def test_draft_board_degrades_to_combine_when_college_blocked():
    import asyncio
    from shared.tools.league import get_draft_board
    r = asyncio.run(get_draft_board.ainvoke({"season": "2025-26"}))
    assert r["ok"] is True
    assert r["rows"], "combine-only board expected when cbb is blocked"
    assert r["rows"][0].get("PLAYER_NAME")
