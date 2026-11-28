import re as _re_mod
import threading as _threading
import time as _time
from typing import Any

from langchain_core.tools import tool

from .._core import warehouse_identity_meta
from ..season_semantics import annotate_schema
from ..splits import _resolve_name as _rname
from ._helpers import _pkg

_SQL_TABLES = [
    "silver_standings", "silver_playoffs", "silver_team_ratings",
    "silver_clutch", "silver_player_gamelogs", "silver_team_games",
    "silver_leaders_pts", "silver_leaders_reb", "silver_leaders_ast",
    "silver_leaders_stl", "silver_leaders_blk", "silver_boxscores",
    "silver_leaders_dreb", "silver_leaders_fg_pct",
    "silver_leaders_fta", "silver_leaders_ft_pct",
    "silver_lineups", "silver_shots", "silver_hustle_player",
    "silver_hustle_team", "silver_injuries", "silver_injury_entries",
    "silver_hist_gamelogs",
    "silver_hist_standings", "silver_hist_possessions",
    "silver_hist_shots", "silver_hist_lineups", "silver_salaries",
    "silver_hist_draft", "silver_hist_team_seasons", "silver_raptor_player",
    "silver_free_agents", "silver_cap_room",
    "silver_draft_boards", "silver_prospect_stats",
    "silver_raptor_team",
    "silver_hist_player_seasons", "silver_player_season", "silver_advanced",
    "silver_on_off", "silver_four_factors", "silver_four_factors_team",
    "silver_cap_players", "silver_news",
    "silver_rapm", "silver_rapm_prior", "silver_impact",
    "silver_hist_hustle", "silver_hist_pbp",
    "silver_bbref_awards", "silver_combine", "silver_rosters",
    "silver_schedule", "silver_stints", "silver_playoff_gamelogs",
    "silver_transactions", "silver_contracts", "silver_preseason_projections",
    "silver_future_picks", "silver_draft_value_curve",
    "silver_bbref_gamelogs_2024_25", "silver_boxscores_ext",
    "silver_cap_history",
    "silver_hist_salaries",
    "silver_playoff_inactive", "silver_scoreboard",
    "silver_tracking_pt_defend", "silver_tracking_pt_shot",
    "silver_tracking_pt_stats", "silver_wowy", "silver_zone_splits",
]

RERUN_ROW_CAP = 200
RERUN_TIMEOUT_S = 30

_SCHEMA_TTL_S = 3600.0
_SCHEMA_DISPLAY_COLUMN_LIMIT = 40
_schema_cache: dict[str, object] = {"at": 0.0, "present": [], "cols": {}}
_schema_cache_stats: dict[str, int] = {"hits": 0, "misses": 0}
_season_span_cache: dict[str, object] = {"at": 0.0, "spans": {}}


def _describe_warehouse_schema(cols: dict[str, dict]) -> str:
    display, budget = _schema_for_display(cols)
    lines = []
    truncated = budget["truncated_tables"]
    for table, columns in display.items():
        line = f"{table}: {', '.join(columns)}"
        if table == 'silver_hist_draft':
            line += (". Raw draft rows only: value-curve, median-career-WAR-by-slot,"
                     " and pick-value-index asks belong to silver_draft_value_curve"
                     " (SLOT, MEDIAN_CAREER_WAR, VALUE_INDEX; one row per slot 1-60)"
                     " via sql_exec, not to aggregating this table.")
        if table == 'silver_hist_lineups':
            line += (". Variant rows: MUST filter season_type ('regular-season', 'playoffs'),"
                     " measure_type ('base', 'advanced', 'defense', 'misc', 'opponent', 'scoring', 'usage'),"
                     " per_mode ('totals', 'pergame'). Default: regular-season/base/totals."
                     " Never aggregate across variants: each unit appears up to 28 times (2x7x2), so unfiltered sums multiply minutes and possessions. Ratings and pace are populated only in advanced;"
                     " join on group_id, team_id, _season, season_type, per_mode with measure_type='advanced'.")
        omitted = truncated.get(table)
        if omitted:
            line += (
                f" (schema truncated: showing {omitted['shown_columns']} of "
                f"{omitted['total_columns']} columns; "
                f"{omitted['omitted_columns']} omitted)"
            )
        lines.append(line)
    return "\n".join(lines)


