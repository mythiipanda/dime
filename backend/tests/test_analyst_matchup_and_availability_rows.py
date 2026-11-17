import asyncio
import importlib
import re
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(BACKEND / "analyst"))

from analyst import python_tools  # noqa: E402

SECTION_COLUMNS = ["section"]

SECTIONED = (
    {
        "name": "get_matchup_brief",
        "module": "shared.tools.team",
        "attribute": "get_matchup_brief",
        "arguments": {"a": "BOS", "b": "LAL", "season": "2025-26"},
        "description": "Two-team matchup brief with ratings, form, injuries, season series, and win probability.",
        "upstream_rows": {
            "teams": ["BOS", "LAL"],
            "ratings_provenance": {"kind": "warehouse", "source": "silver_ratings"},
            "ratings": {
                "BOS": {"TEAM": "BOS", "OFF_RATING": 118.4, "NET_RATING": 8.1},
                "LAL": {"TEAM": "LAL", "OFF_RATING": 114.9, "NET_RATING": 2.7},
            },
            "form": {"BOS": {"last10": "7-3", "splits": [{"split": "LAST_10", "W": 7}]}},
            "injuries": {"BOS": {"out": ["A. Star"], "questionable": []}},
            "season_series": {
                "teams": ["BOS", "LAL"],
                "available": True,
                "games": [{"GAME_ID": "0022400001", "winner": "BOS"}],
            },
            "prediction": {
                "matchup": {"home": "BOS", "away": "LAL"},
                "win_prob": {"BOS": 0.58, "LAL": 0.42},
                "projected_total": 226.5,
            },
        },
    },
    {
        "name": "get_matchup_preview",
        "module": "shared.tools.preview",
        "attribute": "get_matchup_preview",
        "arguments": {"a": "BOS", "b": "LAL", "game_date": "", "season": "2025-26"},
        "description": "Narrative preview of a scheduled NBA game.",
        "upstream_rows": {
            "game": {"game_id": "0022400101", "date": "2026-01-05",
                     "home": "BOS", "away": "LAL", "arena": "TD Garden"},
            "form": {"away": {"last10": "6-4"}, "home": {"last10": "8-2"}},
            "matchups": [{"player": "A. Star", "opponent": "B. Guard",
                          "angle": "scoring"}],
            "injuries": {"away": {"out": []}, "home": {"out": ["C. Wing"]}},
            "xfactors": {"away": {"note": "pace"}, "home": {"note": "foul rate"}},
            "why_watch": "The bench minutes decide the margins.",
        },
    },
    {
        "name": "get_scout_pack",
        "module": "shared.tools.team",
        "attribute": "get_scout_pack",
        "arguments": {"team": "BOS", "opponent": "LAL", "season": "2025-26"},
        "description": "One-call next-opponent brief: record, net rating, top lineups, injuries.",
        "upstream_rows": {
            "team": {
                "abbrev": "BOS",
                "record": "41-24",
                "net_rating": 8.1,
                "top_lineups": [{"GROUP_NAME": "L1", "PLUS_MINUS": 12.4}],
                "injuries": [],
            },
            "opponent": {
                "abbrev": "LAL",
                "record": "38-27",
                "net_rating": 2.7,
                "top_lineups": [],
                "injuries": [],
            },
            "edge": "BOS (41-24, net +8.1) vs LAL (38-27, net +2.7): net gap +5.4.",
        },
    },
    {
        "name": "get_injury_impact",
        "module": "shared.tools.team",
        "attribute": "get_injury_impact",
        "arguments": {"team": "BOS", "season": "2025-26"},
        "description": "Injury impact in one call: outs, net rating, last-10, heuristic impact.",
        "upstream_rows": {
            "team": "BOS",
            "out": ["A. Star", "D. Wing"],
            "questionable": ["B. Guard"],
            "availability_known": True,
            "net_rating": 8.1,
            "net_rank": 3,
            "last10": "7-3",
            "impact": "moderate",
        },
    },
    {
        "name": "get_rotation_check",
        "module": "shared.tools.team",
        "attribute": "get_rotation_check",
        "arguments": {"team": "BOS", "season": "2025-26",
                      "min_possessions": 100, "top_units": 5},
        "description": "Rotation and closing-unit check from warehouse five-man units, minutes, and cached on/off.",
        "upstream_rows": {
            "team": {"id": 1610612747, "abbrev": "BOS"},
            "coverage": {"season": "2025-26", "units": 12, "total_unit_poss": 2400},
            "tiers": {"core": [{"PLAYER": "A. Star", "MIN": 32.0}], "bench": [], "fringe": []},
            "starter_bench_split": {"starter_min_share": 0.61, "starter_avg_diff": 3.2},
            "most_used_unit": {"GROUP_NAME": "L1", "EST_MIN": 980.0, "NET_RATING": 9.4},
            "closing_candidates": [{"PLAYER": "B. Guard", "GP": 9, "W": 5, "L": 4}],
            "thin_flags": ["short bench: only 7 players at 10+ MPG"],
            "clutch_context": {"note": "player-scope clutch only", "closers": []},
        },
    },
    {
        "name": "get_matchup_splits",
        "module": "shared.tools.splits",
        "attribute": "get_matchup_splits",
        "arguments": {"player": "A. Star", "n": 15, "season": "2025-26"},
        "description": "Situational splits over the last N games: defense tier, home/away, rest.",
        "upstream_rows": {
            "player": "A. Star",
            "player_id": 424242,
            "window_games": 15,
            "splits": [
                {"split": "vs top-10 defenses", "gp": 6, "per_game": 27.2,
                 "low_sample": False},
                {"split": "home", "gp": 8, "per_game": 29.4, "low_sample": False},
            ],
            "defense_splits": "ok",
        },
    },
    {
        "name": "get_regression_check",
        "module": "shared.tools.splits",
        "attribute": "get_regression_check",
        "arguments": {"player": "A. Star", "stat": "PTS", "n": 10,
                      "season": "2025-26"},
        "description": "Sustainability check on a hot stat line: window vs season plus drivers.",
        "upstream_rows": {
            "player": "A. Star",
            "player_id": 424242,
            "stat": "PTS",
            "window_n": 10,
            "window": {"gp": 10, "per_game": 31.4, "mpg": 36.1, "ts_pct": 0.622},
            "season": {"gp": 62, "per_game": 24.8, "mpg": 33.0, "ts_pct": 0.581},
            "career": {"available": True, "gp": 310, "seasons": 7,
                       "per_game": 22.1, "stat": "PTS"},
            "drivers": [
                {"factor": "true_shooting", "window": 62.2, "baseline": 58.1,
                 "delta": 4.1, "unit": "pct"},
            ],
            "drivers_all": [
                {"factor": "true_shooting", "window": 62.2, "baseline": 58.1,
                 "delta": 4.1, "unit": "pct"},
                {"factor": "minutes", "window": 36.1, "baseline": 33.0,
                 "delta": 3.1, "unit": "min"},
                {"factor": "shot_volume", "window": 19.2, "baseline": 18.4,
                 "delta": 0.8, "unit": "fga"},
                {"factor": "opponent_defense", "window": 14.0, "baseline": 15.5,
                 "delta": 1.5, "unit": "rank"},
            ],
            "verdict": "sustainable",
            "verdict_note": "Scoring is holding above the season baseline.",
        },
    },
)

