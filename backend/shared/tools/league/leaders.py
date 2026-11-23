import duckdb
from typing import Any

from langchain_core.tools import tool

from ..leader_metrics import COUNTING_METRICS, per_game_column, per_game_value
from ._helpers import _pkg

_BOX_TOTAL_COLUMNS = {
    "PTS": "points", "REB": "reboundsTotal", "AST": "assists",
    "STL": "steals", "BLK": "blocks", "FGM": "fieldGoalsMade",
    "FGA": "fieldGoalsAttempted", "FG3M": "threePointersMade",
    "FG3A": "threePointersAttempted", "FTM": "freeThrowsMade",
    "FTA": "freeThrowsAttempted", "OREB": "reboundsOffensive",
    "DREB": "reboundsDefensive", "TOV": "turnovers", "PF": "foulsPersonal",
}

_TOTAL_MINUTES_FLOOR = 500
_TOTAL_MINUTES_TS_FLOOR = 1000


def _completed_season_totals(stat_category, season, order="DESC"):
    pkg = _pkg()
    column = _BOX_TOTAL_COLUMNS.get(stat_category)
    if column is None:
        return None
    con = pkg.store.connect(read_only=True)
    try:
        tables = {row[0] for row in con.execute("SHOW TABLES").fetchall()}
        raw = []
        if "silver_boxscores" in tables:
            columns = {
                row[1]
                for row in con.execute(
                    "PRAGMA table_info(silver_boxscores)").fetchall()
            }
            if {"PLAYER_ID", "firstName", "familyName", "GAME_ID",
                    "teamTricode", column, "comment", "_season"} <= columns:
                raw = con.execute(
                    "SELECT PLAYER_ID, firstName || ' ' || familyName AS PLAYER, "
                    "MODE(teamTricode) AS TEAM, "
                    "COUNT(DISTINCT GAME_ID) AS GP, "
                    f"SUM({column}) AS TOTAL "
                    "FROM silver_boxscores WHERE _season = ? "
                    "AND (comment IS NULL OR comment = '') "
                    "GROUP BY PLAYER_ID, firstName, familyName "
                    f"ORDER BY TOTAL {order}",
                    [season],
                ).fetchall()
        if not raw and {"silver_player_gamelogs",
                        "silver_player_season"} <= tables:
            try:
                raw = con.execute(
                    "SELECT g.Player_ID, s.PLAYER, MODE(s.TEAM) AS TEAM, "
                    "COUNT(DISTINCT g.Game_ID) AS GP, "
                    f"SUM(g.{stat_category}) AS TOTAL "
                    "FROM silver_player_gamelogs g "
                    "JOIN silver_player_season s "
                    "  ON s.PLAYER_ID = g.Player_ID AND s._season = g._season "
                    "WHERE g._season = ? "
                    "GROUP BY g.Player_ID, s.PLAYER "
                    f"ORDER BY TOTAL {order}",
                    [season],
                ).fetchall()
            except duckdb.Error:
                raw = []
    finally:
        con.close()
    if not raw:
        return None
    rows = [
        {"RANK": index, "PLAYER_ID": row[0], "PLAYER": row[1], "TEAM": row[2],
         "GP": row[3], stat_category: row[4], "PLAYER_NAME": row[1]}
        for index, row in enumerate(raw, 1)
    ]
    meta = {
        "source": "warehouse", "season": season,
        "stat_category": stat_category, "rows": len(rows),
        "cached": True, "static_season": True,
        "qualification": (
            "Season totals summed from warehouse game logs; "
            "games not played are left out."
        ),
        "coverage": (
            "Full player population in warehouse game logs "
            "for the season, ordered by total."
        ),
        **pkg.store.warehouse_identity(),
    }
    return rows, meta


