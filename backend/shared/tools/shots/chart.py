import sys
from typing import Any

from langchain_core.tools import tool


def _pkg():
    return sys.modules[__package__]


_REGION_SQL = "SHOT_ZONE_BASIC || '|' || SHOT_ZONE_AREA"

_COLUMNS = ["zone", "label", "x", "y", "att", "makes", "pct", "league_pct", "delta_pp"]


def _region_clause(region: str) -> str:
    basic, _, area = region.partition("|")
    if area.startswith("Left"):
        return "L"
    if area.startswith("Right"):
        return "R"
    return "C"


_TEAM_STATIC: dict[str, list] = {"loaded": False}


def _static_teams() -> list:
    if not _TEAM_STATIC["loaded"]:
        try:
            from nba_api.stats.static import teams as _st
            for t in _st.get_teams():
                _TEAM_STATIC[int(t["id"])] = (str(t["abbreviation"]), str(t["full_name"]))
        except Exception:
            pass
        _TEAM_STATIC["loaded"] = True
    return [k for k in _TEAM_STATIC if isinstance(k, int)]


def _team_ids(con: Any, season: str, raw: str) -> tuple[list[int], str | None]:
    text = (raw or "").strip()
    if not text:
        return [], None
    pkg = _pkg()
    ids = _static_teams()
    up = text.upper()
    low = text.lower()
    rows = _pkg()._qrows(
        con,
        f"SELECT DISTINCT TEAM_ID, TEAM_NAME FROM {_pkg().TABLE} WHERE _season = ?",
        [season],
    )
    ware_ids = [int(r["TEAM_ID"]) for r in rows]
    ware_names = {int(r["TEAM_ID"]): str(r["TEAM_NAME"] or "") for r in rows}
    by_abbr = {
        tid: pkg._team_abbr(tid) for tid in set(ids) | set(ware_ids)
    }
    exact_abbr = [tid for tid, ab in by_abbr.items() if ab == up]
    if exact_abbr:
        return sorted(exact_abbr), None
    name_of = {tid: (info[1] if (info := _TEAM_STATIC.get(tid)) else ware_names.get(tid, ""))
               for tid in by_abbr}
    exact_name = [tid for tid, nm in name_of.items() if nm.lower() == low]
    if exact_name:
        return sorted(exact_name), None
    partial = [tid for tid, nm in name_of.items() if low in nm.lower()]
    if len(partial) == 1:
        return [int(partial[0])], None
    if partial:
        names = sorted({name_of[tid] for tid in partial})
        return [], f"ambiguous team {text!r}: {', '.join(names)}"
    return [], f"unknown team {text!r}"


def _zones_for(con: Any, where: str, params: list[object]) -> dict[str, dict[str, Any]]:
    zone_case = _pkg()._zone_case_sql()
    rows = _pkg()._qrows(
        con,
        f"""SELECT {_REGION_SQL} AS region,
                   {zone_case} AS zone,
                   AVG(LOC_X) / 10.0 AS cx,
                   AVG(LOC_Y) / 10.0 AS cy,
                   COUNT(*) AS att,
                   SUM(CASE WHEN SHOT_MADE_FLAG = '1' THEN 1 ELSE 0 END) AS makes
            FROM {_pkg().TABLE}
            WHERE {where} AND {_REGION_SQL} IS NOT NULL
            GROUP BY 1, 2""",
        params,
    )
    out: dict[str, dict[str, Any]] = {}
    for r in rows:
        att = int(r["att"] or 0)
        if att <= 0:
            continue
        makes = int(r["makes"] or 0)
        out[r["region"]] = {
            "zone": r["zone"],
            "x": round(float(r["cx"] or 0), 1),
            "y": round(float(r["cy"] or 0), 1),
            "att": att,
            "makes": makes,
            "pct": round(100.0 * makes / att, 1),
        }
    return out