SQL_EXEC = {
    "name": "sql_exec",
    "module": "shared.tools.sql_exec",
    "attribute": "sql_exec",
    "arguments": {"sql": "SELECT COUNT(*) AS n FROM silver_games"},
    "description": "Run one agent-written read-only analytical query over the warehouse.",
    "default_columns": [],
}

DEFENSIVE_MATCHUPS = {
    "name": "get_defensive_matchups",
    "module": "shared.tools.tracking",
    "attribute": "get_defensive_matchups",
    "arguments": {"player": "Synthetic Defender", "season": "2025-26"},
    "description": "One defender's defended-shot profile: frequency and shooter results.",
    "upstream_row": {
        "CLOSE_DEF_PERSON_ID": 424242,
        "PLAYER_NAME": "Synthetic Defender",
        "PLAYER_LAST_TEAM_ABBREVIATION": "TST",
        "GP": 41,
        "FREQ": 0.312,
        "D_FGM": 3.4,
        "D_FGA": 7.9,
        "D_FG_PCT": 0.430,
        "NORMAL_FG_PCT": 0.458,
        "PCT_PLUSMINUS": -1.2,
    },
}

TRACKING_PROFILE = {
    "name": "get_tracking_profile",
    "module": "shared.tools.tracking",
    "attribute": "get_tracking_profile",
    "description": "Player or team tracking profile: drives, shooting, touches, rebounding, speed.",
    "columns": ["subject", "season", "measure_type", "stat", "value"],
}

TRACKING_IDENTITY_VALUES = {
    "PLAYER_ID": 2544,
    "PLAYER_NAME": "Synthetic Scorer",
    "TEAM_ID": 1610612747,
    "TEAM_ABBREVIATION": "TST",
    "TEAM_NAME": "Test Team",
    "GP": 70,
    "W": 40,
    "L": 30,
    "MIN": 2400,
}

CATCH_SHOOT_MEASURES = {
    "CATCH_SHOOT_FGM": 100,
    "CATCH_SHOOT_FGA": 220,
    "CATCH_SHOOT_FG_PCT": 0.455,
    "CATCH_SHOOT_PTS": 250,
    "CATCH_SHOOT_FG3M": 40,
    "CATCH_SHOOT_FG3A": 110,
    "CATCH_SHOOT_FG3_PCT": 0.364,
    "CATCH_SHOOT_EFG_PCT": 0.53,
}

DEFENSE_MEASURES = {
    "STL": 1.4,
    "BLK": 0.8,
    "DREB": 4.2,
    "DEF_RIM_FGM": 2.1,
    "DEF_RIM_FGA": 4.5,
    "DEF_RIM_FG_PCT": 0.467,
}

PLAYTYPE_PROFILE = {
    "name": "get_playtype_profile",
    "module": "shared.tools.playtypes",
    "attribute": "get_playtype_profile",
    "arguments": {"subject": "Synthetic Scorer", "kind": "player",
                  "side": "offense", "season": "2025-26"},
    "description": "Synergy play-type profile for one player or team and season: frequency share, PPP, and percentile.",
    "subject": "Synthetic Scorer",
    "default_columns": ["play_type", "poss_pct", "ppp", "percentile", "gp", "poss"],
    "play_types": [
        {"play_type": "Pick and Roll", "poss_pct": 0.31, "ppp": 1.02,
         "percentile": 88.0, "gp": 70, "poss": 1200},
        {"play_type": "Isolation", "poss_pct": 0.22, "ppp": 0.98,
         "percentile": 74.0, "gp": 70, "poss": 850},
    ],
}

STREAKS = {
    "name": "get_streaks",
    "module": "shared.tools.streaks",
    "attribute": "get_streaks",
    "arguments": {"stat": "points"},
    "description": "Longest or currently-active streaks, ranked league-wide.",
    "default_columns": ["holder", "streak", "start_date", "end_date", "active"],
    "emitted_columns": ["holder", "holder_id", "streak", "start_date", "end_date", "active"],
    "streak_rows": [
        {"holder": "Synthetic Scorer", "holder_id": 2544, "streak": 12,
         "start_date": "2026-01-02", "end_date": "2026-01-20", "active": True},
        {"holder": "Synthetic Wing", "holder_id": 2545, "streak": 8,
         "start_date": "2026-02-01", "end_date": "2026-02-12", "active": False},
    ],
}

HEAD_TO_HEAD = {
    "name": "get_head_to_head",
    "module": "shared.tools.headtohead",
    "attribute": "get_head_to_head",
    "arguments": {"player": "Synthetic Scorer", "opponent": "OPP",
                  "season": "2025-26"},
    "description": "Head-to-head game log between two players.",
    "literal_columns": ["date", "matchup", "wl", "min", "pts", "reb", "ast",
                        "stl", "blk", "plus_minus"],
    "game_row": {
        "date": "2026-01-04", "game_id": "0022400001", "matchup": "TST vs. OPP",
        "home": True, "pts": 21, "reb": 5, "ast": 4, "stl": 1, "blk": 0,
        "tov": 2, "fgm": 8, "fga": 17, "fg3m": 2, "fg3a": 6,
        "min": "34:12", "plus_minus": 7, "wl": "W",
    },
}

LINEUP_MATCHUP = {
    "name": "get_lineup_matchup_matrix",
    "module": "shared.tools.lineup_matrix",
    "attribute": "get_lineup_matchup_matrix",
    "arguments": {"team_a": "AAA", "team_b": "BBB"},
    "description": "Lineup-vs-lineup matrix for a team matchup crossing qualifying 5-man units.",
    "literal_columns": ["team_a_lineup", "team_b_lineup", "poss", "est_minutes",
                        "OFF_RATING_A", "DEF_RATING_A", "NET_RATING_A", "blowout_share"],
    "extras": ["team_a_ids", "team_b_ids", "off_poss_a", "off_poss_b",
               "pts_a", "pts_b", "flags"],
}

