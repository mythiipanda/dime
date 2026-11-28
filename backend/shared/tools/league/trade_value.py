import itertools as _it
import re as _re
from typing import Any

from langchain_core.tools import tool

from ...contracts import canonical_team_abbr, contract_details, match_record, normalize_name, salary_records
from ._helpers import _owned_connection, _pkg, _warehouse_tables, declare_money, declare_units
from .cba_cap import (
    CAP,
    SalaryColumnError,
    _allowed_incoming,
    _outgoing_needed,
    _apron_state,
    _auto_correct_side,
    _hard_cap_consequences,
    _locate_player_team,
    _match_trade_players,
    _matching_election,
    _norm_trade_teams,
    _operative_match_rule,
    _payroll,
    _payroll_proxy_meta,
    _payroll_source,
    _salary_date,
    _season_player_team,
    _salary_vintage,
    _unknown_player_hints,
    _used_expanded_matching,
)

PICK_VALUE_M: dict[int, float] = {
    1: 45.0, 2: 38.0, 3: 32.0, 4: 28.0, 5: 25.0,
    6: 18.0, 7: 18.0, 8: 18.0, 9: 18.0, 10: 18.0,
    11: 12.0, 12: 12.0, 13: 12.0, 14: 12.0,
    15: 8.0, 16: 8.0, 17: 8.0, 18: 8.0, 19: 8.0, 20: 8.0,
    21: 5.0, 22: 5.0, 23: 5.0, 24: 5.0, 25: 5.0,
    26: 5.0, 27: 5.0, 28: 5.0, 29: 5.0, 30: 5.0,
}


def _pick_value_for_slot(slot: int, is_frp: bool,
                         curve_m: dict[int, float] | None = None) -> float:
    if curve_m is not None and slot in curve_m:
        return curve_m[slot]
    if is_frp:
        return PICK_VALUE_M.get(max(1, min(slot, 30)), 5.0)
    if 31 <= slot <= 40:
        return 2.5
    return 1.0


def _draft_value_curve_m(con) -> dict[int, float] | None:
    try:
        rows = con.execute(
            "select SLOT, VALUE_INDEX from silver_draft_value_curve "
            "where _season = '2026-27'").fetchall()
    except Exception:
        return None
    if not rows:
        return None
    return {int(slot): round(float(idx) * PICK_VALUE_M[1], 1)
            for slot, idx in rows if idx is not None}


_TRADE_CHECK_UNMODELED = (
    "cash in trade", "prior trade exceptions", "taxpayer midlevel hard cap",
    "frozen pick plus Stepien",
    "base-year plus trade-kicker plus minimum-salary plus sign-and-trade",
)


def _trade_guard_vintage_error(con, season: str) -> str | None:
    cols = {r[1] for r in con.execute(
        "PRAGMA table_info(silver_salaries)").fetchall()}
    explicit = sorted(c for c in cols
                      if _re.fullmatch(r"SALARY_\d{4}_\d{2}", c))
    if explicit:
        wanted = "SALARY_" + str(season).replace("-", "_")
        if wanted in cols:
            return None
        labels = sorted(c[7:].replace("_", "-") for c in explicit)
        shown = labels[0] if len(labels) == 1 else ", ".join(labels)
        return (f"salary data covers {shown}, not {season}; "
                "trade math was not calculated")
    if season and "silver_salaries" in _warehouse_tables(con):
        columns = {r[1] for r in con.execute(
            "PRAGMA table_info(silver_salaries)").fetchall()}
        if "SALARY_" + season.replace("-", "_") in columns:
            return None
        vintages = sorted(
            c[len("SALARY_"):].replace("_", "-") for c in columns
            if _re.fullmatch(r"SALARY_\d{4}_\d{2}", c))
        if vintages:
            label = vintages[0] if len(vintages) == 1 else (
                f"{vintages[0]}..{vintages[-1]}")
            return (f"salary data covers {label}, not {season}; "
                    "trade math was not calculated")
    salary_season, salary_rows, _ = _salary_vintage(con)
    if not (salary_rows and salary_season and salary_season != season):
        return None
    return (f"salary data is for {salary_season}, not {season}; "
            "trade math was not calculated")


def _trade_guard_team_error(con, team: str, players: str,
                            season: str | None = None) -> str | None:
    team_code = canonical_team_abbr(team)
    for player in [x.strip() for x in str(players).split(",") if x.strip()]:
        actual = _season_player_team(con, player, season) if season else None
        if not actual:
            kind_filter = ""
            try:
                scols = {r[1] for r in con.execute("PRAGMA table_info(silver_salaries)").fetchall()}
                if "ROW_KIND" in scols:
                    kind_filter = "AND ROW_KIND = 'roster'"
            except Exception:
                pass
            row = con.execute(
                "SELECT TEAM FROM silver_salaries WHERE lower(PLAYER_NAME) = lower(?) "
                + kind_filter + " ORDER BY TEAM LIMIT 1",
                [player]).fetchone()
            actual = canonical_team_abbr(row[0]) if row and row[0] else ""
        if actual and actual != team_code:
            return (f"salary data lists {player} with {actual}, "
                    f"not {team_code} in season {season}; "
                    "trade math was not calculated")
    return None


def _trade_guard(con, season: str, team_a: str, players_a: str, team_b: str,
                 players_b: str) -> str | None:
    guard_error = _trade_guard_vintage_error(con, season)
    if guard_error:
        return guard_error
    for team, players in ((team_a, players_a), (team_b, players_b)):
        if not team:
            continue
        team_error = _trade_guard_team_error(con, team, players, season)
        if team_error:
            return team_error
    return None


def _infer_trade_side(plist: str, con: object, season: str | None = None) -> str:
    teams: set[str] = set()
    for nm in [x.strip() for x in str(plist).split(",") if x.strip()]:
        hit = _locate_player_team(nm, con, season)
        if hit is None:
            return ""
        teams.add(str(hit[1]))
    return teams.pop() if len(teams) == 1 else ""