class QualificationFloor:

    __slots__ = ("metric", "floor", "label", "cleared_column")

    def __init__(self, metric: str, floor: int, label: str,
                 cleared_column: str) -> None:
        self.metric = metric
        self.floor = floor
        self.label = label
        self.cleared_column = cleared_column

    def payload(self) -> dict[str, Any]:
        return {"metric": self.metric, "floor": self.floor,
                "label": self.label, "cleared_column": self.cleared_column}


class _FloorValueUnavailable(Exception):
    pass


def _floor_rows(con, sql: str, params: list[Any], table: str,
                floor: QualificationFloor) -> list[Any]:
    try:
        return con.execute(sql, params).fetchall()
    except duckdb.Error as exc:
        raise _FloorValueUnavailable(
            f"{table} cannot evidence the {floor.label} qualification "
            f"because the column behind it is unreadable: {exc}") from exc


def _qualified_rate_board(
        con, stat_category: str, season: str, order: str, min_attempts: int,
) -> tuple[list[dict[str, Any]], QualificationFloor, Any]:
    if stat_category == "TS_PCT":
        floor_value = max(_TOTAL_MINUTES_TS_FLOOR, min_attempts)
        qualification = QualificationFloor(
            "total_minutes", floor_value, f"{floor_value:,}+ total minutes",
            "TOTAL_MINUTES")
        probe = _floor_rows(
            con,
            "SELECT MAX(MIN) FROM silver_advanced WHERE _season = ?",
            [season], "silver_advanced", qualification)
        probe_value = probe[0][0] if probe else None
        per_game = probe_value is not None and probe_value <= 60.0
        total_expr = "MIN * GP" if per_game else "MIN"
        raw = _floor_rows(
            con,
            "SELECT PLAYER_NAME, TEAM_ABBREVIATION, GP, MIN, TS_PCT "
            "FROM silver_advanced WHERE _season = ? "
            f"AND {total_expr} >= ? "
            f"ORDER BY TS_PCT {order}, {total_expr} DESC",
            [season, floor_value], "silver_advanced", qualification)
        rows = [
            {"RANK": index, "PLAYER": row[0], "TEAM": row[1],
             "GP": row[2],
             "MPG": row[3] if per_game
                  else (row[3] / row[2] if row[2] else 0),
             "TOTAL_MINUTES": row[3] * row[2] if per_game else row[3],
             "TS_PCT": round(float(row[4]) * 100, 1)}
            for index, row in enumerate(raw, 1)
        ]
        return rows, qualification, (
            lambda row: f"{row['TS_PCT']:.1f}% true shooting")

    rate_to_total = {"PPG": "PTS", "RPG": "REB", "APG": "AST",
                     "SPG": "STL", "BPG": "BLK"}
    total_stat = rate_to_total[stat_category]
    table = f"silver_leaders_{total_stat.lower()}"
    qualification = QualificationFloor(
        "total_minutes", _TOTAL_MINUTES_FLOOR,
        f"{_TOTAL_MINUTES_FLOOR}+ total minutes", "MIN")
    raw = _floor_rows(
        con,
        f"SELECT PLAYER, TEAM, GP, MIN,"
        f" {total_stat} / CAST(GP AS DOUBLE) AS RATE "
        f"FROM {table} WHERE _season = ? AND GP > 0"
        f" AND MIN >= {_TOTAL_MINUTES_FLOOR} "
        f"ORDER BY RATE {order}, GP DESC, PLAYER",
        [season], table, qualification)
    rows = [
        {"RANK": index, "PLAYER": row[0], "TEAM": row[1],
         "GP": row[2], "MIN": row[3],
         stat_category: float(row[4])}
        for index, row in enumerate(raw, 1)
    ]
    noun = {"PPG": "points", "RPG": "rebounds", "APG": "assists",
            "SPG": "steals", "BPG": "blocks"}[stat_category]
    return rows, qualification, (
        lambda row: f"{row[stat_category]:.2f} {noun} per game")