def _schema_for_display(
        cols: dict[str, dict]
        ) -> tuple[dict[str, dict], dict[str, Any]]:
    schema_cols = {
        table: (columns if isinstance(columns, dict)
                else {name: {} for name in columns})
        for table, columns in cols.items()
    }
    annotated = annotate_schema({"tables": schema_cols})["tables"]
    display: dict[str, dict] = {}
    truncated_tables: dict[str, dict[str, int]] = {}
    provenance = {name.lower() for name in _pkg().store.PROVENANCE_COLS}
    limit = _SCHEMA_DISPLAY_COLUMN_LIMIT
    for table, columns in annotated.items():
        names = list(columns)
        preferred = []
        for name, metadata in columns.items():
            semantics = metadata.get("season_semantics", {})
            if (name.lower() in provenance
                    or (table == 'silver_hist_lineups' and name in {'season_type', 'measure_type', 'per_mode'})
                    or (semantics.get("encoding") not in (None, "unknown")
                        and semantics.get("source")
                        != "no source-backed mapping")):
                preferred.append(name)
        selected = set(preferred[:limit])
        for name in names:
            if len(selected) >= limit:
                break
            selected.add(name)
        display[table] = {
            name: metadata for name, metadata in columns.items()
            if name in selected
        }
        if len(names) > len(display[table]):
            shown = len(display[table])
            truncated_tables[table] = {
                "total_columns": len(names),
                "shown_columns": shown,
                "omitted_columns": len(names) - shown,
            }
    return display, {
        "max_columns_per_table": limit,
        "truncated_tables": truncated_tables,
    }


def _clear_warehouse_schema_cache() -> None:
    _schema_cache["at"] = 0.0
    _schema_cache["present"] = []
    _schema_cache["cols"] = {}
    _schema_cache_stats["hits"] = 0
    _schema_cache_stats["misses"] = 0
    _season_span_cache["at"] = 0.0
    _season_span_cache["spans"] = {}


def _warehouse_schema_cache_info() -> dict[str, float]:
    return {"hits": _schema_cache_stats["hits"],
            "misses": _schema_cache_stats["misses"],
            "at": _schema_cache["at"]}


def _season_span(seasons: list[str]) -> str:
    labels = sorted({
        str(value).strip() for value in seasons
        if value is not None and str(value).strip()
    })
    if not labels:
        return "n/a"
    count = len(labels)
    unit = "season" if count == 1 else "seasons"
    return f"{labels[0]}..{labels[-1]} ({count} {unit})"


def _table_seasons(table: str, columns: dict[str, Any]) -> list[str]:
    names = {str(name).lower() for name in columns}
    upper = {str(name).upper() for name in columns}
    if "_season" not in names:
        return []
    if "game_id" in upper:
        try:
            return list(_pkg().store.seasons_with_data(table))
        except Exception:
            return []
    con = _pkg().store.connect(read_only=True)
    try:
        rows = con.execute(
            f"SELECT DISTINCT _season FROM {table} ORDER BY _season"
        ).fetchall()
    except Exception:
        return []
    finally:
        con.close()
    return [str(row[0]) for row in rows if row and row[0] is not None]


def _get_warehouse_season_spans(
        present: list[str], columns: dict[str, dict[str, Any]]
        ) -> dict[str, str]:
    now = _time.monotonic()
    at = float(_season_span_cache.get("at") or 0.0)
    if now - at < _SCHEMA_TTL_S and _season_span_cache.get("spans"):
        return dict(_season_span_cache["spans"])
    spans = {
        name: _season_span(_table_seasons(name, columns.get(name) or {}))
        for name in present
    }
    _season_span_cache["at"] = now
    _season_span_cache["spans"] = spans
    return dict(spans)