@tool(
    description='Half-court shot chart data from the warehouse silver shots table for one\nplayer or one team: per-region attempt counts, makes, FG% and the\nleague-average FG% delta for the same season, plus court-center\ncoordinates ready for the shot_chart artifact. Supply player or team\n(name or abbreviation). season is the _season label (e.g. "2025-26").\nplayoffs restricts to playoff games (regular season otherwise).\nopponent restricts to games vs that team (name or abbreviation).\nRegions split by shot zone and court side; each row carries x/y in\nfeet, att, makes, pct, league_pct and delta_pp. Always pair this tool\nwith the shot_chart artifact, passing these zones through with\nprovenance, and keep full names in the title.'
)
def get_shot_chart(
    player: str = "",
    team: str = "",
    season: str | None = None,
    playoffs: bool = False,
    opponent: str = "",
) -> dict[str, Any]:
    pkg = _pkg()
    if (player and team) or (not player and not team):
        return {
            "tool": "get_shot_chart", "ok": False,
            "error": "supply exactly one of player or team",
        }
    try:
        season = pkg.clamp_season(pkg.resolve_season(season))
    except Exception as exc:
        return {"tool": "get_shot_chart", "ok": False, "error": str(exc)}
    shot_seasons = pkg._shots_seasons()
    if season not in shot_seasons:
        covered = ", ".join(shot_seasons) or "no season on hand"
        return {
            "tool": "get_shot_chart", "ok": False,
            "error": f"warehouse silver_shots covers {covered}; requested {season!r}",
        }
    try:
        con = pkg._warehouse_conn()
    except Exception as exc:
        return {"tool": "get_shot_chart", "ok": False, "error": f"warehouse unavailable: {exc}"}
    try:
        player_id = None
        team_ids: list[int] = []
        scope_name = ""
        clauses = ["_season = ?"]
        params: list[object] = [season]
        clauses.append(
            "substr(GAME_ID, 1, 3) = ?"
        )
        params.append("004" if playoffs else "002")
        if player:
            player_id, status, payload = pkg._resolve_player(con, season, player)
            if status != "ok":
                return {
                    "tool": "get_shot_chart", "ok": False,
                    "error": f"player lookup failed ({status}): {payload}",
                }
            clauses.append("PLAYER_ID = ?")
            params.append(player_id)
            scope_name = pkg._player_full_name(player_id) or player
        else:
            team_ids, err = _team_ids(con, season, team)
            if err:
                return {"tool": "get_shot_chart", "ok": False, "error": err}
            in_list = ", ".join("?" for _ in team_ids)
            clauses.append(f"TEAM_ID IN ({in_list})")
            params.extend(team_ids)
            scope_name = pkg._team_abbr(team_ids[0]) or team
        opp_abbr = None
        opp_abbrs: list[str] = []
        opp_ids: list[int] = []
        if opponent.strip():
            opp_ids, err = _team_ids(con, season, opponent)
            if err:
                return {"tool": "get_shot_chart", "ok": False, "error": err}
            opp_abbrs = sorted({pkg._team_abbr(t) for t in opp_ids if pkg._team_abbr(t)})
            if not opp_abbrs:
                return {
                    "tool": "get_shot_chart", "ok": False,
                    "error": f"opponent {opponent!r} has no abbreviation mapping",
                }
            if team_ids:
                own_abbrs = [pkg._team_abbr(t) for t in team_ids if pkg._team_abbr(t)]
            else:
                own_abbrs = [
                    pkg._team_abbr(r["TEAM_ID"])
                    for r in _pkg()._qrows(
                        con,
                        f"SELECT DISTINCT TEAM_ID FROM {_pkg().TABLE} "
                        f"WHERE _season = ? AND PLAYER_ID = ?",
                        [season, player_id],
                    )
                    if pkg._team_abbr(r["TEAM_ID"])
                ]
            keep = [a for a in opp_abbrs if a not in own_abbrs]
            if not keep:
                return {
                    "tool": "get_shot_chart", "ok": True,
                    "scope": {"player" if player else "team": scope_name},
                    "season": season, "playoffs": playoffs,
                    "opponent": opp_abbrs[0], "zones": [], "rows": [], "columns": _COLUMNS,
                    "meta": {"source": f"warehouse {_pkg().TABLE}", "season": season},
                    "note": "opponent matches the subject's team; no opposing shots",
                }
            opp_abbr = keep[0]
            ph = ", ".join("?" for _ in keep)
            clauses.append(f"(HTM IN ({ph}) OR VTM IN ({ph}))")
            params.extend(keep)
            params.extend(keep)
        where = " AND ".join(clauses)
        zones = _zones_for(con, where, params)
        league_clauses = ["_season = ?", "substr(GAME_ID, 1, 3) = ?"]
        league_params: list[object] = [season, "004" if playoffs else "002"]
        if opponent.strip():
            opp_abbrs2 = sorted({pkg._team_abbr(t) for t in opp_ids if pkg._team_abbr(t)})
            ph = ", ".join("?" for _ in opp_abbrs2)
            league_clauses.append(f"(HTM IN ({ph}) OR VTM IN ({ph}))")
            league_params.extend(opp_abbrs2)
            league_params.extend(opp_abbrs2)
        league_where = " AND ".join(league_clauses)
        league = _zones_for(con, league_where, league_params)
        if not zones:
            return {
                "tool": "get_shot_chart", "ok": True,
                "scope": {"player" if player else "team": scope_name},
                "season": season, "playoffs": playoffs,
                "opponent": opp_abbr, "zones": [], "rows": [], "columns": _COLUMNS,
                "meta": {"source": f"warehouse {_pkg().TABLE}", "season": season},
                "note": "no shots matched the filters",
            }
        out = []
        for region, z in sorted(zones.items(), key=lambda kv: -kv[1]["att"]):
            lg = league.get(region)
            league_pct = round(lg["pct"], 1) if lg else None
            out.append({
                **z,
                "label": f"{z['zone']}-{_region_clause(region)}",
                "league_pct": league_pct,
                "delta_pp": round(z["pct"] - league_pct, 1) if league_pct is not None else None,
            })
        max_fetched = _pkg()._qrows(
            con, f"SELECT MAX(_fetched_at) AS m FROM {_pkg().TABLE} WHERE {where}", params
        )[0].get("m")
        return {
            "tool": "get_shot_chart", "ok": True,
            "scope": {"player" if player else "team": scope_name},
            "season": season, "playoffs": playoffs, "opponent": opp_abbr,
            "zones": out, "rows": out, "columns": _COLUMNS,
            "meta": {
                "source": f"warehouse {_pkg().TABLE}", "season": season,
                "as_of": str(max_fetched) if max_fetched else None,
                "shots_scanned": sum(z["att"] for z in zones.values()),
                "sql": (
                    f"SELECT {_REGION_SQL}, ... FROM {_pkg().TABLE} "
                    f"WHERE {where} GROUP BY 1, 2"
                ),
                "league_baseline": "same-season league FG% per region",
            },
        }
    finally:
        try:
            con.close()
        except Exception:
            pass
