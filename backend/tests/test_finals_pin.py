import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pytest


def test_2026_finals_winner_is_pinned_to_warehouse():
    from shared import store
    con = store.connect(read_only=True)
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        if "silver_playoffs" not in tables:
            pytest.skip("no silver_playoffs in this warehouse")
        wins = dict(con.execute(
            "SELECT TEAM_ABBREVIATION, SUM(CASE WHEN WL = 'W' THEN 1 ELSE 0 END) "
            "FROM silver_playoffs WHERE _season = '2025-26' "
            "AND GAME_ID LIKE '004%' AND GAME_DATE LIKE '2026-06%' "
            "GROUP BY TEAM_ABBREVIATION").fetchall())
    finally:
        con.close()
    assert wins.get("NYK") == 4
    assert wins.get("SAS") == 1
