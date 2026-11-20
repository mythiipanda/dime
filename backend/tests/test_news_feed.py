import duckdb
import polars as pl
import pytest

from shared import store
from shared.tools.league.news import get_news_feed


@pytest.fixture()
def news_db(tmp_path, monkeypatch):
    db = tmp_path / "news.duckdb"
    frame = pl.DataFrame({
        "HEADLINE": [
            "Jayson Tatum day-to-day for Celtics",
            "Nets lose to Knicks in overtime",
            "League-wide ratings shakeup",
        ],
        "PUBLISHED": [
            "2026-11-19T12:00:00+00:00",
            "2026-11-18T12:00:00+00:00",
            "2026-11-17T12:00:00+00:00",
        ],
        "URL": [
            "https://espn.example/a",
            "https://cbs.example/b",
            "https://yahoo.example/c",
        ],
        "SOURCE_FEED": ["espn:nba-rss", "cbssports:nba-rss", "yahoo:nba-rss"],
        "SUMMARY": ["Tatum left with an ankle tweak.",
                    "Bridges scored 35.", "Power index moves."],
        "PLAYERS": ['["Jayson Tatum"]', '[]', '[]'],
        "TEAMS": ['["BOS"]', '["BKN", "NYK"]', '[]'],
        "_source": ["rss:espn", "rss:cbs", "rss:yahoo"],
        "_season": ["news", "news", "news"],
        "_fetched_at": ["2026-11-19T13:00:00+00:00"] * 3,
        "_entity": ["league"] * 3,
    })
    con = duckdb.connect(str(db))
    con.execute("CREATE TABLE silver_news AS SELECT * FROM frame")
    con.close()
    monkeypatch.setattr(store, "DB_PATH", db)
    yield db


def test_news_feed_returns_items(news_db):
    res = get_news_feed.invoke({})
    assert res["ok"] is True
    assert len(res["rows"]) == 3
    assert res["rows"][0]["headline"].startswith("Jayson Tatum")
    assert res["meta"]["source"] == "warehouse"


def test_news_feed_team_filter(news_db):
    res = get_news_feed.invoke({"team": "BOS"})
    assert len(res["rows"]) == 1
    assert "Tatum" in res["rows"][0]["headline"]


def test_news_feed_player_filter(news_db):
    res = get_news_feed.invoke({"player": "Jayson Tatum"})
    assert len(res["rows"]) == 1
    assert res["rows"][0]["teams"] == ["BOS"]


def test_news_feed_player_headline_match(news_db):
    res = get_news_feed.invoke({"player": "Tatum"})
    assert len(res["rows"]) == 1


def test_news_feed_limit(news_db):
    res = get_news_feed.invoke({"limit": 2})
    assert len(res["rows"]) == 2
    assert res["meta"]["matched"] == 3


def test_news_feed_no_match_warns(news_db):
    res = get_news_feed.invoke({"team": "LAL"})
    assert res["rows"] == []
    assert "warning" in res["meta"]


def test_news_feed_missing_table(tmp_path, monkeypatch):
    db = tmp_path / "empty.duckdb"
    duckdb.connect(str(db)).close()
    monkeypatch.setattr(store, "DB_PATH", db)
    res = get_news_feed.invoke({})
    assert res["ok"] is False
    assert "seed_injury_news" in res["error"]
