import json
import os
import subprocess
from typing import Any
from langchain_core.tools import tool

_DEFAULT_CLI = os.path.expanduser("~/.local/bin/espn-pp-cli")
_BIN_DIR = os.path.expanduser("~/.local/bin")
_TIMEOUT = 30
EXPECTED_CLI_VERSION = "2026.9.2"

_PAIRS = {
    "nfl": ("football", "nfl"),
    "nba": ("basketball", "nba"),
    "mlb": ("baseball", "mlb"),
    "nhl": ("hockey", "nhl"),
    "wnba": ("basketball", "wnba"),
    "ncaaf": ("football", "college-football"),
    "ncaab": ("basketball", "mens-college-basketball"),
    "mls": ("soccer", "mls"),
    "epl": ("soccer", "eng.1"),
}

_PROBE_ORDER = (
    ("football", "nfl"),
    ("basketball", "nba"),
    ("baseball", "mlb"),
    ("hockey", "nhl"),
)


def _env() -> dict[str, str]:
    env = dict(os.environ)
    path = env.get("PATH", "")
    parts = path.split(os.pathsep) if path else []
    if _BIN_DIR not in parts:
        env["PATH"] = _BIN_DIR + os.pathsep + path if path else _BIN_DIR
    return env


class EspnUnavailable(Exception):
    def __init__(self, reason: str, detail: str = "") -> None:
        self.reason = reason
        message = f"espn-pp-cli unavailable: {reason}"
        if detail:
            message += f": {detail[:120]}"
        super().__init__(message)


def _resolve_cli_path() -> str:
    return os.environ.get("ESPN_CLI_PATH", _DEFAULT_CLI)


def cli_version_info() -> tuple[str, str | None]:
    path = _resolve_cli_path()
    try:
        proc = subprocess.run(
            [path, "--version"],
            capture_output=True, text=True, timeout=10, env=_env(),
        )
    except Exception:
        return path, None
    first = (proc.stdout or "").strip().splitlines()
    if not first or proc.returncode != 0:
        return path, None
    parts = first[0].strip().rsplit(None, 1)
    version = parts[-1] if len(parts) == 2 else None
    return path, version


def _run(args: list[str]) -> Any:
    cli = _resolve_cli_path()
    if not (os.path.isfile(cli) and os.access(cli, os.X_OK)):
        raise EspnUnavailable("binary_not_found", cli)
    try:
        proc = subprocess.run(
            [cli, *args, "--agent"],
            capture_output=True,
            text=True,
            timeout=_TIMEOUT,
            env=_env(),
        )
    except FileNotFoundError:
        raise EspnUnavailable("binary_not_found", cli)
    except subprocess.TimeoutExpired:
        raise EspnUnavailable("timeout", f"{_TIMEOUT}s")
    except Exception as exc:
        raise EspnUnavailable(type(exc).__name__, str(exc))
    try:
        data = json.loads(proc.stdout)
    except Exception:
        raise EspnUnavailable("bad_response", "unparseable scores service response")
    if proc.returncode != 0 and isinstance(data, dict) and data.get("results", {}).get("error"):
        raise EspnUnavailable("service_error", str(data["results"]["error"]))
    return data


def _resolve(sport: str) -> Any:
    key = sport.strip().lower()
    if key not in _PAIRS:
        raise EspnUnavailable(
            "unknown_sport", f"{sport.strip()!r} (try nfl, nba, mlb, nhl)")
    return _PAIRS[key]


def _failure(tool: str, exc: EspnUnavailable) -> dict[str, Any]:
    return {"tool": tool, "ok": False, "error": str(exc)}


@tool(description="Today's live scores and results for a sport. Pass sport as nfl, nba, mlb, or nhl. Returns each game with teams, score, status, and event id.")
def get_espn_scores(sport: str) -> Any:
    try:
        pair = _resolve(sport)
        data = _run(["scores", pair[0], pair[1]])
    except EspnUnavailable as exc:
        return _failure("get_espn_scores", exc)
    return {
        "tool": "get_espn_scores",
        "ok": True,
        "rows": data,
        "meta": {"sport": sport.strip().lower(), "source": "espn"},
    }


@tool(description="Detailed recap for one game by ESPN event id: final score, box score, stat leaders, scoring plays, and win probability. Get the event id from get_espn_scores first.")
def get_espn_event_summary(event_id: str) -> Any:
    eid = event_id.strip()
    last_error: EspnUnavailable | None = None
    for s, l in _PROBE_ORDER:
        try:
            data = _run(["summary", s, l, "--event", eid])
        except EspnUnavailable as exc:
            if exc.reason in ("binary_not_found", "timeout"):
                return _failure("get_espn_event_summary", exc)
            last_error = exc
            continue
        if isinstance(data, dict) and isinstance(data.get("results"), dict):
            if data["results"].get("error"):
                last_error = EspnUnavailable(
                    "service_error", str(data["results"]["error"]))
                continue
            return {
                "tool": "get_espn_event_summary",
                "ok": True,
                "rows": data["results"],
                "meta": {
                    "event_id": eid,
                    "sport": s,
                    "league": l,
                    "source": "espn",
                },
            }
        last_error = EspnUnavailable("no_summary", f"no summary for event {eid}")
    if last_error is not None:
        return _failure("get_espn_event_summary", last_error)
    return {"tool": "get_espn_event_summary", "ok": False,
            "error": f"espn-pp-cli unavailable: no_summary: no summary found for event {eid}"}


@tool(description="Current spread, total, and moneyline lines for a sport's slate, as pricing context for breaking down matchups. Analysis only, never betting advice. Pass sport as nfl, nba, mlb, or nhl.")
def get_espn_odds(sport: str) -> Any:
    try:
        pair = _resolve(sport)
        data = _run(["odds", pair[0], pair[1]])
    except EspnUnavailable as exc:
        return _failure("get_espn_odds", exc)
    return {
        "tool": "get_espn_odds",
        "ok": True,
        "rows": data,
        "meta": {
            "sport": sport.strip().lower(),
            "source": "espn",
            "analysis_only": True,
        },
    }