MORNING_BRIEFING = {
    "name": "get_morning_briefing",
    "module": "shared.tools.today",
    "attribute": "get_morning_briefing",
    "arguments": {"season": "2025-26"},
    "description": "Morning briefing: today's games, watchlist updates, leaderboard movers.",
    "upstream_rows": {
        "today": {
            "last_night": [{
                "GAME_ID": "1",
                "VISITOR_TEAM_ABBREVIATION": "LAL",
                "HOME_TEAM_ABBREVIATION": "BOS",
                "VISITOR_TEAM_PTS": 110,
                "HOME_TEAM_PTS": 118,
                "GAME_STATUS_TEXT": "Final",
            }],
            "tonight": [{
                "GAME_ID": "2",
                "VISITOR_TEAM_ABBREVIATION": "GSW",
                "HOME_TEAM_ABBREVIATION": "NYK",
                "GAME_STATUS_TEXT": "7:30 pm ET",
            }],
            "movers": [{
                "PLAYER": "A. Star", "TEAM": "BOS",
                "RANK_CHANGE": "+2", "PTS_CHANGE": "1.4",
            }],
            "streaks": [{
                "TEAM": "Denver Nuggets", "W": 9, "L": 2,
                "STREAK": "W5", "GAMES": 5,
            }],
        },
        "watchlist": [{
            "entity_type": "player",
            "entity_id": "A. Star",
            "added_at": "2026-03-01T12:00:00Z",
            "snapshot": {
                "found": True, "player": "A. Star", "team": "BOS",
                "gp": 60, "ppg": 24.5, "rpg": 5.2, "apg": 4.1,
            },
        }],
        "movers": {
            "climbers": [{
                "player": "C. Guard", "team": "BOS",
                "rank_base": 12, "rank_now": 10, "rank_change": 2,
                "pts_base": 20.0, "pts_now": 21.4, "pts_change": 1.4,
            }],
            "fallers": [{
                "player": "D. Forward", "team": "LAL",
                "rank_base": 8, "rank_now": 9, "rank_change": -1,
                "pts_base": 24.0, "pts_now": 23.2, "pts_change": -0.8,
            }],
            "new_entries": [{
                "player": "E. Rookie", "team": "NYK",
                "rank": 25, "pts": 18.5,
            }],
        },
    },
}

MORNING_BRIEFING_SECTIONS = [
    "last_night", "tonight", "today_movers", "streaks", "watchlist",
    "movers_climbers", "movers_fallers", "movers_new_entries",
]

GET_TODAY = {
    "name": "get_today",
    "module": "shared.tools.today",
    "attribute": "get_today",
    "arguments": {"season": "2025-26"},
    "description": (
        "Today home view: last night's results, tonight's games, "
        "leaderboard movers, streaks."
    ),
}

GET_TODAY_COLUMNS = [
    "category", "home_team", "away_team", "score", "status",
    "player", "team", "detail",
]

SEARCH_SHOTS = {
    "name": "search_shots",
    "module": "shared.tools.shots",
    "attribute": "search_shots",
    "arguments": {
        "player": "Synthetic Scorer",
        "team": "BOS",
        "zones": "",
        "periods": "",
        "three_only": False,
        "made": "any",
        "late_clock": "",
        "exclude_heaves": True,
        "limit": 25,
        "season": "2025-26",
        "group_by": "",
        "include_ot": "auto",
    },
    "description": "Search shot attempts by player, team, zone, period and clock.",
    "columns": ["game_id", "player_name", "period", "minutes_remaining",
                "seconds_remaining", "shot_distance", "zone", "made"],
}


class _FakeTool:
    def __init__(self, description: str, result=None, exc: Exception | None = None):
        self.description = description
        self._result = result
        self._exc = exc
        self.calls: list[dict] = []

    def invoke(self, args):
        self.calls.append(args)
        if self._exc is not None:
            raise self._exc
        return self._result

    async def ainvoke(self, args):
        return self.invoke(args)


def _catalogue(monkeypatch, stubs: dict[tuple[str, str], object]):
    for (module_name, attribute), stub in stubs.items():
        module = importlib.import_module(module_name)
        monkeypatch.setattr(module, attribute, stub)
    return python_tools.catalogue()


def _invoke(tool, arguments: dict):
    return asyncio.run(tool.ainvoke(arguments))


def _holds(row: dict, key: str, expected) -> bool:
    if key in row:
        return row[key] == expected
    for value in row.values():
        if isinstance(value, dict) and _holds(value, key, expected):
            return True
    return False


def _assert_reachable(rows: list[dict], upstream: dict):
    by_section: dict[str, list[dict]] = {}
    for row in rows:
        by_section.setdefault(row["section"], []).append(row)
    for name, value in upstream.items():
        section_rows = by_section.get(name, [])
        assert section_rows, f"section {name} was dropped"
        if isinstance(value, list):
            assert len(section_rows) == len(value), name
            for item, row in zip(value, section_rows):
                if isinstance(item, dict):
                    for key, expected in item.items():
                        assert _holds(row, key, expected), f"{name}.{key}"
                else:
                    assert "value" in row and row["value"] == item, name
        elif isinstance(value, dict):
            assert len(section_rows) == 1, name
            for key, expected in value.items():
                assert _holds(section_rows[0], key, expected), f"{name}.{key}"
        else:
            assert any("value" in row and row["value"] == value
                       for row in section_rows), name


def _stub(spec, result=None, exc=None) -> _FakeTool:
    return _FakeTool(spec["description"], result=result, exc=exc)


def _upstream_ok(spec) -> dict:
    return {
        "tool": spec["name"],
        "ok": True,
        "rows": spec["upstream_rows"],
        "meta": {"source": "warehouse", "season": "2025-26"},
    }


def _get_today_upstream():
    today = MORNING_BRIEFING["upstream_rows"]["today"]
    return {
        "last_night": [dict(r) for r in today["last_night"]],
        "tonight": [dict(r) for r in today["tonight"]],
        "movers": [dict(r) for r in today["movers"]],
        "streaks": [dict(r) for r in today["streaks"]],
    }


def _get_today_result(monkeypatch, upstream_rows):
    fake = _stub(GET_TODAY, result={
        "tool": GET_TODAY["name"],
        "ok": True,
        "rows": upstream_rows,
        "meta": {"source": "nba_api+warehouse", "season": "2025-26"},
    })
    tools = _catalogue(monkeypatch, {
        (GET_TODAY["module"], GET_TODAY["attribute"]): fake,
    })
    return _invoke(tools[GET_TODAY["name"]], GET_TODAY["arguments"])


def _search_shot_row(clock="3:24", **overrides):
    row = {
        "player_id": 2544,
        "player": "Synthetic Scorer",
        "team_id": 1610612747,
        "team": "BOS",
        "period": 3,
        "clock": clock,
        "zone": "left_corner_three",
        "zone_label": "Left Corner 3",
        "action": "catch and shoot",
        "distance_ft": 23.7,
        "made": True,
        "game_id": "0022400001",
    }
    row.update(overrides)
    return row


def _search_shots_result(monkeypatch, rows):
    spec = SEARCH_SHOTS
    fake = _FakeTool(spec["description"], result={
        "tool": spec["name"],
        "ok": True,
        "filters": {},
        "aggregate": {"attempts": len(rows)},
        "by_zone": {},
        "by_period": {},
        "shots": rows,
        "meta": {"source": "warehouse", "season": "2025-26"},
    })
    tools = _catalogue(monkeypatch, {
        (spec["module"], spec["attribute"]): fake,
    })
    return _invoke(tools[spec["name"]], spec["arguments"])


