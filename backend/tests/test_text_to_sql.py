"""text_to_sql schema-cap regression tests. Read the real warehouse."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import tools
from app.config import settings
from app.tools.league import _describe_warehouse_schema

WH = Path(__file__).resolve().parent.parent / "data" / "warehouse.duckdb"


def _leaders_cols():
    cols = [f"C{i}" for i in range(32)]
    cols[0] = "PLAYER_ID"
    cols[20] = "STL"
    cols[21] = "BLK"
    cols[24] = "PTS"
    return cols


def test_schema_description_keeps_late_leader_columns():
    out = _describe_warehouse_schema({"silver_leaders_stl": _leaders_cols()})
    assert "STL" in out
    assert "BLK" in out
    assert "PTS" in out


def test_schema_description_truncates_wide_tables():
    wide = [f"C{i}" for i in range(60)]
    out = _describe_warehouse_schema({"wide_table": wide})
    parts = out.split(": ", 1)[1].split(", ")
    assert len(parts) == 40
    assert "C39" in out
    assert "C59" not in out


def test_steals_leader_matches_warehouse():
    import asyncio

    import duckdb

    if not WH.exists():
        pytest.skip("warehouse missing")
    if not settings.mistral_api_key:
        pytest.skip("no Mistral API key")
    try:
        con = duckdb.connect(str(WH), read_only=True)
        try:
            expected = con.execute(
                "SELECT PLAYER, STL FROM silver_leaders_stl"
                " WHERE _season = '2025-26' ORDER BY STL DESC LIMIT 1"
            ).fetchone()
        finally:
            con.close()
    except Exception:
        pytest.skip("silver_leaders_stl unavailable")
    if not expected:
        pytest.skip("no 2025-26 steals leader row")
    res = asyncio.run(
        tools.text_to_sql.ainvoke(
            {"question": "who led the 2025-26 season in steals"}
        )
    )
    assert res["ok"] is True
    first = res["rows"][0]
    assert first["PLAYER"] == expected[0]
    assert int(first["STL"]) == int(expected[1])