_COLUMN_UNITS: dict[str, tuple[str, str]] = {
    "PCT": ("fraction_0_1", "fraction on a 0-1 scale, not a 0-100 number"),
    "MPG": ("minutes_per_game", "minutes per game, not total minutes; "
                                "multiply by GP for a season total"),
    "PPG": ("points_per_game", "points per game, not a season total"),
    "RPG": ("rebounds_per_game", "rebounds per game, not a season total"),
    "APG": ("assists_per_game", "assists per game, not a season total"),
    "SPG": ("steals_per_game", "steals per game, not a season total"),
    "BPG": ("blocks_per_game", "blocks per game, not a season total"),
    "GP": ("games_played", "games played; the denominator for a per-game rate"),
    "GS": ("games_started", "games started, at most GP"),
    "MP": ("total_minutes", "total minutes played across the season"),
    "AGE": ("years", "age in years"),
    "RANK": ("rank", "leading rank; a tie shares it"),
    "RATE": ("per_100_possessions", "rate per 100 possessions"),
    "RAPM": ("points_per_100_possessions", "regularized adjusted plus-minus per 100 possessions"),
    "POSSESSIONS": ("possessions", "total tracked possessions"),
    "AWARD_SHARE": ("fraction_0_1", "fraction of maximum possible award points won"),
    "VOTES_FIRST": ("first_place_votes", "number of first-place award votes received"),
    "STANDING_REACH": ("inches", "standing reach measured in inches at the NBA draft combine"),
    "WINGSPAN": ("inches", "wingspan measured in inches at the NBA draft combine"),
    "HEIGHT_WO_SHOES": ("inches", "height without shoes measured in inches at the NBA draft combine"),
    "SALARY": ("usd_dollars", "cap hit in US dollars for the row's season"),
    "COMMITTED_SALARY": ("usd_dollars", "committed salary in US dollars for the cap season"),
    "PENDING_OPTION_SALARY": ("usd_dollars", "salary in US dollars pending player/team option decisions"),
    "FA_HOLDS_EST": ("usd_dollars", "estimated free-agent cap holds in US dollars"),
    "INCOMPLETE_ROSTER_CHARGES": ("usd_dollars", "roster charges in US dollars for incomplete rosters"),
    "ROSTER_CHARGE_MINIMUM": ("usd_dollars", "minimum salary used for incomplete-roster charges in US dollars"),
    "PROJECTED_ROOM": ("usd_dollars", "projected cap room in US dollars"),
    "MAX_ROOM": ("usd_dollars", "maximum achievable cap room in US dollars"),
    "PROJECTED_CAP": ("usd_dollars", "projected salary cap in US dollars"),
    "PROJECTED_TAX": ("usd_dollars", "projected luxury tax line in US dollars"),
    "PROJECTED_APRON1": ("usd_dollars", "projected first apron in US dollars"),
    "PROJECTED_APRON2": ("usd_dollars", "projected second apron in US dollars"),
    "ROOM_EST": ("usd_dollars", "estimated cap room in US dollars"),
    "NTMLE_EST": ("usd_dollars", "estimated non-taxpayer mid-level exception in US dollars"),
    "BAE_EST": ("usd_dollars", "estimated bi-annual exception in US dollars"),
    "TMLE_EST": ("usd_dollars", "estimated taxpayer mid-level exception in US dollars"),
    "PRIOR_SALARY": ("usd_dollars", "prior-season salary in US dollars"),
    "CAP_HOLD_EST": ("usd_dollars", "estimated cap hold in US dollars"),
    "SALARY_CAP": ("usd_dollars", "salary cap in US dollars for the season"),
    "LUXURY_TAX": ("usd_dollars", "luxury tax line in US dollars for the season"),
    "APRON_1": ("usd_dollars", "first apron in US dollars for the season"),
    "APRON_2": ("usd_dollars", "second apron in US dollars for the season"),
    "CAP_HIT": ("usd_dollars", "cap hit in US dollars"),
    "DEAD_MONEY": ("usd_dollars", "dead money in US dollars counting against the cap"),
}
_COLUMN_PREFIX_UNITS: tuple[tuple[str, tuple[str, str]], ...] = (
    ("_PCT", ("fraction_0_1",
              "fraction on a 0-1 scale, not a 0-100 number")),
    ("_PTS_PER_100", ("points_per_100_possessions",
                      "points per 100 possessions")),
)
_COLUMN_SUFFIXES = ("_PTS", "_REB", "_AST", "_STL", "_BLK", "_TOV", "_MIN")
_PROVENANCE_PREFIXES = ("_PROV_",)