def test_sectioned_success_returns_rows_array_with_section(monkeypatch):
    for spec in SECTIONED:
        fake = _stub(spec, result=_upstream_ok(spec))
        tools = _catalogue(monkeypatch, {(spec["module"], spec["attribute"]): fake})

        res = _invoke(tools[spec["name"]], spec["arguments"])

        assert res["ok"] is True, spec["name"]
        assert isinstance(res["rows"], list), spec["name"]
        assert res["rows"], spec["name"]
        for row in res["rows"]:
            assert isinstance(row, dict), spec["name"]
            assert "section" in row, spec["name"]
        assert res["meta"]["source"] == "warehouse", spec["name"]
        assert fake.calls == [spec["arguments"]], spec["name"]


def test_sectioned_success_keeps_every_upstream_value(monkeypatch):
    for spec in SECTIONED:
        fake = _stub(spec, result=_upstream_ok(spec))
        tools = _catalogue(monkeypatch, {(spec["module"], spec["attribute"]): fake})

        res = _invoke(tools[spec["name"]], spec["arguments"])

        _assert_reachable(res["rows"], spec["upstream_rows"])
        assert res["columns"] == list(res["rows"][0].keys()), spec["name"]


def test_sectioned_columns_are_emitted_row_keys(monkeypatch):
    for spec in SECTIONED:
        fake = _stub(spec, result=_upstream_ok(spec))
        tools = _catalogue(monkeypatch, {(spec["module"], spec["attribute"]): fake})

        res = _invoke(tools[spec["name"]], spec["arguments"])

        emitted_keys = {key for row in res["rows"] for key in row}
        assert set(res["columns"]) <= emitted_keys, spec["name"]
        assert not set(res["columns"]) & set(spec["upstream_rows"]), spec["name"]
        assert "section" in res["columns"], spec["name"]


def test_sectioned_empty_rows_returns_rows_array(monkeypatch):
    for spec in SECTIONED:
        fake = _stub(spec, result={"tool": spec["name"], "ok": True, "rows": {}})
        tools = _catalogue(monkeypatch, {(spec["module"], spec["attribute"]): fake})

        res = _invoke(tools[spec["name"]], spec["arguments"])

        assert res["ok"] is True, spec["name"]
        assert res["rows"] == [], spec["name"]
        assert res["columns"] == SECTION_COLUMNS, spec["name"]
        assert not set(res["columns"]) & set(spec["upstream_rows"]), spec["name"]


def test_sectioned_upstream_error_returns_rows_array(monkeypatch):
    for spec in SECTIONED:
        fake = _stub(spec, result={
            "tool": spec["name"],
            "ok": False,
            "rows": {},
            "meta": {"source": "warehouse"},
            "error": "upstream refused the request",
        })
        tools = _catalogue(monkeypatch, {(spec["module"], spec["attribute"]): fake})

        res = _invoke(tools[spec["name"]], spec["arguments"])

        assert res["ok"] is False, spec["name"]
        assert res["rows"] == [], spec["name"]
        assert isinstance(res["columns"], list), spec["name"]
        assert res["columns"] == SECTION_COLUMNS, spec["name"]
        assert not set(res["columns"]) & set(spec["upstream_rows"]), spec["name"]
        assert res["error"] == "upstream refused the request", spec["name"]
        assert res["meta"]["source"] == "warehouse", spec["name"]


def test_sectioned_upstream_exception_becomes_structured_error(monkeypatch):
    for spec in SECTIONED:
        fake = _stub(spec, exc=RuntimeError("warehouse unavailable"))
        tools = _catalogue(monkeypatch, {(spec["module"], spec["attribute"]): fake})

        res = _invoke(tools[spec["name"]], spec["arguments"])

        assert res["ok"] is False, spec["name"]
        assert res["rows"] == [], spec["name"]
        assert isinstance(res["columns"], list), spec["name"]
        assert res["columns"] == SECTION_COLUMNS, spec["name"]
        assert res["error"] == "RuntimeError: warehouse unavailable", spec["name"]
        assert res["tool"] == spec["name"], spec["name"]


def test_sectioned_non_section_rows_becomes_actionable_error(monkeypatch):
    for spec in SECTIONED:
        fake = _stub(spec, result={
            "tool": spec["name"],
            "ok": True,
            "rows": [{"section": "rows"}],
            "meta": {"source": "warehouse"},
        })
        tools = _catalogue(monkeypatch, {(spec["module"], spec["attribute"]): fake})

        res = _invoke(tools[spec["name"]], spec["arguments"])

        assert res["ok"] is False, spec["name"]
        assert res["rows"] == [], spec["name"]
        assert res["columns"] == SECTION_COLUMNS, spec["name"]
        assert "expected a section object" in res["error"], spec["name"]


def test_sql_exec_success_keeps_rows_and_columns(monkeypatch):
    fake = _stub(SQL_EXEC, result={
        "tool": "sql_exec",
        "ok": True,
        "rows": [{"n": 12}],
        "columns": ["n"],
        "meta": {"source": "warehouse"},
    })
    tools = _catalogue(monkeypatch, {(SQL_EXEC["module"], SQL_EXEC["attribute"]): fake})

    res = _invoke(tools["sql_exec"], SQL_EXEC["arguments"])

    assert res["ok"] is True
    assert isinstance(res["rows"], list)
    assert res["rows"] == [{"n": 12}]
    assert res["columns"] == ["n"]
    assert fake.calls == [SQL_EXEC["arguments"]]


def test_sql_exec_failure_returns_rows_array(monkeypatch):
    fake = _stub(SQL_EXEC, result={
        "tool": "sql_exec",
        "ok": False,
        "rows": {},
        "meta": {"sql": "SELECT COUNT(*) AS n FROM silver_games"},
        "error": "sql_exec: query returned 0 rows, so no answer can be published",
    })
    tools = _catalogue(monkeypatch, {(SQL_EXEC["module"], SQL_EXEC["attribute"]): fake})

    res = _invoke(tools["sql_exec"], SQL_EXEC["arguments"])

    assert res["ok"] is False
    assert res["rows"] == []
    assert isinstance(res["columns"], list)
    assert res["columns"] == []
    assert res["error"] == "sql_exec: query returned 0 rows, so no answer can be published"
    assert res["meta"]["sql"] == "SELECT COUNT(*) AS n FROM silver_games"


def test_sql_exec_exception_becomes_structured_error(monkeypatch):
    fake = _stub(SQL_EXEC, exc=RuntimeError("warehouse unavailable"))
    tools = _catalogue(monkeypatch, {(SQL_EXEC["module"], SQL_EXEC["attribute"]): fake})

    res = _invoke(tools["sql_exec"], SQL_EXEC["arguments"])

    assert res["ok"] is False
    assert res["rows"] == []
    assert isinstance(res["columns"], list)
    assert res["error"] == "RuntimeError: warehouse unavailable"


def test_sql_exec_non_list_rows_becomes_actionable_error(monkeypatch):
    fake = _stub(SQL_EXEC, result={
        "tool": "sql_exec",
        "ok": True,
        "rows": {"n": 12},
        "columns": ["n"],
        "meta": {"source": "warehouse"},
        "error": "upstream query shape changed",
    })
    tools = _catalogue(monkeypatch, {(SQL_EXEC["module"], SQL_EXEC["attribute"]): fake})

    res = _invoke(tools["sql_exec"], SQL_EXEC["arguments"])

    assert res["ok"] is False
    assert res["rows"] == []
    assert res["columns"] == []
    assert res["error"].startswith("upstream query shape changed; "), res["error"]
    assert "sql_exec returned dict rows, expected a list" in res["error"]


