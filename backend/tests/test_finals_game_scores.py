"""Finals game rows carry explicit home team and scores (sweep3)."""
import asyncio

from app.tools.league import get_playoffs


def _finals():
    r = asyncio.run(get_playoffs.ainvoke({"season": "2025-26"}))
    assert r["ok"]
    return r["rows"]["finals"]


def test_finals_games_have_home_and_scores():
    games = {g["date"]: g for g in _finals()["games"]}
    assert len(games) == 5
    g1 = games["2026-06-03"]
    assert g1["home"] == "SAS" and g1["winner"] == "NYK"
    assert g1["score"] == {"NYK": 105, "SAS": 95}
    assert g1["scoreline"] == "NYK 105, SAS 95"


def test_finals_game3_home_is_explicit():
    # The composed answer used to say SAS won game 3 "at home"; the
    # game was at NYK. The payload must say so explicitly.
    games = {g["date"]: g for g in _finals()["games"]}
    g3 = games["2026-06-08"]
    assert g3["home"] == "NYK" and g3["winner"] == "SAS"
    assert g3["score"] == {"NYK": 111, "SAS": 115}
