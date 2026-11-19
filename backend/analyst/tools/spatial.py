from typing import Any

from langchain_core.tools import tool

from .common import (
    call_async_in_sync,
    call_sync,
    finish_dict_list,
    finish_strict_rows,
)


def _shot_compare_rows(res: dict[str, Any]) -> list[dict[str, Any]]:
    raw_rows = res.get("rows")
    raw_list: list[dict[str, Any]] = []
    if isinstance(raw_rows, list):
        raw_list = [r for r in raw_rows if isinstance(r, dict)]
    elif isinstance(raw_rows, dict):
        nested = raw_rows.get("rows")
        raw_list = [r for r in nested if isinstance(r, dict)] if isinstance(nested, list) else [raw_rows]
    return [
        {
            "zone": r.get("zone"),
            "a_eFG": r.get("a_eFG"),
            "b_eFG": r.get("b_eFG"),
            "a_fg": r.get("a_fg"),
            "b_fg": r.get("b_fg"),
            "a_share": r.get("a_share"),
            "b_share": r.get("b_share"),
            "edge": r.get("edge"),
        }
        for r in raw_list
    ]


def _zone_deltas_rows(res: dict[str, Any]) -> list[dict[str, Any]]:
    raw_rows = res.get("rows")
    raw_list: list[dict[str, Any]] = []
    if isinstance(raw_rows, dict):
        for key in ("zones", "deltas", "rows"):
            if isinstance(raw_rows.get(key), list):
                raw_list = [r for r in raw_rows[key] if isinstance(r, dict)]
                break
        else:
            raw_list = [raw_rows]
    elif isinstance(raw_rows, list):
        raw_list = [r for r in raw_rows if isinstance(r, dict)]
    elif isinstance(res.get("deltas"), list):
        raw_list = [r for r in res["deltas"] if isinstance(r, dict)]
    elif isinstance(res.get("zones"), list):
        raw_list = [r for r in res["zones"] if isinstance(r, dict)]
    return [
        {
            "zone": r.get("zone"),
            "attempts": r.get("attempts"),
            "makes": r.get("makes"),
            "fg_pct": r.get("fg_pct"),
            "league_fg_pct": r.get("league_fg_pct"),
            "delta_pp": r.get("delta_pp"),
            "league_attempts": r.get("league_attempts"),
        }
        for r in raw_list
    ]


def _clock_part(r: dict[str, Any], idx: int) -> Any:
    parts = str(r.get("clock") or "").split(":")
    if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
        return parts[idx]
    return None


def _shot_row(r: dict[str, Any]) -> dict[str, Any]:
    min_rem = r.get("minutes_remaining")
    if min_rem is None:
        min_rem = r.get("MINUTES_REMAINING")
    if min_rem is None:
        min_rem = _clock_part(r, 0)
    sec_rem = r.get("seconds_remaining")
    if sec_rem is None:
        sec_rem = r.get("SECONDS_REMAINING")
    if sec_rem is None:
        sec_rem = _clock_part(r, 1)
    made = r.get("made")
    if made is None:
        made = str(r.get("SHOT_MADE_FLAG") or "").strip() == "1"
    return {
        "game_id": r.get("game_id") if r.get("game_id") is not None else r.get("GAME_ID"),
        "player_name": r.get("player") if r.get("player") is not None else (r.get("player_name") or r.get("PLAYER_NAME")),
        "period": r.get("period") if r.get("period") is not None else r.get("PERIOD"),
        "minutes_remaining": min_rem,
        "seconds_remaining": sec_rem,
        "shot_distance": r.get("distance_ft") if r.get("distance_ft") is not None else (r.get("shot_distance") or r.get("SHOT_DISTANCE")),
        "zone": r.get("zone"),
        "made": made,
    }


def _search_shots_rows(res: dict[str, Any]) -> list[dict[str, Any]]:
    raw_list: list[dict[str, Any]] = []
    if isinstance(res.get("shots"), list):
        raw_list = [r for r in res["shots"] if isinstance(r, dict)]
    elif isinstance(res.get("rows"), list):
        raw_list = [r for r in res["rows"] if isinstance(r, dict)]
    return [_shot_row(r) for r in raw_list]


def _team_shot_zone_row(r: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "team", "team_id", "shots",
        "rim_share", "rim_efg", "rim_share_delta_pp", "rim_efg_delta_pp",
        "short_mid_share", "short_mid_efg", "short_mid_share_delta_pp", "short_mid_efg_delta_pp",
        "long_mid_share", "long_mid_efg", "long_mid_share_delta_pp", "long_mid_efg_delta_pp",
        "corner_3_share", "corner_3_efg", "corner_3_share_delta_pp", "corner_3_efg_delta_pp",
        "atb_3_share", "atb_3_efg", "atb_3_share_delta_pp", "atb_3_efg_delta_pp",
    )
    return {k: r.get(k) for k in keys}


