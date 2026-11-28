import difflib as _dl
from typing import Any

from langchain_core.tools import tool

from ...contracts import canonical_team_abbr, contract_details, resolve_salary_column, salary_records
from .._core import coerce_team_id, team_error_message, warehouse_identity_meta
from ..competitive import _resolve_team_abbr
from ._helpers import _owned_connection, _pkg, _warehouse_tables, declare_money
from .cba_two_way import (
    explicit_two_way_record,
    inferred_dead_entry,
    payroll_evidence_season,
    two_way_state_for_record,
    two_way_states,
)

from ..cap_rules import (
    CAP,
    EXPANDED_TPE_CUSHION as _EXPANDED_TPE_CUSHION,
    EXPANDED_TPE_LOW_MAX as _EXPANDED_TPE_LOW_MAX,
    EXPANDED_TPE_MID_MAX as _EXPANDED_TPE_MID_MAX,
    allowed_incoming as _allowed_incoming,
    apron_state as _apron_state,
    hard_cap_consequences as _hard_cap_consequences,
    matching_election as _matching_election,
    operative_match_rule as _operative_match_rule,
    payroll_proxy_meta as _payroll_proxy_meta,
    used_expanded_matching as _used_expanded_matching,
)


_CAP_ROW_UNITS = {
    "payroll": "usd_dollars",
    "cap_room": "usd_dollars",
    "room_under_apron2": "usd_dollars",
}


def _team_salary_lookup(con, name: str) -> str | None:
    pkg = _pkg()
    if not (pkg.season_static(pkg.last_completed_season())
            and "silver_salaries" in _warehouse_tables(con)):
        return None
    try:
        scols = {r[1] for r in con.execute("PRAGMA table_info(silver_salaries)").fetchall()}
        order = " ORDER BY CASE WHEN ROW_KIND = 'roster' THEN 0 ELSE 1 END" if "ROW_KIND" in scols else ""
        row = con.execute(
            "SELECT TEAM FROM silver_salaries "
            "WHERE LOWER(PLAYER_NAME) = LOWER(?)" + order + " LIMIT 1", [name]).fetchone()
    except Exception:
        return None
    return str(row[0]) if row and row[0] else None


def _team_leaders_lookup(con, name: str, tables: set[str]) -> str | None:
    if not name or "silver_leaders_pts" not in tables:
        return None
    try:
        row = con.execute(
            "SELECT TEAM FROM silver_leaders_pts "
            "WHERE _season = ? AND LOWER(PLAYER) = LOWER(?) LIMIT 1",
            [_pkg().last_completed_season(), name]).fetchone()
    except Exception:
        return None
    return str(row[0]) if row and row[0] else None


def _player_id_lookup(con, name: str, tables: set[str]) -> object:
    if not name or "silver_leaders_pts" not in tables:
        return None
    try:
        found = con.execute(
            "SELECT PLAYER_ID FROM silver_leaders_pts "
            "WHERE LOWER(PLAYER) = LOWER(?) LIMIT 1", [name]).fetchone()
    except Exception:
        return None
    return int(found[0]) if found and found[0] is not None else None


def _gamelog_team_lookup(con, pid: object, tables: set[str]) -> str | None:
    if pid is None or "silver_player_gamelogs" not in tables:
        return None
    for where, params in (
            ("Player_ID = ? AND _season = ?", [pid, _pkg().last_completed_season()]),
            ("Player_ID = ?", [pid])):
        try:
            row = con.execute(
                f"SELECT MATCHUP FROM silver_player_gamelogs "
                f"WHERE {where} LIMIT 1", params).fetchone()
        except Exception:
            row = None
        if row and row[0]:
            return str(row[0]).split()[0].upper()
        if row:
            break
    return None


def _current_team_for_player(
    player_name: str, player_id: object = None, fallback: str = "",
    con: object = None,
) -> str:
    name = str(player_name or "").strip()
    try:
        with _owned_connection(con) as live:
            tables = _warehouse_tables(live)
            for found in (_team_salary_lookup(live, name),
                          _team_leaders_lookup(live, name, tables)):
                if found:
                    return found
            pid = player_id
            if pid is None:
                pid = _player_id_lookup(live, name, tables)
            abbr = _gamelog_team_lookup(live, pid, tables)
            if abbr:
                return abbr
    except Exception:
        return fallback
    return fallback


