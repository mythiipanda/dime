import sys
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_surname_grouping_merges_distinct_players():
    con = duckdb.connect(":memory:")
    try:
        con.execute(
            "CREATE TABLE silver_hist_shots "
            "(person_id BIGINT, player_name TEXT, game_id TEXT, "
            "shot_value INTEGER, shot_result TEXT, _season TEXT)")
        con.executemany(
            "INSERT INTO silver_hist_shots VALUES (?, ?, '00201', 3, 'Made', '2024-25')",
            [(101, "Porter Jr.")] * 30 + [(202, "Porter Jr.")] * 48
            + [(303, "Thompson")] * 647 + [(404, "Thompson")] * 49)
        by_name = con.execute(
            "SELECT player_name, COUNT(*) FROM silver_hist_shots "
            "WHERE _season='2024-25' GROUP BY player_name").fetchall()
        by_id = con.execute(
            "SELECT person_id, COUNT(*) FROM silver_hist_shots "
            "WHERE _season='2024-25' GROUP BY person_id").fetchall()
    finally:
        con.close()
    assert sorted(by_name) == [("Porter Jr.", 78), ("Thompson", 696)]
    assert sorted(by_id) == [(101, 30), (202, 48), (303, 647), (404, 49)]


def test_season_row_counts_are_per_game_not_totals():
    con = duckdb.connect(":memory:")
    try:
        con.execute(
            "CREATE TABLE silver_hist_player_seasons "
            "(player_id BIGINT, player_name TEXT, gp INTEGER, fg3a DOUBLE, _season TEXT)")
        con.execute(
            "INSERT INTO silver_hist_player_seasons VALUES "
            "(101, 'Craig Porter Jr.', 77, 0.6, '2024-25')")
        row = con.execute(
            "SELECT fg3a FROM silver_hist_player_seasons "
            "WHERE player_id=101 AND _season='2024-25'").fetchone()
    finally:
        con.close()
    assert row[0] < 40
