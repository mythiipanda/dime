import json as _json
import re as _re
from calendar import monthrange
from itertools import combinations
from datetime import date, timedelta
from functools import lru_cache
from typing import Any

from langchain_core.tools import tool

from ...contracts import canonical_team_abbr
from ..cap_rules import (
    matching_election as _matching_election,
    payroll_proxy_meta as _payroll_proxy_meta,
)
from ._helpers import _owned_connection, _pkg, declare_money
from .cba_cap import (
    CAP,
    SalaryColumnError,
    _allowed_incoming,
    _apron_state,
    _hard_cap_consequences,
    _locate_player_team,
    _match_trade_players,
    _operative_match_rule,
    _payroll,
    _payroll_source,
    _resolve_team_abbr,
    _salary_date,
    _used_expanded_matching,
)
from .trade_value import _trade_guard_vintage_error

_STEPIEN_WINDOW = 7
_FROZEN_PICK_OFFSET = 8
_TPE_CUSHION = 250_000
_TPE_KINDS = {
    "ordinary": "ordinary",
    "standard": "ordinary",
    "sign_and_trade": "sign_and_trade",
    "sign_and_trade_generated": "sign_and_trade",
    "snt": "sign_and_trade",
    "snt_generated": "sign_and_trade",
}
_SNT_GUARANTEE_DISCLOSURE = (
    "first-season full guarantee required by 2023 CBA Art. VII sec. 8(e)(1) "
    "is not validated")
_SNT_OPTION_YEAR_DISCLOSURE = (
    "years is treated as total declared seasons; non-option seasons cannot be "
    "distinguished, so option-year treatment is unsupported")
_PICK_OWNERSHIP_LIMITATIONS = (
    "protection/swap reconciliation and pooled/conditional picks are not "
    "modeled; same-year multiple firsts are validated only at year grain "
    "because the leg input does not identify the original team of a "
    "same-year first")


def _parse_json_arg(text: str, label: str) -> tuple[Any, str | None]:
    raw = str(text or "").strip()
    if not raw:
        return [], None
    try:
        value = _json.loads(raw)
    except _json.JSONDecodeError:
        return None, (f"{label} must be JSON, got: {raw[:80]}")
    if label == "legs":
        if not isinstance(value, list) or not value:
            return None, "legs must be a non-empty JSON array"
        return value, None
    if not isinstance(value, (list, dict)):
        return None, f"{label} must be a JSON object or array"
    return value, None


def _leg_team(value: Any) -> str:
    abbr = _resolve_team_abbr(str(value or ""))
    return canonical_team_abbr(abbr or value)


def _leg_players(leg: dict) -> list[str]:
    raw = leg.get("players", [])
    if isinstance(raw, str):
        return [x.strip() for x in raw.split(",") if x.strip()]
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if str(x).strip()]
    return []


def _leg_picks(leg: dict) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for raw in leg.get("picks", []) or []:
        if not isinstance(raw, dict):
            continue
        try:
            year = int(raw.get("year"))
        except (TypeError, ValueError):
            continue
        out.append({"year": year,
                    "round": int(raw.get("round", 1) or 1),
                    "swap": bool(raw.get("swap", False)),
                    "protection": str(raw.get("protection") or "")})
    return out


def _parse_cash(rows: Any, parties: set[str]
                ) -> tuple[list[dict[str, Any]], str | None]:
    if isinstance(rows, dict):
        rows = [rows]
    out: list[dict[str, Any]] = []
    for index, raw in enumerate(rows or [], 1):
        if not isinstance(raw, dict):
            return [], f"cash row {index} is not an object"
        null_keys = [key for key in ("from", "to", "amount")
                     if key in raw and raw[key] is None]
        if null_keys:
            return [], (f"cash row {index} has explicit null for "
                        f"{', '.join(null_keys)}")
        sender = _leg_team(raw.get("from"))
        receiver = _leg_team(raw.get("to"))
        if not sender or not receiver:
            return [], f"cash row {index} needs from and to teams"
        amount = _strict_integer(raw.get("amount"))
        if amount is None or amount <= 0:
            return [], (f"cash row {index} amount must be a positive "
                        "integer")
        for label, team in (("from", sender), ("to", receiver)):
            if canonical_team_abbr(team) not in parties:
                return [], (f"cash row {index} {label} team {team} is not "
                            "a trade party")
        out.append({"from": sender, "to": receiver, "amount": amount})
    return out, None


