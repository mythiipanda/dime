from v2.adapters import AdapterError, call_capability
import pytest

def _series_payload():
    return {
        "tool": "get_season_series",
        "ok": True,
        "rows": {
            "teams": ["BOS", "NYK"],
            "summary": {"games": 2, "bos_wins": 1, "nyk_wins": 1},
            "games": [
                {"game_id": "0022500001", "date": "Oct 22, 2025", "matchup": "BOS vs. NYK", "phase": "regular season", "winner": "BOS"},
                {"game_id": "0022500002", "date": "Jan 15, 2026", "matchup": "NYK vs. BOS", "phase": "regular season", "winner": "NYK"},
            ],
        },
        "meta": {"source": "warehouse", "season": "2025-26"},
    }

def _h2h_payload():
    return {
        "tool": "get_head_to_head",
        "ok": True,
        "rows": {
            "player": "Jayson Tatum",
            "player_id": 1628369,
            "player_team": "BOS",
            "opponent": "NYK",
            "opponent_name": "New York Knicks",
            "vs_opponent": {"gp": 3, "ppg": 28.3, "rpg": 8.0, "apg": 5.0, "fg_pct": 0.471, "ts_pct": 0.589, "w": 2, "l": 1},
            "season_baseline": {"gp": 72, "ppg": 26.9, "rpg": 8.1, "apg": 4.9, "fg_pct": 0.461, "ts_pct": 0.601, "w": 50, "l": 22},
            "deltas": {"ppg": 1.4, "rpg": -0.1, "apg": 0.1, "fg_pct": 0.010, "ts_pct": -0.012},
            "team_record": "2-1",
            "games": [
                {"game_id": "0022500001", "matchup": "BOS vs. NYK", "pts": 32.0, "reb": 9.0, "ast": 5.0, "wl": "W"},
            ],
            "small_sample": True,
            "note": None,
        },
        "meta": {"source": "warehouse", "season": "2025-26"},
    }

def _splits_payload():
    return {
        "tool": "get_matchup_splits",
        "ok": True,
        "rows": {
            "player": "Jayson Tatum",
            "player_id": 1628369,
            "window_games": 15,
            "splits": [
                {"split": "vs top-10 defenses", "gp": 6, "ppg": 27.5, "rpg": 8.2, "apg": 5.1, "fg_pct": 0.465, "plus_minus": 4.2, "low_sample": False},
                {"split": "home", "gp": 8, "ppg": 28.1, "rpg": 8.0, "apg": 5.3, "fg_pct": 0.472, "plus_minus": 5.0, "low_sample": False},
                {"split": "away", "gp": 7, "ppg": 26.2, "rpg": 7.9, "apg": 4.6, "fg_pct": 0.455, "plus_minus": 2.1, "low_sample": False},
                {"split": "rest 1 day", "gp": 9, "ppg": 27.0, "rpg": 8.1, "apg": 5.0, "fg_pct": 0.460, "plus_minus": 3.3, "low_sample": False},
            ],
            "defense_splits": "ok",
        },
        "meta": {"source": "warehouse", "season": "2025-26"},
    }

class _Tool:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def invoke(self, arguments):
        self.calls.append(arguments)
        return self.payload

def test_season_series_envelope_carries_meetings():
    tool = _Tool(_series_payload())
    env = call_capability("season_series", {"team_a": "BOS", "team_b": "NYK", "season": "2025-26"}, tools={"get_season_series": tool})
    assert env.capability == "season_series"
    assert env.season == "2025-26"
    assert env.rows["teams"] == ["BOS", "NYK"]
    assert env.rows["summary"]["games"] == 2
    assert env.rows["summary"]["bos_wins"] == 1
    assert env.rows["summary"]["nyk_wins"] == 1
    assert len(env.rows["games"]) == 2
    assert env.rows["games"][0]["winner"] == "BOS"
    assert env.rows["games"][1]["winner"] == "NYK"
    assert env.qualification
    assert env.coverage

def test_season_series_failure_surfaces():
    tool = _Tool({"tool": "get_season_series", "ok": False, "error": "two different teams needed"})
    with pytest.raises(AdapterError, match="two different teams"):
        call_capability("season_series", {"team_a": "BOS", "team_b": "BOS", "season": "2025-26"}, tools={"get_season_series": tool})

def test_head_to_head_envelope_carries_deltas():
    tool = _Tool(_h2h_payload())
    env = call_capability("head_to_head", {"player": "Jayson Tatum", "opponent": "NYK", "season": "2025-26"}, tools={"get_head_to_head": tool})
    assert env.capability == "head_to_head"
    assert env.season == "2025-26"
    assert env.rows["player_id"] == 1628369
    assert env.rows["opponent"] == "NYK"
    assert env.rows["vs_opponent"]["ppg"] == 28.3
    assert env.rows["season_baseline"]["ppg"] == 26.9
    assert env.rows["deltas"]["ppg"] == 1.4
    assert env.rows["team_record"] == "2-1"
    assert env.rows["small_sample"] is True
    assert env.units["ppg"] == "per_game"
    assert env.units["fg_pct"] == "fraction_0_1"
    assert env.qualification
    assert env.coverage

def test_head_to_head_failure_surfaces():
    tool = _Tool({"tool": "get_head_to_head", "ok": False, "error": "unknown player: ZZZ"})
    with pytest.raises(AdapterError, match="unknown player"):
        call_capability("head_to_head", {"player": "ZZZ", "opponent": "NYK", "season": "2025-26"}, tools={"get_head_to_head": tool})

def test_matchup_splits_envelope_carries_splits():
    tool = _Tool(_splits_payload())
    env = call_capability("matchup_splits", {"player": "Jayson Tatum", "n": 15, "season": "2025-26"}, tools={"get_matchup_splits": tool})
    assert env.capability == "matchup_splits"
    assert env.season == "2025-26"
    assert env.rows["player_id"] == 1628369
    assert env.rows["window_games"] == 15
    by_split = {row["split"]: row for row in env.rows["splits"]}
    assert by_split["home"]["ppg"] == 28.1
    assert by_split["away"]["ppg"] == 26.2
    assert by_split["rest 1 day"]["gp"] == 9
    assert env.units["ppg"] == "per_game"
    assert env.units["fg_pct"] == "fraction_0_1"
    assert env.qualification
    assert env.coverage

def test_matchup_splits_failure_surfaces():
    tool = _Tool({"tool": "get_matchup_splits", "ok": False, "error": "unknown player: ZZZ"})
    with pytest.raises(AdapterError, match="unknown player"):
        call_capability("matchup_splits", {"player": "ZZZ", "season": "2025-26"}, tools={"get_matchup_splits": tool})