def _cleared(lead: dict[str, Any], floor: QualificationFloor) -> str:
    column = floor.cleared_column
    observed = lead.get(column)
    if observed is None:
        raise ValueError(
            f"qualification floor {floor.label} has no published value: the "
            f"leader row carries no {column}, so the floor would publish as a "
            f"label with no number behind it")
    return (f"{observed:,.0f} {floor.metric.replace('_', ' ')} over "
            f"{lead.get('GP')} games")


_RATE_BOARD_CATEGORIES = {"TS_PCT", "PPG", "RPG", "APG", "SPG", "BPG"}

_DIRECTION_ALIASES = {"ascending": "asc", "ascend": "asc",
                      "descending": "desc", "descend": "desc"}


def _leaders_direction(ranking_direction: str) -> str:
    direction = _DIRECTION_ALIASES.get(
        str(ranking_direction).strip().casefold(),
        str(ranking_direction).strip().casefold())
    if direction not in {"asc", "desc"}:
        raise ValueError("ranking_direction must be 'asc' or 'desc'")
    return direction


def _leaders_check_min_attempts(min_attempts: object) -> None:
    if isinstance(min_attempts, bool) or not isinstance(min_attempts, int):
        raise TypeError("min_attempts must be an integer")
    if not 0 <= min_attempts <= 5000:
        raise ValueError("min_attempts must be between 0 and 5000")


def _leaders_unevidenced(stat_category: str, exc: Exception, season: str,
                         direction: str, min_attempts: int) -> dict[str, Any]:
    return {"tool": "get_leaders", "ok": False, "rows": [],
            "error": (f"{exc}; refusing to publish a "
                      f"{stat_category} board whose "
                      f"qualification cannot be evidenced"),
            "meta": {"source": "warehouse", "season": season,
                     "stat_category": stat_category,
                     "ranking_direction": direction,
                     "min_attempts": min_attempts}}


def _leaders_rate_board(stat_category: str, season: str, order: str,
                        direction: str, min_attempts: int):
    con = _pkg().store.connect(read_only=True)
    try:
        rows, qualification, value = _qualified_rate_board(
            con, stat_category, season, order, min_attempts)
    except _FloorValueUnavailable as exc:
        return None, _leaders_unevidenced(stat_category, exc, season,
                                          direction, min_attempts)
    finally:
        con.close()
    meta = {
        "source": "warehouse", "season": season,
        "stat_category": stat_category, "rows": len(rows),
        "ranking_direction": direction, "min_attempts": min_attempts,
        "qualification": qualification.label,
        "qualification_floor": qualification.payload(),
    }
    return (rows, meta), (value, qualification)


def _leaders_table_board(stat_category: str, season: str, order: str):
    pkg = _pkg()
    table = f"silver_leaders_{stat_category.lower()}"
    if pkg.season_static(season):
        totals = pkg._completed_season_totals(stat_category, season, order)
        if totals is not None:
            return totals
    rows, meta = pkg._warehouse_or_live(
        table, "_season = ?",
        [season], lambda: pkg.nba_stats.leaders(stat_category, season), season,
    )
    meta["stat_category"] = stat_category
    meta.setdefault("season", season)
    if rows:
        meta.setdefault(
            "qualification",
            "Season totals summed from warehouse game logs; "
            "games not played are left out.")
        meta.setdefault(
            "coverage",
            "Full player population in warehouse game logs "
            "for the season, ordered by total.")
    needs_id_fallback = bool(rows) and not any(
        "PLAYER_ID" in row or "player_id" in row for row in rows
    )
    if (not rows or needs_id_fallback) and pkg.season_static(season):
        fallback = pkg._completed_season_totals(stat_category, season, order)
        if fallback is not None:
            rows, meta = fallback
    return rows, meta


