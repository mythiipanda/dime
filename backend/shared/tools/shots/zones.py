import sys
from typing import Any


def _pkg():
    return sys.modules[__package__]


TABLE = "silver_shots"

ZONE_KEYS = ("rim", "short_mid", "long_mid", "corner_3", "atb_3")
THREE_ZONES = frozenset({"corner_3", "atb_3"})

ZONE_LABEL_MAP = {
    "Restricted Area": "rim",
    "In The Paint (Non-RA)": "short_mid",
    "Mid-Range": "long_mid",
    "Left Corner 3": "corner_3",
    "Right Corner 3": "corner_3",
    "Above the Break 3": "atb_3",
}

ZONE_LEGEND = {
    "rim": "Restricted Area",
    "short_mid": "In The Paint (Non-RA)",
    "long_mid": "Mid-Range",
    "corner_3": "Left/Right Corner 3",
    "atb_3": "Above the Break 3",
}

_PERIOD_TOKEN_MAP = {
    "1": {1},
    "2": {2},
    "3": {3},
    "4": {4},
    "4th": {4},
    "ot": {5},
    "1h": {1, 2},
    "2h": {3, 4},
}

_MADE_VALUES = ("made", "missed", "any")
_GROUP_BY_VALUES = ("", "player", "team")

SMALL_SAMPLE_MIN = 10

_TEAM_ABBR_BY_ID: dict[int, str] = {}
_PLAYER_NAME_BY_ID: dict[int, str] = {}
_STATIC_LOADED = {"teams": False, "players": False}


def _shots_seasons() -> list[str]:
    try:
        con = _pkg()._store.connect(read_only=True)
        try:
            rows = con.execute("SELECT DISTINCT _season FROM silver_shots").fetchall()
        finally:
            try:
                con.close()
            except Exception:
                pass
    except Exception:
        return []
    return sorted(r[0] for r in rows if r and r[0])


def _team_abbr(team_id: object) -> str | None:
    try:
        tid = int(team_id)
    except (TypeError, ValueError):
        return None
    if tid in _TEAM_ABBR_BY_ID:
        return _TEAM_ABBR_BY_ID[tid]
    if _STATIC_LOADED["teams"]:
        return None
    try:
        from nba_api.stats.static import teams as _static_teams

        for t in _static_teams.get_teams():
            try:
                _TEAM_ABBR_BY_ID[int(t["id"])] = str(t["abbreviation"])
            except (TypeError, ValueError, KeyError):
                continue
    except Exception:
        return None
    finally:
        _STATIC_LOADED["teams"] = True
    return _TEAM_ABBR_BY_ID.get(tid)


def _player_full_name(player_id: object) -> str | None:
    try:
        pid = int(player_id)
    except (TypeError, ValueError):
        return None
    if pid in _PLAYER_NAME_BY_ID:
        return _PLAYER_NAME_BY_ID[pid]
    if _STATIC_LOADED["players"]:
        return None
    try:
        from nba_api.stats.static import players as _static_players

        for p in _static_players.get_players():
            try:
                _PLAYER_NAME_BY_ID[int(p["id"])] = str(p["full_name"])
            except (TypeError, ValueError, KeyError):
                continue
    except Exception:
        return None
    finally:
        _STATIC_LOADED["players"] = True
    return _PLAYER_NAME_BY_ID.get(pid)


def zone_of_label(label: object) -> str | None:
    if label is None:
        return None
    return ZONE_LABEL_MAP.get(str(label).strip())


def parse_zones(raw: str) -> set[str]:
    token = (raw or "").strip().lower()
    if not token:
        return set(ZONE_KEYS)
    out: set[str] = set()
    for piece in token.split(","):
        piece = piece.strip()
        if not piece:
            continue
        if piece not in ZONE_KEYS:
            raise ValueError(
                f"unknown zone {piece!r}; valid zones: {', '.join(ZONE_KEYS)}"
            )
        out.add(piece)
    if not out:
        return set(ZONE_KEYS)
    return out


def parse_periods(raw: str) -> set[int] | None:
    token = (raw or "").strip().lower()
    if not token:
        return None
    out: set[int] = set()
    for piece in token.split(","):
        piece = piece.strip()
        if not piece:
            continue
        if piece not in _PERIOD_TOKEN_MAP:
            raise ValueError(
                f"unknown period {piece!r}; valid tokens: 1-4, ot, 1h, 2h, 4th"
            )
        out |= _PERIOD_TOKEN_MAP[piece]
    if not out:
        return None
    return out


def period_matches(period: object, allowed: set[int] | None) -> bool:
    if allowed is None:
        return True
    try:
        p = int(period)
    except (TypeError, ValueError):
        return False
    if p >= 5:
        return 5 in allowed
    return p in allowed


def parse_made(raw: str) -> str:
    value = (raw or "").strip().lower()
    if value not in _MADE_VALUES:
        raise ValueError(
            f"invalid made filter {raw!r}; use one of: made, missed, any"
        )
    return value