def test_sql_exec_missing_rows_becomes_actionable_error(monkeypatch):
    fake = _stub(SQL_EXEC, result={
        "tool": "sql_exec",
        "ok": True,
        "meta": {"source": "warehouse"},
    })
    tools = _catalogue(monkeypatch, {(SQL_EXEC["module"], SQL_EXEC["attribute"]): fake})

    res = _invoke(tools["sql_exec"], SQL_EXEC["arguments"])

    assert res["ok"] is False
    assert res["rows"] == []
    assert res["columns"] == []
    assert res["error"] == "sql_exec returned NoneType rows, expected a list"


def test_sql_exec_keeps_non_dict_rows_under_value(monkeypatch):
    fake = _stub(SQL_EXEC, result={
        "tool": "sql_exec",
        "ok": True,
        "rows": [{"n": 12}, "extra", 7],
        "meta": {"source": "warehouse"},
    })
    tools = _catalogue(monkeypatch, {(SQL_EXEC["module"], SQL_EXEC["attribute"]): fake})

    res = _invoke(tools["sql_exec"], SQL_EXEC["arguments"])

    assert res["ok"] is True
    assert res["rows"] == [{"n": 12}, {"value": "extra"}, {"value": 7}]
    assert res["columns"] == ["n"]


def test_defensive_matchups_columns_follow_upstream_row_keys(monkeypatch):
    row = dict(DEFENSIVE_MATCHUPS["upstream_row"])
    fake = _FakeTool(DEFENSIVE_MATCHUPS["description"], result={
        "tool": DEFENSIVE_MATCHUPS["name"],
        "ok": True,
        "rows": [row],
        "meta": {"source": "warehouse"},
    })
    tools = _catalogue(monkeypatch, {
        (DEFENSIVE_MATCHUPS["module"], DEFENSIVE_MATCHUPS["attribute"]): fake,
    })

    res = _invoke(tools[DEFENSIVE_MATCHUPS["name"]], DEFENSIVE_MATCHUPS["arguments"])

    assert res["ok"] is True
    assert isinstance(res["rows"], list)
    assert len(res["rows"]) == 1
    assert isinstance(res["columns"], list)
    assert res["columns"] == list(row.keys())
    assert not set(res["columns"]) - set(row.keys())
    assert res["rows"][0] == row
    for key in row:
        assert key in res["columns"], key


def _playtype_upstream_rows(shape):
    spec = PLAYTYPE_PROFILE
    play_types = [dict(p) for p in spec["play_types"]]
    if shape == "dict":
        rows = {
            "subject": spec["subject"],
            "subject_id": 2544,
            "kind": "player",
            "side": "offense",
            "season": "2025-26",
            "play_types": play_types,
        }
    else:
        rows = [{"subject": spec["subject"], **p} for p in play_types]
    return {
        "tool": spec["name"],
        "ok": True,
        "rows": rows,
        "meta": {"source": "warehouse"},
    }


def _playtype_tools(monkeypatch, fake):
    spec = PLAYTYPE_PROFILE
    return _catalogue(monkeypatch, {
        (spec["module"], spec["attribute"]): fake,
    })


def test_playtype_profile_columns_follow_upstream_row_keys_both_shapes(monkeypatch):
    spec = PLAYTYPE_PROFILE
    for shape in ("dict", "list"):
        fake = _FakeTool(spec["description"], result=_playtype_upstream_rows(shape))
        tools = _playtype_tools(monkeypatch, fake)

        res = _invoke(tools[spec["name"]], spec["arguments"])

        assert res["ok"] is True, shape
        assert isinstance(res["rows"], list), shape
        assert len(res["rows"]) == len(spec["play_types"]), shape
        assert isinstance(res["columns"], list), shape
        assert res["columns"] == list(res["rows"][0].keys()), shape
        assert "subject" in res["columns"], shape
        assert res["rows"][0]["subject"] == spec["subject"], shape
        for key in spec["default_columns"]:
            assert key in res["columns"], key


def test_playtype_profile_empty_rows_keeps_default_columns(monkeypatch):
    spec = PLAYTYPE_PROFILE
    fake = _FakeTool(spec["description"], result={
        "tool": spec["name"], "ok": True, "rows": {},
        "meta": {"source": "warehouse"},
    })
    tools = _playtype_tools(monkeypatch, fake)

    res = _invoke(tools[spec["name"]], spec["arguments"])

    assert res["ok"] is True
    assert res["rows"] == []
    assert res["columns"] == spec["default_columns"]


def test_playtype_profile_error_paths_keep_default_columns(monkeypatch):
    spec = PLAYTYPE_PROFILE
    cases = (
        ({"tool": spec["name"], "ok": False, "rows": {},
          "error": "upstream refused the request"}, None),
        (None, RuntimeError("warehouse unavailable")),
    )
    for result, exc in cases:
        fake = _FakeTool(spec["description"], result=result, exc=exc)
        tools = _playtype_tools(monkeypatch, fake)

        res = _invoke(tools[spec["name"]], spec["arguments"])

        assert res["ok"] is False
        assert res["rows"] == []
        assert res["columns"] == spec["default_columns"]


def _streaks_upstream_rows(shape):
    spec = STREAKS
    streaks = [dict(r) for r in spec["streak_rows"]]
    if shape == "dict":
        rows = {"streaks": streaks, "count": len(streaks)}
    else:
        rows = streaks
    return {
        "tool": spec["name"],
        "ok": True,
        "rows": rows,
        "meta": {"source": "warehouse"},
    }


def _streaks_tools(monkeypatch, fake):
    spec = STREAKS
    return _catalogue(monkeypatch, {
        (spec["module"], spec["attribute"]): fake,
    })


def test_streaks_columns_follow_emitted_row_keys_both_shapes(monkeypatch):
    spec = STREAKS
    for shape in ("dict", "list"):
        fake = _FakeTool(spec["description"], result=_streaks_upstream_rows(shape))
        tools = _streaks_tools(monkeypatch, fake)

        res = _invoke(tools[spec["name"]], spec["arguments"])

        assert res["ok"] is True, shape
        assert isinstance(res["rows"], list), shape
        assert len(res["rows"]) == len(spec["streak_rows"]), shape
        assert isinstance(res["columns"], list), shape
        assert res["columns"] == list(res["rows"][0].keys()), shape
        assert res["columns"] == spec["emitted_columns"], shape
        assert "holder_id" in res["columns"], shape
        assert res["rows"][0]["holder_id"] == spec["streak_rows"][0]["holder_id"], shape
        for key in spec["default_columns"]:
            assert key in res["columns"], key