def _column_semantics(table: str, name: str) -> tuple[str, str]:
    table_key = str(table or "").lower()
    upper = str(name or "").upper()
    if table_key == "silver_salaries":
        if upper == "SALARY":
            return (
                "usd_dollars",
                "cap hit for the row's _season; payroll sums this after "
                "filtering rows to the requested _season",
            )
        if upper == "GUARANTEED":
            return (
                "usd_dollars",
                "remaining guaranteed salary in US dollars",
            )
        if _re_mod.fullmatch(r"SALARY_\d{4}_\d{2}", upper):
            label = f"{upper[7:11]}-{upper[12:14]}"
            return (
                "usd_dollars",
                f"contract-year salary for exactly {label}; use only for "
                "that requested year, never as a substitute for another year",
            )
    if table_key == "silver_leaders_pts":
        cumulative_units = {
            "PTS": ("total_points", "points"),
            "REB": ("total_rebounds", "rebounds"),
            "AST": ("total_assists", "assists"),
        }
        if upper in cumulative_units:
            unit, stat = cumulative_units[upper]
            note = (
                f"cumulative season {stat}; scripts/seed.py loads this table "
                "from nba_stats.leaders, whose LeagueLeaders endpoint defaults "
                "per_mode48 to PerMode48.default='Totals'"
            )
            return unit, note
    if table_key == "silver_prospect_stats" and upper == "USG":
        return (
            "pct",
            "usage rate in percentage points on a 0-100 scale, not a 0-1 fraction",
        )
    if table_key == "silver_hist_player_seasons":
        totals_units = {
            "PTS_TOTAL": (
                "total_points",
                "cumulative season points from upstream sportsdataverse totals slice",
            ),
            "REB_TOTAL": (
                "total_rebounds",
                "cumulative season rebounds from upstream sportsdataverse totals slice",
            ),
            "AST_TOTAL": (
                "total_assists",
                "cumulative season assists from upstream sportsdataverse totals slice",
            ),
            "GP_TOTAL": (
                "games",
                "games played associated with upstream sportsdataverse totals slice",
            ),
        }
        if upper in totals_units:
            return totals_units[upper]
        per_game_units = {
            "PTS": (
                "points_per_game",
                "per-game average; seed_player_season_stats.py stores "
                "regular-season rows filtered to per_mode='pergame', not "
                "cumulative totals",
            ),
            "REB": (
                "rebounds_per_game",
                "per-game average; seed_player_season_stats.py stores "
                "regular-season rows filtered to per_mode='pergame', not "
                "cumulative totals",
            ),
            "AST": (
                "assists_per_game",
                "per-game average; seed_player_season_stats.py stores "
                "regular-season rows filtered to per_mode='pergame', not "
                "cumulative totals",
            ),
        }
        if upper in per_game_units:
            return per_game_units[upper]
    if any(upper.startswith(prefix) for prefix in _PROVENANCE_PREFIXES):
        return ("provenance", "provenance column; never filter or group on it")
    if upper.startswith("_PROV") or upper in {"_SOURCE", "_FETCHED_AT", "_ENTITY"}:
        return ("provenance", "provenance column; never filter or group on it")
    if upper == "_SEASON":
        return ("season", "the season these rows describe; filter on this")
    for prefix, entry in _COLUMN_PREFIX_UNITS:
        if upper.endswith(prefix):
            return entry
    if upper in _COLUMN_UNITS:
        return _COLUMN_UNITS[upper]
    for suffix in _COLUMN_SUFFIXES:
        if upper.endswith(suffix):
            return (f"total_{suffix.lstrip('_').lower()}",
                    "season total, not per game")
    return ("", "")


def _warehouse_cache_key() -> str:
    store = _pkg().store
    return str(getattr(store, "DB_PATH", "") or "")


def _get_warehouse_schema() -> tuple[list[str], dict[str, dict[str, dict]]]:
    now = _time.monotonic()
    at = float(_schema_cache.get("at") or 0.0)
    if (now - at < _SCHEMA_TTL_S and _schema_cache.get("present")
            and _schema_cache.get("db") == _warehouse_cache_key()):
        _schema_cache_stats["hits"] += 1
        return (list(_schema_cache["present"]),
                {k: dict(v) for k, v in
                 _schema_cache["cols"].items()})
    _schema_cache_stats["misses"] += 1
    con = _pkg().store.connect(read_only=True)
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        present = [t for t in _SQL_TABLES if t in tables]
        cols: dict[str, dict[str, dict[str, str]]] = {}
        for t in present:
            cols[t] = {}
            for row in con.execute(
                    f"PRAGMA table_info({t})").fetchall():
                unit, note = _column_semantics(t, row[1])
                cols[t][row[1]] = {
                    "type": str(row[2]), "unit": unit, "note": note}
    finally:
        con.close()
    _schema_cache["at"] = now
    _schema_cache["db"] = _warehouse_cache_key()
    _schema_cache["present"] = present
    _schema_cache["cols"] = cols
    return (list(present),
            {k: dict(v) for k, v in cols.items()})


