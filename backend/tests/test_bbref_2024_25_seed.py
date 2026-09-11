"""2024-25 bbref seeder tests. Offline only: synthetic HTML plus a temp
DuckDB copy. Never touches the network or the real warehouse."""

import sys
from pathlib import Path

import pytest
from lxml import html

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import seed_bbref_gamelogs_2024_25 as seed
from seed_bbref_gamelogs import parse_minutes
from app import store


def _table(rows_html: str):
    doc = html.fromstring(
        "<table id='player_game_log_reg'><tbody>" + rows_html + "</tbody></table>"
    )
    return doc.xpath("//table")[0]


def _row(date, team, loc, opp, result, mp, href=None, cls=""):
    link = f"<a href='{href}'>{date}</a>" if href else date
    return (
        f"<tr class='{cls}'>"
        f"<td data-stat='date'>{link}</td>"
        f"<td data-stat='team_name_abbr'>{team}</td>"
        f"<td data-stat='game_location'>{loc}</td>"
        f"<td data-stat='opp_name_abbr'>{opp}</td>"
        f"<td data-stat='game_result'>{result}</td>"
        f"<td data-stat='mp'>{mp}</td>"
        "<td data-stat='fg'>8</td><td data-stat='fga'>15</td>"
        "<td data-stat='fg_pct'>.533</td>"
        "<td data-stat='fg3'>2</td><td data-stat='fg3a'>5</td>"
        "<td data-stat='fg3_pct'>.400</td>"
        "<td data-stat='ft'>4</td><td data-stat='fta'>4</td>"
        "<td data-stat='ft_pct'>1.000</td>"
        "<td data-stat='orb'>1</td><td data-stat='drb'>6</td>"
        "<td data-stat='trb'>7</td><td data-stat='ast'>9</td>"
        "<td data-stat='stl'>2</td><td data-stat='blk'>1</td>"
        "<td data-stat='tov'>3</td><td data-stat='pf'>2</td>"
        "<td data-stat='pts'>22</td><td data-stat='plus_minus'>+5</td>"
        "</tr>"
    )


def _sample_table():
    return _table(
        _row("", "", "", "", "", "", cls="thead")
        + _row("2024-10-22", "LAL", "", "MIN", "", "Inactive")
        + _row("2024-10-24", "LAL", "", "PHX", "W (+5)", "35:24",
               href="/boxscores/202410240LAL.html")
        + _row("2024-10-26", "LAL", "@", "SAC", "L (-3)", "12:05",
               href="/boxscores/202410260SAC.html")
        + _row("2024-10-28", "LAL", "", "DEN", "", "20:00")
    )


def test_inactive_and_thead_rows_skipped():
    rows = seed.parse_gamelog_table_2024_25(_sample_table(), 2544)
    assert len(rows) == 3


def test_minutes_parsing():
    assert parse_minutes("35:24") == 35
    assert parse_minutes("12:05") == 12
    assert parse_minutes("") is None
    assert parse_minutes("Inactive") is None
    rows = seed.parse_gamelog_table_2024_25(_sample_table(), 2544)
    assert [r["MIN"] for r in rows] == [35, 12, 20]


def test_wl_extraction():
    rows = seed.parse_gamelog_table_2024_25(_sample_table(), 2544)
    assert [r["WL"] for r in rows] == ["W", "L", None]


def test_matchup_home_away():
    rows = seed.parse_gamelog_table_2024_25(_sample_table(), 2544)
    assert rows[0]["MATCHUP"] == "LAL vs. PHX"
    assert rows[1]["MATCHUP"] == "LAL @ SAC"


def test_game_id_from_href_and_fallback():
    rows = seed.parse_gamelog_table_2024_25(_sample_table(), 2544)
    assert rows[0]["Game_ID"] == "202410240LAL"
    assert rows[2]["Game_ID"].startswith("bbref-2024-10-28")


def test_season_stamp():
    rows = seed.parse_gamelog_table_2024_25(_sample_table(), 2544)
    assert {r["SEASON_ID"] for r in rows} == {"22024"}
    assert {r["Player_ID"] for r in rows} == {2544}


def test_batch_assert_rejects_duplicate_game_id():
    rows = seed.parse_gamelog_table_2024_25(_sample_table(), 2544)
    rows.append(dict(rows[0]))
    with pytest.raises(AssertionError):
        seed.assert_player_batch(rows, 2544)


def test_batch_assert_rejects_wrong_player():
    rows = seed.parse_gamelog_table_2024_25(_sample_table(), 2544)
    with pytest.raises(AssertionError):
        seed.assert_player_batch(rows, 9999)


def test_table_and_season_constants_guard():
    assert seed.TABLE == "silver_bbref_gamelogs_2024_25"
    assert seed.SEASON == "2024-25"
    assert seed.BBREF_YEAR == "2025"
    assert seed.SEASON_ID == "22024"
    assert seed.TABLE not in ("silver_player_gamelogs", "silver_playoff_gamelogs")


def test_load_player_paths_missing_file_returns_empty(tmp_path):
    assert seed.load_player_paths(tmp_path / "nope.txt") == []


def test_save_path_temp_db_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "t.duckdb")
    monkeypatch.setattr(store, "LOCK_PATH", tmp_path / ".write.lock")
    rows = seed.parse_gamelog_table_2024_25(_sample_table(), 2544)
    seed.assert_player_batch(rows, 2544)
    n1 = seed.save_rows_2024_25(rows, 2544)
    n2 = seed.save_rows_2024_25(rows, 2544)
    assert n1 == len(rows) == n2
    con = store.connect()
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        assert seed.TABLE in tables
        count = con.execute(f"SELECT COUNT(*) FROM {seed.TABLE}").fetchone()[0]
        seasons = con.execute(f"SELECT DISTINCT _season FROM {seed.TABLE}").fetchall()
    finally:
        con.close()
    assert count == len(rows)
    assert seasons == [(seed.SEASON,)]