def test_streaks_empty_rows_keeps_default_columns(monkeypatch):
    spec = STREAKS
    fake = _FakeTool(spec["description"], result={
        "tool": spec["name"], "ok": True, "rows": {},
        "meta": {"source": "warehouse"},
    })
    tools = _streaks_tools(monkeypatch, fake)

    res = _invoke(tools[spec["name"]], spec["arguments"])

    assert res["ok"] is True
    assert res["rows"] == []
    assert res["columns"] == spec["default_columns"]


def test_streaks_error_paths_keep_default_columns(monkeypatch):
    spec = STREAKS
    cases = (
        ({"tool": spec["name"], "ok": False, "rows": {},
          "error": "upstream refused the request"}, None),
        (None, RuntimeError("warehouse unavailable")),
    )
    for result, exc in cases:
        fake = _FakeTool(spec["description"], result=result, exc=exc)
        tools = _streaks_tools(monkeypatch, fake)

        res = _invoke(tools[spec["name"]], spec["arguments"])

        assert res["ok"] is False
        assert res["rows"] == []
        assert res["columns"] == spec["default_columns"]


def _head_to_head_upstream_rows(shape):
    spec = HEAD_TO_HEAD
    game = dict(spec["game_row"])
    if shape == "dict":
        rows = {
            "player": spec["arguments"]["player"],
            "opponent": spec["arguments"]["opponent"],
            "games": [game],
        }
    else:
        rows = [game]
    return {
        "tool": spec["name"],
        "ok": True,
        "rows": rows,
        "meta": {"source": "warehouse", "season": "2025-26"},
    }


def _head_to_head_tools(monkeypatch, fake):
    spec = HEAD_TO_HEAD
    return _catalogue(monkeypatch, {
        (spec["module"], spec["attribute"]): fake,
    })


def _lineup_pair_row():
    from shared.tools.lineup_matrix import _pair_row

    return _pair_row(
        (101, 102, 103, 104, 105),
        (201, 202, 203, 204, 205),
        {"poss": 120, "off_poss_a": 60, "off_poss_b": 58,
         "pts_a": 130, "pts_b": 118, "blowout": 12},
        "Unit Alpha",
        "Unit Beta",
    )


def _lineup_tools(monkeypatch, fake):
    spec = LINEUP_MATCHUP
    return _catalogue(monkeypatch, {
        (spec["module"], spec["attribute"]): fake,
    })


def test_head_to_head_columns_follow_emitted_row_keys_both_shapes(monkeypatch):
    spec = HEAD_TO_HEAD
    for shape in ("dict", "list"):
        fake = _FakeTool(spec["description"], result=_head_to_head_upstream_rows(shape))
        tools = _head_to_head_tools(monkeypatch, fake)

        res = _invoke(tools[spec["name"]], spec["arguments"])

        assert res["ok"] is True, shape
        assert isinstance(res["rows"], list), shape
        assert len(res["rows"]) == 1, shape
        assert isinstance(res["columns"], list), shape
        assert res["columns"] == list(res["rows"][0].keys()), shape
        assert not set(res["columns"]) - set(res["rows"][0]), shape
        for key in spec["literal_columns"]:
            assert key in res["columns"], (shape, key)
        for key in spec["game_row"]:
            assert key in res["columns"], (shape, key)


def test_head_to_head_dict_shape_emits_full_game_row(monkeypatch):
    spec = HEAD_TO_HEAD
    fake = _FakeTool(spec["description"], result=_head_to_head_upstream_rows("dict"))
    tools = _head_to_head_tools(monkeypatch, fake)

    res = _invoke(tools[spec["name"]], spec["arguments"])

    emitted = set(res["rows"][0])
    assert len(emitted) == 19
    assert {"player", "opponent", "game_id", "home", "tov", "fgm",
            "fga", "fg3m", "fg3a"} <= emitted
    assert res["columns"] == list(res["rows"][0].keys())


def test_head_to_head_empty_rows_keeps_literal_columns(monkeypatch):
    spec = HEAD_TO_HEAD
    fake = _FakeTool(spec["description"], result={
        "tool": spec["name"], "ok": True, "rows": {},
        "meta": {"source": "warehouse"},
    })
    tools = _head_to_head_tools(monkeypatch, fake)

    res = _invoke(tools[spec["name"]], spec["arguments"])

    assert res["ok"] is True
    assert res["rows"] == []
    assert res["columns"] == spec["literal_columns"]


def test_head_to_head_error_path_keeps_literal_columns(monkeypatch):
    spec = HEAD_TO_HEAD
    fake = _FakeTool(spec["description"], result={
        "tool": spec["name"], "ok": False, "rows": {},
        "error": "upstream refused the request",
    })
    tools = _head_to_head_tools(monkeypatch, fake)

    res = _invoke(tools[spec["name"]], spec["arguments"])

    assert res["ok"] is False
    assert res["rows"] == []
    assert res["columns"] == spec["literal_columns"]


def test_lineup_matchup_columns_follow_real_pair_row_keys(monkeypatch):
    spec = LINEUP_MATCHUP
    row = _lineup_pair_row()
    assert len(row) == 15
    fake = _FakeTool(spec["description"], result={
        "tool": spec["name"], "ok": True, "rows": [row],
        "meta": {"source": "warehouse"},
    })
    tools = _lineup_tools(monkeypatch, fake)

    res = _invoke(tools[spec["name"]], spec["arguments"])

    assert res["ok"] is True
    assert isinstance(res["rows"], list)
    assert len(res["rows"]) == 1
    assert isinstance(res["columns"], list)
    assert res["columns"] == list(row.keys())
    assert res["columns"] == list(res["rows"][0].keys())
    assert not set(res["columns"]) - set(row.keys())
    assert res["rows"][0] == row
    for key in spec["extras"]:
        assert key in res["columns"], key
    assert len(fake.calls) == 1
    assert fake.calls[0]["team_a"] == spec["arguments"]["team_a"]
    assert fake.calls[0]["team_b"] == spec["arguments"]["team_b"]


def test_lineup_matchup_empty_rows_keeps_literal_columns(monkeypatch):
    spec = LINEUP_MATCHUP
    fake = _FakeTool(spec["description"], result={
        "tool": spec["name"], "ok": True, "rows": [],
        "meta": {"source": "warehouse"},
    })
    tools = _lineup_tools(monkeypatch, fake)

    res = _invoke(tools[spec["name"]], spec["arguments"])

    assert res["ok"] is True
    assert res["rows"] == []
    assert isinstance(res["columns"], list)
    assert res["columns"] == spec["literal_columns"]


def test_lineup_matchup_error_path_keeps_literal_columns(monkeypatch):
    spec = LINEUP_MATCHUP
    fake = _FakeTool(spec["description"], result={
        "tool": spec["name"], "ok": False, "rows": [],
        "error": "upstream refused the request",
    })
    tools = _lineup_tools(monkeypatch, fake)

    res = _invoke(tools[spec["name"]], spec["arguments"])

    assert res["ok"] is False
    assert res["rows"] == []
    assert isinstance(res["columns"], list)
    assert res["columns"] == spec["literal_columns"]


