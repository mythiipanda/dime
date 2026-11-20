import sys
from pathlib import Path

import duckdb
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_silver_shots_dedup_by_game_event_key():
    con = duckdb.connect(":memory:")
    try:
        con.execute(
            "CREATE TABLE silver_shots (GAME_ID TEXT, GAME_EVENT_ID TEXT, "
            "PLAYER_NAME TEXT, SHOT_ZONE_BASIC TEXT, SHOT_ATTEMPTED_FLAG INTEGER, "
            "SHOT_MADE_FLAG INTEGER)")
        con.executemany(
            "INSERT INTO silver_shots VALUES ('00201', ?, 'LeBron James', 'Restricted Area', 1, ?)",
            [(str(i), 1 if i % 2 == 0 else 0) for i in range(10)]
            * 2)
        con.executemany(
            "INSERT INTO silver_shots VALUES ('00202', ?, 'Luka Dončić', 'Above the Break 3', 1, ?)",
            [(str(i), 0) for i in range(7)])
        raw = con.execute(
            "SELECT PLAYER_NAME, COUNT(*) FROM silver_shots GROUP BY 1"
        ).fetchall()
        dedup = con.execute(
            "SELECT PLAYER_NAME, COUNT(*) FROM "
            "(SELECT DISTINCT GAME_ID, GAME_EVENT_ID, PLAYER_NAME, SHOT_ZONE_BASIC, "
            "SHOT_ATTEMPTED_FLAG, SHOT_MADE_FLAG FROM silver_shots) d "
            "GROUP BY 1"
        ).fetchall()
        assert dict(raw)["LeBron James"] == 20
        assert dict(dedup)["LeBron James"] == 10
        assert dict(raw)["Luka Dončić"] == 7
        assert dict(dedup)["Luka Dončić"] == 7
    finally:
        con.close()


def test_overlaps_predicate_is_not_duckdb():
    con = duckdb.connect(":memory:")
    try:
        with pytest.raises(duckdb.ParserException):
            con.execute("SELECT [1, 2] OVERLAPS [2, 3]")
    finally:
        con.close()


def test_canonical_unit_key_dedups_equivalent_player_sets():
    con = duckdb.connect(":memory:")
    try:
        con.execute(
            "CREATE TABLE silver_hist_lineups (group_id TEXT, team_id TEXT, "
            "min DOUBLE, net_rating DOUBLE, season_type TEXT, measure_type TEXT, "
            "per_mode TEXT, poss DOUBLE)")
        con.execute(
            "INSERT INTO silver_hist_lineups VALUES "
            "('203999 - 1629008 - 1 - 2 - 3', 'DEN', 300.0, 8.0, 'Regular Season', 'Advanced', 'Totals', 600),"
            "('1 - 2 - 3 - 1629008 - 203999', 'DEN', 300.0, 8.0, 'Regular Season', 'Advanced', 'Totals', 600),"
            "('203999 - 1629008 - 4 - 5 - 6', 'DEN', 250.0, -2.0, 'Regular Season', 'Advanced', 'Totals', 500)")
        rows = con.execute(
            "SELECT array_to_string(list_sort(list_distinct(string_split(group_id, ' - '))), ',') AS canon, "
            "COUNT(*) n, SUM(min) min "
            "FROM silver_hist_lineups "
            "GROUP BY team_id, canon ORDER BY min DESC"
        ).fetchall()
        assert rows[0][0] == "1,1629008,2,203999,3"
        assert rows[0][1] == 2
        assert rows[0][2] == 600.0
        assert rows[1][1] == 1
        assert con.execute(
            "SELECT list_has_any(list_value('1','2'), list_value('2','3'))"
        ).fetchone()[0] is True
    finally:
        con.close()


def test_mmss_minutes_blank_is_zero():
    con = duckdb.connect(":memory:")
    try:
        con.execute("CREATE TABLE silver_boxscores (minutes TEXT, fta INTEGER)")
        con.executemany(
            "INSERT INTO silver_boxscores VALUES (?, ?)",
            [("17:03", 5), ("", 0), (None, 0), ("30:30", 4)])
        total = con.execute(
            "SELECT SUM(CASE WHEN minutes IS NULL OR minutes = '' THEN 0 "
            "ELSE CAST(split_part(minutes, ':', 1) AS INTEGER) "
            "+ CAST(split_part(minutes, ':', 2) AS DOUBLE) / 60 END) "
            "FROM silver_boxscores"
        ).fetchone()[0]
        assert abs(total - (17 + 3 / 60 + 30 + 30 / 60)) < 1e-9
    finally:
        con.close()
