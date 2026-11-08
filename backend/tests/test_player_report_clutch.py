import copy
import socket
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest


@pytest.fixture()
def clutch_seams(monkeypatch):
    attempts = {"network": 0}

    def _blocked(*_args, **_kwargs):
        attempts["network"] += 1
        raise RuntimeError("network access blocked in clutch regression test")

    monkeypatch.setattr(socket.socket, "connect", _blocked)
    monkeypatch.setattr(socket, "create_connection", _blocked)
    monkeypatch.setattr(socket, "getaddrinfo", _blocked)

    from shared.tools import league, player

    season_line = {"PLAYER_ID": 2544, "PLAYER": "LeBron James", "GP": 71,
                   "PPG": 24.0, "RPG": 7.1, "APG": 8.3, "TS_PCT": .617}
    clutch_row = {"PLAYER_ID": 2544, "PLAYER_NAME": "LeBron James",
                  "GP": 20, "W": 12, "L": 8, "PTS": 88,
                  "FG_PCT": .52, "FG3_PCT": .38, "PLUS_MINUS": 34}

    class StubTool:
        def __init__(self, payload):
            self.payload = payload

        def invoke(self, _args):
            return copy.deepcopy(self.payload)

    def _coerce(value):
        text = str(value).strip().lower()
        if text.isdigit():
            return int(text)
        if text == "lebron james":
            return 2544
        raise ValueError(f"unknown player: {value}")

    monkeypatch.setattr(player, "resolve_season", lambda s: s or "2025-26")
    monkeypatch.setattr(player, "last_completed_season", lambda: "2025-26")
    monkeypatch.setattr(player, "coerce_player_id", _coerce)
    monkeypatch.setattr(player, "get_season_averages",
                        StubTool({"ok": True, "rows": [season_line]}))
    monkeypatch.setattr(player, "get_advanced",
                        StubTool({"ok": True, "rows": {"TS_PCT": 61.7, "USG_PCT": 30.1,
                                                        "PIE": .205, "NET_RATING": 7.0}}))
    monkeypatch.setattr(player, "get_shot_zones",
                        StubTool({"ok": True, "rows": []}))
    monkeypatch.setattr(league, "resolve_season", lambda s: s or "2025-26")
    monkeypatch.setattr(league, "_warehouse_or_live",
                        lambda *_a, **_k: ([dict(clutch_row)], {"source": "stub"}))
    monkeypatch.setattr(league, "_derive_hist_clutch",
                        lambda *_a, **_k: ([dict(clutch_row)], {"source": "stub"}))
    return attempts


@pytest.mark.parametrize("player_arg", [2544, "2544", "LeBron James"])
def test_report_clutch_filter_matches_by_line_name(clutch_seams, player_arg):
    from shared.tools import get_player_report
    out = get_player_report.invoke({"player": player_arg, "season": "2025-26"})
    assert out["ok"] is True
    clutch = out["rows"]["clutch"]
    assert clutch is not None
    assert clutch["PLAYER_NAME"] == "LeBron James"
    assert clutch["PTS"] == 88
    assert "Clutch:" in out["meta"]["deterministic_answer"]
    assert clutch_seams["network"] == 0


def test_report_clutch_answer_equivalent_across_player_forms(clutch_seams):
    from shared.tools import get_player_report
    int_out = get_player_report.invoke({"player": 2544, "season": "2025-26"})
    str_out = get_player_report.invoke({"player": "2544", "season": "2025-26"})
    name_out = get_player_report.invoke({"player": "LeBron James", "season": "2025-26"})
    assert int_out["meta"]["deterministic_answer"] == str_out["meta"]["deterministic_answer"]
    assert int_out["meta"]["deterministic_answer"] == name_out["meta"]["deterministic_answer"]
    assert int_out["rows"]["clutch"] == str_out["rows"]["clutch"] == name_out["rows"]["clutch"]
    assert clutch_seams["network"] == 0


def test_historical_report_skips_clutch_lookup(clutch_seams, monkeypatch):
    from shared.tools import league

    def _no_call(*_args, **_kwargs):
        raise AssertionError("get_clutch must not run for historical seasons")

    monkeypatch.setattr(league, "get_clutch", type("NoCall", (), {"invoke": staticmethod(_no_call)})())
    from shared.tools import get_player_report
    out = get_player_report.invoke({"player": "LeBron James", "season": "2023-24"})
    assert out["ok"] is True
    assert out["rows"]["clutch"] is None
    assert "Clutch:" not in out["meta"]["deterministic_answer"]
    assert clutch_seams["network"] == 0
