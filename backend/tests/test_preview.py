"""Matchup preview tests. All hermetic: past and upcoming paths run on the
warehouse-cached scoreboard (2026-04-12 finale, 2026-10-21 opening week);
marquee-pick tests use fixtures with a stubbed standings call. No live
nba_api reads anywhere in this file."""

import asyncio
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import tools  # noqa: E402
from app.tools import preview as preview_mod  # noqa: E402

PAST_DATE = "04/12/2026"  # regular-season finale, cached in the warehouse
FUTURE_DATE = "10/21/2026"  # opening week, cached in the warehouse

BANNED_SCORE_TOKENS = (
    "win_prob", "projected_total", "projected score", "spread",
    "moneyline", "over/under", "will win", "predicted winner",
)


def _run(args: dict):
    return asyncio.run(tools.get_matchup_preview.ainvoke(args))


def _upcoming():
    res = _run({"a": "Lakers", "game_date": FUTURE_DATE,
                "season": "2025-26"})
    assert res["ok"] is True, res.get("error")
    return res


def test_past_game_pair_returns_recap_path():
    res = _run({"a": "Orlando Magic", "b": "Boston Celtics",
                "game_date": PAST_DATE})
    assert res["ok"] is True
    rows = res["rows"]
    assert rows["already_played"] is True
    assert rows["game_id"] == "0022501186"
    assert rows["matchup"] == "ORL @ BOS"
    assert "get_recap" in rows["suggestion"]
    assert "0022501186" in rows["suggestion"]


def test_past_game_date_only_picks_marquee():
    res = _run({"game_date": PAST_DATE})
    assert res["ok"] is True
    assert res["rows"]["already_played"] is True
    assert res["rows"]["game_id"]


def test_unknown_team_errors():
    res = _run({"a": "Not A Real Team", "b": "Lakers",
                "game_date": PAST_DATE})
    assert res["ok"] is False
    assert "unknown team" in res["error"]


def test_bad_date_format_errors():
    res = _run({"a": "Lakers", "b": "Celtics", "game_date": "2026-04-12"})
    assert res["ok"] is False
    assert "MM/DD/YYYY" in res["error"]


def test_no_teams_no_date_errors():
    res = _run({})
    assert res["ok"] is False
    assert "two teams" in res["error"]


def test_offseason_pair_returns_honest_no_schedule():
    # 2025-26 is complete and the next 14 days hold no games: the tool
    # must say so, not fabricate a matchup.
    res = _run({"a": "Lakers", "b": "Celtics"})
    assert res["ok"] is False
    assert "no scheduled" in res["error"]
    assert "LAL" in res["error"] and "BOS" in res["error"]


def test_upcoming_game_has_all_sections():
    res = _upcoming()
    rows = res["rows"]
    for key in ("game", "form", "matchups", "injuries", "xfactors",
                "why_watch"):
        assert key in rows, f"missing section: {key}"
    game = rows["game"]
    assert game["home"] == "LAL"
    assert game["away"] == "GSW"
    assert game["date"] == FUTURE_DATE
    assert game["game_id"] == "0022600005"
    assert "score" not in game
    assert len(rows["matchups"]) >= 2
    assert rows["why_watch"].count(".") >= 2
    assert res["meta"]["source"] == "warehouse"


def test_never_predicts_scores():
    rows = _upcoming()["rows"]
    blob = json.dumps(rows).lower()
    for token in BANNED_SCORE_TOKENS:
        assert token not in blob, f"score prediction leaked: {token}"
    assert "prediction" not in rows["why_watch"].lower()


def test_injury_section_present_with_impact():
    rows = _upcoming()["rows"]
    injuries = rows["injuries"]
    assert set(injuries) == {"away", "home"}
    away_outs = injuries["away"]["out"]
    assert away_outs, "expected real injury data for the cached game"
    assert all(o["name"] and o["impact"] for o in away_outs)


def test_xfactor_section_present():
    rows = _upcoming()["rows"]
    xfactors = rows["xfactors"]
    assert set(xfactors) == {"away", "home"}
    for side in xfactors.values():
        assert "player" in side or "note" in side