def _strict_integer(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _iso_date(value: Any) -> date | None:
    if not isinstance(value, str) or not _re.fullmatch(
            r"\d{4}-\d{2}-\d{2}", value):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _today() -> date:
    from datetime import datetime
    from zoneinfo import ZoneInfo

    return datetime.now(ZoneInfo("America/New_York")).date()


def _nth_weekday(year: int, month: int, weekday: int,
                 occurrence: int) -> date:
    first = date(year, month, 1)
    offset = ((weekday - first.weekday()) % 7) + 7 * (occurrence - 1)
    return first + timedelta(days=offset)


def _last_weekday(year: int, month: int, weekday: int) -> date:
    last = date(year, month, monthrange(year, month)[1])
    return last - timedelta(days=(last.weekday() - weekday) % 7)


def _federal_holidays(year: int) -> set[date]:
    fixed = {date(year, month, day) for month, day in
             ((1, 1), (6, 19), (7, 4), (11, 11), (12, 25))}
    floating = (
        _nth_weekday(year, 1, 0, 3), _nth_weekday(year, 2, 0, 3),
        _last_weekday(year, 5, 0), _nth_weekday(year, 9, 0, 1),
        _nth_weekday(year, 10, 0, 2), _nth_weekday(year, 11, 3, 4),
    )
    return fixed | set(floating)


def _roll_business_deadline(day: date) -> date:
    while day.weekday() >= 5 or day in _federal_holidays(day.year):
        day += timedelta(days=1)
    return day


def _league_year_start(day: date) -> int:
    return day.year if day.month >= 7 else day.year - 1


def _next_anniversary(day: date) -> date:
    try:
        return day.replace(year=day.year + 1)
    except ValueError:
        return date(day.year + 1, 2, 28)


def _tpe_dates(raw: dict[str, Any], index: int
               ) -> tuple[date | None, date | None, str | None]:
    origin_date = None
    expiry_date = None
    if "origin_date" in raw:
        origin_date = _iso_date(raw.get("origin_date"))
        if origin_date is None:
            return None, None, f"tpe row {index} origin_date must be YYYY-MM-DD"
    if "expiry_date" in raw:
        expiry_date = _iso_date(raw.get("expiry_date"))
        if expiry_date is None:
            return None, None, f"tpe row {index} expiry_date must be YYYY-MM-DD"
    if (origin_date and expiry_date and expiry_date <= origin_date):
        return None, None, (f"tpe row {index} expiry_date must be after "
                            "origin_date")
    return origin_date, expiry_date, None


def _tpe_origin_year(raw: dict[str, Any]) -> tuple[int | None, str | None]:
    year = None
    if "origin_year" in raw:
        year = _strict_integer(raw.get("origin_year"))
        if year is None:
            return None, "origin_year must be an integer season-start year"
    season_year = None
    if "origin_season" in raw:
        value = raw.get("origin_season")
        match = (_re.fullmatch(r"(\d{4})-(\d{2})", value)
                 if isinstance(value, str) else None)
        if not match:
            return None, "origin_season must be YYYY-YY with consecutive years"
        season_year = int(match.group(1))
        if int(match.group(2)) != (season_year + 1) % 100:
            return None, "origin_season must be YYYY-YY with consecutive years"
    if year is not None and season_year is not None and year != season_year:
        return None, "origin_year and origin_season disagree"
    return year if year is not None else season_year, None


def _parse_tpe(rows: Any) -> tuple[list[dict[str, Any]], str | None]:
    if isinstance(rows, dict):
        rows = [rows]
    out: list[dict[str, Any]] = []
    for index, raw in enumerate(rows or [], 1):
        if not isinstance(raw, dict):
            return [], f"tpe row {index} is not an object"
        null_keys = [key for key in ("amount", "kind", "origin_year",
                                     "origin_season", "origin_date",
                                     "expiry_date")
                     if key in raw and raw[key] is None]
        if null_keys:
            return [], (f"tpe row {index} has explicit null for "
                        f"{', '.join(null_keys)}")
        team = _leg_team(raw.get("team"))
        if not team:
            return [], f"tpe row {index} needs a team"
        amount = _strict_integer(raw.get("amount"))
        if amount is None:
            return [], f"tpe row {index} needs an integer amount"
        if amount <= 0:
            return [], f"tpe row {index} amount must be positive"
        raw_kind = raw.get("kind", "ordinary")
        key = (raw_kind.strip().lower() if isinstance(raw_kind, str) else "")
        key = key.replace("-", "_").replace(" ", "_")
        kind = _TPE_KINDS.get(key)
        if kind is None:
            return [], (f"tpe row {index} kind must be ordinary or "
                        "sign_and_trade")
        origin_year, err = _tpe_origin_year(raw)
        if err:
            return [], f"tpe row {index} {err}"
        origin_date, expiry_date, date_err = _tpe_dates(raw, index)
        if date_err:
            return [], date_err
        if origin_date:
            date_year = _league_year_start(origin_date)
            if origin_year is not None and origin_year != date_year:
                return [], (f"tpe row {index} origin_date does not match "
                            "origin_year/origin_season")
            origin_year = date_year
        typed = "kind" in raw and (
            "origin_year" in raw or "origin_season" in raw
            or "origin_date" in raw)
        out.append({"team": team, "amount": amount, "kind": kind,
                    "origin_year": origin_year, "typed": typed,
                    "origin_date": origin_date, "expiry_date": expiry_date})
    return out, None


def _tpe_status(origin_year: int, season_start: int) -> str:
    if origin_year > season_start:
        return "future"
    if origin_year < season_start - 1:
        return "expired"
    return "current_year" if origin_year == season_start else "prior_year"


def _season_label(season_start: int) -> str:
    return f"{season_start}-{(season_start + 1) % 100:02d}"


def _tpe_expiry(raw: dict[str, Any]) -> tuple[date | None, date | None, bool]:
    expiry = raw["expiry_date"]
    derived = False
    if not expiry and raw["origin_date"]:
        expiry = _next_anniversary(raw["origin_date"])
        derived = True
    if expiry is None:
        return None, None, False
    return expiry, _roll_business_deadline(expiry), derived


def _tpe_timing(raw: dict[str, Any], season_status: str,
                as_of: date | None) -> dict[str, Any]:
    expiry, effective_expiry, derived = _tpe_expiry(raw)
    exact = bool(as_of and (raw["origin_date"] or expiry))
    status = season_status
    if exact:
        if raw["origin_date"] and raw["origin_date"] > as_of:
            status = "future"
        elif effective_expiry and effective_expiry < as_of:
            status = "expired"
    return {"status": status,
            "timing_basis": "exact_date" if exact else "season_approximate",
            "as_of_date": as_of.isoformat() if exact and as_of else None,
            "origin_date": (raw["origin_date"].isoformat()
                            if raw["origin_date"] else None),
            "expiry_date": expiry.isoformat() if expiry else None,
            "effective_expiry_date": (effective_expiry.isoformat()
                                      if effective_expiry else None),
            "expiry_date_derived": derived}


def _seasonize_tpes(rows: list[dict[str, Any]], season_start: int,
                    as_of: date | None) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for raw in rows:
        team = canonical_team_abbr(raw["team"])
        origin = (raw["origin_year"] if raw["origin_year"] is not None
                  else season_start)
        season_status = _tpe_status(origin, season_start)
        item = {"team": team, "amount": raw["amount"],
                "kind": raw["kind"], "origin_year": origin,
                "origin_season": _season_label(origin),
                "legacy_defaults": not raw["typed"],
                **_tpe_timing(raw, season_status, as_of)}
        grouped.setdefault(team, []).append(item)
    return grouped


def _placement_fits(salaries: list[int], capacities: list[int],
                    required_bins: int,
                    matching_limit: int | None = None) -> bool:
    ordered = sorted((int(salary or 0) for salary in salaries), reverse=True)
    bins = tuple(int(capacity or 0) for capacity in capacities)

    @lru_cache(maxsize=None)
    def place(index: int, remaining: tuple[int, ...], used: int,
              matching_total: int) -> bool:
        if index == len(ordered):
            return (used & required_bins) == required_bins
        salary = ordered[index]
        if salary <= 0:
            return place(index + 1, remaining, used, matching_total)
        seen: set[tuple[int, bool, bool, bool]] = set()
        for position, capacity in enumerate(remaining):
            marker = (capacity, position == 0,
                      bool(used & (1 << position)),
                      bool(required_bins & (1 << position)))
            if capacity < salary or marker in seen:
                continue
            seen.add(marker)
            next_matching = (matching_total + salary if position == 0
                             else matching_total)
            if (matching_limit is not None
                    and next_matching > matching_limit):
                continue
            reduced = (remaining[:position] + (capacity - salary,) +
                       remaining[position + 1:])
            if place(index + 1, reduced, used | (1 << position),
                     next_matching):
                return True
        return False

    return place(0, bins, 0, 0)


def _expanded_matching_use(incoming_salaries: list[int], in_total: int,
                           out_eff: int, room_before: int,
                           capacities: list[int],
                           required_bins: int,
                           cushion: int = _TPE_CUSHION) -> bool:
    if not _used_expanded_matching(
            in_total, out_eff, room_before, cushion=cushion):
        return False
    if not capacities:
        return True
    strict_limit = out_eff + cushion
    if room_before > 0:
        strict_limit += room_before
    return not _placement_fits(
        incoming_salaries, [strict_limit] + capacities, required_bins,
        strict_limit)


def _public_tpe(tpe: dict[str, Any], over_apron1: bool) -> dict[str, Any]:
    active = tpe["status"] in ("current_year", "prior_year")
    cushion = 0 if over_apron1 or not active else _TPE_CUSHION
    return {"amount": tpe["amount"], "kind": tpe["kind"],
            "origin_year": tpe["origin_year"],
            "origin_season": tpe["origin_season"],
            "status": tpe["status"], "capacity": tpe["amount"] + cushion,
            "legacy_defaults": tpe["legacy_defaults"],
            "timing_basis": tpe["timing_basis"],
            "as_of_date": tpe["as_of_date"],
            "origin_date": tpe["origin_date"],
            "expiry_date": tpe["expiry_date"],
            "effective_expiry_date": tpe["effective_expiry_date"],
            "expiry_date_derived": tpe["expiry_date_derived"]}


def _parse_snt(value: Any) -> tuple[dict[str, Any] | None, str | None]:
    if value is None:
        return None, None
    if not isinstance(value, dict):
        return None, "sign_and_trade must be a JSON object"
    keys = ("player", "new_salary", "years")
    missing = [key for key in keys if key not in value]
    if missing:
        return None, f"sign_and_trade missing {', '.join(missing)}"
    null_keys = [key for key in keys if value[key] is None]
    if null_keys:
        return None, (f"sign_and_trade has explicit null for "
                      f"{', '.join(null_keys)}")
    player = value["player"]
    if not isinstance(player, str) or not player.strip():
        return None, "sign_and_trade player must be a non-empty string"
    new_salary = _strict_integer(value["new_salary"])
    if new_salary is None or new_salary <= 0:
        return None, "sign_and_trade new_salary must be a positive integer"
    years = _strict_integer(value["years"])
    if years is None or years <= 0:
        return None, "sign_and_trade years must be a positive integer"
    return {"player": player.strip(), "new_salary": new_salary,
            "years": years}, None


def _picks_season(con, cols: set[str] | None = None) -> str:
    if cols is None:
        cols = {r[1] for r in con.execute(
            "PRAGMA table_info(silver_future_picks)").fetchall()}
    if "_season" not in cols:
        return ""
    row = con.execute("select max(_season) from silver_future_picks").fetchone()
    return row[0] if row and row[0] else (_pkg().current_season() or "")


def _picks_vintage(con) -> tuple[str, str]:
    cols = {r[1] for r in con.execute(
        "PRAGMA table_info(silver_future_picks)").fetchall()}
    if "_season" not in cols:
        return "", "unvintaged_fallback"
    return _picks_season(con, cols), "warehouse_vintage"


def _pick_inventory(con, season_start: int
                    ) -> tuple[dict[str, set[int]] | None,
                               dict[str, str] | None]:
    tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
    if "silver_future_picks" not in tables:
        return None, None
    held: dict[str, set[int]] = {}
    season, basis = _picks_vintage(con)
    sql = ("select DRAFT_YEAR, ROUND, ORIG_TEAM, STATUS, HELD_BY "
           "from silver_future_picks where ROUND = 1")
    params: list[str] = []
    if basis == "warehouse_vintage":
        sql += " and _season = ?"
        params.append(season)
    rows = con.execute(sql, params).fetchall()
    for year, _rnd, orig, status, held_by in rows:
        y = int(year)
        if not (season_start < y <= season_start + _STEPIEN_WINDOW):
            continue
        owners: set[str] = set()
        status = str(status or "")
        orig_code = canonical_team_abbr(orig)
        if status in ("own", "swap") and orig_code:
            owners.add(orig_code)
        if status == "traded":
            for holder in str(held_by or "").split(";"):
                holder_code = canonical_team_abbr(holder)
                if holder_code:
                    owners.add(holder_code)
        for team in owners:
            held.setdefault(team, set()).add(y)
    return held, {"season": season, "basis": basis}


def _outgoing_firsts(moves: list[dict[str, Any]]
                     ) -> list[tuple[str, dict[str, Any]]]:
    return [(canonical_team_abbr(move["from"]), pick)
            for move in moves for pick in move["picks"]
            if pick["round"] == 1]


def _pick_duplicate_error(moves: list[dict[str, Any]]) -> str | None:
    seen: set[tuple[str, int]] = set()
    for team, pick in _outgoing_firsts(moves):
        key = (team, pick["year"])
        if key in seen:
            return (f"{team} declares the {pick['year']} first-round pick "
                    "more than once")
        seen.add(key)
    return None


def _pick_ownership_error(moves: list[dict[str, Any]],
                          pick_held: dict[str, set[int]] | None,
                          season_start: int | None) -> str | None:
    if pick_held is None or not season_start:
        return None
    for team, pick in _outgoing_firsts(moves):
        year = pick["year"]
        if not (season_start < year <= season_start + _STEPIEN_WINDOW):
            continue
        if year not in pick_held.get(team, set()):
            return (f"{team} cannot declare a {year} first-round pick "
                    "it does not own")
    return None


def _stepien_issues(team: str, owned: set[int], season_start: int) -> list[str]:
    issues: list[str] = []
    for y in range(season_start + 1, season_start + _STEPIEN_WINDOW):
        if y not in owned and (y + 1) not in owned:
            issues.append(
                f"{team} would hold no first-round pick in {y} or {y + 1} "
                f"(Stepien rule)")
    return issues


def _salary_season_start(season: str) -> int | None:
    m = _re.match(r"(\d{4})", str(season or ""))
    return int(m.group(1)) if m else None


def _trade_error(error: str, reason: str | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {"tool": "get_trade_legality", "ok": False,
                           "error": error}
    if reason is not None:
        out["reason"] = reason
    return out


def _parse_trade_args(legs: str, cash: str, tpe: str,
                      sign_and_trade: str) -> tuple[list[Any], str | None]:
    parsed: list[Any] = []
    for label, raw in (("legs", legs), ("cash", cash), ("tpe", tpe),
                       ("sign_and_trade", sign_and_trade)):
        value, err = _parse_json_arg(raw, label)
        if err:
            return [], err
        parsed.append(value)
    return parsed, None


def _parse_evaluation_date(value: Any) -> tuple[date | None, str | None]:
    if value in (None, ""):
        return _today(), None
    parsed = _iso_date(value)
    if parsed is None:
        return None, "evaluation_date must be YYYY-MM-DD"
    return parsed, None


def _parse_moves(rows: Any) -> tuple[list[dict[str, Any]], str | None]:
    moves: list[dict[str, Any]] = []
    for index, leg in enumerate(rows, 1):
        if not isinstance(leg, dict):
            return [], f"leg {index} is not an object"
        src = _leg_team(leg.get("from"))
        dst = _leg_team(leg.get("to"))
        if not src or not dst:
            return [], f"leg {index} needs from and to teams"
        if src == dst:
            return [], f"leg {index} is {src} to itself - same team"
        moves.append({"from": src, "to": dst,
                      "players": _leg_players(leg),
                      "picks": _leg_picks(leg)})
    if not any(m["players"] for m in moves) and not any(m["picks"] for m in moves):
        return [], "no players or picks in the legs"
    return moves, None


def _snt_in_moves(snt: dict[str, Any], moves: list[dict[str, Any]]) -> bool:
    return any(snt["player"].lower() in player.lower()
               for move in moves for player in move["players"])


def _snt_receiver(snt: dict[str, Any] | None,
                  moves: list[dict[str, Any]]) -> str | None:
    if not snt:
        return None
    return next((canonical_team_abbr(move["to"]) for move in moves
                 if any(player.lower() == snt["player"].lower()
                        for player in move["players"])), None)


def _resolve_legality_season(con: Any, season: str | None) -> str:
    resolved = str(season or "").strip()
    if resolved:
        return resolved
    cols = {row[1] for row in con.execute(
        "PRAGMA table_info(silver_salaries)").fetchall()}
    explicit = sorted(col for col in cols
                      if _re.fullmatch(r"SALARY_\d{4}_\d{2}", col))
    if explicit:
        return explicit[-1][len("SALARY_"):].replace("_", "-")
    return (_pkg()._salary_vintage(con)[0]
            or _pkg().current_season()
            or _pkg().resolve_season(None))


def _incoming_player_row(team: str, player: str, con: Any, season: str,
                         snt: dict[str, Any] | None
                         ) -> tuple[dict[str, Any] | None, str | None]:
    hit = _locate_player_team(player, con, season)
    if hit is None:
        return None, f"cannot resolve incoming player {player} to {team}"
    cname, _cteam, csal = hit
    if snt and cname.lower() == snt["player"].lower() and snt["new_salary"]:
        salary = snt["new_salary"]
    else:
        salary = int(csal or 0)
    return {"player": cname, "salary": salary}, None


def _incoming_rows(team: str, moves: list[dict[str, Any]], con: Any,
                   season: str, snt: dict[str, Any] | None
                   ) -> tuple[list[dict[str, Any]], list[str], int, str | None]:
    rows: list[dict[str, Any]] = []
    names: list[str] = []
    total = 0
    team_code = canonical_team_abbr(team)
    for move in moves:
        if canonical_team_abbr(move["to"]) != team_code:
            continue
        for player in move["players"]:
            row, err = _incoming_player_row(team, player, con, season, snt)
            if err or row is None:
                return [], [], 0, err or "incoming player resolution failed"
            rows.append(row)
            names.append(row["player"])
            total += row["salary"]
    return rows, names, total, None


def _team_side(team: str, moves: list[dict[str, Any]], con: Any,
               season: str, snt: dict[str, Any] | None
               ) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    team_code = canonical_team_abbr(team)
    plist = ",".join(player for move in moves
                     if canonical_team_abbr(move["from"]) == team_code
                     for player in move["players"])
    try:
        out_total, out_names, out_unk = _match_trade_players(
            team_code, plist, con, season)
    except SalaryColumnError as exc:
        return None, _trade_error(str(exc), exc.reason)
    if out_unk:
        return None, _trade_error(
            f"{team_code}: unknown outgoing players {'; '.join(out_unk)}")
    try:
        pay_before, _payroll_rows, _dead_rows = _payroll(team_code, con, season)
    except SalaryColumnError as exc:
        return None, _trade_error(str(exc), exc.reason)
    in_rows, in_names, in_total, err = _incoming_rows(
        team_code, moves, con, season, snt)
    if err:
        return None, _trade_error(err)
    return {"out_names": out_names, "out_total": out_total,
            "in_names": in_names, "in_rows": in_rows,
            "in_total": in_total, "pay_before": pay_before}, None


def _load_trade_state(con: Any, moves: list[dict[str, Any]], season: str | None,
                      snt: dict[str, Any] | None,
                      tpe_rows: list[dict[str, Any]]
                      ) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    resolved_season = _resolve_legality_season(con, season)
    guard_error = _trade_guard_vintage_error(con, resolved_season)
    if guard_error:
        return None, _trade_error(guard_error)
    teams = sorted({canonical_team_abbr(move["from"]) for move in moves} |
                   {canonical_team_abbr(move["to"]) for move in moves})
    side: dict[str, dict[str, Any]] = {}
    for team in teams:
        row, err = _team_side(team, moves, con, resolved_season, snt)
        if err or row is None:
            return None, err or _trade_error("could not build team side")
        side[team] = row
    season_start = _salary_season_start(resolved_season)
    if tpe_rows and season_start is None:
        return None, _trade_error("season must be YYYY-YY when tpe is used")
    pick_held = None
    pick_vintage = None
    if season_start:
        pick_held, pick_vintage = _pick_inventory(con, season_start)
    snt_salary_prior = 0
    if snt:
        hit = _locate_player_team(snt["player"], con, resolved_season)
        if hit is not None:
            snt_salary_prior = int(hit[2] or 0)
    return {"season": resolved_season, "teams": teams, "side": side,
            "salary_date": _salary_date(con),
            "source": _payroll_source(con),
            "season_start": season_start, "pick_held": pick_held,
            "pick_vintage": pick_vintage,
            "snt_salary_prior": snt_salary_prior}, None


def _byc_adjustment(side: dict[str, Any], snt: dict[str, Any] | None,
                    snt_salary_prior: int) -> tuple[int, str | None]:
    out_total = side["out_total"]
    if not snt or not snt["new_salary"]:
        return out_total, None
    if not any(player.lower() == snt["player"].lower()
               for player in side["out_names"]):
        return out_total, None
    raise_ratio = (snt["new_salary"] / snt_salary_prior
                   if snt_salary_prior else 0)
    if raise_ratio <= 1.2 or side["pay_before"] <= CAP["cap"]:
        return out_total, None
    byc = max(snt_salary_prior, snt["new_salary"] // 2)
    adjusted = out_total - snt_salary_prior + byc
    note = (f"{snt['player']} counts at ${byc:,} outgoing "
            "under base-year compensation")
    return adjusted, note


def _tpe_usage(team_tpes: list[dict[str, Any]],
               over_apron1: bool) -> dict[str, Any]:
    active = [item for item in team_tpes
              if item["status"] in ("current_year", "prior_year")]
    inactive = [item for item in team_tpes
                if item["status"] not in ("current_year", "prior_year")]
    cushion = 0 if over_apron1 else _TPE_CUSHION
    return {"active": active, "inactive": inactive,
            "used": sum(item["amount"] for item in active),
            "prior": any(item["status"] == "prior_year" for item in active),
            "snt": any(item["kind"] == "sign_and_trade" for item in active),
            "capacities": [item["amount"] + cushion for item in active]}


def _elect_tpe_subset(incoming_salaries: list[int], allow: int,
                      capacities: list[int]) -> tuple[int, ...] | None:
    if _placement_fits(incoming_salaries, [allow], 0):
        return ()
    if not capacities:
        return None
    for size in range(1, len(capacities) + 1):
        for combo in combinations(range(len(capacities)), size):
            bins = [capacities[index] for index in combo]
            required = sum(1 << (position + 1) for position in range(len(bins)))
            if _placement_fits(incoming_salaries, [allow] + bins, required):
                return combo
    return None


def _inactive_tpe_issue(team: str, item: dict[str, Any]) -> str:
    kind_label = ("sign-and-trade-generated"
                  if item["kind"] == "sign_and_trade" else "ordinary")
    if item["status"] == "expired":
        if item["timing_basis"] == "exact_date":
            ending = (f"its effective expiry date "
                      f"{item['effective_expiry_date']} passed before the "
                      f"{item['as_of_date']} evaluation date")
        else:
            ending = ("season-only expiry is approximate; its season bin "
                      "is expired")
    else:
        ending = "it is not yet available"
    return (f"{team} cannot use the {kind_label} traded player exception "
            f"from {item['origin_season']}; {ending}")


def _inactive_tpe_issues(team: str,
                         inactive_tpes: list[dict[str, Any]]) -> list[str]:
    return [_inactive_tpe_issue(team, item) for item in inactive_tpes]


def _frozen_pick_issues(team: str, picks_out: list[dict[str, Any]],
                        season_start: int | None) -> list[str]:
    if not season_start:
        return []
    frozen_year = season_start + _FROZEN_PICK_OFFSET
    return [f"{team}'s {frozen_year} first-round pick is frozen above "
            "the second apron"
            for pick in picks_out
            if not pick["swap"] and pick["round"] == 1
            and pick["year"] == frozen_year]


def _apron2_issues(team: str, out_names: list[str], cash_out: int,
                   picks_out: list[dict[str, Any]],
                   season_start: int | None) -> list[str]:
    issues: list[str] = []
    if len(out_names) > 1:
        issues.append(f"{team} cannot aggregate outgoing salaries above "
                      "the second apron")
    if cash_out:
        issues.append(f"{team} cannot send cash above the second apron")
    issues.extend(_frozen_pick_issues(team, picks_out, season_start))
    return issues


def _matching_issue(team: str, salary_fit: bool, active_tpes: list[dict[str, Any]],
                    in_total: int, allow: int, rule: str) -> list[str]:
    if salary_fit:
        return []
    if active_tpes:
        return [f"{team} takes back too much; traded player exceptions "
                "cannot be combined with player salary or each other "
                "for one acquisition"]
    return [f"{team} takes back too much "
            f"(${in_total:,} vs ${allow:,} allowed under {rule})"]


def _future_pick_issues(team: str, picks_out: list[dict[str, Any]],
                        season_start: int | None) -> list[str]:
    if not season_start:
        return []
    return [f"{team} cannot trade a {pick['year']} pick - more than "
            "7 drafts out"
            for pick in picks_out
            if pick["year"] > season_start + _STEPIEN_WINDOW]


def _evaluate_team(team: str, side: dict[str, Any],
                   moves: list[dict[str, Any]],
                   cash_moves: list[dict[str, Any]],
                   team_tpes: list[dict[str, Any]],
                   snt_receiver: str | None,
                   snt: dict[str, Any] | None,
                   snt_salary_prior: int,
                   season_start: int | None
                   ) -> tuple[dict[str, Any], list[str]]:
    team = canonical_team_abbr(team)
    out_eff, byc_note = _byc_adjustment(side, snt, snt_salary_prior)
    pay_after = side["pay_before"] - side["out_total"] + side["in_total"]
    state_after = _apron_state(pay_after)
    state_before = _apron_state(side["pay_before"])
    room_before = max(0, CAP["cap"] - side["pay_before"])
    allow, rule = _allowed_incoming(
        out_eff, bool(state_after["over_apron1"]), room_before)
    usage = _tpe_usage(team_tpes, bool(state_after["over_apron1"]))
    incoming_salaries = [row["salary"] for row in side["in_rows"]]
    elected = _elect_tpe_subset(incoming_salaries, allow, usage["capacities"])
    elected_active = [usage["active"][index] for index in elected] if elected else []
    usage["used"] = sum(item["amount"] for item in elected_active)
    usage["prior"] = any(item["status"] == "prior_year" for item in elected_active)
    usage["snt"] = any(item["kind"] == "sign_and_trade" for item in elected_active)
    elected_capacities = ([usage["capacities"][index] for index in elected]
                          if elected else [])
    if elected is None and usage["capacities"]:
        elected_capacities = usage["capacities"]
    required_tpe_bins = sum(1 << (index + 1)
                            for index in range(len(elected_capacities)))
    salary_fit = (elected is not None) and _placement_fits(
        incoming_salaries, [allow] + elected_capacities, required_tpe_bins)
    aggregates = len(side["out_names"]) > 1
    cash_out = sum(cash["amount"] for cash in cash_moves
                   if canonical_team_abbr(cash["from"]) == team)
    cash_in = sum(cash["amount"] for cash in cash_moves
                  if canonical_team_abbr(cash["to"]) == team)
    picks_out = [pick for move in moves
                 if canonical_team_abbr(move["from"]) == team
                 for pick in move["picks"]]
    picks_in = [pick for move in moves
                if canonical_team_abbr(move["to"]) == team
                for pick in move["picks"]]
    is_snt_receiver = team == canonical_team_abbr(snt_receiver)
    cushion = 0 if state_after["over_apron1"] else _TPE_CUSHION
    expanded_matching = _expanded_matching_use(
        incoming_salaries, side["in_total"], out_eff, room_before,
        elected_capacities, required_tpe_bins, cushion)
    tpe_in_structure = (bool(elected_active)
                        or (elected is None and bool(usage["capacities"])))
    election = _matching_election(
        side["in_total"], out_eff, room_before, cushion,
        len(side["out_names"]), expanded_matching,
        tpe_in_structure)
    rule = _operative_match_rule(rule, election)
    hard_cap = _hard_cap_consequences(
        team, pay_after, aggregates=aggregates, cash_out=cash_out,
        prior_tpe=usage["prior"], snt_tpe=usage["snt"],
        is_snt_receiver=is_snt_receiver, expanded_matching=expanded_matching)
    tpe_creation = None
    if (out_eff > side["in_total"]
            and side["pay_before"] > CAP["cap"]
            and pay_after > CAP["cap"]
            and not state_after["over_apron1"]):
        amount = out_eff - side["in_total"]
        tpe_creation = {
            "amount": amount,
            "expiry": "one year from the trade execution date",
            "condition": ("would generate only if this construction is executed as a "
                          "non-simultaneous trade; a simultaneous execution forfeits the exception"),
            "copy": (f"If executed as a non-simultaneous trade, this construction would generate "
                     f"a ${amount / 1_000_000:.1f}M trade exception expiring one year from the "
                     f"execution date. Executed simultaneously, it generates nothing."),
        }

    issues = _inactive_tpe_issues(team, usage["inactive"])
    if state_after["over_apron2"]:
        issues.extend(_apron2_issues(team, side["out_names"], cash_out,
                                     picks_out, season_start))
    issues.extend(hard_cap["issues"])
    issues.extend(_matching_issue(team, salary_fit, usage["active"],
                                  side["in_total"], allow, rule))
    issues.extend(_future_pick_issues(team, picks_out, season_start))
    row = {
        "team": team,
        "payroll_before": side["pay_before"],
        "payroll_after": pay_after,
        "outgoing": side["out_total"],
        "outgoing_matching": out_eff,
        "incoming": side["in_total"],
        "players_out": side["out_names"],
        "players_in": side["in_names"],
        "picks_out": picks_out,
        "picks_in": picks_in,
        "cash_out": cash_out, "cash_in": cash_in,
        "tpe_used": usage["used"],
        "tpe_creation": tpe_creation,
        "tpe_details": [_public_tpe(item, bool(state_after["over_apron1"]))
                        for item in team_tpes],
        "allowed_incoming": allow, "match_rule": rule,
        "matching_ok": salary_fit,
        "aggregates": aggregates,
        "hard_cap": hard_cap["hard_cap"],
        "hard_cap_causes": hard_cap["causes"],
        "hard_cap_violations": hard_cap["violations"],
        **election,
        "over_apron1": state_after["over_apron1"],
        "over_apron2": state_after["over_apron2"],
        "room_apron2": state_after["room_apron2"],
        "over_apron1_before": state_before["over_apron1"],
        "over_apron2_before": state_before["over_apron2"],
        **({"byc_note": byc_note} if byc_note else {}),
    }
    return row, issues


def _snt_result(snt: dict[str, Any] | None,
                receiver: str | None) -> tuple[list[str], dict[str, Any] | None]:
    if not snt:
        return [], None
    issues: list[str] = []
    if snt["years"] < 3:
        issues.append("sign-and-trade contracts must run at least 3 seasons")
    if snt["years"] > 4:
        issues.append("sign-and-trade contracts cannot exceed 4 seasons")
    unvalidated_note = (f"{_SNT_GUARANTEE_DISCLOSURE}; prior-team and "
                        "preseason eligibility not modeled")
    if receiver:
        note = (f"{snt['player']} to {receiver}; {receiver} is "
                "hard-capped at the first apron; "
                f"{unvalidated_note}")
    else:
        note = (f"{snt['player']} is not moving teams; "
                f"{unvalidated_note}")
    return issues, {"rule": "sign-and-trade", "checked": True, "note": note}


def _owned_after_trade(team: str, moves: list[dict[str, Any]],
                       pick_held: dict[str, set[int]]) -> set[int]:
    team_code = canonical_team_abbr(team)
    owned: set[int] = set()
    for held_team, years in pick_held.items():
        if canonical_team_abbr(held_team) == team_code:
            owned.update(years)
    for move in moves:
        move_from = canonical_team_abbr(move["from"])
        move_to = canonical_team_abbr(move["to"])
        for pick in move["picks"]:
            if pick["round"] != 1:
                continue
            if move_from == team_code and not pick["swap"]:
                owned.discard(pick["year"])
            if move_to == team_code and not pick["swap"]:
                owned.add(pick["year"])
    return owned


def _pick_inventory_check(pick_held: dict[str, set[int]] | None
                          ) -> dict[str, Any]:
    if pick_held is None:
        return {"rule": "pick ownership", "checked": False,
                "note": "duplicate declarations checked; silver_future_picks "
                        "not seeded - ownership not verified; "
                        f"{_PICK_OWNERSHIP_LIMITATIONS}"}
    return {"rule": "pick ownership", "checked": True,
            "note": "outgoing first-round ownership and duplicate "
                    "declarations checked at year grain against "
                    f"silver_future_picks; {_PICK_OWNERSHIP_LIMITATIONS}"}


def _stepien_result(teams: list[str], moves: list[dict[str, Any]],
                    pick_held: dict[str, set[int]] | None,
                    season_start: int | None
                    ) -> tuple[list[str], dict[str, Any]]:
    if pick_held is None or not season_start:
        return [], {"rule": "Stepien consecutive firsts + 7-year limit",
                    "checked": False,
                    "note": "silver_future_picks not seeded - pick "
                            "ownership not verified"}
    issues: list[str] = []
    for team in teams:
        team_code = canonical_team_abbr(team)
        owned_after = _owned_after_trade(team_code, moves, pick_held)
        owned_before = set(pick_held.get(team_code, set()))
        if owned_after == owned_before:
            continue
        issues.extend(_stepien_issues(team_code, owned_after, season_start))
    return issues, {"rule": "Stepien consecutive firsts + 7-year limit",
                    "checked": True,
                    "note": "verified against silver_future_picks; "
                            "evaluated only for teams whose first-round "
                            "inventory the trade changes"}


def _build_checks(team_rows: dict[str, Any],
                  snt_check: dict[str, Any] | None,
                  pick_check: dict[str, Any],
                  stepien_check: dict[str, Any],
                  legacy_tpes: bool) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    if snt_check:
        checks.append(snt_check)
    checks.append(pick_check)
    checks.append(stepien_check)
    checks.insert(0, {"rule": "salary matching",
                      "checked": True,
                      "note": "; ".join(
                          f"{team} {team_rows[team]['match_rule']}"
                          for team in sorted(team_rows))})
    checks.insert(1, {"rule": "apron aggregation bans",
                      "checked": True,
                      "note": "no aggregation above the second apron; "
                              "aggregation hard-caps at the second apron"})
    checks.append({"rule": "cash in trade",
                   "checked": True,
                   "note": "positive trade-party cash validated; apron2 ban "
                           "+ second-apron hard-cap trigger checked; annual "
                           "cash limit not tracked"})
    tpe_note = ("kind, origin timing, amount capacity and non-combination "
                "checked for declared uses; exact expiry deadlines remain "
                "usable through their date, roll forward from weekends and "
                "federal holidays, and are compared with the evaluation "
                "date, while season-only expiry uses conservative "
                "approximate legacy season bins")
    if legacy_tpes:
        tpe_note += ("; untyped rows default missing kind/origin fields "
                     "to ordinary/current-season values")
    checks.append({"rule": "traded player exceptions",
                   "checked": True, "note": tpe_note})
    checks.append({"rule": "no-trade clauses, trade kickers, rosters "
                          "minimums, prior TPE inventory",
                   "checked": False, "note": "not modeled"})
    return checks


@tool(description='Trade legality verdict across 2+ teams. "legs" is a JSON array:\n'
    '[{"from":"BOS","to":"DEN","players":"Jayson Tatum, Sam Hauser",'
    '"picks":[{"year":2028,"round":1,"protection":"top-4"},{"year":2030,"round":1,"swap":true}]}].\n'
    'Optional "sign_and_trade" = {"player":"...","new_salary":15000000,"years":3} '
    '(positive salary, 3-4 season term, BYC handled; '
    + _SNT_GUARANTEE_DISCLOSURE
    + '; prior-team and preseason eligibility not modeled; '
    + _SNT_OPTION_YEAR_DISCLOSURE + '), '
    '"cash" = [{"from","to","amount"}] with positive integer amounts '
    'between trade parties, '
    '"tpe" = [{"team","amount","kind":"ordinary|sign_and_trade",'
    '"origin_season":"YYYY-YY","origin_date":"YYYY-MM-DD",'
    '"expiry_date":"YYYY-MM-DD"}]; rows are declared uses, not inventory. '
    'Present keys must be non-null; omit unused optional keys. Amount and '
    'origin_year must be JSON integers. Optional "evaluation_date" is '
    'YYYY-MM-DD and defaults to the league date in America/New_York. '
    'Amount-only legacy rows assume an ordinary current-season origin. '
    'origin_date must agree with origin_year/origin_season when both are '
    'supplied and derives a one-year expiry when expiry_date is omitted. '
    'Exact expiry deadlines remain usable through their date and expire '
    'only afterward; weekend and federal-holiday deadlines roll to the '
    'following business day. Season-only rows keep conservative '
    'approximate legacy season bins. '
    'TPE capacity is amount plus the '
    'CBA $250k cushion, reduced to $0 over the first apron; entries '
    'older than the prior season are treated as expired. Outgoing '
    'first-round picks are duplicate-checked and validated at year grain '
    'against silver_future_picks when seeded; '
    + _PICK_OWNERSHIP_LIMITATIONS
    + '. Checks 2023 '
    'CBA salary matching tiers, apron aggregation bans, post-trade '
    'hard caps, typed TPE restrictions, cash bans, the frozen '
    'second-apron pick, and Stepien consecutive-first rules. '
    'REACH FOR THIS for any trade-legality ask beyond a trivial two-team '
    'player swap: sign-and-trade, multi-team, picks/Stepien, apron '
    'aggregation, TPE or cash involved. For a simple two-team salary '
    'match get_trade_check is enough.')
def get_trade_legality(legs: str = "", sign_and_trade: str = "",
                       cash: str = "", tpe: str = "",
                       season: str | None = None,
                       evaluation_date: str = "") -> dict[str, Any]:
    values, err = _parse_trade_args(legs, cash, tpe, sign_and_trade)
    if err:
        return _trade_error(err)
    legs_value, cash_value, tpe_value, snt_value = values
    moves, err = _parse_moves(legs_value)
    if err:
        return _trade_error(err)
    pick_error = _pick_duplicate_error(moves)
    if pick_error:
        return _trade_error(pick_error)

    parties = {canonical_team_abbr(move["from"]) for move in moves} | {
        canonical_team_abbr(move["to"]) for move in moves}
    cash_moves, cash_err = _parse_cash(cash_value, parties)
    if cash_err:
        return _trade_error(cash_err)
    tpe_rows, tpe_err = _parse_tpe(tpe_value)
    if tpe_err:
        return _trade_error(tpe_err)
    snt_input = snt_value if str(sign_and_trade or "").strip() else None
    snt, snt_err = _parse_snt(snt_input)
    if snt_err:
        return _trade_error(snt_err)
    if snt and not _snt_in_moves(snt, moves):
        return _trade_error(
            f"sign_and_trade player {snt['player']} is not in any leg")
    evaluation_day, evaluation_err = _parse_evaluation_date(evaluation_date)
    if evaluation_err:
        return _trade_error(evaluation_err)

    with _owned_connection(None, read_only=True) as con:
        state, load_error = _load_trade_state(con, moves, season, snt, tpe_rows)
        if load_error or state is None:
            return load_error or _trade_error("could not load trade state")

    pick_error = _pick_ownership_error(
        moves, state["pick_held"], state["season_start"])
    if pick_error:
        return _trade_error(pick_error)

    tpe_by_team = (_seasonize_tpes(tpe_rows, state["season_start"],
                                   evaluation_day)
                   if tpe_rows else {})
    legacy_tpes = any(item["legacy_defaults"]
                      for rows in tpe_by_team.values() for item in rows)
    issues: list[str] = []
    team_rows: dict[str, Any] = {}
    receiver = _snt_receiver(snt, moves)
    for team in state["teams"]:
        row, team_issues = _evaluate_team(
            team, state["side"][team], moves, cash_moves,
            tpe_by_team.get(team, []), receiver, snt,
            state["snt_salary_prior"], state["season_start"])
        team_rows[team] = row
        issues.extend(team_issues)

    snt_issues, snt_check = _snt_result(snt, receiver)
    issues.extend(snt_issues)
    stepien_issues, stepien_check = _stepien_result(
        state["teams"], moves, state["pick_held"], state["season_start"])
    issues.extend(stepien_issues)
    pick_check = _pick_inventory_check(state["pick_held"])
    checks = _build_checks(
        team_rows, snt_check, pick_check, stepien_check, legacy_tpes)

    meta: dict[str, Any] = {
        "source": state["source"], "rules": "v2-2023cba-full",
        "salary_date": state["salary_date"],
        "season": state["season"],
        **_payroll_proxy_meta(),
        "disclaimer": "Estimate only. Covers matching, apron "
        "aggregation, hard caps, typed TPE restrictions, cash "
        "bans, sign-and-trade terms/BYC, year-grain pick "
        "ownership, Stepien and frozen-pick rules. Salary-matching "
        "mechanism use is inferred as the least restrictive structure "
        "available from the supplied players; actual NBA trade-call "
        "exception elections and prior hard-cap history are not modeled. "
        "Skips no-trade clauses, trade kickers, poison-pill, and "
        "minimum-salary exceptions; "
        f"{_PICK_OWNERSHIP_LIMITATIONS}; sign-and-trade "
        f"{_SNT_GUARANTEE_DISCLOSURE}; prior-team/preseason "
        "eligibility not modeled. Confirm with a cap "
        "specialist."}
    if state["pick_vintage"]:
        meta["pick_vintage_basis"] = state["pick_vintage"]["basis"]
        if state["pick_vintage"]["season"]:
            meta["pick_vintage_season"] = state["pick_vintage"]["season"]
    out = {"tool": "get_trade_legality", "ok": True,
            "rows": [team_rows[team] for team in sorted(team_rows)],
            "legal": not issues,
            "issues": issues,
            "checks": checks,
            "salary_date": state["salary_date"],
            "meta": meta}
    return declare_money(out, ["amount", "salary", "incoming", "outgoing", "allowed_incoming", "capacity", "payroll", "cap_room", "room_apron2"])
