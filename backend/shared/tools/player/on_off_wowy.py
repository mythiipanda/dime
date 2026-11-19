import sys
from typing import Any

from langchain_core.tools import tool
from ...lineup_variants import SeasonType, validate_variants


def _pkg():
    return sys.modules[__package__]


def _hist_on_off_rows(pid: int, tid: int, season: str) -> list[dict[str, Any]]:
    pkg = _pkg()
    season = pkg.resolve_season(season)
    try:
        con = pkg.store.connect(read_only=True)
    except Exception:
        return []
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        if "silver_hist_possessions" not in tables:
            return []
        rows = con.execute(
            """
            WITH tp AS (
              SELECT
                CASE WHEN offense_team_id = ? THEN 'off' ELSE 'def' END
                    AS side,
                CASE WHEN (
                    offense_team_id = ? AND ? IN (off_player_1, off_player_2,
                        off_player_3, off_player_4, off_player_5)) OR (
                    defense_team_id = ? AND ? IN (def_player_1, def_player_2,
                        def_player_3, def_player_4, def_player_5))
                    THEN 'on' ELSE 'off' END AS floor,
                points,
                count_as_possession = 'true' AS isposs
              FROM silver_hist_possessions
              WHERE _season = ?
                AND (offense_team_id = ? OR defense_team_id = ?)
                AND (garbage = 0 OR garbage IS NULL)
            )
            SELECT floor,
              round(100.0 * sum(CASE WHEN side = 'off' THEN points END)
                    / nullif(sum(CASE WHEN side = 'off' AND isposs
                                 THEN 1 END), 0), 1) AS off_rtg,
              round(100.0 * sum(CASE WHEN side = 'def' THEN points END)
                    / nullif(sum(CASE WHEN side = 'def' AND isposs
                                 THEN 1 END), 0), 1) AS def_rtg,
              sum(CASE WHEN isposs THEN 1 ELSE 0 END) AS poss
            FROM tp GROUP BY floor
            """,
            [tid, tid, pid, tid, pid, season, tid, tid],
        ).fetchall()
    except Exception:
        try:
            con.close()
        except Exception:
            pass
        return []
    try:
        con.close()
    except Exception:
        pass
    by_floor = {r[0]: r for r in rows}
    on, off = by_floor.get("on"), by_floor.get("off")
    if not on or not off or not on[3] or not off[3]:
        return []

    def _net(r):
        return round((r[1] or 0) - (r[2] or 0), 1)

    out = []
    for stat, ov, fv in (
        ("Offensive Rating", on[1], off[1]),
        ("Defensive Rating", on[2], off[2]),
        ("Net Rating", _net(on), _net(off)),
    ):
        if ov is None or fv is None:
            continue
        out.append({"Stat": stat, "On": f"{ov:.1f}", "Off": f"{fv:.1f}", "On-Off": f"{ov - fv:+.1f}"})
    out.append({"Stat": "Possessions (volume)", "On": str(int(on[3])), "Off": str(int(off[3])), "On-Off": ""})
    return out


@tool(description="On and off splits for one player on one team. Possession level.")
def get_on_off(player_id: str | int, team_id: str | int, season: str | None = None) -> dict[str, Any]:
    pkg = _pkg()
    season = pkg.resolve_season(season)
    player_id = pkg.coerce_player_id(player_id)
    team_id = pkg.coerce_team_id(team_id)
    from ...sources import pbpstats

    rows, meta = pkg._warehouse_or_live(
        "silver_on_off",
        "_season = ? AND _entity = ?",
        [season, f"player:{player_id}"],
        lambda: pbpstats.on_off(player_id, team_id, season),
        season,
        entity=f"player:{player_id}",
        ttl_s=pkg.TTL_PBPSTATS,
    )
    if not rows:
        hist = pkg._hist_on_off_rows(int(player_id), int(team_id), str(season))
        if hist:
            return {
                "tool": "get_on_off",
                "ok": True,
                "rows": hist,
                "meta": {"source": "warehouse", "season": str(season), "coverage": "historical_on_off"},
            }
        return {
            "tool": "get_on_off",
            "ok": False,
            "error": (
                f"No on/off data on file for {season}; on/off "
                "splits cover 2009-10 through the current season."
            ),
        }
    return {"tool": "get_on_off", "ok": True, "rows": rows, "meta": meta}


_HIST_LINEUP_FILTER = " AND season_type = 'regular-season' AND measure_type = 'base' AND per_mode = 'totals'"


def _wowy_pair(player_a: str, player_b: str, player_ids: str) -> tuple[str, str]:
    raw_a = (player_a or "").strip()
    raw_b = (player_b or "").strip()
    if raw_a or raw_b or not player_ids:
        return raw_a, raw_b
    parts = [part.strip() for part in player_ids.split(",") if part.strip()]
    if len(parts) >= 2:
        return parts[0], parts[1]
    return (parts[0], "") if parts else (raw_a, raw_b)