def _leaders_fg3_rows(season: str, order: str, min_attempts: int) -> list:
    con = _pkg().store.connect(read_only=True)
    try:
        raw = con.execute(
            "SELECT PLAYER, TEAM, GP, MIN, FG3M, FG3A, FG3_PCT "
            "FROM silver_leaders_pts WHERE _season = ? "
            f"AND FG3M >= ? AND FG3A >= ? "
            f"ORDER BY FG3_PCT {order}, FG3M DESC",
            [season, 0 if min_attempts else 82, min_attempts]).fetchall()
    finally:
        con.close()
    return [
        {"RANK": i, "PLAYER": r[0], "TEAM": r[1], "GP": r[2],
         "MPG": r[3], "FG3M": r[4], "FG3A": r[5],
         "FG3_PCT": r[6]}
        for i, r in enumerate(raw, 1)
    ]


def _leaders_fg3_meta(rows: list, season: str, direction: str,
                      min_attempts: int, stat_category: str) -> dict[str, Any]:
    qualification = (f"{min_attempts}+ three-point attempts"
                     if min_attempts else "82+ made threes")
    meta = {"source": "warehouse", "season": season,
            "stat_category": stat_category, "rows": len(rows),
            "ranking_direction": direction,
            "min_attempts": min_attempts,
            "qualification": qualification}
    if rows:
        leaders = "; ".join(
            f"{row['PLAYER']} {row['FG3_PCT'] * 100:.1f}% "
            f"({row['FG3M']} makes on {row['FG3A']} attempts)"
            for row in rows[:5]
        )
        meta["deterministic_answer"] = (
            f"Qualified three-point percentage leaders: {leaders}. "
            f"Qualification: {qualification}.")
    return meta


def _leaders_fg3_board(season: str, order: str, direction: str,
                       min_attempts: int, stat_category: str,
                       meta: dict[str, Any]):
    try:
        rows = _leaders_fg3_rows(season, order, min_attempts)
    except Exception:
        return [], meta
    return rows, _leaders_fg3_meta(rows, season, direction, min_attempts,
                                   stat_category)


def _leaders_pin_columns(stat_category: str) -> list[str]:
    pin = ["RANK", "PLAYER", "TEAM", stat_category]
    if stat_category == "FG3_PCT":
        pin.extend(["FG3M", "FG3A"])
    pin.extend(["GP", "MIN", "MPG", "TOTAL_MINUTES"])
    return pin


def _pin_leader_row(r: Any, pin: list[str]) -> Any:
    if not isinstance(r, dict):
        return r
    slim = {k: r[k] for k in pin if k in r}
    for metric in COUNTING_METRICS:
        rate = per_game_value(slim.get(metric), slim.get("GP"))
        if rate is not None:
            slim[per_game_column(metric)] = rate
    for identifier in ("PLAYER_ID", "player_id", "TEAM_ID", "team_id"):
        if identifier in r and identifier not in slim:
            slim[identifier] = r[identifier]
    if "PLAYER" in slim and "PLAYER_NAME" not in slim:
        slim["PLAYER_NAME"] = slim["PLAYER"]
    return slim


def _leaders_lead_answer(pinned: list, lead_answer: tuple, season: str):
    value, qualification = lead_answer
    return (f"{pinned[0]['PLAYER']} leads qualified players at "
            f"{value(pinned[0])} in {season}. Qualification: "
            f"{qualification.label}; "
            f"{_cleared(pinned[0], qualification)}.")


