import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import shared.tools.espn as espn_mod
from shared.tools import TOOL_NAMES, v1_tools

_REAL_RESOLVE_CLI_PATH = espn_mod._resolve_cli_path


@pytest.fixture(autouse=True)
def _pinned_cli_version(monkeypatch, tmp_path):
    monkeypatch.setattr(
        espn_mod, "cli_version_info",
        lambda *args, **kwargs: ("fake-cli", espn_mod.EXPECTED_CLI_VERSION))
    if "ESPN_CLI_PATH" not in os.environ:
        fake = tmp_path / "espn-pp-cli"
        fake.write_bytes(b"#!/bin/sh\nexit 0\n")
        fake.chmod(0o755)
        monkeypatch.setattr(
            espn_mod, "_resolve_cli_path", lambda: str(fake))


def _pinned_version(monkeypatch):
    pass


def test_version_mismatch_fails_loud(monkeypatch):
    monkeypatch.setattr(
        espn_mod, "cli_version_info", lambda *args, **kwargs: ("fake-cli", "0.0.0"))
    out = espn_mod.get_espn_scores.invoke({"sport": "nfl"})
    assert out["ok"] is False
    assert out["reason"] == "version_mismatch"


def test_unreadable_version_fails_loud(monkeypatch):
    monkeypatch.setattr(
        espn_mod, "cli_version_info", lambda *args, **kwargs: ("fake-cli", None))
    out = espn_mod.get_espn_scores.invoke({"sport": "nfl"})
    assert out["ok"] is False
    assert out["reason"] == "version_mismatch"


def test_failure_dicts_carry_machine_reason(monkeypatch):
    _pinned_version(monkeypatch)
    out = espn_mod.get_espn_scores.invoke({"sport": "quidditch"})
    assert out["ok"] is False
    assert out["reason"] == "unknown_sport"


SCORES_FIXTURE = [
    {
        "id": "401872964",
        "matchup": "PIT @ CLE",
        "away_team": "PIT",
        "away_score": "24",
        "home_team": "CLE",
        "home_score": "27",
        "status": "post",
        "detail": "Final",
    },
    {
        "id": "401872965",
        "matchup": "IND VS WSH",
        "away_team": "IND",
        "away_score": "0",
        "home_team": "WSH",
        "home_score": "0",
        "status": "pre",
        "detail": "Sun, October 4th at 9:30 AM EDT",
    },
]

ODDS_FIXTURE = [
    {
        "event_id": "401872965",
        "matchup": "IND VS WSH",
        "spread": "IND -3.5",
        "over_under": "48.5",
        "away_moneyline": "",
        "home_moneyline": "",
    },
    {
        "event_id": "401872971",
        "matchup": "NE @ BUF",
        "spread": "BUF -7",
        "over_under": "48.5",
        "away_moneyline": "",
        "home_moneyline": "",
    },
]

SUMMARY_FIXTURE = {
    "meta": {"source": "live"},
    "results": {
        "header": {"competitions": [{"status": {"type": {"shortDetail": "Final"}}}]},
        "boxscore": {"players": [{"statistics": [{"athletes": [{"athlete": {"displayName": "Aaron Rodgers"}}]}]}]},
        "leaders": [{"leaders": [{"displayName": "Passing Yards"}]}],
        "scoringPlays": [],
        "winprobability": [],
        "odds": [],
    },
}

ERROR_SUMMARY_FIXTURE = {
    "meta": {"source": "local"},
    "results": {"error": "sport is required"},
}


class _Completed:
    def __init__(self, stdout, returncode=0, stderr=""):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


def _run_json(payload, calls=None):
    def _fake(*args, **kwargs):
        if calls is not None:
            calls.append(args[0])
        return _Completed(json.dumps(payload))
    return _fake


def test_scores_returns_fixture_games(monkeypatch):
    monkeypatch.setattr(subprocess, "run", _run_json(SCORES_FIXTURE))
    out = espn_mod.get_espn_scores.invoke({"sport": "nfl"})
    assert out["ok"] is True
    matchups = [g["matchup"] for g in out["rows"]]
    assert "PIT @ CLE" in matchups
    assert "IND VS WSH" in matchups


def test_scores_unknown_sport_is_typed_error():
    out = espn_mod.get_espn_scores.invoke({"sport": "quidditch"})
    assert out["ok"] is False
    assert out["tool"] == "get_espn_scores"
    assert "unknown_sport" in out["error"]


def test_scores_bad_json_is_typed_error(monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _Completed("not json{{{"))
    out = espn_mod.get_espn_scores.invoke({"sport": "nfl"})
    assert out["ok"] is False
    assert "bad_response" in out["error"]


def test_scores_timeout_is_typed_error(monkeypatch):
    def _boom(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=args[0], timeout=30)
    monkeypatch.setattr(subprocess, "run", _boom)
    out = espn_mod.get_espn_scores.invoke({"sport": "nfl"})
    assert out["ok"] is False
    assert "timeout" in out["error"]


def test_scores_missing_binary_is_typed_error(monkeypatch):
    def _boom(*args, **kwargs):
        raise FileNotFoundError("no such file")
    monkeypatch.setattr(subprocess, "run", _boom)
    out = espn_mod.get_espn_scores.invoke({"sport": "nfl"})
    assert out["ok"] is False
    assert "binary_not_found" in out["error"]