def _trade_unknown_message(team_a: str, unk_a: list[str], team_b: str,
                           unk_b: list[str], con: object) -> str:
    parts = []
    if unk_a:
        parts.append(f"{team_a.upper()}: {'; '.join(unk_a)}")
    if unk_b:
        parts.append(f"{team_b.upper()}: {'; '.join(unk_b)}")
    msg = "unknown players: " + " | ".join(parts)
    hints = _unknown_player_hints(unk_a + unk_b, con)
    return msg + ". " + "; ".join(hints) if hints else msg


def _trade_autocorrect_side(unknown: list[str], team: str, plist: str,
                            con: object, matched: tuple,
                            season: str | None = None) -> tuple:
    if not unknown:
        return team, matched, []
    fix = _auto_correct_side(unknown, team, plist, con, season)
    if not fix:
        return team, matched, []
    return fix


def _trade_match_sides(team_a: str, players_a: str, team_b: str,
                       players_b: str, con: object,
                       season: str | None = None):
    side_a = _match_trade_players(team_a, players_a, con, season)
    side_b = _match_trade_players(team_b, players_b, con, season)
    corrections: list[str] = []
    team_a, side_a, corr_a = _trade_autocorrect_side(
        side_a[2], team_a, players_a, con, side_a, season)
    corrections.extend(corr_a)
    team_b, side_b, corr_b = _trade_autocorrect_side(
        side_b[2], team_b, players_b, con, side_b, season)
    corrections.extend(corr_b)
    return team_a, side_a, team_b, side_b, corrections


def _trade_side_rows(team: str, side: tuple, payroll: int, state: dict,
                     allow: int, rule: str, needed: int,
                     hard_cap: str,
                     election: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"team": team.upper(), "out": side[0], "players": side[1],
            "payroll": payroll, "allowed_in": allow, "match_rule": rule,
            "outgoing_needed": needed, "hard_cap": hard_cap,
            **(election or {}),
            **{k: v for k, v in state.items()}}


def _trade_check_issues(team_a: str, state_a: dict, names_a: list[str],
                        team_b: str, state_b: dict, names_b: list[str],
                        out_a: int, allow_a: int, out_b: int,
                        allow_b: int) -> list[str]:
    issues = []
    if state_a["over_apron2"] and len(names_a) > 1:
        issues.append(f"{team_a.upper()} cannot aggregate above second apron")
    if state_b["over_apron2"] and len(names_b) > 1:
        issues.append(f"{team_b.upper()} cannot aggregate above second apron")
    if out_b > allow_a:
        issues.append(f"{team_a.upper()} takes back too much")
    if out_a > allow_b:
        issues.append(f"{team_b.upper()} takes back too much")
    return issues


def _trade_check_checks(team_a: str, rule_a: str, team_b: str,
                        rule_b: str) -> list[dict[str, Any]]:
    return [
        {"rule": "salary matching", "checked": True,
         "note": f"{team_a.upper()} {rule_a}, {team_b.upper()} {rule_b}"},
        {"rule": "second apron aggregation ban", "checked": True,
         "note": "multi player out banned above second apron"},
        *({"rule": rule, "checked": False, "note": "not modeled"}
          for rule in _TRADE_CHECK_UNMODELED),
    ]


def _tpe_creation_block(outgoing: int, incoming: int, pay_before: int,
                        pay_after: int, over_apron1: bool) -> dict[str, Any] | None:
    if not (outgoing > incoming and pay_before > CAP["cap"]
            and pay_after > CAP["cap"] and not over_apron1):
        return None
    amount = outgoing - incoming
    return {
        "amount": amount,
        "expiry": "one year from the trade execution date",
        "condition": ("would generate only if this construction is executed as a "
                      "non-simultaneous trade — a simultaneous execution forfeits the exception"),
        "copy": (f"If executed as a non-simultaneous trade, this construction would generate "
                 f"a ${amount / 1_000_000:.1f}M trade exception expiring one year from the "
                 f"execution date. Executed simultaneously, it generates nothing."),
    }

@tool(description='Trade legality check. Player names comma separated per side.\n\n2023 CBA matching for 2026-27 below the first apron: 200 percent plus\n250k when outgoing is up to 8.846M, outgoing plus 9.096M up to 35.384M,\n125 percent plus 250k above that. 100 percent above the first apron, no\naggregation above the second apron. Expanded matching use hard-caps at the\nfirst apron; cap-room absorption does not. Cash and exceptions stay out.')

