"""Analyst-boundary contract for the award race and last-x tools.

Both tools must hand the analyst a rows array. submit_answer rejects a source
ref whose rows payload is not a list, so the award-race tool's dict-shaped
rows are flattened at the analyst boundary and every failure path still
returns an array.
"""

import asyncio
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(BACKEND / "analyst"))

from analyst import python_tools  # noqa: E402

AWARD_COLS = ["rank", "player", "team", "score"]
LAST_X_COLS = ["GAME_DATE", "MATCHUP", "PTS", "REB", "AST", "MIN"]


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


def _catalogue(monkeypatch, *, award=None, last_x=None):
    """Rebuild the analyst catalogue over stubbed shared tools."""
    import shared.tools.awards as awards
    import shared.tools.player as player

    if award is not None:
        monkeypatch.setattr(awards, "get_award_race", award)
    if last_x is not None:
        monkeypatch.setattr(player, "get_last_x", last_x)
    return python_tools.catalogue()


def _invoke(tool, arguments: dict):
    return asyncio.run(tool.ainvoke(arguments))


def test_award_race_flattens_candidates_to_rows_array(monkeypatch):
    fake = _FakeTool(
        "Award race top 5 for MVP/DPOY/ROY/6MOY.",
        result={
            "tool": "get_award_race",
            "ok": True,
            "rows": {
                "candidates": [
                    {"rank": 1, "player": "A. Star", "team": "BOS", "score": 1.42},
                    {"rank": 2, "player": "B. Buck", "team": "DEN", "score": 1.10},
                ]
            },
            "meta": {
                "source": "warehouse (nba_api)",
                "score_unit": "weighted_z_score",
                "results_tool": "get_award_results",
            },
        },
    )
    tools = _catalogue(monkeypatch, award=fake)

    res = _invoke(tools["get_award_race"], {"award": "MVP", "season": "2024-25"})

    assert res["ok"] is True
    assert isinstance(res["rows"], list)
    assert [row["player"] for row in res["rows"]] == ["A. Star", "B. Buck"]
    assert res["columns"] == AWARD_COLS
    assert res["meta"]["score_unit"] == "weighted_z_score"
    assert res["meta"]["results_tool"] == "get_award_results"
    assert fake.calls == [{"award": "MVP", "season": "2024-25"}]


def test_award_race_unknown_award_returns_empty_rows_array(monkeypatch):
    fake = _FakeTool(
        "Award race top 5 for MVP/DPOY/ROY/6MOY.",
        result={
            "tool": "get_award_race",
            "ok": False,
            "rows": {},
            "meta": {"note": "no candidates"},
            "error": "unknown award",
        },
    )
    tools = _catalogue(monkeypatch, award=fake)

    res = _invoke(tools["get_award_race"], {"award": "NOT_AN_AWARD"})

    assert res["ok"] is False
    assert res["rows"] == []
    assert res["columns"] == AWARD_COLS
    assert res["error"] == "unknown award"


def test_award_race_upstream_exception_becomes_structured_error(monkeypatch):
    fake = _FakeTool(
        "Award race top 5 for MVP/DPOY/ROY/6MOY.",
        exc=RuntimeError("warehouse unavailable"),
    )
    tools = _catalogue(monkeypatch, award=fake)

    res = _invoke(tools["get_award_race"], {"award": "MVP"})

    assert res["ok"] is False
    assert res["rows"] == []
    assert res["error"] == "RuntimeError: warehouse unavailable"


def test_last_x_keeps_game_rows_and_columns(monkeypatch):
    fake = _FakeTool(
        "Last n games for one player id, most recent first.",
        result={
            "tool": "get_last_x",
            "ok": True,
            "rows": [
                {
                    "GAME_DATE": "2026-01-05",
                    "MATCHUP": "BOS @ NYK",
                    "PTS": 30,
                    "REB": 8,
                    "AST": 6,
                    "MIN": 36,
                }
            ],
            "meta": {"source": "warehouse"},
        },
    )
    tools = _catalogue(monkeypatch, last_x=fake)

    res = _invoke(tools["get_last_x"], {"player_id": 2544, "n": 5, "season": "2024-25"})

    assert res["ok"] is True
    assert isinstance(res["rows"], list)
    assert res["rows"][0]["PTS"] == 30
    assert res["columns"] == LAST_X_COLS
    assert fake.calls[0]["n"] == 5
    assert fake.calls[0]["season"] == "2024-25"
    assert str(fake.calls[0]["player_id"]) == "2544"


def test_last_x_upstream_error_returns_rows_array(monkeypatch):
    fake = _FakeTool(
        "Last n games for one player id, most recent first.",
        result={"tool": "get_last_x", "ok": False, "error": "empty upstream response"},
    )
    tools = _catalogue(monkeypatch, last_x=fake)

    res = _invoke(tools["get_last_x"], {"player_id": 2544})

    assert res["ok"] is False
    assert res["rows"] == []
    assert res["columns"] == LAST_X_COLS
    assert res["error"] == "empty upstream response"


def test_both_tools_are_registered_with_anchorable_names(monkeypatch):
    tools = _catalogue(monkeypatch)

    assert "get_award_race" in tools
    assert "get_last_x" in tools
    for name in ("get_award_race", "get_last_x"):
        schema = tools[name].args_schema.model_json_schema()
        assert schema["properties"]