def parse_late_clock(raw: str) -> int | None:
    token = (raw or "").strip()
    if not token:
        return None
    try:
        seconds = int(token)
    except (TypeError, ValueError):
        raise ValueError(
            f"invalid late_clock {raw!r}; pass integer seconds remaining "
            f"(e.g. '30'), or empty for no clock filter"
        )
    if seconds < 0 or seconds > 720:
        raise ValueError(
            f"invalid late_clock {raw!r}; seconds must be 0-720"
        )
    return seconds


def parse_group_by(raw: str) -> str:
    value = (raw or "").strip().lower()
    if value in _GROUP_BY_VALUES:
        return value
    raise ValueError(
        f"invalid group_by {raw!r}; use one of: player, team (or empty for none)"
    )


def parse_include_ot(raw: str, default: bool) -> bool:
    token = (raw or "").strip().lower()
    if token in ("", "auto"):
        return default
    if token in ("yes", "true", "1", "y"):
        return True
    if token in ("no", "false", "0", "n"):
        return False
    raise ValueError(f"invalid include_ot {raw!r}; use auto, yes, or no")


def fold_ot(periods: set[int] | None, include_ot: bool) -> set[int] | None:
    if periods is None or not include_ot:
        return periods
    return set(periods) | {5}


def seconds_left(
    minutes_remaining: object, seconds_remaining: object
) -> int | None:
    try:
        total = int(minutes_remaining) * 60 + int(seconds_remaining)
    except (TypeError, ValueError):
        return None
    return total if total >= 0 else None


def is_heave(
    distance_ft: object, minutes_remaining: object, seconds_remaining: object
) -> bool:
    try:
        far = float(distance_ft) >= 30.0
    except (TypeError, ValueError):
        return False
    left = seconds_left(minutes_remaining, seconds_remaining)
    return bool(far and left is not None and left <= 3)


def format_clock(minutes_remaining: object, seconds_remaining: object) -> str:
    left = seconds_left(minutes_remaining, seconds_remaining)
    if left is None:
        return "unknown"
    return f"{left // 60}:{left % 60:02d}"


def efficiency(
    attempts: int, makes: int, threes_made: int
) -> dict[str, float]:
    if attempts <= 0:
        return {"fg_pct": 0.0, "efg_pct": 0.0}
    return {
        "fg_pct": round(makes / attempts, 4),
        "efg_pct": round((makes + 0.5 * threes_made) / attempts, 4),
    }


def summarize(shots: list[dict[str, Any]]) -> dict[str, Any]:
    attempts = len(shots)
    makes = sum(1 for s in shots if s.get("made"))
    threes = sum(
        1 for s in shots if s.get("made") and s.get("zone") in THREE_ZONES
    )
    games = len({s.get("game_id") for s in shots if s.get("game_id") is not None})
    return {
        "attempts": attempts,
        "makes": makes,
        "threes_made": threes,
        "games": games,
        **efficiency(attempts, makes, threes),
    }


def summarize_by_zone(shots: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for key in ZONE_KEYS:
        group = [s for s in shots if s.get("zone") == key]
        makes = sum(1 for s in group if s.get("made"))
        threes = sum(1 for s in group if s.get("made") and key in THREE_ZONES)
        out.append(
            {
                "zone": key,
                "attempts": len(group),
                "makes": makes,
                **efficiency(len(group), makes, threes),
            }
        )
    return out


def summarize_by_period(shots: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[Any, list[dict[str, Any]]] = {}
    for s in shots:
        try:
            p = int(s.get("period"))
        except (TypeError, ValueError):
            continue
        buckets.setdefault("OT" if p >= 5 else p, []).append(s)
    order = [1, 2, 3, 4, "OT"]
    out = []
    for key in order:
        group = buckets.get(key, [])
        if not group:
            continue
        makes = sum(1 for s in group if s.get("made"))
        threes = sum(
            1 for s in group if s.get("made") and s.get("zone") in THREE_ZONES
        )
        out.append(
            {
                "period": key,
                "attempts": len(group),
                "makes": makes,
                **efficiency(len(group), makes, threes),
            }
        )
    return out


def group_row(
    attempts: int, makes: int, threes_made: int, games: int = 0
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "attempts": attempts,
        "makes": makes,
        "threes_made": threes_made,
        "points": 2 * makes + threes_made,
        **efficiency(attempts, makes, threes_made),
        "small_sample": attempts < SMALL_SAMPLE_MIN,
    }
    if games:
        row["games"] = games
    return row


def disambiguate_last_name(
    raw: str, pairs: list[tuple[Any, Any]]
) -> dict[str, Any]:
    key = (raw or "").strip().lower()
    hits: dict[int, str] = {}
    for name, pid in pairs:
        text = str(name or "").strip().lower()
        surname = text.rsplit(" ", 1)[-1] if text else ""
        if text != key and surname != key:
            continue
        try:
            pid_int = int(pid)
        except (TypeError, ValueError):
            continue
        hits.setdefault(pid_int, str(name))
    candidates = [
        {"player": hits[pid], "player_id": pid} for pid in sorted(hits)
    ]
    if len(hits) == 1:
        return {
            "player_id": next(iter(hits)),
            "candidates": candidates,
            "ambiguous": False,
        }
    return {
        "player_id": None,
        "candidates": candidates,
        "ambiguous": len(hits) > 1,
    }
