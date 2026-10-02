
from typing import Any

from langchain_core.tools import tool

from .. import store
from ..sources import nba_stats
from ._core import coerce_player_id, coerce_team_id

_TRACKING_TABLE = "silver_tracking_pt_stats"
_DEFEND_TABLE = "silver_tracking_pt_defend"
_DEFEND_ENTITY = "ptdefend:Overall"
_DEFAULT_SEASON = "2025-26"

_PLAYER_IDENTITY = (
    "PLAYER_ID",
    "PLAYER_NAME",
    "TEAM_ID",
    "TEAM_ABBREVIATION",
    "TEAM_NAME",
    "GP",
    "W",
    "L",
    "MIN",
)

_TEAM_IDENTITY = (
    "TEAM_ID",
    "TEAM_ABBREVIATION",
    "TEAM_NAME",
    "GP",
    "W",
    "L",
    "MIN",
)

_MEASURE_COLUMNS: dict[str, tuple[str, ...]] = {
    "CatchShoot": (
        "CATCH_SHOOT_FGM", "CATCH_SHOOT_FGA", "CATCH_SHOOT_FG_PCT",
        "CATCH_SHOOT_PTS", "CATCH_SHOOT_FG3M", "CATCH_SHOOT_FG3A",
        "CATCH_SHOOT_FG3_PCT", "CATCH_SHOOT_EFG_PCT",
    ),
    "Defense": (
        "STL", "BLK", "DREB",
        "DEF_RIM_FGM", "DEF_RIM_FGA", "DEF_RIM_FG_PCT",
    ),
    "Drives": (
        "DRIVES",
        "DRIVE_FGM", "DRIVE_FGA", "DRIVE_FG_PCT",
        "DRIVE_FTM", "DRIVE_FTA", "DRIVE_FT_PCT",
        "DRIVE_PTS", "DRIVE_PTS_PCT",
        "DRIVE_PASSES", "DRIVE_PASSES_PCT",
        "DRIVE_AST", "DRIVE_AST_PCT",
        "DRIVE_TOV", "DRIVE_TOV_PCT",
        "DRIVE_PF", "DRIVE_PF_PCT",
    ),
    "Efficiency": ("EFF_FG_PCT", "POINTS"),
    "ElbowTouch": (
        "ELBOW_TOUCHES",
        "ELBOW_TOUCH_FGM", "ELBOW_TOUCH_FGA",
        "ELBOW_TOUCH_FTM", "ELBOW_TOUCH_FTA", "ELBOW_TOUCH_FT_PCT",
        "ELBOW_TOUCH_PTS", "ELBOW_TOUCH_FG_PCT", "ELBOW_TOUCH_PTS_PCT",
        "ELBOW_TOUCH_PASSES", "ELBOW_TOUCH_PASSES_PCT",
        "ELBOW_TOUCH_AST", "ELBOW_TOUCH_AST_PCT",
        "ELBOW_TOUCH_TOV", "ELBOW_TOUCH_TOV_PCT",
        "ELBOW_TOUCH_FOULS", "ELBOW_TOUCH_FOULS_PCT",
        "PTS_PER_ELBOW_TOUCH",
    ),
    "PaintTouch": (
        "PAINT_TOUCHES",
        "PAINT_TOUCH_FGM", "PAINT_TOUCH_FGA",
        "PAINT_TOUCH_FTM", "PAINT_TOUCH_FTA", "PAINT_TOUCH_FT_PCT",
        "PAINT_TOUCH_PTS", "PAINT_TOUCH_FG_PCT", "PAINT_TOUCH_PTS_PCT",
        "PAINT_TOUCH_PASSES", "PAINT_TOUCH_PASSES_PCT",
        "PAINT_TOUCH_AST", "PAINT_TOUCH_AST_PCT",
        "PAINT_TOUCH_TOV", "PAINT_TOUCH_TOV_PCT",
        "PAINT_TOUCH_FOULS", "PAINT_TOUCH_FOULS_PCT",
        "PTS_PER_PAINT_TOUCH",
    ),
    "Passing": (
        "PASSES_MADE", "PASSES_RECEIVED", "AST", "FT_AST",
        "SECONDARY_AST", "POTENTIAL_AST", "AST_PTS_CREATED", "AST_ADJ",
        "AST_TO_PASS_PCT", "AST_TO_PASS_PCT_ADJ", "FRONT_CT_TOUCHES",
    ),
    "Possessions": (
        "TOUCHES", "TIME_OF_POSS", "AVG_SEC_PER_TOUCH",
        "AVG_DRIB_PER_TOUCH", "PTS_PER_TOUCH", "FRONT_CT_TOUCHES",
    ),
    "PostTouch": (
        "POST_TOUCHES",
        "POST_TOUCH_FGM", "POST_TOUCH_FGA",
        "POST_TOUCH_FTM", "POST_TOUCH_FTA", "POST_TOUCH_FT_PCT",
        "POST_TOUCH_PTS", "POST_TOUCH_FG_PCT", "POST_TOUCH_PTS_PCT",
        "POST_TOUCH_PASSES", "POST_TOUCH_PASSES_PCT",
        "POST_TOUCH_AST", "POST_TOUCH_AST_PCT",
        "POST_TOUCH_TOV", "POST_TOUCH_TOV_PCT",
        "POST_TOUCH_FOULS", "POST_TOUCH_FOULS_PCT",
        "PTS_PER_POST_TOUCH",
    ),
    "PullUpShot": (
        "PULL_UP_FGM", "PULL_UP_FGA",
        "PULL_UP_FG3M", "PULL_UP_FG3A", "PULL_UP_FG3_PCT",
        "PULL_UP_PTS", "PULL_UP_FG_PCT", "PULL_UP_EFG_PCT",
    ),
    "Rebounding": (
        "OREB",
        "OREB_CONTEST", "OREB_UNCONTEST", "OREB_CONTEST_PCT",
        "OREB_CHANCES", "OREB_CHANCE_PCT",
        "OREB_CHANCE_DEFER", "OREB_CHANCE_PCT_ADJ", "AVG_OREB_DIST",
        "DREB",
        "DREB_CONTEST", "DREB_UNCONTEST", "DREB_CONTEST_PCT",
        "DREB_CHANCES", "DREB_CHANCE_PCT",
        "DREB_CHANCE_DEFER", "DREB_CHANCE_PCT_ADJ", "AVG_DREB_DIST",
        "REB",
        "REB_CONTEST", "REB_UNCONTEST", "REB_CONTEST_PCT",
        "REB_CHANCES", "REB_CHANCE_PCT",
        "REB_CHANCE_DEFER", "REB_CHANCE_PCT_ADJ", "AVG_REB_DIST",
    ),
    "SpeedDistance": (
        "DIST_FEET", "DIST_MILES", "DIST_MILES_OFF", "DIST_MILES_DEF",
        "AVG_SPEED", "AVG_SPEED_OFF", "AVG_SPEED_DEF",
    ),
}

