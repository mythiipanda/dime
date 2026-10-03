from v2.adapters import AdapterError, call_capability
import pytest


def _today_payload():
    return {
        "tool": "get_today",
        "ok": True,
        "rows": {
            "last_night": [
                {"GAME_ID": "0022500001", "HOME": "BOS", "AWAY": "NYK",
                 "HOME_PTS": 112, "AWAY_PTS": 105, "STATUS": "Final"},
            ],
            "tonight": [
                {"GAME_ID": "0022500002", "HOME": "LAL", "AWAY": "DEN",
                 "STATUS": "Scheduled"},
            ],
            "movers": [
                {"PLAYER": "Current Star", "TEAM": "DEN",
                 "RANK_CHANGE": "+2", "PTS_CHANGE": 1.4},
            ],
            "streaks": [
                {"TEAM": "Boston Celtics", "W": 58, "L": 24,
                 "STREAK": "W 5", "GAMES": 5},
            ],
        },
        "meta": {"source": "nba_api+warehouse", "season": "2025-26",
                 "date": "10/02/2026", "scoreboard_ok": True},
    }


def _today_empty_payload():
    return {
        "tool": "get_today",
        "ok": True,
        "rows": {"last_night": [], "tonight": [], "movers": [],
                 "streaks": []},
        "meta": {"source": "nba_api+warehouse", "season": "2025-26",
                 "date": "07/15/2026", "scoreboard_ok": True},
    }


def _briefing_payload():
    return {
        "tool": "get_morning_briefing",
        "ok": True,
        "rows": {
            "today": {
                "last_night": [
                    {"GAME_ID": "0022500001", "HOME": "BOS",
                     "AWAY": "NYK", "STATUS": "Final"},
                ],
                "tonight": [
                    {"GAME_ID": "0022500002", "HOME": "LAL",
                     "AWAY": "DEN", "STATUS": "Scheduled"},
                ],
                "movers": [
                    {"PLAYER": "Current Star", "TEAM": "DEN",
                     "RANK_CHANGE": "+2", "PTS_CHANGE": 1.4},
                ],
                "streaks": [
                    {"TEAM": "Boston Celtics", "W": 58, "L": 24,
                     "STREAK": "W 5", "GAMES": 5},
                ],
            },
            "watchlist": [
                {"player": "Current Star", "team": "DEN",
                 "note": "track scoring"},
            ],
            "movers": {
                "climbers": [
                    {"player": "Current Star", "team": "DEN",
                     "rank_change": 2},
                ],
                "fallers": [],
                "new_entries": [],
            },
        },
        "meta": {"source": "nba_api+warehouse", "season": "2025-26",
                 "scoreboard_ok": True, "watchlist_count": 1},
    }


def _briefing_empty_payload():
    return {
        "tool": "get_morning_briefing",
        "ok": True,
        "rows": {
            "today": {"last_night": [], "tonight": [], "movers": [],
                      "streaks": []},
            "watchlist": [],
            "movers": {"climbers": [], "fallers": [], "new_entries": []},
        },
        "meta": {"source": "nba_api+warehouse", "season": "2025-26",
                 "scoreboard_ok": True, "watchlist_count": 0},
    }


class _Tool:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def invoke(self, arguments):
        self.calls.append(arguments)
        return self.payload


def test_today_envelope_carries_scoreboard_sections():
    tool = _Tool(_today_payload())
    env = call_capability("today", {"season": "2025-26"},
                          tools={"get_today": tool})
    assert tool.calls == [{"season": "2025-26"}]
    assert env.capability == "today"
    assert env.season == "2025-26"
    assert env.rows["last_night"][0]["GAME_ID"] == "0022500001"
    assert env.rows["last_night"][0]["HOME_PTS"] == 112
    assert env.rows["tonight"][0]["HOME"] == "LAL"
    assert env.rows["movers"][0]["RANK_CHANGE"] == "+2"
    assert env.rows["streaks"][0]["GAMES"] == 5
    assert env.qualification
    assert env.coverage


def test_today_honest_empty_offseason_stays_empty():
    tool = _Tool(_today_empty_payload())
    env = call_capability("today", {"season": "2025-26"},
                          tools={"get_today": tool})
    assert env.capability == "today"
    assert env.season == "2025-26"
    assert env.rows["last_night"] == []
    assert env.rows["tonight"] == []
    assert env.rows["movers"] == []
    assert env.rows["streaks"] == []


def test_today_failure_surfaces():
    tool = _Tool({"tool": "get_today", "ok": False,
                  "error": "scoreboard unavailable"})
    with pytest.raises(AdapterError, match="scoreboard unavailable"):
        call_capability("today", {"season": "2025-26"},
                        tools={"get_today": tool})


def test_morning_briefing_envelope_carries_sections():
    tool = _Tool(_briefing_payload())
    env = call_capability("morning_briefing", {"season": "2025-26"},
                          tools={"get_morning_briefing": tool})
    assert tool.calls == [{"season": "2025-26"}]
    assert env.capability == "morning_briefing"
    assert env.season == "2025-26"
    assert env.rows["today"]["last_night"][0]["GAME_ID"] == "0022500001"
    assert env.rows["today"]["tonight"][0]["HOME"] == "LAL"
    assert env.rows["watchlist"][0]["player"] == "Current Star"
    assert env.rows["movers"]["climbers"][0]["rank_change"] == 2
    assert env.qualification
    assert env.coverage


def test_morning_briefing_honest_empty_offseason_stays_empty():
    tool = _Tool(_briefing_empty_payload())
    env = call_capability("morning_briefing", {"season": "2025-26"},
                          tools={"get_morning_briefing": tool})
    assert env.capability == "morning_briefing"
    assert env.season == "2025-26"
    assert env.rows["today"]["last_night"] == []
    assert env.rows["today"]["tonight"] == []
    assert env.rows["watchlist"] == []
    assert env.rows["movers"]["climbers"] == []


def test_morning_briefing_failure_surfaces():
    tool = _Tool({"tool": "get_morning_briefing", "ok": False,
                  "error": "briefing unavailable"})
    with pytest.raises(AdapterError, match="briefing unavailable"):
        call_capability("morning_briefing", {"season": "2025-26"},
                        tools={"get_morning_briefing": tool})