def get_trade_check(
    team_a: str = "", players_a: str = "", team_b: str = "", players_b: str = "",
    season: str | None = None,
) -> dict[str, Any]:
    season = (str(season or "").strip() or _pkg().current_season()
              or _pkg().resolve_season(None))
    if not players_a and not players_b:
        return {"tool": "get_trade_check", "ok": False,
                "error": "two teams needed"}

    with _owned_connection(None, read_only=True) as guard_con:
        guard_error = _trade_guard(guard_con, season, team_a, players_a,
                                   team_b, players_b)
    if guard_error:
        return {"tool": "get_trade_check", "ok": False, "error": guard_error}

    if (not team_a or not team_b) and players_a and players_b:
        with _owned_connection(None, read_only=True) as infer_con:
            team_a = team_a or _infer_trade_side(players_a, infer_con, season)
            team_b = team_b or _infer_trade_side(players_b, infer_con, season)
    if not team_a or not team_b:
        return {"tool": "get_trade_check", "ok": False,
                "error": "two teams needed"}
    norm = _norm_trade_teams(team_a, team_b)
    if norm is None:
        return {"tool": "get_trade_check", "ok": False,
                "error": (f"both sides resolve to the same team "
                          f"({team_a} / {team_b}) - a trade needs two "
                          f"different teams; check the team names")}
    team_a, team_b = norm

    with _owned_connection(None, read_only=True) as con:
        try:
            team_a, side_a, team_b, side_b, corrections = _trade_match_sides(
                team_a, players_a, team_b, players_b, con, season)
        except SalaryColumnError as exc:
            return {"tool": "get_trade_check", "ok": False,
                    "reason": exc.reason, "error": str(exc)}
        out_a, names_a, unk_a = side_a
        out_b, names_b, unk_b = side_b
        if unk_a or unk_b:
            return {"tool": "get_trade_check", "ok": False,
                    "error": _trade_unknown_message(
                        team_a, unk_a, team_b, unk_b, con)}
        if not names_a or not names_b:
            empty = team_a.upper() if not names_a else team_b.upper()
            return {"tool": "get_trade_check", "ok": False,
                    "error": (f"no players matched on the {empty} side - "
                              f"not grading a one-sided 'trade'. If you "
                              f"meant a past real-world trade, say which "
                              f"teams and players were in it.")}
        pay_a, _roster_a, _dead_a = _payroll(team_a, con, season)
        pay_b, _roster_b, _dead_b = _payroll(team_b, con, season)
        salary_date = _salary_date(con)
        source = _payroll_source(con)
    pay_after_a = pay_a - out_a + out_b
    pay_after_b = pay_b - out_b + out_a
    state_a = _apron_state(pay_after_a)
    state_b = _apron_state(pay_after_b)
    room_a = max(0, CAP["cap"] - pay_a)
    room_b = max(0, CAP["cap"] - pay_b)
    allow_a, rule_a = _allowed_incoming(out_a, bool(state_a["over_apron1"]), room_a)
    allow_b, rule_b = _allowed_incoming(out_b, bool(state_b["over_apron1"]), room_b)
    need_a = _outgoing_needed(out_b, bool(state_a["over_apron1"]), room_a)
    need_b = _outgoing_needed(out_a, bool(state_b["over_apron1"]), room_b)
    cushion_a = 0 if state_a["over_apron1"] else 250_000
    cushion_b = 0 if state_b["over_apron1"] else 250_000
    expanded_a = _used_expanded_matching(
        out_b, out_a, room_a, cushion=cushion_a)
    expanded_b = _used_expanded_matching(
        out_a, out_b, room_b, cushion=cushion_b)
    election_a = _matching_election(
        out_b, out_a, room_a, cushion_a, len(names_a), expanded_a)
    election_b = _matching_election(
        out_a, out_b, room_b, cushion_b, len(names_b), expanded_b)
    rule_a = _operative_match_rule(rule_a, election_a)
    rule_b = _operative_match_rule(rule_b, election_b)
    hard_cap_a = _hard_cap_consequences(
        team_a.upper(), pay_after_a, aggregates=len(names_a) > 1,
        expanded_matching=expanded_a)
    hard_cap_b = _hard_cap_consequences(
        team_b.upper(), pay_after_b, aggregates=len(names_b) > 1,
        expanded_matching=expanded_b)
    issues = _trade_check_issues(team_a, state_a, names_a, team_b, state_b,
                                 names_b, out_a, allow_a, out_b, allow_b)
    issues.extend(hard_cap_a["issues"])
    issues.extend(hard_cap_b["issues"])
    rows_a = _trade_side_rows(
        team_a, side_a, pay_a, state_a, allow_a, rule_a,
        need_a, hard_cap_a["hard_cap"], election_a)
    rows_b = _trade_side_rows(
        team_b, side_b, pay_b, state_b, allow_b, rule_b,
        need_b, hard_cap_b["hard_cap"], election_b)
    rows_a["tpe_creation"] = _tpe_creation_block(
        out_a, out_b, pay_a, pay_after_a, bool(state_a["over_apron1"]))
    rows_b["tpe_creation"] = _tpe_creation_block(
        out_b, out_a, pay_b, pay_after_b, bool(state_b["over_apron1"]))
    out = {"tool": "get_trade_check", "ok": True,
            "rows": {"team_a": rows_a,
                     "team_b": rows_b,
                     "legal": not issues, "issues": issues,
                     "checks": _trade_check_checks(team_a, rule_a, team_b,
                                                   rule_b),
                     "salary_date": salary_date,
                     **({"attribution_corrections": corrections}
                        if corrections else {}),
                     "disclaimer": "Estimate only, rules simplified. Skips cash, "
                     "prior trade exceptions, taxpayer midlevel, frozen pick, Stepien, "
                     "base-year, trade-kicker, minimum-salary, and sign-and-trade rules. "
                     "Confirm with a cap specialist."},
            "meta": {"source": source, "rules": "v1-simplified",
                     "salary_date": salary_date, "season": season,
                     **_payroll_proxy_meta()}}
    return declare_money(out, ["amount", "salary", "incoming", "outgoing", "allowed_incoming", "capacity", "payroll", "cap_room", "player_salary", "max_return_salary"])


_TRADE_PARTNER_PACKAGE_MAX = 3

_TRADE_PARTNER_DISCLAIMER = (
    "Estimate only, rules simplified. Skips cash, prior trade exceptions, "
    "taxpayer midlevel, frozen pick, Stepien, base-year, trade-kicker, "
    "minimum-salary, and sign-and-trade rules. Confirm with a cap specialist.")


def _partner_package_rows(team: str, roster: list[dict], incoming: int,
                          pay_a: int, room_a: int, pay_b: int, room_b: int,
                          limit: int) -> list[dict]:
    paid = [p for p in roster
            if isinstance(p.get("salary"), (int, float)) and p["salary"] > 0]
    paid.sort(key=lambda p: int(p["salary"]))
    fits: list[tuple[int, list[dict], int, str, dict]] = []
    for size in range(1, _TRADE_PARTNER_PACKAGE_MAX + 1):
        for combo in _it.combinations(paid, size):
            total = sum(int(p["salary"]) for p in combo)
            state_a = _apron_state(pay_a - incoming + total)
            state_b = _apron_state(pay_b - total + incoming)
            if size > 1 and state_b["over_apron2"]:
                continue
            allow_a, _ = _allowed_incoming(
                incoming, bool(state_a["over_apron1"]), room_a)
            allow_b, rule_b = _allowed_incoming(
                total, bool(state_b["over_apron1"]), room_b)
            if total > allow_a or allow_b < incoming:
                continue
            fits.append((total, list(combo), size, rule_b, state_b))
    fits.sort(key=lambda item: (item[2], item[0]))
    return [{"team": team.upper(),
             "players": ", ".join(str(p["player"]) for p in combo),
             "package_salary": total, "incoming": incoming,
             "match_rule": rule_b,
             "over_apron1": bool(state_b["over_apron1"]),
             "over_apron2": bool(state_b["over_apron2"]), "legal": True}
            for total, combo, _, rule_b, state_b in fits[:limit]]


