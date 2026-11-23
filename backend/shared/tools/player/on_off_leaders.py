import sys
from typing import Any

from langchain_core.tools import tool


def _pkg():
    return sys.modules[__package__]


_TS_CTE = """
    ts AS (
        SELECT home_abbr AS team, poss_end - poss_start AS poss,
               (score_home_out - score_home_in) AS tpts,
               (score_away_out - score_away_in) AS opts,
               home_player_1 AS p1, home_player_2 AS p2, home_player_3 AS p3,
               home_player_4 AS p4, home_player_5 AS p5
        FROM silver_stints
        WHERE _season = ? AND SUBSTR(game_id, 1, 3) = '002'
        UNION ALL
        SELECT away_abbr, poss_end - poss_start,
               (score_away_out - score_away_in),
               (score_home_out - score_home_in),
               away_player_1, away_player_2, away_player_3, away_player_4, away_player_5
        FROM silver_stints
        WHERE _season = ? AND SUBSTR(game_id, 1, 3) = '002'
    )
"""


def _board(con, season: str, team: str | None,
           min_on_possessions: int, min_off_possessions: int) -> list[dict[str, Any]]:
    params: list[Any] = [season, season]
    roster_where = ""
    if team:
        roster_where = "AND team = ?"
        params.append(team)
    rows = con.execute(
        f"""
        WITH {_TS_CTE},
        roster AS (
            SELECT DISTINCT team, pid FROM (
                SELECT team, p1 pid FROM ts UNION SELECT team, p2 FROM ts
                UNION SELECT team, p3 FROM ts UNION SELECT team, p4 FROM ts
                UNION SELECT team, p5 FROM ts
            ) WHERE pid IS NOT NULL {roster_where}
        ),
        onagg AS (
            SELECT r.team, r.pid,
                   SUM(CASE WHEN r.pid IN (t.p1,t.p2,t.p3,t.p4,t.p5) THEN t.poss ELSE 0 END) AS on_poss,
                   SUM(CASE WHEN r.pid IN (t.p1,t.p2,t.p3,t.p4,t.p5) THEN t.tpts ELSE 0 END) AS on_tpts,
                   SUM(CASE WHEN r.pid IN (t.p1,t.p2,t.p3,t.p4,t.p5) THEN t.opts ELSE 0 END) AS on_opts
            FROM roster r JOIN ts t ON t.team = r.team
            GROUP BY 1, 2
        ),
        tot AS (
            SELECT team, SUM(poss) tposs, SUM(tpts) ttpts, SUM(opts) topts FROM ts GROUP BY team
        )
        SELECT o.team, o.pid, o.on_poss, t.tposs - o.on_poss AS off_poss,
               o.on_tpts, o.on_opts, t.ttpts - o.on_tpts AS off_tpts,
               t.topts - o.on_opts AS off_opts
        FROM onagg o JOIN tot t ON t.team = o.team
        WHERE o.on_poss >= ? AND (t.tposs - o.on_poss) >= ?
        """,
        params + [min_on_possessions, min_off_possessions],
    ).fetchall()
    return [
        {
            "team": r[0], "player_id": int(r[1]),
            "on_poss": int(r[2]), "off_poss": int(r[3]),
            "on_tpts": r[4], "on_opts": r[5], "off_tpts": r[6], "off_opts": r[7],
        }
        for r in rows
    ]


def _names(con, season_slug: str, year: int) -> dict[int, str]:
    try:
        rows = con.execute(
            "SELECT DISTINCT PLAYER_ID, firstName || ' ' || familyName "
            "FROM silver_boxscores WHERE _season = ?",
            [season_slug],
        ).fetchall()
        return {int(r[0]): r[1] for r in rows}
    except Exception:
        return {}


def _rate_raw(tpts: float | None, opts: float | None, poss: int) -> tuple[Any, Any]:
    if not poss:
        return None, None
    return 100.0 * (tpts or 0) / poss, 100.0 * (opts or 0) / poss


def _rate(tpts: float | None, opts: float | None, poss: int) -> tuple[Any, Any, Any]:
    ortg_raw, drtg_raw = _rate_raw(tpts, opts, poss)
    if ortg_raw is None:
        return None, None, None
    return round(ortg_raw, 1), round(drtg_raw, 1), round(ortg_raw - drtg_raw, 1)


