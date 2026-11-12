"""Analyst-boundary contract for the matchup, availability and SQL tools.

These shared tools return dict-shaped rows. submit_answer rejects a source ref
whose rows payload is not a list, so each section is flattened into
self-describing rows at the analyst boundary and every failure path still
returns an array.
"""

import asyncio
import importlib
import re
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(BACKEND / "analyst"))

from analyst import python_tools  # noqa: E402

SECTIONED = (
    {
        "name": "get_matchup_brief",
        "module": "shared.tools.team",
        "attribute": "get_matchup_brief",
        "arguments": {"a": "BOS", "b": "LAL", "season": "2025-26"},
        "description": "Two-team matchup brief with ratings, form, injuries, season series, and win probability.",
        "default_columns": [
            "section", "teams", "ratings_provenance", "ratings", "form",
            "injuries", "season_series", "prediction",
        ],
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
        "default_columns": [
            "section", "game", "form", "matchups", "injuries", "xfactors",
            "why_watch", "already_played", "game_id", "date", "matchup",
            "score", "suggestion",
        ],
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
        "default_columns": ["section", "team", "opponent", "edge"],
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
        "default_columns": [
            "section", "team", "out", "questionable", "availability_known",
            "net_rating", "net_rank", "last10", "impact",
        ],
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
        "default_columns": [
            "section", "team", "coverage", "tiers", "starter_bench_split",
            "most_used_unit", "closing_candidates", "thin_flags",
            "clutch_context",
        ],
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
        "default_columns": [
            "section", "player", "player_id", "window_games", "splits",
            "defense_splits",
        ],
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
        "default_columns": [
            "section", "player", "player_id", "stat", "window_n", "window",
            "season", "career", "drivers", "drivers_all", "verdict",
            "verdict_note",
        ],
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


class _FakeTool:
    """Stand-in for a langchain tool invoked by the analyst wrappers."""

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
    """Rebuild the analyst catalogue over stubbed shared tools."""
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
    """Every upstream value must survive in exactly one emitted row."""
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


def test_sectioned_empty_rows_returns_rows_array(monkeypatch):
    for spec in SECTIONED:
        fake = _stub(spec, result={"tool": spec["name"], "ok": True, "rows": {}})
        tools = _catalogue(monkeypatch, {(spec["module"], spec["attribute"]): fake})

        res = _invoke(tools[spec["name"]], spec["arguments"])

        assert res["ok"] is True, spec["name"]
        assert res["rows"] == [], spec["name"]
        assert res["columns"] == spec["default_columns"], spec["name"]


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
        assert res["columns"] == spec["default_columns"], spec["name"]
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
        assert res["columns"] == spec["default_columns"], spec["name"]
        assert res["error"] == "RuntimeError: warehouse unavailable", spec["name"]
        assert res["tool"] == spec["name"], spec["name"]


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


def test_registry_matches_the_typescript_tool_names(monkeypatch):
    tools = _catalogue(monkeypatch, {})

    source = (BACKEND / "analyst" / "python-tools.ts").read_text(encoding="utf-8")
    block = source.split(
        "export const ANALYST_TOOL_NAMES: readonly PythonToolName[] = [", 1)[1]
    block = block.split("] as const;", 1)[0]
    declared = re.findall(r'"([^"]+)"', block)

    assert len(declared) == 89
    assert list(tools.keys()) == declared
    for spec in SECTIONED:
        assert spec["name"] in tools