@tool(description='Find CBA-legal salary-matching trade packages for one player '
      'across the league. Player name; season defaults to 2026-27; teams '
      'optionally restricts partners (comma-separated abbreviations); '
      'max_packages caps rows per team (default 3). Each row is a roster '
      'package (up to 3 players) whose salary satisfies both sides\' matching '
      'rules under the same simplified 2023 CBA as get_trade_check.')
def get_trade_partners(player: str = "", season: str | None = None,
                       teams: str = "", max_packages: int = 3) -> dict[str, Any]:
    season = str(season or "").strip() or "2026-27"
    if not str(player or "").strip():
        return {"tool": "get_trade_partners", "ok": False,
                "error": "player needed"}
    try:
        limit = max(1, min(int(max_packages or 3), 10))
    except (TypeError, ValueError):
        limit = 3
    restrict = {canonical_team_abbr(t)
                for t in str(teams or "").split(",") if t.strip()}

    with _owned_connection(None, read_only=True) as con:
        records = salary_records(con, salary_season=season,
                                 include_fallback=True)
        record = match_record(records, player)
        if record is None:
            hit = _locate_player_team(player, con, season)
            if hit:
                record = match_record(records, hit[0])
        if record is None:
            hints = _unknown_player_hints([player], con)
            return {"tool": "get_trade_partners", "ok": False,
                    "error": f"unknown player: {player}"
                             + (". " + "; ".join(hints) if hints else "")}
        if record.get("salary") is None:
            return {"tool": "get_trade_partners", "ok": False,
                    "error": f"no {season} salary for {record['PLAYER_NAME']}"}
        name = str(record["PLAYER_NAME"])
        team_a = canonical_team_abbr(record["TEAM"])
        incoming = int(record["salary"])
        pay_a, _roster_a, _dead_a = _payroll(team_a, con, season)
        room_a = max(0, CAP["cap"] - pay_a)
        expanded_a, rule_expanded_a = _allowed_incoming(incoming, False, room_a)
        strict_a, rule_strict_a = _allowed_incoming(incoming, True, room_a)
        below_apron_max = CAP["apron1"] - pay_a + incoming
        if min(expanded_a, below_apron_max) >= strict_a:
            allow_a = min(expanded_a, below_apron_max)
            rule_a = rule_expanded_a
        else:
            allow_a, rule_a = strict_a, rule_strict_a
        rows: list[dict] = []
        no_fit: list[str] = []
        partners = sorted({canonical_team_abbr(r["TEAM"]) for r in records
                           if r.get("TEAM")} - {team_a})
        for team in partners:
            if restrict and team not in restrict:
                continue
            pay_b, roster, _dead = _payroll(team, con, season)
            room_b = max(0, CAP["cap"] - pay_b)
            packages = _partner_package_rows(
                team, roster, incoming, pay_a, room_a, pay_b, room_b, limit)
            if packages:
                rows.extend(packages)
            else:
                no_fit.append(team)
        source = _payroll_source(con)
        salary_date = _salary_date(con)
    out = {"tool": "get_trade_partners", "ok": True,
            "rows": rows,
            "meta": {"source": source, "salary_date": salary_date,
                     "season": season, "rules": "v1-simplified",
                     **_payroll_proxy_meta(),
                     "player": name, "player_team": team_a,
                     "player_salary": incoming, "max_return_salary": allow_a,
                     "match_rule_in": rule_a,
                     "teams_without_fit": no_fit,
                     "disclaimer": _TRADE_PARTNER_DISCLAIMER}}
    return declare_money(out, ["amount", "salary", "incoming", "outgoing", "allowed_incoming", "capacity", "payroll", "cap_room", "player_salary", "max_return_salary"])


_TRADE_VALUE_WEIGHTS = {"PTS": 1.0, "REB": 1.2, "AST": 1.5,
                        "STL": 2.0, "BLK": 2.0, "TOV": -1.5}

_TRADE_LEADERS_COLUMNS = ["PLAYER", "GP", "PTS", "REB", "AST", "STL",
                          "BLK", "TOV", "FG3M", "FG3_PCT"]

_TRADE_RANK_COLUMNS = ["OFF_RATING_RANK", "DEF_RATING_RANK",
                       "NET_RATING_RANK", "TS_PCT_RANK", "AST_PCT_RANK",
                       "REB_PCT_RANK"]

_TRADE_NEED_COLUMNS = [("need_offense", "OFF_RATING_RANK"),
                       ("need_defense", "DEF_RATING_RANK"),
                       ("need_shooting", "TS_PCT_RANK"),
                       ("need_playmaking", "AST_PCT_RANK"),
                       ("need_rebounding", "REB_PCT_RANK")]

_TRADE_TAG_NEEDS = {"spacer": "need_shooting",
                    "playmaker": "need_playmaking",
                    "defensive playmaker": "need_defense",
                    "efficient scorer": "need_offense",
                    "high-usage creator": "need_offense"}


def _trade_value_norm(s: object) -> str:
    return normalize_name(s)


class _TradeWarehouse:

    __slots__ = ("tables", "cols", "gaps")

    def __init__(self, con, prod_season: str, sal_season: str) -> None:
        self.tables = _warehouse_tables(con)
        self.cols = {t: {r[1] for r in
                         con.execute(f"PRAGMA table_info({t})").fetchall()}
                     for t in self.tables if t.startswith("silver_")}
        self.gaps: list[str] = []

    def missing(self, table: str, required: list[str]) -> list[str]:
        have = self.cols.get(table, set())
        return [c for c in required if c not in have]

    def has_leaders(self) -> bool:
        return "silver_leaders_pts" in self.tables

    def note(self, text: str) -> None:
        self.gaps.append(text)