_SELECT_RE = _re_mod.compile(r"(?i)^\s*(select|with)\b")
_WRITE_RE = _re_mod.compile(
    r"(?i)\b(insert|update|delete|drop|alter|create|pragma|attach|copy|"
    r"vacuum|detach)\b")
_TABLE_REF_RE = _re_mod.compile(r"(?i)from\s+(\w+)|join\s+(\w+)")

_TABLE_FREE_UNSAFE_NODES = {
    "read_csv", "readcsv", "read_parquet", "read_json", "parquet_scan",
    "csv_scan", "json_scan", "sqlite_scan", "glob",
    "pragma_table_info", "read_blob", "read_text",
}


def _validate_readonly_sql(sql: str, present: set[str]) -> tuple[str, list[str]]:
    sql = (sql or "").strip().rstrip(";").strip()
    if not _SELECT_RE.match(sql):
        raise ValueError("only SELECT/WITH queries are allowed")
    if ";" in sql:
        raise ValueError("stacked statements are not allowed")
    if _WRITE_RE.search(sql):
        raise ValueError("write operations are not allowed")
    from sqlglot import exp as _sql_exp, parse_one as _parse_one
    from sqlglot.errors import ParseError as _ParseError
    from sqlglot.optimizer.scope import (
        Scope as _Scope,
        traverse_scope as _traverse_scope,
    )

    try:
        statement = _parse_one(sql, read="duckdb")
    except _ParseError as exc:
        raise ValueError("invalid SQL syntax") from exc
    present_by_lower = {name.lower(): name for name in present}
    used = set()
    for scope in _traverse_scope(statement):
        for source in scope.sources.values():
            if isinstance(source, _Scope):
                continue
            if (not isinstance(source, _sql_exp.Table) or source.db
                    or source.catalog or not source.name):
                raise ValueError("unknown or unavailable tables")
            used.add(present_by_lower.get(source.name.lower(), source.name))
    if not used:
        unsafe = {type(node).__name__.lower() for node in statement.walk()}
        unsafe |= {
            str(node.name).lower()
            for node in statement.walk()
            if isinstance(node, _sql_exp.Anonymous)
        }
        if unsafe & _TABLE_FREE_UNSAFE_NODES:
            raise ValueError("unknown or unavailable tables")
    elif not used.issubset(present):
        rejected = sorted(used - present)
        suffix = f": {', '.join(rejected)}" if rejected else ""
        raise ValueError(f"unknown or unavailable tables{suffix}")
    return sql, sorted(used)


def _attach_player_names(rows: list[dict]) -> None:
    if not rows:
        return
    has_pid = any("Player_ID" in r or "player_id" in r for r in rows)
    has_name = any(
        any(str(k).lower() in ("player", "player_name", "name")
            for k in r)
        for r in rows)
    if not has_pid or has_name:
        return
    for r in rows:
        pid = r.get("Player_ID", r.get("player_id"))
        if pid is None:
            continue
        try:
            r["PLAYER"] = _rname(int(pid), str(pid))
        except (TypeError, ValueError):
            pass


def _normalized_name_sql(column: str) -> str:
    ident = str(column or "").strip()
    if not _re_mod.fullmatch(
            r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)?", ident):
        raise ValueError("column must be a simple SQL identifier")
    return (
        "regexp_replace(regexp_replace(regexp_replace("
        f"lower(strip_accents(trim({ident}))), "
        "'[^a-z0-9\\s]', '', 'g'), "
        "'(?:\\s+(?:jr|sr|ii|iii|iv|v))+$', '', 'i'), "
        "'\\s+', '', 'g')"
    )


_SALARY_GUIDANCE = (
    "Salary rules. In silver_salaries, SALARY is the cap hit for the row's "
    "_season. Payroll for a season filters rows to that _season and sums "
    "SALARY. Use SALARY_YYYY_YY only when the user explicitly asks for that "
    "exact contract year and the column exists. If rows or the exact column "
    "for the requested year are absent, say salary for that year is "
    "unavailable instead of substituting another year.\n"
)