def test_lineup_matchup_exception_becomes_structured_error(monkeypatch):
    spec = LINEUP_MATCHUP
    fake = _FakeTool(spec["description"], exc=RuntimeError("warehouse unavailable"))
    tools = _lineup_tools(monkeypatch, fake)

    res = _invoke(tools[spec["name"]], spec["arguments"])

    assert res["ok"] is False
    assert res["rows"] == []
    assert isinstance(res["columns"], list)
    assert res["columns"] == []
    assert res["error"] == "warehouse unavailable"


def test_morning_briefing_surfaces_all_faithful_upstream_sections(monkeypatch):
    spec = MORNING_BRIEFING
    fake = _FakeTool(spec["description"], result={
        "tool": spec["name"],
        "ok": True,
        "rows": spec["upstream_rows"],
        "meta": {"season": "2025-26"},
    })
    tools = _catalogue(monkeypatch, {(spec["module"], spec["attribute"]): fake})

    res = _invoke(tools[spec["name"]], spec["arguments"])

    cols = ["section", "headline", "detail", "team", "player"]
    assert res["ok"] is True
    assert isinstance(res["rows"], list)
    assert isinstance(res["columns"], list)
    assert res["columns"] == cols
    assert len(res["rows"]) == 8
    sections = [r["section"] for r in res["rows"]]
    assert sorted(sections) == sorted(MORNING_BRIEFING_SECTIONS)
    assert len(set(sections)) == len(sections)
    assert "movers" not in sections
    for row in res["rows"]:
        assert isinstance(row, dict)
        assert set(row.keys()) == set(cols)
    assert set(res["columns"]) == {key for row in res["rows"] for key in row}

    last = next(r for r in res["rows"] if r["section"] == "last_night")
    assert last["headline"] == "LAL @ BOS"
    assert last["detail"] == "110-118 Final"
    assert last["player"] is None
    tonight = next(r for r in res["rows"] if r["section"] == "tonight")
    assert tonight["headline"] == "GSW @ NYK"
    assert tonight["detail"] == "?-? 7:30 pm ET"
    assert tonight["player"] is None

    today_movers = [r for r in res["rows"] if r["section"] == "today_movers"]
    assert any(r["player"] == "A. Star" for r in today_movers)
    assert any(r["team"] == "BOS" for r in today_movers)
    assert any(r["section"] == "streaks" and r["team"] == "Denver Nuggets"
               for r in res["rows"])
    assert any(r["section"] == "watchlist" and r["player"] == "A. Star"
               for r in res["rows"])

    by_section = {r["section"]: r for r in res["rows"]}
    watch = by_section["watchlist"]
    assert watch["player"] == "A. Star"
    assert watch["team"] == "BOS"
    assert watch["headline"] == "Watching player A. Star"
    assert watch["detail"] == "Added 2026-03-01T12:00:00Z \u00b7 24.5 PPG / 5.2 RPG / 4.1 APG"
    assert by_section["movers_climbers"]["player"] == "C. Guard"
    assert by_section["movers_climbers"]["detail"] == "2 rank (1.4 pts)"
    assert by_section["movers_fallers"]["player"] == "D. Forward"
    assert by_section["movers_fallers"]["detail"] == "-1 rank (-0.8 pts)"
    assert by_section["movers_new_entries"]["player"] == "E. Rookie"
    assert by_section["movers_new_entries"]["detail"] == "new #25 (18.5 pts)"


def test_morning_briefing_watchlist_maps_real_entity_rows(monkeypatch):
    spec = MORNING_BRIEFING
    watch_rows = [
        {"entity_type": "player", "entity_id": "A. Star",
         "added_at": "2026-03-01T12:00:00Z",
         "snapshot": {"found": True, "player": "A. Star", "team": "BOS",
                      "gp": 60, "ppg": 24.5, "rpg": 5.2, "apg": 4.1}},
        {"entity_type": "team", "entity_id": "BOS",
         "added_at": "2026-03-02T09:30:00Z",
         "snapshot": {"found": True, "team": "BOS", "name": "Boston Celtics",
                      "wins": 41, "losses": 24, "record": "41-24"}},
        {"entity_type": "player", "entity_id": "Unknown Guy",
         "added_at": "2026-03-03T00:00:00Z",
         "snapshot": {"found": False, "player": "Unknown Guy"}},
        {"entity_type": "player", "entity_id": "No Data",
         "snapshot": {"found": False}},
    ]
    upstream = dict(spec["upstream_rows"])
    upstream["watchlist"] = watch_rows
    fake = _FakeTool(spec["description"], result={
        "tool": spec["name"], "ok": True, "rows": upstream,
        "meta": {"season": "2025-26"},
    })
    tools = _catalogue(monkeypatch, {(spec["module"], spec["attribute"]): fake})

    res = _invoke(tools[spec["name"]], spec["arguments"])

    cols = ["section", "headline", "detail", "team", "player"]
    watch = [r for r in res["rows"] if r["section"] == "watchlist"]
    assert len(watch) == len(watch_rows)
    for row in watch:
        assert set(row.keys()) == set(cols)

    assert watch[0]["player"] == "A. Star"
    assert watch[0]["team"] == "BOS"
    assert watch[0]["headline"] == "Watching player A. Star"
    assert watch[0]["detail"] == "Added 2026-03-01T12:00:00Z \u00b7 24.5 PPG / 5.2 RPG / 4.1 APG"

    assert watch[1]["player"] is None
    assert watch[1]["team"] == "BOS"
    assert watch[1]["headline"] == "Watching team Boston Celtics"
    assert watch[1]["detail"] == "Added 2026-03-02T09:30:00Z \u00b7 41-24"

    assert watch[2]["player"] == "Unknown Guy"
    assert watch[2]["team"] is None
    assert watch[2]["headline"] == "Watching player Unknown Guy"
    assert watch[2]["detail"] == "Added 2026-03-03T00:00:00Z"

    assert watch[3]["player"] == "No Data"
    assert watch[3]["team"] is None
    assert watch[3]["headline"] == "Watching player No Data"
    assert watch[3]["detail"] is None


def test_get_today_maps_real_scoreboard_keys(monkeypatch):
    res = _get_today_result(monkeypatch, _get_today_upstream())

    assert res["ok"] is True
    assert res["columns"] == GET_TODAY_COLUMNS
    assert len(res["rows"]) == 4
    for row in res["rows"]:
        assert set(row.keys()) == set(GET_TODAY_COLUMNS)

    by_category = {row["category"]: row for row in res["rows"]}
    last = by_category["last_night"]
    assert last["home_team"] == "BOS"
    assert last["away_team"] == "LAL"
    assert last["score"] == "110-118"
    assert last["status"] == "Final"
    assert last["detail"] == "LAL @ BOS"

    tonight = by_category["tonight"]
    assert tonight["home_team"] == "NYK"
    assert tonight["away_team"] == "GSW"
    assert tonight["score"] == "?-?"
    assert tonight["status"] == "7:30 pm ET"
    assert tonight["detail"] == "GSW @ NYK"