def _trade_leader_rows(con, prod_season: str) -> dict[str, dict]:
    rows: dict[str, dict] = {}
    columns = {r[1] for r in con.execute('PRAGMA table_info(silver_leaders_pts)').fetchall()}
    pid = 'PLAYER_ID' if 'PLAYER_ID' in columns else 'NULL'
    for r in con.execute(
            f"SELECT PLAYER, TEAM, GP, PTS, REB, AST, STL, BLK, TOV,"
            f" FG3M, FG3_PCT, {pid} FROM silver_leaders_pts WHERE _season = ?",
            [prod_season]).fetchall():
        rows.setdefault(_trade_value_norm(r[0]), {
            "name": r[0], "team": r[1], "gp": r[2] or 0, 'PLAYER_ID': r[11],
            "tot": {"PTS": r[3] or 0, "REB": r[4] or 0, "AST": r[5] or 0,
                    "STL": r[6] or 0, "BLK": r[7] or 0, "TOV": r[8] or 0},
            "fg3m": r[9] or 0, "fg3_pct": r[10]})
    return rows


def _trade_leader_weights(warehouse: _TradeWarehouse) -> dict[str, float]:
    missing = warehouse.missing("silver_leaders_pts", _TRADE_LEADERS_COLUMNS)
    if missing:
        warehouse.note(
            "silver_leaders_pts missing columns skipped at zero weight: "
            + ", ".join(missing))
    return {c: (0.0 if c in missing else w)
            for c, w in _TRADE_VALUE_WEIGHTS.items()}


def _trade_adv_rows(con, warehouse: _TradeWarehouse,
                    prod_season: str) -> dict[tuple[str, object], dict]:
    if "silver_advanced" not in warehouse.tables:
        warehouse.note("silver_advanced missing: age, TS_PCT, USG_PCT "
                       "and NET_RATING unavailable")
        return {}
    missing = warehouse.missing(
        "silver_advanced", ["PLAYER_NAME", "AGE", "TS_PCT", "USG_PCT"])
    if missing:
        warehouse.note("silver_advanced missing columns: " + ", ".join(missing))
    pid = "PLAYER_ID" if "PLAYER_ID" in warehouse.cols.get(
        "silver_advanced", set()) else "NULL"
    rows: dict[tuple[str, object], dict] = {}
    for r in con.execute(
            f"SELECT PLAYER_NAME, AGE, TS_PCT, USG_PCT, {pid} FROM "
            "silver_advanced WHERE _season = ?", [prod_season]).fetchall():
        row = {"age": r[1], "ts": r[2], "usg": r[3]}
        rows.setdefault(("name", _trade_value_norm(r[0])), row)
        if r[4] is not None:
            rows.setdefault(("id", r[4]), row)
    return rows


def _trade_salary_column(scols: set[str]) -> str:
    if "SALARY" in scols:
        return "SALARY"
    return next((c for c in scols if "SALARY" in c.upper()), "")


def _trade_season_scoped(table: str, name_col: str, val_col: str,
                         scols: set[str], sal_season: str):
    if "_season" in scols:
        return (f"SELECT {name_col}, {val_col} FROM {table} WHERE _season = ?",
                [sal_season])
    return f"SELECT {name_col}, {val_col} FROM {table}", []


def _inferred_salary_column_season(con, sal_season: str) -> str | None:
    if "silver_salaries" not in _warehouse_tables(con):
        return sal_season
    try:
        scols = {r[1] for r in con.execute(
            "PRAGMA table_info(silver_salaries)").fetchall()}
    except Exception:
        return sal_season
    exact = "SALARY_" + sal_season.replace("-", "_")
    if exact in scols:
        return sal_season
    return None if "SALARY" in scols else sal_season


def _trade_sheet_salaries(con, warehouse: _TradeWarehouse,
                          sal_season: str | None, leaders: dict | None = None) -> dict[str, int]:
    salaries: dict[str, int] = {}
    records = salary_records(con, sal_season, include_fallback=True)
    matched = set()
    for key, lead in (leaders or {}).items():
        contract = match_record(records, lead['name'], lead.get('PLAYER_ID'), lead['team'])
        if contract is not None:
            matched.add(id(contract))
            lead['contract'] = contract
            if contract['salary'] is not None:
                salaries[key] = int(contract['salary'])
    if leaders is not None:
        for contract in records:
            key = _trade_value_norm(contract['PLAYER_NAME'])
            if id(contract) in matched or key in leaders:
                continue
            leaders[key] = {'name': contract['PLAYER_NAME'], 'team': contract['TEAM'],
                            'PLAYER_ID': contract.get('PLAYER_ID'), 'gp': 0,
                            'tot': {}, 'fg3m': 0, 'contract': contract}
            if contract['salary'] is not None:
                salaries[key] = int(contract['salary'])
        return salaries
    for table, name_col, val_col in (
            ("silver_salaries", "PLAYER_NAME", None),
            ("silver_cap_players", "player", "salary")):
        if table not in warehouse.tables:
            continue
        scols = warehouse.cols.get(table, set())
        val = val_col or _trade_salary_column(scols)
        if not val:
            continue
        query, params = _trade_season_scoped(table, name_col, val, scols,
                                             sal_season)
        for r in con.execute(query, params).fetchall():
            if r[1] is not None:
                salaries.setdefault(_trade_value_norm(r[0]), int(r[1]))
    return salaries


def _trade_team_id_to_abbr() -> dict:
    try:
        from nba_api.stats.static import teams as _static

        return {t["id"]: t["abbreviation"] for t in _static.get_teams()}
    except Exception:
        return {}


def _trade_rating_rows(con, warehouse: _TradeWarehouse,
                       prod_season: str) -> dict[str, dict]:
    if "silver_team_ratings" not in warehouse.tables:
        warehouse.note("silver_team_ratings missing: pick slots assumed "
                       "mid-first and team needs unavailable")
        return {}
    have = warehouse.cols.get("silver_team_ratings", set())
    ranks = [c for c in _TRADE_RANK_COLUMNS if c in have]
    if len(ranks) < len(_TRADE_RANK_COLUMNS):
        warehouse.note("silver_team_ratings missing columns: " + ", ".join(
            c for c in _TRADE_RANK_COLUMNS if c not in ranks))
    names = ["TEAM_ID", "TEAM_NAME"] + ranks
    id_to_abbr = _trade_team_id_to_abbr()
    ratings: dict[str, dict] = {}
    for r in con.execute(
            f"SELECT {', '.join(names)} FROM silver_team_ratings "
            f"WHERE _season = ?", [prod_season]).fetchall():
        row = dict(zip(names, r))
        abbr = id_to_abbr.get(row["TEAM_ID"], "")
        if abbr:
            ratings[canonical_team_abbr(abbr)] = row
    return ratings


