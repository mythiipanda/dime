import difflib as _dl
from typing import Any

from langchain_core.tools import tool

from ...contracts import contract_details, resolve_salary_column, salary_records
from .._core import coerce_team_id
from ..competitive import _resolve_team_abbr
from ._helpers import _owned_connection, _pkg, _warehouse_tables

CAP = {"cap": 165_000_000, "tax": 201_048_000,
       "apron1": 209_661_000, "apron2": 222_372_000}


def _team_salary_lookup(con, name: str) -> str | None:
    pkg = _pkg()
    if not (pkg.season_static(pkg.last_completed_season())
            and "silver_salaries" in _warehouse_tables(con)):
        return None
    try:
        row = con.execute(
            "SELECT TEAM FROM silver_salaries "
            "WHERE LOWER(PLAYER_NAME) = LOWER(?) LIMIT 1", [name]).fetchone()
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
    target = str(team or "").upper()
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
                if str(_stale_candidate_team(cand, live)).upper() == target:
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
        return cname, str(cur or cteam).upper(), csal
    return None


def _norm_trade_teams(team_a: str, team_b: str) -> tuple[str, str] | None:
    a = _resolve_team_abbr(team_a) or str(team_a or "").strip().upper()
    b = _resolve_team_abbr(team_b) or str(team_b or "").strip().upper()
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
    if new_team == str(old_team).upper():
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


def _payroll(team: str, con: object = None,
             season: str | None = None) -> tuple[int, list[dict]]:
    own = con is None
    if own:
        con = _pkg().store.connect()
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        if "silver_salaries" in tables:
            scols = [r[1] for r in con.execute(
                "PRAGMA table_info(silver_salaries)").fetchall()]
            scol = _resolve_salary_column(set(scols), season)
            if not scol:
                raise SalaryColumnError(
                    "salary_column_unmatched",
                    f"silver_salaries has no salary column for season "
                    f"{season or 'unknown'}")
            records = [r for r in salary_records(con, salary_season=season) if str(r['TEAM']).upper() == team.upper()]
            rows = [(r['PLAYER_NAME'], r['salary']) for r in records]
            if rows:
                players = [{"player": r['PLAYER_NAME'], "salary": r['salary'],
                            **contract_details(r)} for r in records]
                return sum(r[1] or 0 for r in rows), players
        if "silver_cap_players" in tables:
            rows = con.execute(
                """SELECT player, salary FROM silver_cap_players
                WHERE team = ?""",
                [team.upper()],
            ).fetchall()
        else:
            rows = []
    finally:
        if own:
            con.close()
    players = [{"player": r[0], "salary": r[1], **contract_details(None)} for r in rows]
    return sum(r[1] or 0 for r in rows), players


def _apron_state(payroll: int) -> dict[str, object]:
    return {
        "over_tax": payroll > CAP["tax"],
        "over_apron1": payroll > CAP["apron1"],
        "over_apron2": payroll > CAP["apron2"],
        "room_apron1": CAP["apron1"] - payroll,
        "room_apron2": CAP["apron2"] - payroll,
    }


def _allowed_incoming(outgoing: int, over_apron1: bool,
                      cap_room: int = 0) -> tuple[int, str]:
    if over_apron1:
        return outgoing, "100% (above the first apron)"
    matched = int(outgoing * 1.25 + 250_000)
    if cap_room > 0 and outgoing + cap_room + 250_000 > matched:
        return outgoing + cap_room + 250_000, "cap room plus outgoing salary plus $250k (under the cap)"
    return matched, "125% plus $250k (below the first apron)"


def _outgoing_needed(incoming: int, over_apron1: bool,
                     cap_room: int = 0) -> int:
    if over_apron1:
        return incoming
    by_room = incoming - cap_room - 250_000 if cap_room > 0 else incoming
    return max(0, min(-(-(incoming - 250_000) * 4 // 5), by_room))


def _salary_vintage(con: object = None) -> tuple[str, int, str | None]:
    own = con is None
    if own:
        con = _pkg().store.connect()
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        if "silver_salaries" not in tables:
            return "", 0, None
        row = con.execute(
            "SELECT _season, COUNT(*), MAX(_fetched_at) FROM silver_salaries "
            "GROUP BY _season ORDER BY COUNT(*) DESC LIMIT 1"
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
        con = _pkg().store.connect()
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
        con = _pkg().store.connect()
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


@tool(description='Payroll plus apron room for one abbreviation. 2026-27 thresholds.')
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
                "error": f"unknown team: {team}"}
    con = _pkg().store.connect()
    try:
        try:
            total, players = _payroll(team, con)
        except SalaryColumnError as exc:
            return {"tool": "get_cap_ledger", "ok": False,
                    "reason": exc.reason, "error": str(exc)}
        source = _payroll_source(con)
        salary_date = _salary_date(con)
        season, _, _ = _salary_vintage(con)
    finally:
        con.close()
    return {"tool": "get_cap_ledger", "ok": True,
            "rows": {"team": team.upper(), "payroll": total,
                     "players": sorted(players, key=lambda p: p["salary"] or 0,
                                       reverse=True),
                     "room_under_apron2": CAP["apron2"] - total,
                     "over_tax": total > CAP["tax"]},
            "meta": {"source": source, "season": season or "2026-27",
                     "salary_date": salary_date,
                     **{k: v for k, v in CAP.items()}}}


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
        _, roster = _payroll(team, live, season)
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
        con2 = _pkg().store.connect() if own else con
        try:
            for u in unknown:
                base = u.split(" (suggestions")[0].strip()
                bits = [b for b in base.split() if len(b) > 1]
                like = "%" + "%".join(bits[:2]) + "%" if bits else base
                hit = con2.execute(
                    """SELECT TEAM, PLAYER_NAME FROM silver_salaries
                    WHERE PLAYER_NAME LIKE ? LIMIT 1""",
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
