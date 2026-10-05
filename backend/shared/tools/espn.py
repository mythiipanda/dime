import json
import os
import subprocess
from typing import Any
from langchain_core.tools import tool

_CLI = os.path.expanduser("~/.local/bin/espn-pp-cli")
_BIN_DIR = os.path.expanduser("~/.local/bin")
_TIMEOUT = 30

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


def _run(args: list[str]) -> Any:
    try:
        proc = subprocess.run(
            [_CLI, *args, "--agent"],
            capture_output=True,
            text=True,
            timeout=_TIMEOUT,
            env=_env(),
        )
    except FileNotFoundError:
        return "espn-pp-cli unavailable: binary not found at ~/.local/bin/espn-pp-cli"
    except subprocess.TimeoutExpired:
        return "espn-pp-cli unavailable: request timed out after 30s"
    except Exception as e:
        return f"espn-pp-cli unavailable: {type(e).__name__}"
    try:
        data = json.loads(proc.stdout)
    except Exception:
        return "espn-pp-cli unavailable: could not read scores service response"
    if proc.returncode != 0 and isinstance(data, dict) and data.get("results", {}).get("error"):
        return f"espn-pp-cli unavailable: {data['results']['error']}"[:160]
    return data


def _resolve(sport: str) -> Any:
    key = sport.strip().lower()
    if key not in _PAIRS:
        return (
            "espn-pp-cli unavailable: unknown sport "
            f"'{sport.strip()}' (try nfl, nba, mlb, nhl)"
        )
    return _PAIRS[key]


@tool(description="Today's live scores and results for a sport. Pass sport as nfl, nba, mlb, or nhl. Returns each game with teams, score, status, and event id.")
def get_espn_scores(sport: str) -> Any:
    pair = _resolve(sport)
    if isinstance(pair, str):
        return pair
    data = _run(["scores", pair[0], pair[1]])
    if isinstance(data, str):
        return data
    return {
        "tool": "get_espn_scores",
        "ok": True,
        "rows": data,
        "meta": {"sport": sport.strip().lower(), "source": "espn"},
    }


@tool(description="Detailed recap for one game by ESPN event id: final score, box score, stat leaders, scoring plays, and win probability. Get the event id from get_espn_scores first.")
def get_espn_event_summary(event_id: str) -> Any:
    eid = event_id.strip()
    last_error = f"espn-pp-cli unavailable: no summary found for event {eid}"
    for s, l in _PROBE_ORDER:
        data = _run(["summary", s, l, "--event", eid])
        if isinstance(data, str):
            if "binary not found" in data or "timed out" in data:
                return data
            last_error = data
            continue
        if isinstance(data, dict) and isinstance(data.get("results"), dict):
            if data["results"].get("error"):
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
        return f"espn-pp-cli unavailable: no summary found for event {eid}"
    return last_error


@tool(description="Current spread, total, and moneyline lines for a sport's slate, as pricing context for breaking down matchups. Analysis only, never betting advice. Pass sport as nfl, nba, mlb, or nhl.")
def get_espn_odds(sport: str) -> Any:
    pair = _resolve(sport)
    if isinstance(pair, str):
        return pair
    data = _run(["odds", pair[0], pair[1]])
    if isinstance(data, str):
        return data
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