def _trade_dollars_per_point(leaders: dict, salaries: dict,
                             use_w: dict[str, float]) -> float:
    total = score = 0.0
    for key, lead in leaders.items():
        gp = lead["gp"]
        if gp < 20 or key not in salaries:
            continue
        total += salaries[key]
        score += sum(lead["tot"][c] / gp * use_w[c] for c in use_w)
    return (total / score) if score > 0 else 0.0


def _trade_archetypes(lead: dict, gp: int, advanced: dict) -> list[str]:
    per = {c: lead["tot"][c] / gp for c in lead["tot"]}
    tags = []
    if (lead["fg3m"] or 0) / gp >= 2.0:
        tags.append("spacer")
    if per["AST"] >= 5.0:
        tags.append("playmaker")
    if per["STL"] + per["BLK"] >= 1.5:
        tags.append("defensive playmaker")
    if advanced.get("ts") is not None and advanced["ts"] >= 0.60:
        tags.append("efficient scorer")
    if advanced.get("usg") is not None and advanced["usg"] >= 0.28:
        tags.append("high-usage creator")
    return tags


def _trade_value_player(display: str, leaders: dict, adv: dict,
                        salaries: dict, use_w: dict, dpp: float,
                        gaps: list[str]) -> dict[str, Any]:
    key = _trade_value_norm(display)
    lead = leaders.get(key)
    matches = [(k, v) for k, v in leaders.items() if normalize_name(v.get('contract', {}).get('PLAYER_NAME')) == normalize_name(display)]
    if len(matches) == 1:
        key, lead = matches[0]
    player_id = lead.get("PLAYER_ID") if lead else None
    advanced = adv.get(("id", player_id), {}) if player_id is not None else {}
    if not advanced:
        advanced = adv.get(("name", key), {})
    gp = lead["gp"] if lead else 0
    out: dict[str, Any] = {
        **contract_details(lead.get('contract') if lead else None),
        "name": display, "salary_26_27": salaries.get(key),
        "age": advanced.get("age"), "gp": gp,
        "ppg": round(lead["tot"]["PTS"] / gp, 1) if lead and gp else 0.0,
        "production_score": None, "est_market_value_m": "unknown",
        "residual_m": "unknown", "archetypes": [],
        "production_source": "2025-26 totals"}
    if not lead or gp < 10:
        gaps.append(
            f"{display}: unknown value treated as 0 in side total "
            "(GP < 10 or no 2025-26 production row)")
        return out
    score = round(sum(lead["tot"][c] / gp * use_w[c] for c in use_w), 2)
    est_m = round(score * dpp / 1e6, 1)
    out["production_score"] = score
    out["est_market_value_m"] = est_m
    if out["salary_26_27"] is not None:
        out["residual_m"] = round(
            (est_m * 1e6 - out["salary_26_27"]) / 1e6, 1)
        rv = out["residual_m"]
        out["residual_note"] = (
            f"surplus value of about ${rv}M (outperforming the contract)"
            if rv >= 0 else
            f"overpaid by an estimated ${abs(rv)}M on this production")
    out["archetypes"] = _trade_archetypes(lead, gp, advanced)
    return out


def _trade_first_round_slot(entry: dict, net_rank: object,
                            giving_abbr: str, prot,
                            curve_m: dict[int, float] | None = None) -> None:
    if net_rank is None:
        slot = 15
        entry["assumptions"].append(
            f"no ratings row for {giving_abbr.upper()}: assumed "
            "mid-first slot 15")
    else:
        slot = max(1, min(round(31 - net_rank * 0.85), 30))
        entry["assumptions"].append(
            f"slot estimated from {giving_abbr.upper()} net rank {net_rank}")
    if prot:
        n = int(prot.group(1))
        slot = max(slot, n + 1)
        entry["assumptions"].append(
            f"top-{n} protected: conveyance risk applied")
    value = _pick_value_for_slot(slot, True, curve_m)
    if curve_m is not None:
        entry["assumptions"].append(
            "valued on empirical draft value curve (silver_draft_value_curve)")
    if prot:
        value = round(value * 0.8, 1)
    entry.update(est_slot=slot, est_value_m=value)


def _trade_second_round_slot(entry: dict, desc: str,
                             curve_m: dict[int, float] | None = None) -> None:
    m = _re.search(r"\b([3-5]\d)\b", desc)
    slot = int(m.group(1)) if m and 31 <= int(m.group(1)) <= 60 else 45
    entry.update(est_slot=slot,
                 est_value_m=_pick_value_for_slot(slot, False, curve_m))
    entry["assumptions"].append("second-round slot estimate")
    if curve_m is not None:
        entry["assumptions"].append(
            "valued on empirical draft value curve (silver_draft_value_curve)")


def _trade_value_pick(desc: str, giving_abbr: str, ratings: dict,
                      gaps: list[str],
                      curve_m: dict[int, float] | None = None
                      ) -> dict[str, Any]:
    low = desc.lower()
    year = _re.search(r"(\d{4})", desc)
    is_frp = bool(_re.search(r"frp|first[\s-]?round", low))
    is_srp = bool(_re.search(r"\bsrp\b|second[\s-]?round", low))
    prot = _re.search(r"top[-\s]?(\d+)\s*protect", low)
    entry: dict[str, Any] = {"desc": desc, "est_slot": None,
                             "est_value_m": 0.0, "assumptions": []}
    if not year or (not is_frp and not is_srp):
        entry["assumptions"].append("unparseable pick description")
        gaps.append(f"{desc}: unparseable pick, valued at 0")
        return entry
    if is_frp:
        net_rank = (ratings.get(canonical_team_abbr(giving_abbr), {}) or {}).get(
            "NET_RATING_RANK")
        _trade_first_round_slot(entry, net_rank, giving_abbr, prot, curve_m)
    else:
        _trade_second_round_slot(entry, desc, curve_m)
    return entry