def _first_name_compatible(want: str, cand: str) -> bool:
    a = (want or "").lower().strip()
    b = (cand or "").lower().strip()
    if not a or not b:
        return False
    if a == b:
        return True
    if len(a) >= 4 and b.startswith(a):
        return True
    if len(b) >= 4 and a.startswith(b):
        return True
    return _dl.SequenceMatcher(None, a, b).ratio() >= 0.9


def _salary_sheet_rows(con: object, season: str | None = None) -> list | None:
    try:
        if "silver_salaries" not in _warehouse_tables(con):
            return None
        columns = {r[1] for r in con.execute('PRAGMA table_info(silver_salaries)').fetchall()}
        if season is None and '_season' in columns:
            season = con.execute('SELECT MAX(_season) FROM silver_salaries').fetchone()[0]
        return [(r['PLAYER_NAME'], r['salary'], r['TEAM']) for r in salary_records(con, salary_season=season)]
    except Exception:
        return None


def _name_match_tiers(rows: list, wl: str) -> tuple[list, list, list]:
    exact = [r for r in rows if str(r[0]).lower() == wl]
    subs = [r for r in rows if wl in str(r[0]).lower() and r not in exact]
    lows = [str(r[0]).lower() for r in rows]
    try:
        fuzzy = [r for m in _dl.get_close_matches(wl, lows, n=3, cutoff=0.8)
                 for r in rows
                 if str(r[0]).lower() == m and r not in exact and r not in subs]
    except Exception:
        fuzzy = []
    return exact, subs, fuzzy


def _stale_candidate_team(cand: tuple, con: object) -> str:
    cname, cteam = str(cand[0]), str(cand[2] or "")
    try:
        return _current_team_for_player(cname, None, cteam, con)
    except Exception:
        return cteam


def _resolve_stale_trade_player(want: str, team: str,
                                con: object = None) -> tuple[str, int] | None:
    target = canonical_team_abbr(team)
    w = str(want or "").strip()
    if not w or not target:
        return None
    try:
        with _owned_connection(con) as live:
            rows = _salary_sheet_rows(live)
            if rows is None:
                return None
            wl = w.lower()
            exact, subs, fuzzy = _name_match_tiers(rows, wl)
            wl_first = wl.split()[0] if wl.split() else ""
            strict = len(exact) + len(subs)
            for i, cand in enumerate(exact + subs + fuzzy):
                cname = str(cand[0])
                if i >= strict:
                    c_first = cname.lower().split()[0] if cname.split() else ""
                    if not _first_name_compatible(wl_first, c_first):
                        continue
                if canonical_team_abbr(_stale_candidate_team(cand, live)) == target:
                    return cname, int(cand[1] or 0)
    except Exception:
        return None
    return None


def _first_token(text: str) -> str:
    parts = str(text or "").lower().split()
    return parts[0] if parts else ""


def _locate_player_team(name: str, con: object, season: str | None = None) -> tuple[str, str, int] | None:
    w = str(name or "").strip().lower()
    if not w:
        return None
    rows = _salary_sheet_rows(con, season)
    if rows is None:
        return None
    exact, subs, loose = _name_match_tiers(rows, w)
    fuzzy = [r for r in loose
             if _first_name_compatible(_first_token(w), _first_token(str(r[0])))]
    for cand in (exact + subs + fuzzy)[:1]:
        cname, csal, cteam = str(cand[0]), int(cand[1] or 0), str(cand[2] or "")
        cur = _stale_candidate_team(cand, con)
        return cname, canonical_team_abbr(cur or cteam), csal
    return None


def _norm_trade_teams(team_a: str, team_b: str) -> tuple[str, str] | None:
    a = canonical_team_abbr(_resolve_team_abbr(team_a) or team_a)
    b = canonical_team_abbr(_resolve_team_abbr(team_b) or team_b)
    if a and b and a == b:
        return None
    return a, b


def _auto_correct_side(unks: list[str], old_team: str, plist: str,
                       con: object, season: str | None = None):
    located = []
    for u in unks:
        base = u.split(" (suggestions")[0].strip()
        hit = _locate_player_team(base, con)
        if hit is None:
            return None
        located.append((base,) + hit)
    new_teams = {t for _, _, t, _ in located}
    if len(new_teams) != 1:
        return None
    new_team = new_teams.pop()
    if canonical_team_abbr(new_team) == canonical_team_abbr(old_team):
        return None
    matched = _match_trade_players(new_team, plist, con, season)
    corrections = [
        f"{cname} is on {t} per the 2026-27 salary sheet "
        f"(not {str(old_team).upper()}); computed for the corrected team"
        for base, cname, t, _s in located
    ]
    return new_team, matched, corrections