@tool(description='Qualified league leaderboard for one stat category.\n\nranking_direction is ``desc`` for highest-first or ``asc`` for\nlowest-first. min_attempts carries an explicit user volume floor for\npercentage metrics; zero keeps the league qualification.\n\nPercentage boards use the NBA minimums carried by the warehouse\ninstead of an arbitrary attempts floor. For 3P%, the qualification is\n82 made threes over an 82-game season. This keeps the board comparable\nto the official league leaderboard and excludes tiny samples.\n\nCovers standard box-score categories. Shot-location boards (corner-3,\nabove-break, rim, midrange) or position-pool counts are not here —\nrun one sql_exec GROUP BY over silver_hist_shots (zone geometry is\ndocumented on get_zone_deltas), joining silver_boxscores for position\nfilters; GROUP BY PLAYER_ID gives player-season totals and\nCOUNT of qualifying rows gives the pool size.')
def get_leaders(
    stat_category: str = "PTS", season: str | None = None,
    ranking_direction: str = "desc", min_attempts: int = 0,
) -> dict[str, Any]:
    pkg = _pkg()
    season = pkg.resolve_season(season)
    try:
        stat_category = pkg.clamp_stat(stat_category)
    except ValueError:
        return {"tool": "get_leaders", "ok": False, "rows": [],
                "error": f"unknown stat_category: {stat_category!r}",
                "meta": {"source": "warehouse", "season": season}}
    direction = _leaders_direction(ranking_direction)
    _leaders_check_min_attempts(min_attempts)
    order = "ASC" if direction == "asc" else "DESC"

    lead_answer: tuple[Any, QualificationFloor] | None = None
    if stat_category in _RATE_BOARD_CATEGORIES:
        board, lead_answer = _leaders_rate_board(
            stat_category, season, order, direction, min_attempts)
        if board is None:
            return lead_answer
        rows, meta = board
    else:
        rows, meta = _leaders_table_board(stat_category, season, order)

    if stat_category == "FG3_PCT":
        rows, meta = _leaders_fg3_board(season, order, direction,
                                        min_attempts, stat_category, meta)

    pin = _leaders_pin_columns(stat_category)
    pinned = [_pin_leader_row(r, pin) for r in rows]
    if lead_answer is not None and pinned:
        try:
            meta["deterministic_answer"] = _leaders_lead_answer(
                pinned, lead_answer, season)
        except (ValueError, KeyError, TypeError) as exc:
            return {"tool": "get_leaders", "ok": False, "rows": [],
                    "error": (f"refusing to publish a {stat_category} answer "
                              f"whose qualification cannot be evidenced from "
                              f"the published row: {exc}"),
                    "meta": meta}
    if not pinned and str(meta.get("error") or "").strip():
        detail = str(meta.get("error")).strip()
        return {"tool": "get_leaders", "ok": False, "rows": [],
                "error": (f"no {stat_category} leaders for {season}: "
                          f"{detail}"),
                "meta": meta}
    return {"tool": "get_leaders", "ok": True, "rows": pinned, "meta": meta}


@tool(description='Qualified usage-rate board for young players from silver_advanced.\n\nUses total minutes (GP * per-game MIN) as the sample floor. The default\nmeans age 22 or younger with at least 1,000 minutes in the asked season.\nA hard 500-total-minute floor is ALWAYS enforced: the caller may raise\nit but never undercut it.')
def get_young_player_usage(max_age: int = 22, min_minutes: int = 1000,
                           season: str | None = None) -> dict[str, Any]:
    pkg = _pkg()
    season = pkg.resolve_season(season)
    max_age = max(18, min(int(max_age), 25))
    min_minutes = max(500, min(int(min_minutes), 3000))
    con = pkg.store.connect(read_only=True)
    try:
        raw = con.execute(
            "SELECT PLAYER_NAME, TEAM_ABBREVIATION, AGE, GP, MIN, USG_PCT "
            "FROM silver_advanced WHERE _season = ? AND AGE <= ? "
            "AND GP * MIN >= ? ORDER BY USG_PCT DESC",
            [season, max_age, min_minutes]).fetchall()
    finally:
        con.close()
    rows = [{"RANK": i, "PLAYER": r[0], "TEAM": r[1], "AGE": r[2],
             "GP": r[3], "MPG": r[4], "MINUTES": round(r[3] * r[4]),
             "USG_PCT": round(float(r[5]) * 100, 1)}
            for i, r in enumerate(raw, 1)]
    meta: dict[str, Any] = {
        "source": "warehouse:silver_advanced", "season": season,
        "max_age": max_age, "min_minutes": min_minutes, "rows": len(rows)}
    if rows:
        lead = rows[0]
        meta["deterministic_answer"] = (
            f"{lead['PLAYER']} leads players age {max_age} or younger in "
            f"usage rate at {lead['USG_PCT']:.1f}% in {season}. "
            f"Qualification: {min_minutes:,}+ total minutes; "
            f"{lead['MINUTES']:,} minutes in {lead['GP']} games.")
    return {"tool": "get_young_player_usage", "ok": True,
            "rows": rows, "meta": meta}