def _trade_value_picks(raw: str, giving_abbr: str, ratings: dict,
                       gaps: list[str],
                       curve_m: dict[int, float] | None = None
                       ) -> list[dict]:
    return [_trade_value_pick(desc, giving_abbr, ratings, gaps, curve_m)
            for desc in [p.strip() for p in str(raw or "").split(",")
                         if p.strip()]]


def _trade_side_total(players: list[dict], picks: list[dict]) -> float:
    return round(sum(p["est_market_value_m"] for p in players
                     if isinstance(p["est_market_value_m"], (int, float)))
                 + sum(k["est_value_m"] for k in picks), 1)


def _trade_grades(winner: str, delta: float, total_a: float, total_b: float,
                  abbr_a: str, abbr_b: str) -> dict[str, str]:
    if winner == "even":
        return {abbr_a: "B", abbr_b: "B"}
    share = abs(delta) / max(total_a, total_b, 1)
    top = abbr_a if winner == abbr_a else abbr_b
    bottom = abbr_b if top == abbr_a else abbr_a
    top_grade = "A" if share >= 0.25 else "A-" if share >= 0.15 else "B+"
    bottom_grade = ("F" if share >= 0.40 else "D" if share >= 0.25
                    else "C+" if share >= 0.15 else "B-")
    return {top: top_grade, bottom: bottom_grade}


def _trade_timeline(ratings: dict, team_abbr: str) -> tuple[str, list]:
    r = ratings.get(canonical_team_abbr(team_abbr), {})
    needs = [name for name, col in _TRADE_NEED_COLUMNS
             if isinstance(r.get(col), (int, float)) and r[col] >= 20]
    net_rank = r.get("NET_RATING_RANK")
    timeline = ("unknown" if not isinstance(net_rank, (int, float))
                else "contender" if net_rank <= 8
                else "rebuilding" if net_rank >= 22 else "middle")
    return timeline, needs


def _trade_fit_notes(player: dict, timeline: str, needs: list) -> list:
    notes = []
    for tag in player.get("archetypes", []):
        need = _TRADE_TAG_NEEDS.get(tag)
        if need and need in needs:
            notes.append(f"{player['name']} fills {need} ({tag})")
    age = player.get("age")
    if isinstance(age, (int, float)) and age >= 32 and timeline == "rebuilding":
        notes.append(f"{player['name']}: timeline clash (age {age:g} "
                     "joining a rebuild)")
    if isinstance(age, (int, float)) and age <= 23 and timeline == "contender":
        notes.append(f"{player['name']}: developmental piece on a contender")
    return notes


def _trade_fit(team_abbr: str, received: list[dict],
               ratings: dict) -> dict[str, Any]:
    timeline, needs = _trade_timeline(ratings, team_abbr)
    notes = [note for player in received
             for note in _trade_fit_notes(player, timeline, needs)]
    notes.append("positional logjam not assessed: no position data "
                 "in warehouse")
    return {"needs": needs, "timeline": timeline, "notes": notes}


def _trade_driver(players_a: list, players_b: list):
    valued = [p for p in players_a + players_b
              if isinstance(p["est_market_value_m"], (int, float))]
    if not valued:
        return None
    return max(valued, key=lambda p: (abs(p["residual_m"])
                                      if isinstance(p["residual_m"],
                                                    (int, float)) else 0))


def _trade_key_add(winner: str, abbr_a: str, players_a: list,
                   players_b: list):
    win_side = players_b if winner == abbr_a else players_a
    got = [p for p in win_side
           if isinstance(p["est_market_value_m"], (int, float))]
    return max(got, key=lambda p: p["est_market_value_m"], default=None)


def _trade_key_fit_note(winner: str, fit: dict, key_add: dict | None) -> str:
    if key_add is None or winner == "even":
        return ""
    notes = fit[winner]["notes"]
    hit = next((n for n in notes if n.startswith(key_add["name"])), "")
    if hit:
        return (f" {key_add['name']} {hit[len(key_add['name']) + 1:]} "
                f"for {winner}.")
    return (f" {key_add['name']} headlines the return for {winner} "
            f"({fit[winner]['timeline']} timeline).")


def _trade_verdict_line(winner: str, total_a: float, total_b: float,
                        delta: float, abbr_a: str, abbr_b: str) -> str:
    if winner == "even":
        return (f"This grades as roughly even, with {abbr_a} at an estimated "
                f"${total_a}M and {abbr_b} at an estimated ${total_b}M, "
                f"a gap of about ${abs(delta)}M.")
    return (f"{winner} wins on estimated value by about ${abs(delta)}M, "
            f"${max(total_a, total_b)}M to ${min(total_a, total_b)}M.")


def _trade_driver_line(driver: dict | None) -> str:
    if driver is None:
        return "No player had enough production data to name a value driver."
    residual = driver["residual_m"]
    res_txt = ("the best value in the deal"
               if isinstance(residual, (int, float)) and residual < 0
               else "the largest gap between salary and production")
    return (f"The biggest driver is {driver['name']}, with an estimated "
            f"${driver['est_market_value_m']}M market value against a "
            f"${(driver['salary_26_27'] or 0) / 1e6:.1f}M salary, "
            f"{res_txt}.")


def _trade_value_sides(con, team_a: str, players_a: str, team_b: str,
                       players_b: str, season: str | None = None):
    _, names_a, unk_a = _match_trade_players(team_a, players_a, con, season)
    _, names_b, unk_b = _match_trade_players(team_b, players_b, con, season)
    if unk_a:
        fix = _auto_correct_side(unk_a, team_a, players_a, con, season)
        if fix:
            team_a, (_, names_a, unk_a), _c = fix
    if unk_b:
        fix = _auto_correct_side(unk_b, team_b, players_b, con, season)
        if fix:
            team_b, (_, names_b, unk_b), _c = fix
    return team_a, names_a, unk_a, team_b, names_b, unk_b


