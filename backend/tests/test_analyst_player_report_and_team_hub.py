"""Analyst-boundary contract for the player report and team hub tools.

Both shared tools return dict-shaped rows. submit_answer rejects a source ref
whose rows payload is not a list, so each section is flattened into
self-describing rows at the analyst boundary and every failure path still
returns an array.
"""

import asyncio
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(BACKEND / "analyst"))

from analyst import python_tools  # noqa: E402

SEASON_LINE = {
    "PLAYER_ID": 424242,
    "PLAYER": "A. Star",
    "TEAM": "BOS",
    "AGE": 27,
    "GP": 82,
    "GS": 82,
    "MPG": 35.1,
    "PPG": 28.4,
    "RPG": 8.1,
    "APG": 6.2,
    "SPG": 1.2,
    "BPG": 0.6,
    "FG_PCT": 0.471,
    "FG3_PCT": 0.382,
    "FT_PCT": 0.855,
    "TS_PCT": 0.601,
}

ROSTER_ROW = {
    "PLAYER": "A. Star",
    "TEAM": "LAL",
    "AGE": 27,
    "GP": 55,
    "PPG": 28.4,
    "RPG": 8.1,
    "APG": 6.2,
}

TEAM_SUMMARY = {
    "games": 65,
    "wins": 41,
    "losses": 24,
    "covers_full_season": False,
    "ppg": 114.8,
    "ppg_games": 65,
    "ts_pct": 57.9,
    "ts_pct_games": 65,
}

PLAYER_COLS = [*SEASON_LINE, "section"]
TEAM_COLS = [*ROSTER_ROW, "section"]
PLAYER_DEFAULT_COLS = ["section", "PLAYER", "TEAM", "PPG", "RPG", "APG"]
TEAM_DEFAULT_COLS = ["section", "PLAYER", "TEAM", "AGE", "GP", "PPG", "RPG", "APG"]


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


def _catalogue(monkeypatch, *, report=None, hub=None):
    """Rebuild the analyst catalogue over stubbed shared tools."""
    import shared.tools.player as player
    import shared.tools.team as team

    if report is not None:
        monkeypatch.setattr(player, "get_player_report", report)
    if hub is not None:
        monkeypatch.setattr(team, "get_team_hub", hub)
    return python_tools.catalogue()


def _invoke(tool, arguments: dict):
    return asyncio.run(tool.ainvoke(arguments))


def test_player_report_flattens_sections_to_rows_array(monkeypatch):
    fake = _FakeTool(
        "Multi-part player report: season line, advanced profile, shots, clutch.",
        result={
            "tool": "get_player_report",
            "ok": True,
            "rows": {
                "season_line": dict(SEASON_LINE),
                "advanced": {
                    "PLAYER_NAME": "A. Star",
                    "TS_PCT": 0.612,
                    "USG_PCT": 0.301,
                },
                "shot_profile": [
                    {"zone": "restricted_area", "share": 0.41, "FG_PCT": 0.68},
                    {"zone": "above_the_break_3", "share": 0.33, "FG_PCT": 0.37},
                ],
                "clutch": {"PLAYER_NAME": "A. Star", "PTS": 44, "GP": 9},
            },
            "meta": {
                "source": "warehouse composite",
                "season": "2024-25",
                "player": "A. Star",
                "deterministic_answer": "A. Star, 2024-25: 28.4 PPG.",
            },
        },
    )
    tools = _catalogue(monkeypatch, report=fake)

    res = _invoke(tools["get_player_report"], {"player": 2544, "season": "2024-25"})

    assert res["ok"] is True
    assert isinstance(res["rows"], list)
    assert [row["section"] for row in res["rows"]] == [
        "season_line", "advanced", "shot_profile", "shot_profile", "clutch",
    ]
    assert res["rows"][0] == {**SEASON_LINE, "section": "season_line"}
    assert res["rows"][0]["TS_PCT"] == 0.601
    assert res["columns"] == PLAYER_COLS
    assert res["meta"]["player"] == "A. Star"
    assert res["meta"]["deterministic_answer"] == "A. Star, 2024-25: 28.4 PPG."
    assert fake.calls == [{"player": 2544, "season": "2024-25"}]


def test_player_report_empty_rows_returns_rows_array(monkeypatch):
    fake = _FakeTool(
        "Multi-part player report: season line, advanced profile, shots, clutch.",
        result={
            "tool": "get_player_report",
            "ok": True,
            "rows": {},
            "meta": {"source": "warehouse composite"},
        },
    )
    tools = _catalogue(monkeypatch, report=fake)

    res = _invoke(tools["get_player_report"], {"player": 2544})

    assert res["ok"] is True
    assert res["rows"] == []
    assert res["columns"] == PLAYER_DEFAULT_COLS