class SalaryColumnError(RuntimeError):
    def __init__(self, reason: str, detail: str) -> None:
        self.reason = reason
        super().__init__(detail)


def _resolve_salary_column(scols: set[str], season: str | None) -> str:
    return resolve_salary_column(scols, season)


def _salary_column_or_raise(scols: list[str], season: str | None) -> str:
    scol = _resolve_salary_column(set(scols), season)
    if scol:
        return scol
    raise SalaryColumnError(
        "salary_column_unmatched",
        f"silver_salaries has no salary column for season {season or 'unknown'}")


def _season_record_team(row: dict, con: object, season: str | None,
                        tables: set[str], cache: dict[str, str]) -> str:
    name = str(row.get('PLAYER_NAME') or '')
    if not season:
        return str(row.get('TEAM') or '')
    key = name.lower()
    if key not in cache:
        cache[key] = (_season_player_team(con, name, season, tables)
                      or str(row.get('TEAM') or ''))
    return cache[key]


def _collect_salary_payroll(records: list[dict], con: object, team_code: str,
                            season: str | None, tables: set[str],
                            evidence_season: str | None) -> tuple[list, list[dict], list[dict]]:
    states_by_player = two_way_states(con, evidence_season, tables)
    team_cache: dict[str, str] = {}
    rows = []
    players = []
    inferred_dead = []
    for row in records:
        name = str(row.get('PLAYER_NAME') or '')
        row_team = canonical_team_abbr(row.get('TEAM'))
        state = two_way_state_for_record(states_by_player, name, row.get('PLAYER_ID'))
        if explicit_two_way_record(row) or (state and state.get("active_team")):
            entry = inferred_dead_entry(row, state, row_team, evidence_season)
            if entry is not None:
                inferred_dead.append(entry)
            continue
        record_team = _season_record_team(row, con, season, tables, team_cache)
        salary = row.get('salary')
        if canonical_team_abbr(record_team) != team_code or salary is None:
            continue
        rows.append((row['PLAYER_NAME'], salary))
        players.append({"player": row['PLAYER_NAME'], "salary": salary,
                        "team": record_team, **contract_details(row)})
    return rows, players, inferred_dead


def _explicit_dead_rows(con: object, scols: list[str], scol: str,
                        team_code: str) -> list[dict]:
    if "ROW_KIND" not in scols:
        return []
    try:
        rows = con.execute(
            "SELECT PLAYER_NAME, TEAM, " + scol + " FROM silver_salaries "
            "WHERE ROW_KIND = 'dead_money' AND UPPER(TEAM) = UPPER(?)",
            [team_code]).fetchall()
    except Exception:
        return []
    return [{"player": str(row[0]), "salary": row[2], "team": str(row[1])}
            for row in rows if row[2] is not None]


def _dead_key(row: dict) -> tuple[str, str, int]:
    try:
        salary = int(row.get("salary") or 0)
    except (TypeError, ValueError):
        salary = 0
    return (str(row.get("player") or "").lower(),
            canonical_team_abbr(row.get("team")), salary)


def _merge_dead_rows(explicit: list[dict], inferred: list[dict],
                     team_code: str) -> list[dict]:
    dead = list(explicit)
    seen = {_dead_key(row) for row in dead}
    for row in inferred:
        key = _dead_key(row)
        if canonical_team_abbr(row.get("team")) == team_code and key not in seen:
            dead.append(row)
            seen.add(key)
    return dead


def _silver_salary_payroll(con: object, team_code: str, season: str | None,
                           tables: set[str]) -> tuple[int, list[dict], list[dict]] | None:
    scols = [r[1] for r in con.execute("PRAGMA table_info(silver_salaries)").fetchall()]
    scol = _salary_column_or_raise(scols, season)
    records = salary_records(con, salary_season=season)
    if not records:
        return None
    evidence_season = payroll_evidence_season(records, scol, season)
    rows, players, inferred = _collect_salary_payroll(
        records, con, team_code, season, tables, evidence_season)
    explicit = _explicit_dead_rows(con, scols, scol, team_code)
    dead = _merge_dead_rows(explicit, inferred, team_code)
    dead_total = sum(row["salary"] or 0 for row in dead)
    return sum(row[1] or 0 for row in rows) + dead_total, players, dead