def _row(r: dict[str, Any], names: dict[int, str]) -> dict[str, Any]:
    on_ortg, on_drtg, on_net = _rate(r["on_tpts"], r["on_opts"], r["on_poss"])
    off_ortg, off_drtg, off_net = _rate(r["off_tpts"], r["off_opts"], r["off_poss"])
    on_o, on_d = _rate_raw(r["on_tpts"], r["on_opts"], r["on_poss"])
    off_o, off_d = _rate_raw(r["off_tpts"], r["off_opts"], r["off_poss"])
    delta = round((on_o - on_d) - (off_o - off_d), 1) if on_o is not None and off_o is not None else None
    return {
        "player": names.get(r["player_id"], str(r["player_id"])),
        "player_id": r["player_id"],
        "team": r["team"],
        "on_poss": r["on_poss"],
        "off_poss": r["off_poss"],
        "on_ortg": on_ortg,
        "on_drtg": on_drtg,
        "on_net": on_net,
        "off_ortg": off_ortg,
        "off_drtg": off_drtg,
        "off_net": off_net,
        "net_delta": delta,
    }


def _pair_rows(con, season: str, tricode: str, pid_a: int, pid_b: int,
               name_a: str, name_b: str) -> list[dict[str, Any]]:
    rows = con.execute(
        f"""
        WITH {_TS_CTE}
        SELECT CASE
                 WHEN ? IN (p1,p2,p3,p4,p5) AND ? IN (p1,p2,p3,p4,p5) THEN 'both_on'
                 WHEN ? IN (p1,p2,p3,p4,p5) THEN 'a_on_b_off'
                 WHEN ? IN (p1,p2,p3,p4,p5) THEN 'b_on_a_off'
                 ELSE 'both_off' END AS cell,
               SUM(poss) AS poss, SUM(tpts) AS tpts, SUM(opts) AS opts
        FROM ts WHERE team = ? GROUP BY 1
        """,
        [season, season, pid_a, pid_b, pid_a, pid_b, tricode],
    ).fetchall()
    labels = {
        "both_on": "both on",
        "a_on_b_off": f"{name_a} on, {name_b} off",
        "b_on_a_off": f"{name_b} on, {name_a} off",
        "both_off": "both off",
    }
    out = []
    for cell, poss, tpts, opts in rows:
        ortg, drtg, net = _rate(tpts, opts, int(poss or 0))
        out.append({
            "split": labels.get(cell, cell),
            "possessions": int(poss or 0),
            "ortg": ortg,
            "drtg": drtg,
            "net": net,
        })
    out.sort(key=lambda r: (0 if r["split"] == "both on" else 1 if r["split"] == "both off" else 0.5, r["split"]))
    return out


def _shared_team(con, season: str, pid_a: int, pid_b: int) -> str | None:
    rows = con.execute(
        f"""
        WITH {_TS_CTE},
        both AS (
            SELECT team FROM ts
            WHERE ? IN (p1,p2,p3,p4,p5) AND ? IN (p1,p2,p3,p4,p5)
            GROUP BY team ORDER BY SUM(poss) DESC LIMIT 1
        )
        SELECT team FROM both
        """,
        [season, season, pid_a, pid_b],
    ).fetchall()
    return rows[0][0] if rows else None