def test_get_today_preserves_real_zero_and_marks_unplayed_with_question(monkeypatch):
    upstream = _get_today_upstream()
    upstream["last_night"][0]["HOME_TEAM_PTS"] = 0

    res = _get_today_result(monkeypatch, upstream)
    by_category = {row["category"]: row for row in res["rows"]}

    assert by_category["last_night"]["score"] == "110-0"
    assert by_category["tonight"]["score"] == "?-?"
    assert not any(c.isdigit() for c in by_category["tonight"]["score"])


def test_registry_matches_the_typescript_tool_names(monkeypatch):
    tools = _catalogue(monkeypatch, {})

    source = (BACKEND / "analyst" / "python-tools.ts").read_text(encoding="utf-8")
    block = re.search(
        r"export const ANALYST_TOOL_NAMES\b[^=]*=\s*\[(.*?)\]\s*as const;", source, re.S
    ).group(1)
    declared = re.findall(r'"([^"]+)"', block)

    assert len(declared) == 93
    assert list(tools.keys()) == declared
    for spec in SECTIONED:
        assert spec["name"] in tools


def test_search_shots_parses_real_upstream_clock_string(monkeypatch):
    res = _search_shots_result(monkeypatch, [_search_shot_row()])

    assert res["ok"] is True
    assert isinstance(res["rows"], list)
    assert isinstance(res["columns"], list)
    assert res["columns"] == SEARCH_SHOTS["columns"]
    assert len(res["rows"]) == 1
    row = res["rows"][0]
    assert list(row.keys()) == SEARCH_SHOTS["columns"]
    assert row["minutes_remaining"] == "3"
    assert row["seconds_remaining"] == "24"
    assert row["game_id"] == "0022400001"
    assert row["player_name"] == "Synthetic Scorer"
    assert row["period"] == 3
    assert row["shot_distance"] == 23.7
    assert row["zone"] == "left_corner_three"
    assert row["made"] is True


def test_search_shots_unparseable_clock_yields_none(monkeypatch):
    for row in (_search_shot_row(clock="unknown"), _search_shot_row(clock=None)):
        res = _search_shots_result(monkeypatch, [row])

        assert res["ok"] is True
        assert res["columns"] == SEARCH_SHOTS["columns"]
        assert len(res["rows"]) == 1
        emitted = res["rows"][0]
        assert emitted["minutes_remaining"] is None
        assert emitted["seconds_remaining"] is None


def test_search_shots_explicit_clock_keys_keep_precedence(monkeypatch):
    row = _search_shot_row(
        clock="3:24", MINUTES_REMAINING="09", SECONDS_REMAINING="07")
    res = _search_shots_result(monkeypatch, [row])

    assert res["ok"] is True
    assert res["columns"] == SEARCH_SHOTS["columns"]
    assert len(res["rows"]) == 1
    emitted = res["rows"][0]
    assert emitted["minutes_remaining"] == "09"
    assert emitted["seconds_remaining"] == "07"


def _tracking_row(measure_type, measures):
    from shared.tools.tracking import _MEASURE_COLUMNS, _PLAYER_IDENTITY

    identity = {key: TRACKING_IDENTITY_VALUES[key] for key in _PLAYER_IDENTITY}
    family = {key: measures[key] for key in _MEASURE_COLUMNS[measure_type] if key in measures}
    return {**identity, **family, "measure_type": measure_type}


def _tracking_result(monkeypatch, rows, arguments=None):
    spec = TRACKING_PROFILE
    fake = _FakeTool(spec["description"], result={
        "tool": spec["name"],
        "ok": True,
        "rows": rows,
        "meta": {"source": "warehouse"},
    })
    tools = _catalogue(monkeypatch, {(spec["module"], spec["attribute"]): fake})
    return _invoke(tools[spec["name"]], arguments or {
        "player": "Synthetic Scorer", "season": "2025-26",
        "measure_type": "CatchShoot",
    })


def test_tracking_profile_emits_concrete_measure_stat_value_pairs(monkeypatch):
    families = (("CatchShoot", CATCH_SHOOT_MEASURES),
                ("Defense", DEFENSE_MEASURES))
    for measure_type, measures in families:
        res = _tracking_result(monkeypatch, [_tracking_row(measure_type, measures)], {
            "player": "Synthetic Scorer", "season": "2025-26",
            "measure_type": measure_type,
        })

        assert res["ok"] is True, measure_type
        assert isinstance(res["rows"], list), measure_type
        assert isinstance(res["columns"], list), measure_type
        assert res["columns"] == TRACKING_PROFILE["columns"], measure_type
        assert len(res["rows"]) == len(measures), measure_type
        assert {row["stat"]: row["value"] for row in res["rows"]} == measures, measure_type
        for row in res["rows"]:
            assert list(row.keys()) == TRACKING_PROFILE["columns"], measure_type
            assert row["subject"] == "Synthetic Scorer", measure_type
            assert row["season"] == "2025-26", measure_type
            assert row["measure_type"] == measure_type, measure_type
        assert "overall" not in {row["stat"] for row in res["rows"]}, measure_type
        assert None not in [row["value"] for row in res["rows"]], measure_type
        assert not set(TRACKING_IDENTITY_VALUES) & {row["stat"] for row in res["rows"]}, measure_type


def test_tracking_profile_catchshoot_pts_maps_real_value(monkeypatch):
    res = _tracking_result(monkeypatch, [_tracking_row("CatchShoot", CATCH_SHOOT_MEASURES)])

    pts = [row for row in res["rows"] if row["stat"] == "CATCH_SHOOT_PTS"]
    assert len(pts) == 1
    assert pts[0]["value"] == 250
    assert all(row["stat"] != "overall" for row in res["rows"])
    assert all(row["value"] is not None for row in res["rows"])


def test_tracking_profile_empty_rows_keeps_rows_and_columns(monkeypatch):
    res = _tracking_result(monkeypatch, [])

    assert res["ok"] is True
    assert isinstance(res["rows"], list)
    assert res["rows"] == []
    assert isinstance(res["columns"], list)
    assert res["columns"] == TRACKING_PROFILE["columns"]


def test_tracking_profile_error_paths_keep_rows_and_columns(monkeypatch):
    spec = TRACKING_PROFILE
    cases = (
        ({"tool": spec["name"], "ok": False, "rows": [],
          "error": "upstream refused the request"}, None, "upstream refused the request"),
        (None, RuntimeError("warehouse unavailable"), "warehouse unavailable"),
    )
    for result, exc, message in cases:
        fake = _FakeTool(spec["description"], result=result, exc=exc)
        tools = _catalogue(monkeypatch, {(spec["module"], spec["attribute"]): fake})
        res = _invoke(tools[spec["name"]], {
            "player": "Synthetic Scorer", "season": "2025-26",
            "measure_type": "CatchShoot",
        })

        assert res["ok"] is False
        assert isinstance(res["rows"], list)
        assert res["rows"] == []
        assert isinstance(res["columns"], list)
        assert res["columns"] == spec["columns"]
        assert res["error"] == message