def _trade_value_error(msg: str) -> dict[str, Any]:
    return {"tool": "get_trade_value", "ok": False, "error": msg}


@tool(description='Trade value grade: estimated production value vs salary per side, plus picks.\n\nReasoning layer on top of get_trade_check (which covers cap legality).\nAll dollar figures are rough estimates from the latest completed\nproduction season versus the current salary sheet. Picks like "2029 FRP"\nor "2030 FRP top-4 protected".')
def get_trade_value(
    team_a: str = "", players_a: str = "", team_b: str = "",
    players_b: str = "", picks_a: str = "", picks_b: str = "",
) -> dict[str, Any]:
    if team_a and team_b:
        norm = _norm_trade_teams(team_a, team_b)
        if norm is None:
            return _trade_value_error(
                f"both sides resolve to the same team ({team_a} / {team_b}) "
                "- check the team names")
        team_a, team_b = norm
    with _owned_connection(None, read_only=True) as vintage_con:
        sal_season, sal_rows, _ = _salary_vintage(vintage_con)
    sal_season = sal_season or "2026-27"
    prod_season = _pkg().last_completed_season()
    disclaimer = (f"All dollar figures are rough estimates from {prod_season} "
                  f"production vs {sal_season} salary data. Not cap-legality "
                  "advice; pair with get_trade_check.")

    if not team_a or not team_b:
        return _trade_value_error("two teams needed")
    with _owned_connection(None) as con:
        salary_column_season = _inferred_salary_column_season(con, sal_season)
        try:
            team_a, names_a, unk_a, team_b, names_b, unk_b = _trade_value_sides(
                con, team_a, players_a, team_b, players_b, salary_column_season)
        except SalaryColumnError as exc:
            return {"tool": "get_trade_value", "ok": False,
                    "reason": exc.reason, "error": str(exc)}
        if unk_a or unk_b:
            out = _trade_value_error(_trade_unknown_message(
                team_a, unk_a, team_b, unk_b, con))
            out["reason"] = "unknown_players"
            return out
        if not names_a or not names_b:
            return {"tool": "get_trade_value", "ok": False,
                    "terminal": True,
                    "error": ("I can only grade proposed trades where "
                              "both sides name players. What a past "
                              "trade's other side actually received is "
                              "not in this dataset.")}

        warehouse = _TradeWarehouse(con, prod_season, sal_season)
        if not warehouse.has_leaders():
            return _trade_value_error(
                "cannot value players: silver_leaders_pts missing from "
                "warehouse")
        use_w = _trade_leader_weights(warehouse)
        leaders = _trade_leader_rows(con, prod_season)
        adv = _trade_adv_rows(con, warehouse, prod_season)
        salaries = _trade_sheet_salaries(con, warehouse, salary_column_season, leaders)
        if not salaries:
            warehouse.note("no 2026-27 salary rows: residuals unavailable")
        ratings = _trade_rating_rows(con, warehouse, prod_season)
        payroll_source = _payroll_source(con)
        curve_m = _draft_value_curve_m(con)

    dpp = _trade_dollars_per_point(leaders, salaries, use_w)
    if not dpp:
        return _trade_value_error(
            "cannot value players: no qualified salary plus production "
            "overlap in warehouse")

    players_a = [_trade_value_player(n, leaders, adv, salaries, use_w, dpp,
                                     warehouse.gaps) for n in names_a]
    players_b = [_trade_value_player(n, leaders, adv, salaries, use_w, dpp,
                                     warehouse.gaps) for n in names_b]
    picks_list_a = _trade_value_picks(picks_a, team_a, ratings,
                                      warehouse.gaps, curve_m)
    picks_list_b = _trade_value_picks(picks_b, team_b, ratings,
                                      warehouse.gaps, curve_m)

    total_a = _trade_side_total(players_a, picks_list_a)
    total_b = _trade_side_total(players_b, picks_list_b)
    delta = round(total_a - total_b, 1)
    abbr_a, abbr_b = canonical_team_abbr(team_a), canonical_team_abbr(team_b)
    winner = abbr_a if delta >= 0.5 else abbr_b if delta <= -0.5 else "even"

    fit = {abbr_a: _trade_fit(abbr_a, players_b, ratings),
           abbr_b: _trade_fit(abbr_b, players_a, ratings)}

    key_fit_note = _trade_key_fit_note(
        winner, fit, _trade_key_add(winner, abbr_a, players_a, players_b))
    s1 = _trade_verdict_line(winner, total_a, total_b, delta, abbr_a, abbr_b)
    s2 = _trade_driver_line(_trade_driver(players_a, players_b))
    s3 = key_fit_note.strip() or "Fit notes are limited by missing team data."
    s4 = (f"All values are rough estimates from {prod_season} production "
          f"versus {sal_season} salaries, so this is not cap-legality advice: "
          "pair it with get_trade_check.")

    return declare_units({"tool": "get_trade_value", "ok": True,
            "rows": {"team_a": {"team": abbr_a, "players": players_a,
                                "picks": picks_list_a, "side_total_m": total_a},
                     "team_b": {"team": abbr_b, "players": players_b,
                                "picks": picks_list_b, "side_total_m": total_b},
                     "fit": fit,
                     "verdict": {"winner": winner, "delta_m": delta,
                                 "grades": _trade_grades(
                                     winner, delta, total_a, total_b,
                                     abbr_a, abbr_b),
                                 "text": " ".join([s1, s2, s3, s4])},
                     "data_gaps": warehouse.gaps,
                     "disclaimer": disclaimer,
                     "residual_meaning": "residual_m = estimated market "
                     "value minus salary; positive = surplus value "
                     "(outperforming the contract), negative = overpaid"},
            "meta": {"source": payroll_source,
                     "production_season": prod_season,
                     "salary_season": sal_season,
                     "estimates": True}},
            {"salary": "usd_dollars", "side_total_m": "usd_millions",
             "delta_m": "usd_millions", "residual_m": "usd_millions",
             "value_m": "usd_millions"})