_NAME_JOIN_GUIDANCE = (
    "Player-name joins: use PLAYER_ID when both sides carry it. Otherwise "
    "write the canonical normalized comparison explicitly on both sides; "
    f"for PLAYER_NAME it is {_normalized_name_sql('PLAYER_NAME')}. SQL tools "
    "do not apply this rewrite automatically, so audit matched and unmatched "
    "row counts.\n"
)

_TEXT_TO_SQL_EXAMPLES = (
    "\nExamples.\nQ: Thunder record this season?\n"
    "SQL: SELECT WINS, LOSSES FROM silver_standings "
    "WHERE TeamCity = 'Oklahoma City' AND _season = '2025-26'\n"
    "Q: OKC wins per season, last 3 seasons?\n"
    "SQL: SELECT _season, SUM(CASE WHEN wl = 'W' THEN 1 ELSE 0 END) AS wins "
    "FROM silver_hist_gamelogs WHERE team_abbreviation = 'OKC' "
    "AND _season IN ('2025-26', '2024-25', '2023-24') GROUP BY _season\n"
    "Q: Which 5 teams have the highest total payroll?\n"
    "Note: silver_salaries.SALARY is the cap hit for the row's _season; "
    "filter rows to the asked season and sum SALARY for payroll.\n"
    "SQL: SELECT TEAM, SUM(SALARY) AS payroll FROM silver_salaries "
    "WHERE _season = '2026-27' GROUP BY TEAM ORDER BY payroll DESC LIMIT 5\n"
    "Q: Which team pays the most per win this season?\n"
    "Note: join payroll to wins on the team abbreviation; wins come from "
    "silver_team_games via split_part(MATCHUP, ' ', 1). LEFT JOIN so no "
    "team silently drops out of the comparison.\n"
    "SQL: SELECT s.TEAM, SUM(s.SALARY) AS payroll, "
    "COUNT(w.WL) AS games, SUM(CASE WHEN w.WL = 'W' THEN 1 ELSE 0 END) AS wins "
    "FROM silver_salaries s LEFT JOIN ("
    "SELECT split_part(MATCHUP, ' ', 1) AS TEAM, WL FROM silver_team_games "
    "WHERE _season = '2025-26') w ON w.TEAM = s.TEAM "
    "WHERE s._season = '2026-27' GROUP BY s.TEAM ORDER BY payroll DESC\n"
    "Q: Who has the best clutch FG% with at least 10 GP?\n"
    "SQL: SELECT PLAYER_NAME, FG_PCT FROM silver_clutch "
    "WHERE GP >= 10 ORDER BY FG_PCT DESC LIMIT 5\n"
    "Q: Which top-10 net-rating team plays fastest?\n"
    "SQL: SELECT TEAM_NAME, PACE, NET_RATING FROM silver_team_ratings "
    "WHERE NET_RATING_RANK <= 10 ORDER BY PACE DESC LIMIT 1\n"
    "Q: How strong is the supporting cast around Shai Gilgeous-Alexander on OKC?\n"
    "SQL: SELECT AVG(l.PTS * 1.0 / l.GP) AS cast_ppg, "
    "MAX(r.NET_RATING) AS net_rating, MAX(r.PACE) AS pace "
    "FROM silver_leaders_pts l JOIN silver_team_ratings r "
    "ON r._season = l._season "
    "WHERE l.TEAM = 'OKC' AND l.PLAYER <> 'Shai Gilgeous-Alexander' "
    "AND r.TEAM_NAME LIKE '%Oklahoma%' "
    "AND l._season = '2025-26' AND l.GP >= 10\n"
    "Q: Who has the most playoff wins in 2025-26?\n"
    "SQL: SELECT TEAM_ABBREVIATION, COUNT(*) AS wins FROM silver_playoffs "
    "WHERE WL = 'W' GROUP BY TEAM_ABBREVIATION ORDER BY wins DESC LIMIT 5\n"
    "Q: Who was drafted #1 overall in the June 2003 NBA draft?\n"
    "Note: DRAFT_YEAR is the June draft year.\n"
    "SQL: SELECT OVERALL_PICK, PLAYER_NAME, TEAM_ABBREVIATION FROM silver_hist_draft "
    "WHERE OVERALL_PICK = 1 AND DRAFT_YEAR = 2003\n"
    "Q: What was Michael Jordan's peak RAPTOR season?\n"
    "SQL: SELECT _season, RAPTOR_TOTAL, WAR_TOTAL FROM silver_raptor_player "
    "WHERE PLAYER_NAME = 'Michael Jordan' ORDER BY RAPTOR_TOTAL DESC LIMIT 1\n"
    "Q: What were LeBron James' per-game stats in 2023-24?\n"
    "Note: silver_hist_player_seasons stores per-game averages already; "
    "select PTS/MIN directly, never divide by GP. "
    "Season ints are end-years, so 2023-24 = SEASON 2024 = _season '2023-24'.\n"
    "SQL: SELECT PLAYER_NAME, TEAM_ABBREVIATION, GP, PTS, AST, TS_PCT, NET_RATING "
    "FROM silver_hist_player_seasons WHERE PLAYER_NAME = 'LeBron James' "
    "AND _season = '2023-24'\n"
    "Q: Which players under 24 averaged at least 15 points and 5 assists last season?\n"
    "Note silver_hist_player_seasons stores per-game averages with AGE, PTS, AST "
    "columns and season end-year ints.\n"
    "SQL: SELECT PLAYER_NAME, TEAM_ABBREVIATION, AGE, GP, PTS, AST "
    "FROM silver_hist_player_seasons WHERE AGE < 24 AND PTS >= 15 AND AST >= 5 "
    "AND SEASON = 2024 ORDER BY PTS DESC LIMIT 10\n"
    "Q: What were the best games in March 2026?\n"
    "Note: current-season per-game logs live in silver_player_gamelogs "
    "with UPPERCASE columns (PLAYER_NAME absent - join player ids via "
    "silver_leaders_pts.PLAYER_ID/PLAYER; GAME_DATE, MATCHUP, PTS). "
    "Dates look like 'Mar 30, 2026'; filter months with ILIKE, e.g. "
    "GAME_DATE ILIKE '%Mar%2026'. A 'no such column' error means "
    "wrong table/column spelling - retry with these names, it NEVER "
    "means the games are missing.\n"
    "SQL: SELECT p.PLAYER, g.GAME_DATE, g.MATCHUP, g.PTS FROM "
    "silver_player_gamelogs g JOIN silver_leaders_pts p ON "
    "p.PLAYER_ID = g.Player_ID AND p._season = g._season "
    "WHERE g._season = '2025-26' AND g.GAME_DATE ILIKE '%Mar%2026' "
    "ORDER BY g.PTS DESC LIMIT 10\n"
    "Q: Who led the 2025-26 season in steals?\n"
    "Note: season totals come from silver_leaders_* tables; "
    "never aggregate silver_player_gamelogs for season totals.\n"
    "SQL: SELECT PLAYER, STL FROM silver_leaders_stl "
    "WHERE _season = '2025-26' ORDER BY STL DESC LIMIT 1"
)