def _wowy_paired_players(con, table: str, extra: str, season: str, tid: object | None, pid_a: int, pid_b: int):
    return con.execute(
        f"""
        SELECT TEAM_ID, TEAM_ABBREVIATION, COUNT(*) FROM {table}
        WHERE _season = ?{extra}
          AND GROUP_ID LIKE '%-' || ? || '-%'
          AND GROUP_ID LIKE '%-' || ? || '-%'
        GROUP BY TEAM_ID, TEAM_ABBREVIATION
        ORDER BY COUNT(*) DESC LIMIT 1
        """,
        [season, str(pid_a), str(pid_b)],
    ).fetchone()


def _wowy_shared_on_team(con, table: str, extra: str, season: str, tid: object, pid_a: int, pid_b: int):
    return con.execute(
        f"""
        SELECT COUNT(*) FROM {table}
        WHERE _season = ? AND TEAM_ID = ?{extra}
          AND GROUP_ID LIKE '%-' || ? || '-%'
          AND GROUP_ID LIKE '%-' || ? || '-%'
        """,
        [season, tid, str(pid_a), str(pid_b)],
    ).fetchone()


def _wowy_pairing(con, season: str, tid: object | None, pid_a: int, pid_b: int, season_type: SeasonType = 'regular-season') -> tuple[str, str, object | None]:
    validate_variants(season_type=season_type)
    extra = _HIST_LINEUP_FILTER.replace('regular-season', season_type)
    if tid:
        row = _wowy_shared_on_team(con, 'silver_hist_lineups', extra, season, tid, pid_a, pid_b)
        if row and row[0]:
            return 'silver_hist_lineups', extra, tid
    else:
        row = _wowy_paired_players(con, 'silver_hist_lineups', extra, season, None, pid_a, pid_b)
        if row:
            return 'silver_hist_lineups', extra, row[0]
    if tid:
        row = _wowy_shared_on_team(con, "silver_lineups", "", season, tid, pid_a, pid_b) if season_type == 'regular-season' else None
        if not row or not row[0]:
            return "silver_lineups", "", None
        return "silver_lineups", "", tid
    row = _wowy_paired_players(con, "silver_lineups", "", season, None, pid_a, pid_b) if season_type == 'regular-season' else None
    if row:
        return "silver_lineups", "", row[0]
    return "", "", None


def _wowy_split_frame(
    con, table: str, extra: str, season: str, tid: object, pid_a: int, pid_b: int, raw_a: str, raw_b: str
):
    source = table
    ratings = """
          ROUND(100.0 * SUM(PTS) / NULLIF(SUM(FGA - OREB + TOV + 0.44 * FTA), 0), 2) AS off_rating,
          ROUND(100.0 * SUM(PTS - PLUS_MINUS) / NULLIF(SUM(FGA - OREB + TOV + 0.44 * FTA), 0), 2) AS def_rating,
          ROUND(100.0 * SUM(PLUS_MINUS) / NULLIF(SUM(FGA - OREB + TOV + 0.44 * FTA), 0), 2) AS net_rating
    """
    if table == 'silver_hist_lineups':
        source = """(
            SELECT b.* EXCLUDE (off_rating, def_rating, net_rating, poss),
                   a.off_rating, a.def_rating, a.net_rating, a.poss
            FROM silver_hist_lineups b LEFT JOIN silver_hist_lineups a
              ON a.group_id = b.group_id AND a.team_id = b.team_id
             AND a._season = b._season AND a.season_type = b.season_type
             AND a.per_mode = b.per_mode AND a.measure_type = 'advanced'
        )"""
        ratings = ', '.join(
            f'ROUND(SUM({name} * poss) / NULLIF(SUM(CASE WHEN {name} IS NOT NULL THEN poss END), 0), 2) AS {name}'
            for name in ('off_rating', 'def_rating', 'net_rating')
        )
    return con.execute(
        f"""
        SELECT
          CASE
            WHEN GROUP_ID LIKE '%-' || ? || '-%' AND GROUP_ID LIKE '%-' || ? || '-%' THEN 'Both ON'
            WHEN GROUP_ID LIKE '%-' || ? || '-%' AND GROUP_ID NOT LIKE '%-' || ? || '-%' THEN ? || ' ON, ' || ? || ' OFF'
            WHEN GROUP_ID NOT LIKE '%-' || ? || '-%' AND GROUP_ID LIKE '%-' || ? || '-%' THEN ? || ' ON, ' || ? || ' OFF'
            ELSE 'Both OFF'
          END AS split,
          ROUND(SUM(MIN), 1) AS minutes,
          ROUND(SUM(FGA - OREB + TOV + 0.44 * FTA), 0) AS possessions,
          {ratings}
        FROM {source}
        WHERE TEAM_ID = ? AND _season = ?{extra}
        GROUP BY split
        ORDER BY minutes DESC
        """,
        [
            str(pid_a),
            str(pid_b),
            str(pid_a),
            str(pid_b),
            raw_a,
            raw_b,
            str(pid_a),
            str(pid_b),
            raw_b,
            raw_a,
            tid,
            season,
        ],
    ).fetchdf()