def test_summary_returns_boxscore_and_leaders(monkeypatch):
    monkeypatch.setattr(subprocess, "run", _run_json(SUMMARY_FIXTURE))
    out = espn_mod.get_espn_event_summary.invoke({"event_id": "401872964"})
    assert out["ok"] is True
    assert "boxscore" in out["rows"]
    assert "leaders" in out["rows"]


def test_summary_skips_wrong_league_pair(monkeypatch):
    calls = []
    responses = iter([ERROR_SUMMARY_FIXTURE, SUMMARY_FIXTURE])

    def _fake(*args, **kwargs):
        calls.append(args[0])
        return _Completed(json.dumps(next(responses)))
    monkeypatch.setattr(subprocess, "run", _fake)
    out = espn_mod.get_espn_event_summary.invoke({"event_id": "401872964"})
    assert out["ok"] is True
    assert len(calls) == 2


def test_summary_timeout_is_typed_error(monkeypatch):
    def _boom(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=args[0], timeout=30)
    monkeypatch.setattr(subprocess, "run", _boom)
    out = espn_mod.get_espn_event_summary.invoke({"event_id": "401872964"})
    assert out["ok"] is False
    assert "timeout" in out["error"]


def test_odds_returns_lines(monkeypatch):
    out = espn_mod.get_espn_odds.invoke({"sport": "nfl"})
    assert out["ok"] is False
    assert "disabled_pending_stance" in out["error"]


def test_odds_bad_json_is_typed_error(monkeypatch):
    out = espn_mod.get_espn_odds.invoke({"sport": "nba"})
    assert out["ok"] is False
    assert "disabled_pending_stance" in out["error"]


def test_v1_tools_includes_espn_names():
    for name in ("get_espn_scores", "get_espn_event_summary", "get_espn_odds"):
        assert name in TOOL_NAMES
        assert name in [t.name for t in v1_tools]


def test_cli_path_env_override_is_honored(monkeypatch, tmp_path):
    import shared.tools.espn as espn
    monkeypatch.setenv("ESPN_CLI_PATH", str(tmp_path / "no-such-binary"))
    monkeypatch.setattr(espn, "_resolve_cli_path", _REAL_RESOLVE_CLI_PATH)
    out = espn.get_espn_scores.invoke({"sport": "nfl"})
    assert out["ok"] is False
    assert "binary_not_found" in out["error"]
    assert "no-such-binary" in out["error"]


def test_cli_version_pin_matches_adopted_release():
    import os
    import shutil
    import shared.tools.espn as espn
    present = shutil.which("espn-pp-cli") is not None or os.path.exists(
        os.path.expanduser("~/.local/bin/espn-pp-cli"))
    if not present:
        import pytest
        pytest.skip("espn-pp-cli not installed")
    assert espn.cli_version_info()[1] == espn.EXPECTED_CLI_VERSION


def test_vendored_blob_matches_pinned_checksum_and_version(tmp_path):
    import hashlib
    import shutil
    import shared.tools.espn as espn
    blob = Path(__file__).resolve().parent.parent / "bin" / "espn-pp-cli"
    assert blob.is_file()
    digest = hashlib.sha256(blob.read_bytes()).hexdigest()
    assert digest == espn.EXPECTED_CLI_SHA256
    exe = tmp_path / "espn-pp-cli"
    shutil.copyfile(blob, exe)
    exe.chmod(0o755)
    proc = subprocess.run(
        [str(exe), "--version"],
        capture_output=True, text=True, timeout=30)
    assert proc.returncode == 0
    assert proc.stdout.strip().rsplit(None, 1)[-1] == espn.EXPECTED_CLI_VERSION


def test_summary_aggregates_all_probe_errors(monkeypatch):
    import shared.tools.espn as espn

    def _fail(*args, **kwargs):
        return _Completed(json.dumps(
            {"meta": {"source": "local"},
             "results": {"error": "no event " + args[0][3]}}))

    monkeypatch.setattr(subprocess, "run", _fail)
    out = espn.get_espn_event_summary.invoke({"event_id": "000000000"})
    assert out["ok"] is False
    for league in ("nfl", "nba", "mlb", "nhl"):
        assert league in out["error"]


def test_summary_probe_timeouts_shrink_within_budget(monkeypatch):
    import shared.tools.espn as espn
    import time as time_mod

    seen = []
    clock = {"now": 1000.0}

    def _fake(*args, **kwargs):
        seen.append(kwargs.get("timeout"))
        clock["now"] += 25.0
        return _Completed(json.dumps(
            {"meta": {"source": "local"}, "results": {"error": "gone"}}))

    monkeypatch.setattr(subprocess, "run", _fake)
    monkeypatch.setattr(time_mod, "monotonic", lambda: clock["now"])
    out = espn.get_espn_event_summary.invoke({"event_id": "000000000"})
    assert out["ok"] is False
    assert all(t is not None and t <= 60 for t in seen)
    assert seen == sorted(seen, reverse=True)


def test_odds_quarantined_pending_stance(monkeypatch):
    import shared.tools.espn as espn
    calls = []
    monkeypatch.setattr(subprocess, "run", _run_json(ODDS_FIXTURE, calls))
    out = espn.get_espn_odds.invoke({"sport": "nfl"})
    assert out["ok"] is False
    assert "disabled_pending_stance" in out["error"]
    assert calls == []