@tool(description='Answer a data question with SQL over warehouse tables. SELECT only.')
async def text_to_sql(question: str) -> dict[str, Any]:
    from langchain_core.messages import HumanMessage, SystemMessage

    from ...providers import invoke_with_fallback
    from ...query import _duplicate_output_error, _duplicate_output_name

    pkg = _pkg()
    present, cols = pkg._get_warehouse_schema()
    if not present:
        return {"tool": "text_to_sql", "ok": False, "error": "warehouse empty"}
    schema = pkg._describe_warehouse_schema(cols)
    feedback = ""
    for _ in range(2):
        try:
            resp = await invoke_with_fallback(
                "mistral", "ministral-8b-2512",
                [SystemMessage(content="Reply with SQL only, no prose."),
                 HumanMessage(
                      content="Write one SQLite SELECT using only these tables "
                      "and columns. Match column case exactly as listed.\n"
                      "Rules. Ratio/percentage leaderboards MUST add a "
                      "minimum-volume floor (AST/TOV: AST >= 300; shooting "
                      "pct: attempts >= 300) or the top row is a junk "
                      "small-sample slice. Season totals and season leaders questions MUST use "
                      "the silver_leaders_* tables directly; they hold final official "
                      "season totals. silver_player_gamelogs is an incomplete per-game "
                      "sample: never SUM it to compute season totals, and never join "
                      "per-game tables to leaders tables (fan-out inflates sums).\n"
                      f"{_SALARY_GUIDANCE}{_NAME_JOIN_GUIDANCE}"
                      f"Schema:\n{schema}{_TEXT_TO_SQL_EXAMPLES}\nQuestion: {question}{feedback}")])
            sql = _re_mod.sub(r"^```sql|```$", "", str(getattr(resp, "content", "") or ""),
                              flags=_re_mod.MULTILINE).strip()
        except Exception as exc:
            return {"tool": "text_to_sql", "ok": False, "error": str(exc)[:160]}
        if not _re_mod.match(r"(?i)^\s*select\b", sql) or _re_mod.search(
                r"(?i)\b(insert|update|delete|drop|alter|create|pragma|attach|copy)\b", sql):
            feedback = "\nPrevious reply was not a single SELECT. Reply with SQL only."
            continue
        try:
            sql, _validated_tables = pkg._validate_readonly_sql(sql, set(present))
        except ValueError as vexc:
            feedback = f"\nPrevious reply was rejected: {vexc}. Reply with SQL only."
            continue
        con = pkg.store.connect(read_only=True)
        try:
            rows = con.execute(sql).fetchall()
            names = [d[0] for d in con.description]
        except Exception as exc:
            feedback = f"\nPrevious SQL failed: {str(exc)[:200]} Fix it."
            continue
        finally:
            con.close()
        if not rows:
            feedback = (
                "\nPrevious SQL ran but returned 0 rows. "
                "A literal value is probably wrong. Query again with "
                "different literals or look at the table first "
                "(SELECT DISTINCT col FROM table LIMIT 20)."
            )
            continue
        duplicate = _duplicate_output_name(names)
        if duplicate is not None:
            feedback = (
                f"\nPrevious SQL failed: "
                f"{_duplicate_output_error(duplicate)} Fix it."
            )
            continue
        out_rows = [dict(zip(names, r)) for r in rows[:25]]
        _attach_player_names(out_rows)
        return {"tool": "text_to_sql", "ok": True,
                "rows": out_rows,
                "sql": sql,
                "meta": {"sql": sql[:500], "source": "warehouse",
                         **warehouse_identity_meta()}}
    return {"tool": "text_to_sql", "ok": False,
            "error": ("the warehouse query did not succeed after several "
                      "attempts; answer from results already gathered or "
                      "state plainly that it could not be computed")}