def test_xfactor_card_uses_real_gamelogs():
    # LeBron (player:2544) has 60 cached gamelog rows: a hot/cold read
    # must come back with a last-5 line, no live calls involved.
    leaders = [
        {"name": "Filler One", "player_id": 1, "pts": 30.0,
         "ast": 5.0, "reb": 5.0, "gp": 60},
        {"name": "Filler Two", "player_id": 2, "pts": 28.0,
         "ast": 5.0, "reb": 5.0, "gp": 60},
        {"name": "LeBron James", "player_id": 2544, "pts": 25.9,
         "ast": 8.2, "reb": 7.9, "gp": 60},
        {"name": "Filler Three", "player_id": 3, "pts": 15.0,
         "ast": 3.0, "reb": 4.0, "gp": 60},
    ]
    card = preview_mod._xfactor_card(leaders, "2025-26")
    assert card["player"] == "LeBron James"
    assert "last5_ppg" in card and "season_ppg" in card
    assert f"Averaging {card['last5_ppg']} ppg over his last 5" in card["line"]


def _standings_stub(rows):
    class _Stub:
        @staticmethod
        def invoke(_args):
            return {"rows": rows}

    return _Stub


def _sched_row(game_id, home_id, home, away_id, away, tv=""):
    return {
        "GAME_ID": game_id,
        "HOME_TEAM_ID": home_id, "VISITOR_TEAM_ID": away_id,
        "HOME_TEAM_ABBREVIATION": home, "VISITOR_TEAM_ABBREVIATION": away,
        "NATL_TV_BROADCASTER_ABBREVIATION": tv,
    }


def _standings_rows():
    # pct: BOS .671, LAL .610, NYK .488, GSW .366
    return [
        {"TeamID": 1610612738, "WINS": 55, "LOSSES": 27},  # BOS
        {"TeamID": 1610612747, "WINS": 50, "LOSSES": 32},  # LAL
        {"TeamID": 1610612752, "WINS": 40, "LOSSES": 42},  # NYK
        {"TeamID": 1610612744, "WINS": 30, "LOSSES": 52},  # GSW
    ]


def test_marquee_pick_prefers_combined_win_pct(monkeypatch):
    import app.tools.league as league_mod

    monkeypatch.setattr(league_mod, "get_standings",
                        _standings_stub(_standings_rows()))
    rows = [
        # BOS+NYK combined 1.159, no national TV
        _sched_row("g1", 1610612738, "BOS", 1610612752, "NYK"),
        # LAL+GSW combined 0.976, on ESPN
        _sched_row("g2", 1610612747, "LAL", 1610612744, "GSW", tv="ESPN"),
    ]
    assert preview_mod._pick_marquee(rows, "2025-26")["GAME_ID"] == "g1"


def test_marquee_pick_tv_breaks_pct_tie(monkeypatch):
    import app.tools.league as league_mod

    monkeypatch.setattr(league_mod, "get_standings",
                        _standings_stub(_standings_rows()))
    rows = [
        _sched_row("g1", 1610612738, "BOS", 1610612752, "NYK"),
        _sched_row("g2", 1610612738, "BOS", 1610612752, "NYK", tv="TNT"),
    ]
    assert preview_mod._pick_marquee(rows, "2025-26")["GAME_ID"] == "g2"


def test_registered_and_labeled():
    from app.graph import tool_label
    from app.subagents import _desk_tool_label

    assert "get_matchup_preview" in tools.TOOL_NAMES
    assert tool_label("get_matchup_preview") == "Previewing the matchup"
    assert _desk_tool_label("get_matchup_preview") == "Previewing the matchup"


def test_abbrev_resolution_prefers_exact_abbrev():
    from app.tools._core import coerce_team_id

    assert coerce_team_id("ORL") == 1610612753
    assert coerce_team_id("NOP") == 1610612740
    assert coerce_team_id("LAL") == 1610612747
    assert coerce_team_id("Los Angeles Lakers") == 1610612747
