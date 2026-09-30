
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.tools.league import _norm_draft_year, get_combine  # noqa: E402


def test_season_label_maps_to_draft_year():
    assert _norm_draft_year("2025-26") == "2026"
    assert _norm_draft_year("2024-25") == "2025"
    assert _norm_draft_year("2025") == "2025"


def test_draft_year_boundaries():
    assert _norm_draft_year("2024") == "2024"
    assert _norm_draft_year("2025") == "2025"
    assert _norm_draft_year("2026") == "2026"
    assert _norm_draft_year("2023-24") == "2024"
    assert _norm_draft_year("2025-26") == "2026"


def test_draft_year_rejects_garbage():
    for bad in ("abc", "20-25", "2025-27", "", "  "):
        with pytest.raises(ValueError):
            _norm_draft_year(bad)


def test_combine_season_label_returns_rows():
    import asyncio
    r = asyncio.run(get_combine.ainvoke({"season": "2024-25"}))
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
    r = asyncio.run(get_draft_board.ainvoke({"season": "2024-25"}))
    assert r["ok"] is True
    assert r["rows"], "combine-only board expected when cbb is blocked"
    assert r["rows"][0].get("PLAYER_NAME")


def test_repro_board_pipeline_resolves_2025():
    from shared.tools._core import COVERAGE_END, clamp_season
    clamped = clamp_season("2025", "1996-97", COVERAGE_END)
    assert _norm_draft_year(clamped) == "2025"


def test_repro_model_slug_parses_to_ending_year():
    assert _norm_draft_year("2024-25") == "2025"


def test_draft_tools_bypass_season_slug_map():
    import app.graph as graph_mod
    for name in ("get_draft_board", "get_draft_model", "get_combine"):
        assert name in graph_mod._SEASON_CLAMP_EXEMPT
    assert _norm_draft_year("2025") == "2025"


def test_season_tools_still_use_ending_year_map():
    from shared.tools._core import COVERAGE_END, clamp_season
    assert clamp_season("2025", "1996-97", COVERAGE_END) == "2024-25"


def test_draft_tools_reject_garbage_year():
    import asyncio
    from shared.tools.league import get_draft_board
    r = asyncio.run(get_draft_board.ainvoke({"season": "abc"}))
    assert r["ok"] is False
    assert "draft year" in str(r.get("error", ""))
    r = asyncio.run(get_combine.ainvoke({"season": "abc"}))
    assert r["ok"] is False
    assert "draft year" in str(r.get("error", ""))