def _execute_with_timeout(con, sql: str, timeout_s: float):
    out: dict[str, Any] = {}

    def _run() -> None:
        try:
            rel = con.execute(sql)
            out["result"] = ([d[0] for d in con.description], rel.fetchall())
        except Exception as exc:
            out["error"] = exc

    th = _threading.Thread(target=_run, daemon=True)
    th.start()
    th.join(timeout_s)
    if th.is_alive():
        try:
            con.close()
        except Exception:
            pass
        raise TimeoutError(f"query exceeded {timeout_s:g}s")
    if "error" in out:
        raise out["error"]
    return out["result"]


async def rerun_sql(sql: str) -> dict[str, Any]:
    from ...query import _duplicate_output_error, _duplicate_output_name

    pkg = _pkg()
    sql = (sql or "").strip()
    con = pkg.store.connect(read_only=True)
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
    except Exception as exc:
        return {"tool": "rerun_sql", "ok": False,
                "error": str(exc)[:160]}
    finally:
        con.close()
    present = tables & set(pkg._SQL_TABLES)
    if not present:
        return {"tool": "rerun_sql", "ok": False,
                "error": "warehouse empty"}
    try:
        sql, validated_tables = pkg._validate_readonly_sql(sql, present)
    except ValueError as vexc:
        return {"tool": "rerun_sql", "ok": False, "error": str(vexc)[:160]}
    t0 = _time.time()
    con = pkg.store.connect(read_only=True)
    try:
        names, rows = pkg._execute_with_timeout(con, sql, RERUN_TIMEOUT_S)
    except Exception as exc:
        return {"tool": "rerun_sql", "ok": False, "error": str(exc)[:160],
                "sql": sql}
    finally:
        try:
            con.close()
        except Exception:
            pass
    duplicate = _duplicate_output_name(names)
    if duplicate is not None:
        return {"tool": "rerun_sql", "ok": False,
                "error": _duplicate_output_error(duplicate),
                "sql": sql}
    capped = len(rows) > RERUN_ROW_CAP
    return {"tool": "rerun_sql", "ok": True,
            "columns": names,
            "rows": [dict(zip(names, r)) for r in rows[:RERUN_ROW_CAP]],
            "tables": validated_tables,
            "sql": sql, "capped": capped,
            "ms": int((_time.time() - t0) * 1000)}