_DEFEND_IDENTITY = (
    "CLOSE_DEF_PERSON_ID",
    "PLAYER_NAME",
    "PLAYER_LAST_TEAM_ABBREVIATION",
)

_DEFEND_COLUMNS = (
    "GP",
    "FREQ",
    "D_FGM",
    "D_FGA",
    "D_FG_PCT",
    "NORMAL_FG_PCT",
    "PCT_PLUSMINUS",
)


def _season_or_default(season: object) -> str:
    text = "" if season is None else str(season).strip()
    return text or _DEFAULT_SEASON


def _valid_measures() -> tuple[str, ...]:
    return tuple(nba_stats.PT_MEASURE_TYPES)


def _canonical_measure(raw: object) -> str | None:
    text = "" if raw is None else str(raw).strip()
    if not text:
        return ""
    lowered = text.lower()
    for name in _valid_measures():
        if name.lower() == lowered:
            return name
    return None


def _as_int(value: object) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _no_coverage(tool: str, table: str, season: str) -> dict[str, Any]:
    from v2.adapters.coverage import table_seasons

    available = sorted(table_seasons(table))
    if available:
        asked = (
            f"Tracking data for the {season} season is not available. "
            f"Available seasons: {', '.join(available)}. "
            "Which season should be used instead?"
        )
    else:
        asked = (
            f"Tracking data for the {season} season is not available. "
            "No seasons are on hand for tracking data right now. "
            "Which season should be used instead?"
        )
    return {"tool": tool, "ok": False, "rows": [], "error": asked,
            "meta": {"source": f"warehouse:{table}", "season": season,
                     "available_seasons": available,
                     "deterministic_answer": asked}}


def _curated(row: dict[str, Any], identity: tuple[str, ...],
             family: tuple[str, ...]) -> dict[str, Any]:
    return {col: row.get(col) for col in (*identity, *family) if col in row}


def _resolve_name(pid: int, fallback: str) -> str:
    from .splits import _resolve_name as _name

    return _name(pid, fallback)