_TEAM_TOTAL_STATS = ("PTS", "REB", "AST", "STL", "BLK", "FG3M", "TOV")
_TEAM_TOTAL_COLUMNS = {
    "PTS": "points",
    "REB": "reboundsTotal",
    "AST": "assists",
    "STL": "steals",
    "BLK": "blocks",
    "FG3M": "threePointersMade",
    "TOV": "turnovers",
}


def _deduped_team_totals(stat: str, season: str):
    pkg = _pkg()
    season = pkg.resolve_season(season)
    column = _TEAM_TOTAL_COLUMNS.get(stat)
    if column is None:
        return None
    con = pkg.store.connect(read_only=True)
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        if "silver_boxscores" not in tables:
            return None
        return con.execute(
            "SELECT MODE(TEAM_ID) AS TEAM_ID, teamTricode AS ABBREV, "
            f"SUM({column}) AS TOTAL, COUNT(DISTINCT GAME_ID) AS GP, "
            f"ROUND(SUM({column}) * 1.0 / COUNT(DISTINCT GAME_ID), 1) "
            "AS PER_GAME "
            "FROM silver_boxscores WHERE _season = ? "
            "AND SUBSTR(GAME_ID, 1, 3) = '002' "
            "AND TEAM_ID IS NOT NULL "
            "AND (comment IS NULL OR comment = '') "
            "GROUP BY teamTricode ORDER BY TOTAL DESC",
            [season]).fetchall()
    finally:
        con.close()


@tool(description='Team totals leaderboard for a counting stat (PTS, REB, AST, STL,\nBLK): player game logs summed by team, with per-game averages.\nUse for "which team leads in total assists" - get_leaders is\nplayer-level only.')
def get_team_leaders(stat_category: str = "AST",
                     season: str | None = None) -> dict[str, Any]:
    pkg = _pkg()
    season = pkg.resolve_season(season)
    try:
        stat = pkg.clamp_stat(stat_category)
    except ValueError:
        stat = "PTS"
    if stat not in _TEAM_TOTAL_STATS:
        stat = "AST"
    fetched = _deduped_team_totals(stat, season)
    if fetched is None:
        return {"tool": "get_team_leaders", "ok": False,
                "error": "no team totals data in the warehouse"}
    from nba_api.stats.static import teams as _static
    names = {t["abbreviation"]: t["full_name"]
             for t in _static.get_teams()}

    _alias = {"PHO": "PHX", "CHO": "CHA", "BRK": "BKN"}
    rows = []
    for i, (team_id, abbrev, total, gp, per_game) in enumerate(fetched, 1):
        rows.append({
            "RANK": i,
            "TEAM_ID": int(team_id) if team_id is not None else None,
            "TEAM": names.get(_alias.get(abbrev, abbrev), abbrev),
            "ABBREV": abbrev,
            stat: int(total),
            "GP": int(gp),
            "PER_GAME": per_game,
        })
    leader = rows[0] if rows else None
    leader_line = (f"{leader['TEAM']} lead with {leader[stat]} total "
                   f"{stat} ({leader['PER_GAME']} per game over "
                   f"{leader['GP']} games)") if leader else ""
    meta = {"stat_category": stat, "season": season, "source": "warehouse",
            "rows": len(rows),
            "leader_line": leader_line,
            "note": "team totals summed from player game logs "
                    "(regular season). Cite the leader's TOTAL value "
                    "and per-game verbatim from leader_line - never "
                    "drop the total (QA: points narrative shipped "
                    "'scored the most points with total points and "
                    "122.1 per game', value missing)."}
    return {"tool": "get_team_leaders", "ok": True, "rows": rows,
            "meta": meta}