def _wowy_result(
    rows: list[dict[str, Any]], table: str, season: str, tabbr: str, raw_a: str, raw_b: str
) -> dict[str, Any]:
    both_on = next((row for row in rows if row["split"] == "Both ON"), None)
    net_rating = both_on.get("net_rating") if both_on is not None else None
    net_text = f"{net_rating:+.1f}" if net_rating is not None else "N/A"
    minutes = both_on["minutes"] if both_on else 0
    meta: dict[str, Any] = {"source": table, "season": season, "team": tabbr}
    if table != "silver_lineups":
        meta["minutes_note"] = "minutes are clock minutes from the warehouse lineup table"
    return {
        "tool": "get_wowy",
        "ok": True,
        "team": tabbr,
        "player_a": raw_a,
        "player_b": raw_b,
        "rows": rows,
        "verdict": f"{tabbr}: Both on court net rating {net_text} across {minutes} minutes.",
        "meta": meta,
    }


def _wowy_team_abbreviation(con, season: str, shared_tid: object) -> str:
    row = con.execute(
        "SELECT TEAM_ABBREVIATION FROM silver_lineups WHERE _season = ? AND TEAM_ID = ? LIMIT 1",
        [season, shared_tid],
    ).fetchone()
    if row and row[0]:
        return str(row[0])
    row = con.execute(
        "SELECT TEAM_ABBREVIATION FROM silver_hist_lineups WHERE _season = ? AND TEAM_ID = ?" + _HIST_LINEUP_FILTER + " LIMIT 1",
        [season, shared_tid],
    ).fetchone()
    return str(row[0]) if row and row[0] else str(shared_tid)


@tool(
    description="With-or-without-you (WOWY) 4-way lineup combination splits for two players.\n\nAccepts player_a and player_b by name or id, or comma-separated player_ids.\nComputes Both ON, A ON / B OFF, B ON / A OFF, and Both OFF with minutes,\noffensive rating, defensive rating, and net rating from warehouse lineups."
)
def get_wowy(
    player_a: str = "",
    player_b: str = "",
    player_ids: str = "",
    team_id: str | int = 0,
    season: str | None = None,
    season_type: SeasonType = 'regular-season',
) -> dict[str, Any]:
    pkg = _pkg()
    season = pkg.resolve_season(season)
    raw_a, raw_b = _wowy_pair(player_a, player_b, player_ids)
    pid_a = pkg.coerce_player_id(raw_a) if raw_a else 0
    pid_b = pkg.coerce_player_id(raw_b) if raw_b else 0

    if pid_a and pid_b:
        con = pkg.store.connect(read_only=True)
        try:
            tid = pkg.coerce_team_id(team_id) if team_id else None
            table, extra, shared_tid = _wowy_pairing(con, season, tid, pid_a, pid_b, season_type)
            if not shared_tid:
                if tid:
                    return {
                        "tool": "get_wowy",
                        "ok": False,
                        "error": f"{raw_a} and {raw_b} never shared the court for team {tid} in {season}.",
                    }
                return {
                    "tool": "get_wowy",
                    "ok": False,
                    "error": f"{raw_a} and {raw_b} never shared the court in {season}. WOWY needs teammates.",
                }
            tabbr = str(shared_tid) if tid else _wowy_team_abbreviation(con, season, shared_tid)
            frame = _wowy_split_frame(con, table, extra, season, shared_tid, pid_a, pid_b, raw_a, raw_b)
            if len(frame) > 0:
                return _wowy_result(frame.to_dict(orient="records"), table, season, tabbr, raw_a, raw_b)
        except Exception:
            pass
        finally:
            con.close()

    from ...sources import pbpstats

    ids = [pid for pid in (pid_a, pid_b) if pid]
    resolved_team = pkg.coerce_team_id(team_id) if team_id else 0
    entity_key = f"wowy:{raw_a}_{raw_b}"
    rows, meta = pkg._warehouse_or_live(
        "silver_wowy",
        "_season = ? AND _entity = ?",
        [season, entity_key],
        lambda: pbpstats.wowy(ids, resolved_team, season),
        season,
        entity=entity_key,
        ttl_s=pkg.TTL_PBPSTATS,
    )
    return {"tool": "get_wowy", "ok": True, "rows": rows, "meta": meta}


@tool(description="Four factor on-off splits for one player on one team.")
def get_four_factors(player_id: str | int, team_id: str | int, season: str | None = None) -> dict[str, Any]:
    pkg = _pkg()
    season = pkg.resolve_season(season)
    player_id = pkg.coerce_player_id(player_id)
    team_id = pkg.coerce_team_id(team_id)
    from ...sources import pbpstats

    rows, meta = pkg._warehouse_or_live(
        "silver_four_factors",
        "_season = ? AND _entity = ?",
        [season, f"player:{player_id}"],
        lambda: pbpstats.four_factors(player_id, team_id, season),
        season,
        entity=f"player:{player_id}",
        ttl_s=pkg.TTL_PBPSTATS,
    )
    return {"tool": "get_four_factors", "ok": True, "rows": rows, "meta": meta}