def _team_shot_zones_rows(res: dict[str, Any]) -> list[dict[str, Any]]:
    raw_rows = res.get("rows")
    raw_list = [r for r in raw_rows if isinstance(r, dict)] if isinstance(raw_rows, list) else []
    return [_team_shot_zone_row(r) for r in raw_list]


def register() -> dict[str, Any]:
    from shared.tools.player import get_shot_zones as _orig_get_shot_zones
    try:
        from shared.tools.player import get_shot_compare as _orig_get_shot_compare
    except ImportError:
        from backend.shared.tools.player import get_shot_compare as _orig_get_shot_compare
    try:
        from shared.tools.zonedelta import get_zone_deltas as _orig_get_zone_deltas
    except ImportError:
        from backend.shared.tools.zonedelta import get_zone_deltas as _orig_get_zone_deltas
    try:
        from shared.tools.shots import search_shots as _orig_search_shots
    except ImportError:
        from backend.shared.tools.shots import search_shots as _orig_search_shots
    try:
        from shared.tools.zone import get_team_shot_zones as _orig_get_team_shot_zones
    except ImportError:
        from backend.shared.tools.zone import get_team_shot_zones as _orig_get_team_shot_zones

    @tool("get_shot_zones", description=_orig_get_shot_zones.description)
    def get_shot_zones(player_id: str | int, season: str | None = None, min_attempts: int = 50) -> dict:
        res = call_sync(_orig_get_shot_zones, "get_shot_zones", {
            "player_id": player_id, "season": season, "min_attempts": min_attempts,
        })
        return finish_dict_list(res, "get_shot_zones", ["zone", "attempts", "makes", "fg_pct", "share_pct"], set_ok=False)

    @tool("get_shot_compare", description=_orig_get_shot_compare.description)
    def get_shot_compare(a: str = "", b: str = "", season: str | None = None) -> dict:
        cols = ["zone", "a_eFG", "b_eFG", "a_fg", "b_fg", "a_share", "b_share", "edge"]
        res = call_async_in_sync(_orig_get_shot_compare, "get_shot_compare", {"a": a, "b": b, "season": season})
        return finish_strict_rows(res, "get_shot_compare", cols, "Shot compare lookup failed", _shot_compare_rows, fixed_cols=True)

    @tool("get_zone_deltas", description=_orig_get_zone_deltas.description)
    def get_zone_deltas(player: str, season: int | str = 2025, min_attempts: int = 50) -> dict:
        cols = ["zone", "attempts", "makes", "fg_pct", "league_fg_pct", "delta_pp", "league_attempts"]
        res = call_sync(_orig_get_zone_deltas, "get_zone_deltas", {
            "player": player, "season": season, "min_attempts": min_attempts,
        })
        return finish_strict_rows(res, "get_zone_deltas", cols, "Zone deltas lookup failed", _zone_deltas_rows, fixed_cols=True)

    @tool("search_shots", description=_orig_search_shots.description)
    def search_shots(
        player: str = "", team: str = "", zones: str = "", periods: str = "",
        three_only: bool = False, made: str = "any", late_clock: str = "",
        exclude_heaves: bool = True, limit: int = 25, season: str | None = None,
        group_by: str = "", include_ot: str = "auto",
    ) -> dict:
        cols = ["game_id", "player_name", "period", "minutes_remaining", "seconds_remaining", "shot_distance", "zone", "made"]
        res = call_sync(_orig_search_shots, "search_shots", {
            "player": player, "team": team, "zones": zones, "periods": periods,
            "three_only": three_only, "made": made, "late_clock": late_clock,
            "exclude_heaves": exclude_heaves, "limit": limit, "season": season,
            "group_by": group_by, "include_ot": include_ot,
        })
        return finish_strict_rows(res, "search_shots", cols, "Shot search failed", _search_shots_rows, fixed_cols=True)

    @tool("get_team_shot_zones", description=_orig_get_team_shot_zones.description)
    def get_team_shot_zones(teams: str = "league", season: str | None = None) -> dict:
        cols = [
            "team", "team_id", "shots",
            "rim_share", "rim_efg", "rim_share_delta_pp", "rim_efg_delta_pp",
            "short_mid_share", "short_mid_efg", "short_mid_share_delta_pp", "short_mid_efg_delta_pp",
            "long_mid_share", "long_mid_efg", "long_mid_share_delta_pp", "long_mid_efg_delta_pp",
            "corner_3_share", "corner_3_efg", "corner_3_share_delta_pp", "corner_3_efg_delta_pp",
            "atb_3_share", "atb_3_efg", "atb_3_share_delta_pp", "atb_3_efg_delta_pp",
        ]
        res = call_sync(_orig_get_team_shot_zones, "get_team_shot_zones", {"teams": teams, "season": season})
        return finish_strict_rows(res, "get_team_shot_zones", cols, "Team shot zones query failed", _team_shot_zones_rows, fixed_cols=True)

    return {
        "get_shot_zones": get_shot_zones,
        "get_shot_compare": get_shot_compare,
        "get_zone_deltas": get_zone_deltas,
        "search_shots": search_shots,
        "get_team_shot_zones": get_team_shot_zones,
    }
