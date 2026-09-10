"""Regression: _trade_sides must fold diacritics when matching names.

_detect_entities finds "Luka Dončić" from an unaccented "Doncic" query via
its accent-folding _norm, but _trade_sides re-filtered found_p against the
raw question with an accent-sensitive match and silently dropped the
player, so the triage path never saw him.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app.graph as graph_mod
from app.graph import _trade_sides
from app.tools import _core as core_mod

_PID = {"Anthony Edwards": 101, "Luka Dončić": 102, "Nikola Jokic": 103}
_TEAM_OF = {101: "MIN", 102: "LAL", 103: "DEN"}


def _stub_ids(monkeypatch):
    monkeypatch.setattr(core_mod, "coerce_player_id", lambda p: _PID[p])
    monkeypatch.setattr(graph_mod, "_player_team_abbr",
                        lambda pid, season: _TEAM_OF[pid])


def test_unaccented_query_matches_accented_name(monkeypatch):
    _stub_ids(monkeypatch)
    res = _trade_sides(
        "Who wins this trade… Edwards (MIN) for Doncic (LAL)?",
        ["Anthony Edwards", "Luka Dončić"],
        ["Minnesota Timberwolves", "Los Angeles Lakers"], "2024-25")
    assert res == {"team_a": "MIN", "players_a": "Anthony Edwards",
                   "team_b": "LAL", "players_b": "Luka Dončić"}


def test_accented_query_matches_unaccented_name(monkeypatch):
    _stub_ids(monkeypatch)
    res = _trade_sides(
        "Who wins this trade: Edwards (MIN) for Jokić (DEN)?",
        ["Anthony Edwards", "Nikola Jokic"],
        ["Minnesota Timberwolves", "Denver Nuggets"], "2024-25")
    assert res == {"team_a": "MIN", "players_a": "Anthony Edwards",
                   "team_b": "DEN", "players_b": "Nikola Jokic"}


def test_exact_match_keeps_working(monkeypatch):
    _stub_ids(monkeypatch)
    res = _trade_sides(
        "Who wins this trade: Anthony Edwards (MIN) for Luka Dončić (LAL)?",
        ["Anthony Edwards", "Luka Dončić"],
        ["Minnesota Timberwolves", "Los Angeles Lakers"], "2024-25")
    assert res == {"team_a": "MIN", "players_a": "Anthony Edwards",
                   "team_b": "LAL", "players_b": "Luka Dončić"}
