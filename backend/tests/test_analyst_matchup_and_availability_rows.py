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
            "headline": "Watch BOS", "detail": "rest",
            "team": "BOS", "player": "A. Star",
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
    assert by_section["movers_climbers"]["player"] == "C. Guard"
    assert by_section["movers_climbers"]["detail"] == "2 rank (1.4 pts)"
    assert by_section["movers_fallers"]["player"] == "D. Forward"
    assert by_section["movers_fallers"]["detail"] == "-1 rank (-0.8 pts)"
    assert by_section["movers_new_entries"]["player"] == "E. Rookie"
    assert by_section["movers_new_entries"]["detail"] == "new #25 (18.5 pts)"


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
