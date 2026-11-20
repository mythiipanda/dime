import duckdb
import polars as pl
import pytest

from shared import store
from shared.tools.league.daily_brief import get_team_daily_brief


@pytest.fixture()
def brief_db(tmp_path, monkeypatch):
    db = tmp_path / "brief.duckdb"
    con = duckdb.connect(str(db))
    con.execute("""
        CREATE TABLE silver_injury_entries AS SELECT * FROM (
        VALUES ('Jayson Tatum', 'BOS', 'Day-To-Day', 'Questionable', 'knee',
                'listed day-to-day', '2026-11-18', 'espn')
        ) AS t(PLAYER, TEAM_ABBR, STATUS, ATHLETE_STATUS, INJURY,
               RETURN_ESTIMATE, REPORT_DATE, SOURCE)
    """)
    con.execute("""
        CREATE TABLE silver_news AS SELECT * FROM (
        VALUES ('Celtics rest Tatum', '2026-11-18T12:00:00+00:00',
                'https://espn.example/a', 'espn:nba-rss', 'load management',
                '["Jayson Tatum"]', '["BOS"]', 'rss:espn', 'news',
                '2026-11-18T13:00:00+00:00', 'league')
        ) AS t(HEADLINE, PUBLISHED, URL, SOURCE_FEED, SUMMARY, PLAYERS, TEAMS,
               _source, _season, _fetched_at, _entity)
    """)
    con.execute("""
        CREATE TABLE silver_transactions AS SELECT * FROM (
        VALUES ('2026-11-17', 'Signing', 'Two Way Guy', 12345, 'BOS',
                1610612738, 'signed two-way contract')
        ) AS t(txn_date, txn_type, player, player_id, team, team_id, detail)
    """)
    con.execute("""
        CREATE TABLE silver_team_games AS SELECT * FROM (
        VALUES (1610612738, '0022500123', 'NOV 18, 2026', 'BOS vs. NYK', 'W',
                5, 3, 0.625, 240, 118, 40, 88, 0.455, 15, 40, 0.375, 20, 25,
                0.8, 10, 35)
        ) AS t(Team_ID, Game_ID, GAME_DATE, MATCHUP, WL, W, L, W_PCT, MIN,
               PTS, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT,
               OREB, DREB)
    """)
    con.execute("""
        CREATE TABLE silver_standings AS SELECT * FROM (
        VALUES (1610612738, 'Boston', 'Celtics', 'East', '5-3', 4, 9, '3-1',
                '8-2', 'W 2')
        ) AS t(TeamID, TeamCity, TeamName, Conference, Record, PlayoffRank,
               LeagueRank, L10, Oct, strCurrentStreak)
    """)
    con.execute("""
        CREATE TABLE silver_schedule AS SELECT * FROM (
        VALUES ('2026-11-19T23:30Z', 'Boston Celtics at Miami Heat',
                '2025-26', 'BOS'),
               ('2026-11-21T00:30Z', 'Chicago Bulls at Boston Celtics',
                '2025-26', 'BOS')
        ) AS t(date, name, season_display_name, team_abbreviation)
    """)
    con.close()
    monkeypatch.setattr(store, "DB_PATH", db)
    yield db


def test_daily_brief_all_sections(brief_db):
    res = get_team_daily_brief.invoke({"team": "BOS"})
    assert res["ok"] is True
    assert res["team"] == "BOS"
    assert set(res["rows"]) == {"injuries", "news", "transactions",
                                "last_result", "standings", "upcoming"}
    assert all(s["ok"] for s in res["rows"].values())
    assert res["meta"]["unseeded_sections"] == []


def test_daily_brief_dates_and_sources(brief_db):
    res = get_team_daily_brief.invoke({"team": "BOS", "since": "2026-11-01"})
    inj = res["rows"]["injuries"]["rows"][0]
    assert inj["player"] == "Jayson Tatum" and inj["date"]
    news = res["rows"]["news"]["rows"][0]
    assert news["date"].startswith("2026-11-18") and news["source"]
    txn = res["rows"]["transactions"]["rows"][0]
    assert txn["date"] == "2026-11-17"
    last = res["rows"]["last_result"]["rows"][0]
    assert last["matchup"] == "BOS vs. NYK" and last["wl"] == "W"
    assert res["rows"]["standings"]["rows"][0]["record"] == "5-3"
    assert len(res["rows"]["upcoming"]["rows"]) == 2


def test_daily_brief_since_filters(brief_db):
    res = get_team_daily_brief.invoke({"team": "BOS", "since": "2026-11-20"})
    assert res["rows"]["news"]["rows"] == []
    assert res["rows"]["transactions"]["rows"] == []
    assert res["rows"]["injuries"]["rows"] != []


def test_daily_brief_unseeded_sections(tmp_path, monkeypatch):
    db = tmp_path / "empty.duckdb"
    con = duckdb.connect(str(db))
    con.execute("""
        CREATE TABLE silver_standings AS SELECT * FROM (
        VALUES (1610612738, 'Boston', 'Celtics', 'East', '5-3', 4, 9, '3-1',
                '8-2', 'W 2')
        ) AS t(TeamID, TeamCity, TeamName, Conference, Record, PlayoffRank,
               LeagueRank, L10, Oct, strCurrentStreak)
    """)
    con.close()
    monkeypatch.setattr(store, "DB_PATH", db)
    res = get_team_daily_brief.invoke({"team": "BOS"})
    assert res["ok"] is True
    unseeded = set(res["meta"]["unseeded_sections"])
    assert {"injuries", "news", "transactions", "last_result",
            "upcoming"} <= unseeded
    assert "standings" in res["meta"]["sections"]


def test_daily_brief_unknown_team():
    res = get_team_daily_brief.invoke({"team": "NOPE"})
    assert res["ok"] is False