def test_player_report_upstream_exception_becomes_structured_error(monkeypatch):
    fake = _FakeTool(
        "Multi-part player report: season line, advanced profile, shots, clutch.",
        exc=RuntimeError("warehouse unavailable"),
    )
    tools = _catalogue(monkeypatch, report=fake)

    res = _invoke(tools["get_player_report"], {"player": 2544})

    assert res["ok"] is False
    assert res["rows"] == []
    assert res["columns"] == PLAYER_DEFAULT_COLS
    assert res["error"] == "RuntimeError: warehouse unavailable"


def test_team_hub_flattens_sections_to_rows_array(monkeypatch):
    fake = _FakeTool(
        "Game log plus roster for one team id. Warehouse first.",
        result={
            "tool": "get_team_hub",
            "ok": True,
            "rows": {
                "roster": [
                    dict(ROSTER_ROW),
                    {
                        "PLAYER": "B. Role",
                        "TEAM": "LAL",
                        "AGE": 24,
                        "GP": 51,
                        "PPG": 11.2,
                        "RPG": 4.0,
                        "APG": 2.1,
                    },
                ],
                "summary": dict(TEAM_SUMMARY),
                "games": [{"GAME_ID": "0022400001", "WL": "W", "PTS": 118}],
            },
            "meta": {"source": "warehouse:silver_hist_gamelogs", "season": "2024-25"},
        },
    )
    tools = _catalogue(monkeypatch, hub=fake)

    res = _invoke(tools["get_team_hub"], {"team_id": 1610612747, "season": "2024-25"})

    assert res["ok"] is True
    assert isinstance(res["rows"], list)
    assert [row["section"] for row in res["rows"]] == [
        "roster", "roster", "summary", "games",
    ]
    assert res["rows"][0] == {**ROSTER_ROW, "section": "roster"}
    assert res["rows"][2] == {**TEAM_SUMMARY, "section": "summary"}
    assert res["rows"][2]["wins"] == 41
    assert res["rows"][2]["covers_full_season"] is False
    assert res["columns"] == TEAM_COLS
    assert res["meta"]["source"] == "warehouse:silver_hist_gamelogs"
    assert fake.calls == [{"team_id": 1610612747, "season": "2024-25"}]


def test_unknown_section_keys_are_surfaced_not_dropped(monkeypatch):
    fake = _FakeTool(
        "Game log plus roster for one team id. Warehouse first.",
        result={
            "tool": "get_team_hub",
            "ok": True,
            "rows": {
                "roster": [dict(ROSTER_ROW)],
                "summary": dict(TEAM_SUMMARY),
                "games": [{"GAME_ID": "0022400001", "WL": "W", "PTS": 118}],
                "awards": [{"name": "All-Star", "season": "2024-25"}],
                "streak": {"length": 4, "kind": "win"},
                "notes": None,
            },
            "meta": {"source": "warehouse:silver_hist_gamelogs"},
        },
    )
    tools = _catalogue(monkeypatch, hub=fake)

    res = _invoke(tools["get_team_hub"], {"team_id": 1610612747})

    assert res["ok"] is True
    assert [row["section"] for row in res["rows"]] == [
        "roster", "summary", "games", "awards", "streak", "notes",
    ]
    assert res["rows"][3] == {"name": "All-Star", "season": "2024-25",
                              "section": "awards"}
    assert res["rows"][4] == {"length": 4, "kind": "win", "section": "streak"}
    assert res["rows"][5] == {"value": None, "section": "notes"}
    assert res["columns"] == [*ROSTER_ROW, "section"]


def test_team_hub_empty_rows_returns_rows_array(monkeypatch):
    fake = _FakeTool(
        "Game log plus roster for one team id. Warehouse first.",
        result={
            "tool": "get_team_hub",
            "ok": True,
            "rows": {},
            "meta": {"source": "warehouse:silver_hist_gamelogs"},
        },
    )
    tools = _catalogue(monkeypatch, hub=fake)

    res = _invoke(tools["get_team_hub"], {"team_id": 1610612747})

    assert res["ok"] is True
    assert res["rows"] == []
    assert res["columns"] == TEAM_DEFAULT_COLS


def test_team_hub_upstream_error_returns_rows_array(monkeypatch):
    fake = _FakeTool(
        "Game log plus roster for one team id. Warehouse first.",
        result={"tool": "get_team_hub", "ok": False, "error": "unknown team"},
    )
    tools = _catalogue(monkeypatch, hub=fake)

    res = _invoke(tools["get_team_hub"], {"team_id": 1610612747})

    assert res["ok"] is False
    assert res["rows"] == []
    assert res["columns"] == TEAM_DEFAULT_COLS
    assert res["error"] == "unknown team"


def test_both_tools_are_registered_with_anchorable_names(monkeypatch):
    tools = _catalogue(monkeypatch)

    assert "get_player_report" in tools
    assert "get_team_hub" in tools
    for name in ("get_player_report", "get_team_hub"):
        schema = tools[name].args_schema.model_json_schema()
        assert schema["properties"]
