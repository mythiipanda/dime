from typing import Any

from langchain_core.tools import tool

from ..league._helpers import _owned_connection, _pkg

_ZONE_CASE = (
    "CASE"
    " WHEN shot_value = 3 AND ABS(x_legacy) >= 220 AND y_legacy <= 92.5 THEN 'corner_3'"
    " WHEN shot_value = 3 THEN 'atb_3'"
    " WHEN shot_value = 2 AND shot_distance <= 4 THEN 'rim'"
    " WHEN shot_value = 2 AND ABS(x_legacy) <= 80 AND y_legacy <= 140 THEN 'short_mid'"
    " WHEN shot_value = 2 THEN 'long_mid'"
    " ELSE 'other' END"
)

_VALID_ZONES = ("rim", "short_mid", "long_mid", "corner_3", "atb_3")


@tool(description=(
    "League-wide shot-zone leaderboard for one season: every qualifying "
    "player's attempts, makes, FG% and share of total FGA in one zone "
    "(rim, short_mid, long_mid, corner_3, atb_3), regular season only, "
    "sorted by zone attempts. Use for any who-leads-the-league or "
    "rank-the-pool ask about shot diet, corner threes, above-the-break "
    "volume, rim rate/finishing or midrange volume - one call instead of "
    "per-player get_shot_zones loops or hand-written coordinate math. "
    "zone: one of rim|short_mid|long_mid|corner_3|atb_3. min_attempts "
    "floors ZONE attempts (default 40). position: '' or C/G/F/PG/SG/SF/PF/C-F "
    "etc as listed in boxscores. Covers every season in silver_hist_shots "
    "including 2024-25 and 2025-26. Rim = within 4 feet; corner_3 = "
    "|x|>=220in, y<=92.5in; atb_3 = all other threes; short_mid = paint "
    "outside 4ft; long_mid = all other twos."))
def get_shot_zone_leaders(
    zone: str = "", season: str | None = None, min_attempts: int = 40,
    position: str = "", limit: int = 25,
) -> dict[str, Any]:
    pkg = _pkg()
    season = pkg.resolve_season(season)
    z = str(zone or "").strip().lower()
    if z not in _VALID_ZONES:
        return {"tool": "get_shot_zone_leaders", "ok": False, "rows": [],
                "error": (f"unknown zone '{zone}'; valid zones: "
                          + ", ".join(_VALID_ZONES)),
                "supported": list(_VALID_ZONES)}
    pos = str(position or "").strip().upper()
    try:
        min_att = max(1, int(min_attempts or 40))
    except (TypeError, ValueError):
        min_att = 40
    try:
        lim = max(1, min(200, int(limit or 25)))
    except (TypeError, ValueError):
        lim = 25
    pos_join = ""
    params: list[Any] = [season]
    if pos:
        pos_join = (" JOIN (SELECT DISTINCT PLAYER_ID FROM silver_boxscores"
                    " WHERE _season = ? AND UPPER(position) = ?) bp"
                    " ON bp.PLAYER_ID = z.person_id")
        params.append(season)
        params.append(pos)
    sql = (
        "WITH z AS ("
        " SELECT person_id, player_name, team_tricode, shot_result,"
        f" {_ZONE_CASE} AS zone"
        " FROM silver_hist_shots"
        " WHERE _season = ? AND shot_value IN (2, 3)"
        " AND (season_type_id = 2 OR SUBSTR(game_id, 1, 3) = '002')"
        ")"
        " SELECT z.person_id, z.player_name,"
        " MODE(z.team_tricode) AS team,"
        " COUNT(*) FILTER (z.zone = ?) AS att,"
        " COUNT(*) FILTER (z.zone = ? AND z.shot_result = 'Made') AS makes,"
        " COUNT(*) AS total_fga"
        f" FROM z{pos_join}"
        " GROUP BY z.person_id, z.player_name"
        " HAVING COUNT(*) FILTER (z.zone = ?) >= ?"
        " ORDER BY att DESC"
        " LIMIT ?"
    )
    params = params[:1] + [z, z] + params[1:] + [z, min_att, lim]
    try:
        with _owned_connection(None, read_only=True) as con:
            rows_raw = con.execute(sql, params).fetchall()
    except Exception as exc:
        return {"tool": "get_shot_zone_leaders", "ok": False, "rows": [],
                "error": f"zone leaderboard query failed: {exc}"}
    if not rows_raw:
        with _owned_connection(None, read_only=True) as con:
            avail = [str(r[0]) for r in con.execute(
                "SELECT DISTINCT _season FROM silver_hist_shots ORDER BY 1").fetchall()]
        return {"tool": "get_shot_zone_leaders", "ok": False, "rows": [],
                "error": (f"no regular-season shot rows for season '{season}'"
                          + (f" with position filter '{pos}'" if pos else "")
                          + "; seasons present in silver_hist_shots: "
                          + ", ".join(avail))}
    rows = []
    for pid, name, team, att, makes, total in rows_raw:
        att = int(att or 0)
        makes = int(makes or 0)
        total = int(total or 0)
        rows.append({
            "player_id": int(pid), "player": name, "team": team,
            "att": att, "makes": makes,
            "fg_pct": round(makes / att, 3) if att else None,
            "total_fga": total,
            "zone_share": round(att / total, 3) if total else None,
        })
    return {"tool": "get_shot_zone_leaders", "ok": True, "rows": rows,
            "columns": ["player_id", "player", "team", "att", "makes",
                        "fg_pct", "total_fga", "zone_share"],
            "meta": {"source": "warehouse:silver_hist_shots",
                     "season": season, "zone": z, "scope": "regular season",
                     "min_attempts": min_att,
                     "position_filter": pos or None,
                     "zone_definitions": ("rim <=4ft; corner_3 |x|>=220in "
                                          "y<=92.5in; atb_3 other threes; "
                                          "short_mid paint beyond 4ft; "
                                          "long_mid other twos")}}