@tool(description='Top-N team compare on one counting stat: total, per-game, games\nplayed, and the win-loss record joined from standings, in one\nboard. Use for multi-metric team compares ("compare the top 3\nscoring teams: totals, per-game, and wins") - get_team_leaders has\nno records and a delegate fan-out composes nameless tables with\nempty cells or invented numbers (F66). The answer is built\ndeterministically from the rows into meta.deterministic_answer;\ncompose ships it verbatim (v67 design law).')
def get_team_compare(stat_category: str = "PTS", top: int = 3,
                     season: str | None = None) -> dict[str, Any]:
    pkg = _pkg()
    season = pkg.resolve_season(season)
    try:
        stat = pkg.clamp_stat(stat_category)
    except ValueError:
        stat = "PTS"
    if stat not in _TEAM_TOTAL_STATS:
        stat = "PTS"
    try:
        top = max(2, min(int(top or 3), 10))
    except (TypeError, ValueError):
        top = 3
    fetched = _deduped_team_totals(stat, season)
    if fetched is None:
        return {"tool": "get_team_compare", "ok": False,
                "error": "no team totals data in the warehouse"}
    con = pkg.store.connect(read_only=True)
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        records: dict[str, tuple[int, int]] = {}
        if "silver_standings" in tables:
            for city, name, w, loss in con.execute(
                    "SELECT TeamCity, TeamName, WINS, LOSSES "
                    "FROM silver_standings WHERE _season = ?",
                    [season]).fetchall():
                records[f"{city or ''} {name or ''}".strip()] = (
                    int(w or 0), int(loss or 0))
    finally:
        con.close()
    from nba_api.stats.static import teams as _static
    names = {t["abbreviation"]: t["full_name"]
             for t in _static.get_teams()}

    _alias = {"PHO": "PHX", "CHO": "CHA", "BRK": "BKN"}
    rows = []
    for i, (team_id, abbrev, total, gp, per_game) in enumerate(
            fetched[:top], 1):
        team = names.get(_alias.get(abbrev, abbrev), abbrev)
        w, loss = records.get(team, (None, None))
        rows.append({
            "RANK": i,
            "TEAM_ID": int(team_id) if team_id is not None else None,
            "TEAM": team,
            "ABBREV": abbrev,
            stat: int(total),
            "GP": int(gp),
            "PER_GAME": per_game,
            "W": w,
            "L": loss,
            "RECORD": f"{w}-{loss}" if w is not None else "",
        })
    if not rows:
        return {"tool": "get_team_compare", "ok": False,
                "error": f"no team totals for {season}"}
    leader = rows[0]
    answer = (f"{leader['TEAM']} lead with {leader[stat]} total {stat} "
              f"({leader['PER_GAME']} per game over {leader['GP']} "
              f"games)")
    if leader.get("RECORD"):
        answer += f" and a {leader['RECORD']} record"
    answer += "."
    if len(rows) > 1:
        parts = []
        for r in rows[1:]:
            part = (f"{r['TEAM']}: {r[stat]} total {stat} "
                    f"({r['PER_GAME']} per game)")
            if r.get("RECORD"):
                part += f", {r['RECORD']}"
            parts.append(part)
        answer += " " + "; ".join(parts) + "."
    meta = {"stat_category": stat, "season": season,
            "source": "warehouse", "rows": len(rows),
            "deterministic_answer": answer,
            "note": "deterministic deep-compare lane (F66): ship "
                    "deterministic_answer verbatim - totals and "
                    "per-game come from deduped player game logs, "
                    "records from standings. Never recompose these "
                    "numbers from scratch."}
    return {"tool": "get_team_compare", "ok": True, "rows": rows,
            "meta": meta}