def _payroll(team: str, con: object = None,
             season: str | None = None) -> tuple[int, list[dict], list[dict]]:
    own = con is None
    if own:
        con = _pkg().store.connect(read_only=True)
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        team_code = canonical_team_abbr(team)
        if "silver_salaries" in tables:
            result = _silver_salary_payroll(con, team_code, season, tables)
            if result is not None:
                return result
        if "silver_cap_players" in tables:
            cap_rows = con.execute(
                "SELECT player, salary, team FROM silver_cap_players").fetchall()
            rows = [(r[0], r[1]) for r in cap_rows
                    if canonical_team_abbr(r[2]) == team_code]
        else:
            rows = []
    finally:
        if own:
            con.close()
    players = [{"player": r[0], "salary": r[1], **contract_details(None)} for r in rows]
    return sum(r[1] or 0 for r in rows), players, []


def _outgoing_needed(incoming: int, over_apron1: bool,
                     cap_room: int = 0) -> int:
    if incoming <= 0:
        return 0
    if over_apron1:
        return incoming
    if cap_room > 0 and incoming <= cap_room + 250_000:
        return 0
    candidates: list[int] = []
    tier1 = max(1, -(-(incoming - 250_000) // 2))
    if tier1 <= _EXPANDED_TPE_LOW_MAX:
        candidates.append(tier1)
    tier2 = incoming - _EXPANDED_TPE_CUSHION
    if _EXPANDED_TPE_LOW_MAX < tier2 <= _EXPANDED_TPE_MID_MAX:
        candidates.append(tier2)
    tier3 = -(-(incoming - 250_000) * 4 // 5)
    if tier3 > _EXPANDED_TPE_MID_MAX:
        candidates.append(tier3)
    needed = min(candidates) if candidates else 0
    if cap_room > 0:
        room_needed = max(1, incoming - cap_room - 250_000)
        needed = min(needed, room_needed) if needed else room_needed
    return needed


def _season_player_team(con: object, name: str, season: str,
                        tables: set[str] | None = None) -> str | None:
    if tables is None:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
    lookups = (
        ("silver_leaders_pts", "PLAYER", "TEAM"),
        ("silver_player_season", "PLAYER", "TEAM"),
        ("silver_hist_player_seasons", "player_name", "team_abbreviation"),
    )
    for table, name_col, team_col in lookups:
        if table not in tables:
            continue
        try:
            row = con.execute(
                f"SELECT {team_col} FROM {table} WHERE _season = ? "
                f"AND lower({name_col}) = lower(?) "
                f"AND upper({team_col}) <> 'TOT' LIMIT 1",
                [season, name]).fetchone()
        except Exception:
            row = None
        if row and row[0]:
            return canonical_team_abbr(row[0])
    return None


def _salary_vintage(con: object = None) -> tuple[str, int, str | None]:
    own = con is None
    if own:
        con = _pkg().store.connect(read_only=True)
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        if "silver_salaries" not in tables:
            return "", 0, None
        row = con.execute(
            "SELECT _season, COUNT(*), MAX(_fetched_at) FROM silver_salaries "
            "GROUP BY _season ORDER BY _season DESC NULLS LAST, "
            "COUNT(*) DESC LIMIT 1"
        ).fetchone()
        if not row:
            return "", 0, None
        return str(row[0] or ""), int(row[1] or 0), row[2]
    except Exception:
        return "", 0, None
    finally:
        if own:
            con.close()


def _payroll_source(con: object = None) -> str:
    own = con is None
    if own:
        con = _pkg().store.connect(read_only=True)
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        if "silver_salaries" in tables:
            season, n, fetched = _salary_vintage(con)
            if n > 300 and season:
                date = f", fetched {str(fetched)[:10]}" if fetched else ""
                return (f"basketball-reference contracts "
                        f"({season} salaries{date}; "
                        f"some players missing or estimated)")
    finally:
        if own:
            con.close()
    return "orojas119/nba-salary-cap (estimated)"


def _salary_date(con: object = None) -> str | None:
    own = con is None
    if own:
        con = _pkg().store.connect(read_only=True)
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        for table in ("silver_salaries", "silver_cap_players"):
            if table not in tables:
                continue
            cols = [r[1] for r in con.execute(f"PRAGMA table_info({table})").fetchall()]
            if "_fetched_at" not in cols:
                continue
            row = con.execute(f"SELECT MAX(_fetched_at) FROM {table}").fetchone()
            if row and row[0]:
                return str(row[0])
    except Exception:
        return None
    finally:
        if own:
            con.close()
    return None


@tool(description='Payroll plus apron room for one abbreviation, on the salary-ledger basis. 2026-27 thresholds. Any all-30-teams sweep or league-wide analysis is ONE sql_exec over the warehouse table the ask names (or silver_cap_room for committed-salary audits), never per-team calls of this tool. Never answer a league-wide payroll-tier, committed-salary, over-tax or over-apron audit from this tool: those audits are ONE sql_exec over silver_cap_room unless the ask names a specific table — a named table is authoritative (COMMITTED_SALARY plus the projected cap/tax/apron lines per team), and the payroll basis here differs, so per-team fanout totals produce wrong tier counts — not a data gap. Team-level only, no player salaries: an individual player salary lives in silver_salaries (PLAYER_NAME, TEAM, SALARY for the row-season cap hit; SALARY_YYYY_YY only for that exact contract year), and trade legality or matching-band math for a named swap goes to get_trade_check, which already returns both sides salaries, the ceiling and the verdict.')
def get_cap_ledger(team: str = "") -> dict[str, Any]:
    if not team:
        return {"tool": "get_cap_ledger", "ok": False, "error": "team needed"}
    from nba_api.stats.static import teams as _teams
    try:
        team_id = coerce_team_id(team)
        team = next(
            item["abbreviation"] for item in _teams.get_teams()
            if item["id"] == team_id)
    except (ValueError, StopIteration):
        return {"tool": "get_cap_ledger", "ok": False,
                "error": team_error_message(team)}
    con = _pkg().store.connect(read_only=True)
    try:
        try:
            total, players, dead = _payroll(team, con)
        except SalaryColumnError as exc:
            return {"tool": "get_cap_ledger", "ok": False,
                    "reason": exc.reason, "error": str(exc)}
        source = _payroll_source(con)
        salary_date = _salary_date(con)
        season, _, _ = _salary_vintage(con)
    finally:
        con.close()
    dead_total = sum(d["salary"] or 0 for d in dead)
    result = {"tool": "get_cap_ledger", "ok": True,
            "rows": {"team": team.upper(), "payroll": total,
                     "roster_payroll": total - dead_total,
                     "dead_money": dead_total,
                     "dead_money_detail": sorted(dead, key=lambda d: d["salary"] or 0, reverse=True),
                     "players": sorted(players, key=lambda p: p["salary"] or 0,
                                       reverse=True),
                     "room_under_apron2": CAP["apron2"] - total,
                     "over_tax": total > CAP["tax"]},
            "units": _CAP_ROW_UNITS,
            "meta": {"source": source, "season": season or "2026-27",
                     **warehouse_identity_meta(),
                     "salary_date": salary_date,
                     **_payroll_proxy_meta(),
                     **{k: v for k, v in CAP.items()}}}
    return declare_money(result, ["payroll", "room_under_apron2", "salary", "remaining_guaranteed"])


@tool(description='League-wide payroll, tax position, and apron room for all 30 teams, ranked by payroll, on the salary-ledger basis. 2026-27 thresholds. For committed-salary audits or over-the-line scans against the projected cap/tax/apron lines, use silver_cap_room via sql_exec instead — its COMMITTED_SALARY basis differs from this payroll total. Requested-season payroll must use salary coverage for that exact season; when coverage is absent, report that season unavailable or surface salary_column_unmatched instead of substituting another year. Team-level only, no player salaries: an individual player salary lives in silver_salaries, and trade legality or matching-band math goes to get_trade_check.')
def get_cap_table(season: str | None = None) -> dict[str, Any]:
    from nba_api.stats.static import teams as _teams
    con = _pkg().store.connect(read_only=True)
    try:
        rows = []
        missing = []
        for item in _teams.get_teams():
            abbr = str(item["abbreviation"]).upper()
            try:
                total, _players, dead = _payroll(abbr, con, season)
            except SalaryColumnError as exc:
                return {"tool": "get_cap_table", "ok": False,
                        "reason": exc.reason, "error": str(exc)}
            except Exception as exc:
                missing.append({"team": abbr, "error": str(exc)[:200]})
                continue
            dead_total = sum(d["salary"] or 0 for d in dead)
            rows.append({"team": abbr, "payroll": total,
                         "roster_payroll": total - dead_total,
                         "dead_money": dead_total,
                         "cap_room": CAP["cap"] - total,
                         "room_under_apron2": CAP["apron2"] - total,
                         "over_tax": total > CAP["tax"],
                         "over_apron1": total > CAP["apron1"],
                         "over_apron2": total > CAP["apron2"]})
        source = _payroll_source(con)
        salary_date = _salary_date(con)
        season_used, _, _ = _salary_vintage(con)
    finally:
        con.close()
    rows.sort(key=lambda r: r["payroll"], reverse=True)
    res = {"tool": "get_cap_table", "ok": True,
           "rows": rows,
           "units": _CAP_ROW_UNITS,
           "meta": {"source": source, "season": season or season_used or "2026-27",
                    **warehouse_identity_meta(),
                    "salary_date": salary_date,
                    **_payroll_proxy_meta(),
                    **{k: v for k, v in CAP.items()}}}
    if missing:
        res["meta"]["missing_teams"] = missing
    return declare_money(res, ["payroll", "cap_room", "room_under_apron2"])


class _RosterIndex:

    __slots__ = ("roster", "lows", "by_low", "disp")

    def __init__(self, roster: list[dict]) -> None:
        self.roster = roster
        self.lows = [p["player"].lower() for p in roster]
        self.by_low = {p["player"].lower(): p for p in roster}
        self.disp = {p["player"].lower(): p["player"] for p in roster}

    def close_hit(self, w: str) -> dict | None:
        hit = next((p for p in self.roster if w in p["player"].lower()), None)
        if hit is not None:
            return hit
        fb = _dl.get_close_matches(w, self.lows, n=1, cutoff=0.8)
        if fb and _first_name_compatible(_first_token(w), _first_token(fb[0])):
            return self.by_low[fb[0]]
        return None

    def suggestions(self, w: str) -> list[str]:
        return [self.disp[s]
                for s in _dl.get_close_matches(w, self.lows, n=2, cutoff=0.6)
                if _first_name_compatible(_first_token(w), _first_token(s))]


def _match_trade_player(orig: str, team: str, index: _RosterIndex,
                        con: object) -> tuple[str, int] | None:
    hit = index.close_hit(orig.lower())
    if hit:
        return hit["player"], hit["salary"] or 0
    return _resolve_stale_trade_player(orig, team, con)


def _unknown_trade_name(orig: str, index: _RosterIndex) -> str:
    sug = index.suggestions(orig.lower())
    return f"{orig} (suggestions: {', '.join(sug)})" if sug else orig


def _match_trade_players(team: str, names: str,
                         con: object = None,
                         season: str | None = None) -> tuple[int, list[str], list[str]]:
    with _owned_connection(con) as live:
        _, roster, _dead = _payroll(team, live, season)
        index = _RosterIndex(roster)
        matched: list[str] = []
        unknown: list[str] = []
        total_out = 0
        for orig in [n.strip() for n in names.split(",") if n.strip()]:
            found = _match_trade_player(orig, team, index, live)
            if found:
                matched.append(found[0])
                total_out += found[1]
            else:
                unknown.append(_unknown_trade_name(orig, index))
    return total_out, matched, unknown


def _unknown_player_hints(unknown: list[str], con: object = None) -> list[str]:
    hints: list[str] = []
    own = con is None
    try:
        con2 = _pkg().store.connect(read_only=True) if own else con
        try:
            for u in unknown:
                base = u.split(" (suggestions")[0].strip()
                bits = [b for b in base.split() if len(b) > 1]
                like = "%" + "%".join(bits[:2]) + "%" if bits else base
                try:
                    scols2 = {r[1] for r in con2.execute("PRAGMA table_info(silver_salaries)").fetchall()}
                except Exception:
                    scols2 = set()
                order2 = " ORDER BY CASE WHEN ROW_KIND = 'roster' THEN 0 ELSE 1 END" if "ROW_KIND" in scols2 else ""
                hit = con2.execute(
                    """SELECT TEAM, PLAYER_NAME FROM silver_salaries
                    WHERE PLAYER_NAME LIKE ?""" + order2 + " LIMIT 1",
                    [like],
                ).fetchone()
                if hit:
                    try:
                        cur = _current_team_for_player(
                            str(hit[1]), None, str(hit[0]), con2)
                    except Exception:
                        cur = hit[0]
                    hints.append(f"{base} is on {cur} per salary data")
        finally:
            if own:
                con2.close()
    except Exception:
        pass
    return hints