@tool
def get_tracking_profile(player: str = "", team: str = "",
                         season: str = "2025-26",
                         measure_type: str = "") -> dict[str, Any]:
    """Player or team tracking profile: drives, shooting, touches, rebounding, speed."""
    season = _season_or_default(season)
    want_player = str(player or "").strip()
    want_team = str(team or "").strip()
    if bool(want_player) == bool(want_team):
        return {"tool": "get_tracking_profile", "ok": False, "rows": [],
                "error": "Give exactly one of player or team, not both and not neither.",
                "meta": {"source": f"warehouse:{_TRACKING_TABLE}",
                         "season": season}}
    measure = _canonical_measure(measure_type)
    if measure is None:
        valid = ", ".join(_valid_measures())
        return {"tool": "get_tracking_profile", "ok": False, "rows": [],
                "error": f"Unknown measure_type {str(measure_type).strip()!r}. "
                         f"Use one of: {valid}.",
                "meta": {"source": f"warehouse:{_TRACKING_TABLE}",
                         "season": season}}
    measures = [measure] if measure else list(_valid_measures())
    scope = "player" if want_player else "team"
    try:
        pid = coerce_player_id(want_player) if want_player else None
    except ValueError:
        return {"tool": "get_tracking_profile", "ok": False, "rows": [],
                "error": f"unknown player: {want_player}",
                "meta": {"source": f"warehouse:{_TRACKING_TABLE}",
                         "season": season}}
    try:
        tid = coerce_team_id(want_team) if want_team else None
    except ValueError:
        return {"tool": "get_tracking_profile", "ok": False, "rows": [],
                "error": f"unknown team: {want_team}",
                "meta": {"source": f"warehouse:{_TRACKING_TABLE}",
                         "season": season}}
    from v2.adapters.coverage import table_seasons

    if season not in table_seasons(_TRACKING_TABLE):
        return _no_coverage("get_tracking_profile", _TRACKING_TABLE, season)
    rows: list[dict[str, Any]] = []
    identity = _PLAYER_IDENTITY if scope == "player" else _TEAM_IDENTITY
    for kind in measures:
        entity = f"ptstats:{scope}:{kind}"
        frame = store.read_frame(
            _TRACKING_TABLE, "_season = ? AND _entity = ?",
            [season, entity])
        if frame is None or frame.height == 0:
            continue
        for raw in frame.to_dicts():
            if scope == "player":
                if _as_int(raw.get("PLAYER_ID")) != pid:
                    continue
            else:
                same_id = _as_int(raw.get("TEAM_ID")) == tid
                same_abbr = (str(raw.get("TEAM_ABBREVIATION") or "").strip().upper()
                             == want_team.upper())
                if not (same_id or same_abbr):
                    continue
            slim = _curated(raw, identity, _MEASURE_COLUMNS[kind])
            slim["measure_type"] = kind
            rows.append(slim)
    if not rows:
        subject = want_player or want_team
        label = measure if measure else "tracking"
        return {"tool": "get_tracking_profile", "ok": False, "rows": [],
                "error": f"No {label} tracking rows for {subject} in {season}.",
                "meta": {"source": f"warehouse:{_TRACKING_TABLE}",
                         "season": season, "scope": scope}}
    if scope == "player" and pid is not None:
        display = _resolve_name(
            pid, str(rows[0].get("PLAYER_NAME") or want_player))
    else:
        display = str(rows[0].get("TEAM_ABBREVIATION") or want_team)
    return {"tool": "get_tracking_profile", "ok": True, "rows": rows,
            "meta": {"source": f"warehouse:{_TRACKING_TABLE}",
                     "season": season, "scope": scope,
                     "subject": display,
                     "measures": sorted({r["measure_type"] for r in rows}),
                     "coverage": "Player and team tracking by measure type "
                                 "for seasons on file; a season outside "
                                 "coverage is reported, never swapped.",
                     **store.warehouse_identity()}}


@tool
def get_defensive_matchups(player: str = "",
                           season: str = "2025-26") -> dict[str, Any]:
    """One defender's defended-shot profile: frequency and shooter results."""
    season = _season_or_default(season)
    want = str(player or "").strip()
    if not want:
        return {"tool": "get_defensive_matchups", "ok": False, "rows": [],
                "error": "Give a player name for defensive matchups.",
                "meta": {"source": f"warehouse:{_DEFEND_TABLE}",
                         "season": season}}
    try:
        pid = coerce_player_id(want)
    except ValueError:
        return {"tool": "get_defensive_matchups", "ok": False, "rows": [],
                "error": f"unknown player: {want}",
                "meta": {"source": f"warehouse:{_DEFEND_TABLE}",
                         "season": season}}
    from v2.adapters.coverage import table_seasons

    if season not in table_seasons(_DEFEND_TABLE):
        return _no_coverage("get_defensive_matchups", _DEFEND_TABLE, season)
    frame = store.read_frame(
        _DEFEND_TABLE, "_season = ? AND _entity = ?",
        [season, _DEFEND_ENTITY])
    rows: list[dict[str, Any]] = []
    if frame is not None and frame.height > 0:
        for raw in frame.to_dicts():
            if _as_int(raw.get("CLOSE_DEF_PERSON_ID")) != pid:
                continue
            rows.append(_curated(raw, _DEFEND_IDENTITY, _DEFEND_COLUMNS))
    if not rows:
        return {"tool": "get_defensive_matchups", "ok": False, "rows": [],
                "error": f"No defended-shot rows for {want} in {season}.",
                "meta": {"source": f"warehouse:{_DEFEND_TABLE}",
                         "season": season}}
    display = _resolve_name(
        pid, str(rows[0].get("PLAYER_NAME") or want))
    return {"tool": "get_defensive_matchups", "ok": True, "rows": rows,
            "meta": {"source": f"warehouse:{_DEFEND_TABLE}",
                     "season": season, "player": display,
                     "coverage": "Per-defender defended shots: how often "
                                 "he was the closest defender and how "
                                 "those shots fell. No per-opponent rows "
                                 "exist, so none are shown.",
                     **store.warehouse_identity()}}