@tool(
    description="Stint-level on/off splits from the possessions warehouse. Modes: "
    "pass player + team for one player's on/off split (per-100 OFF/DEF/NET each way); "
    "pass team alone for that team's board ranked by on-court possessions; pass pair "
    "as 'A,B' (+ team if known) for a two-player 2x2 (both on / each alone / both off); "
    "pass neither for a league board of qualifying players ranked by on-minus-off net "
    "gap (min_on_possessions/min_off_possessions floors). Use for 'better/worse with X "
    "on the floor', on-off net rating gaps, and rotation-impact asks. "
    "Coverage 2009-10 onward, regular season."
)
def get_on_off_leaders(player: str = "", team: str = "", pair: str = "",
                       season: str | None = None,
                       min_on_possessions: int = 2500,
                       min_off_possessions: int = 800,
                       limit: int = 10) -> dict[str, Any]:
    pkg = _pkg()
    season = str(pkg.resolve_season(season))
    season_slug = season
    try:
        year = int(season_slug[:4]) + 1
    except (TypeError, ValueError):
        year = 0
    try:
        limit = max(1, min(int(limit or 10), 30))
    except (TypeError, ValueError):
        limit = 10
    try:
        min_on_possessions = max(0, int(min_on_possessions or 0))
    except (TypeError, ValueError):
        min_on_possessions = 2500
    try:
        min_off_possessions = max(0, int(min_off_possessions or 0))
    except (TypeError, ValueError):
        min_off_possessions = 800
    try:
        con = pkg.store.connect(read_only=True)
    except Exception as exc:
        return {"tool": "get_on_off_leaders", "ok": False,
                "error": f"warehouse unavailable: {exc}"[:240]}
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        if "silver_stints" not in tables:
            return {"tool": "get_on_off_leaders", "ok": False,
                    "error": "silver_stints not loaded; on/off splits unavailable"}
        span = [r[0] for r in con.execute(
            "SELECT DISTINCT _season FROM silver_stints ORDER BY 1").fetchall()]
        if season_slug not in span:
            return {"tool": "get_on_off_leaders", "ok": False,
                    "error": (f"no stint coverage for {season_slug}; "
                              f"silver_stints spans {span[0]} through {span[-1]}")}
        meta = {"source": "silver_stints", "season": season_slug,
                "coverage": "regular-season"}
        names = _names(con, season_slug, year)
        raw_pair = str(pair or "").strip()
        raw_player = str(player or "").strip()
        raw_team = str(team or "").strip().upper()
        if raw_pair:
            parts = [p.strip() for p in raw_pair.split(",") if p.strip()]
            if len(parts) != 2:
                return {"tool": "get_on_off_leaders", "ok": False,
                        "error": "pair expects two players as 'A,B'"}
            try:
                pid_a, pid_b = pkg.coerce_player_id(parts[0]), pkg.coerce_player_id(parts[1])
            except ValueError as exc:
                return {"tool": "get_on_off_leaders", "ok": False, "error": str(exc)}
            tricode = raw_team or _shared_team(con, season_slug, pid_a, pid_b)
            if not tricode:
                return {"tool": "get_on_off_leaders", "ok": False,
                        "error": f"players {pid_a}/{pid_b} share no team in {season_slug}"}
            rows = _pair_rows(con, season_slug, tricode, pid_a, pid_b,
                              names.get(pid_a, parts[0]), names.get(pid_b, parts[1]))
            if not rows:
                return {"tool": "get_on_off_leaders", "ok": False,
                        "error": f"no stint data for {tricode} in {season_slug}"}
            return {"tool": "get_on_off_leaders", "ok": True, "rows": rows,
                    "meta": {**meta, "team": tricode, "pair": [pid_a, pid_b]}}
        board = _board(con, season_slug, raw_team or None,
                       min_on_possessions, min_off_possessions)
        if not board:
            return {"tool": "get_on_off_leaders", "ok": False,
                    "error": (f"no qualifying stint splits for {season_slug} "
                              f"(team={raw_team or 'league'}, floors "
                              f"{min_on_possessions}/{min_off_possessions})")}
        if raw_player:
            try:
                pid = pkg.coerce_player_id(raw_player)
            except ValueError as exc:
                return {"tool": "get_on_off_leaders", "ok": False, "error": str(exc)}
            hits = [r for r in board if r["player_id"] == pid]
            if not hits:
                retry = _board(con, season_slug, raw_team or None, 0, 0)
                hits = [r for r in retry if r["player_id"] == pid]
                if not hits:
                    return {"tool": "get_on_off_leaders", "ok": False,
                            "error": f"no stint split for player {pid} in {season_slug}"}
            return {"tool": "get_on_off_leaders", "ok": True,
                    "rows": [_row(hits[0], names)],
                    "meta": {**meta, "note": "floors ignored for a named player"}}
        rows = [_row(r, names) for r in board]
        if raw_team:
            rows.sort(key=lambda r: r["on_poss"], reverse=True)
        else:
            rows.sort(key=lambda r: (r["net_delta"] is None, -(r["net_delta"] or 0)))
        return {"tool": "get_on_off_leaders", "ok": True, "rows": rows[:limit],
                "meta": {**meta, "qualifying_pool": len(rows),
                         "floors": {"on_possessions": min_on_possessions,
                                    "off_possessions": min_off_possessions}}}
    finally:
        try:
            con.close()
        except Exception:
            pass
