import re as _re
from typing import Any

from ...contracts import canonical_team_abbr, dead_money_row_predicate, normalize_name, row_kind_column, salary_records
from ..cap_rules import apron_state, payroll_proxy_meta, roster_issues
from ..cap_sheet import season_column
from .cap_hold_derivation import derive_cap_holds, hold_amount
from ._helpers import declare_money
from .cap_sheet import cap_lines_for_season
from .cba_cap import _locate_player_team, _match_trade_players
from .cba_two_way import (
    merge_dead_rows,
    salary_row_cap_status,
    two_way_state_for_record,
    two_way_states,
)
from .waivers import player_contract_tail, waiver_dead_money

_SEASON_RE = _re.compile(r"^(\d{4})-(\d{2})$")


def _fmt_money(value: float | int) -> str:
    v = float(value)
    sign = "-" if v < 0 else ""
    return f"{sign}${abs(v) / 1_000_000:.1f}M"


def _shift_season(season: str, years: int) -> str | None:
    m = _SEASON_RE.match(str(season or ""))
    if not m:
        return None
    start = int(m.group(1)) + years
    return f"{start}-{str(start + 1)[-2:]}"


def _horizon_seasons(base_season: str, count: int) -> list[str]:
    seasons = []
    for i in range(count):
        shifted = _shift_season(base_season, i)
        if shifted:
            seasons.append(shifted)
    return seasons


def _salary_column_seasons(con) -> list[str]:
    try:
        cols = [r[1] for r in con.execute("PRAGMA table_info(silver_salaries)").fetchall()]
    except Exception:
        return []
    seasons = []
    for col in cols:
        m = _re.fullmatch(r"SALARY_(\d{4})_(\d{2})", str(col))
        if m:
            seasons.append(f"{m.group(1)}-{m.group(2)}")
    return sorted(seasons)


def _player_schedules(con, salary_season: str,
                      seasons: list[str] | None = None) -> dict[str, dict[str, Any]]:
    schedules: dict[str, dict[str, Any]] = {}
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
    except Exception:
        tables = set()
    states = two_way_states(con, salary_season, tables)
    classification_seasons = seasons or [salary_season]
    for row in salary_records(con, salary_season=salary_season):
        name = str(row.get("PLAYER_NAME") or "")
        if not name:
            continue
        salary_by_season: dict[str, int] = {}
        options: dict[str, str] = {}
        for col, value in row.items():
            m = _re.fullmatch(r"SALARY_(\d{4})_(\d{2})", str(col))
            if m and value is not None:
                salary_by_season[f"{m.group(1)}-{m.group(2)}"] = int(value)
            om = _re.fullmatch(r"OPTION_(\d{4})_(\d{2})", str(col))
            if om and value:
                options[f"{om.group(1)}-{om.group(2)}"] = str(value)
        team = canonical_team_abbr(row.get("TEAM") or "")
        state = two_way_state_for_record(states, name, row.get("PLAYER_ID"))
        status_by_season: dict[str, dict[str, Any]] = {}
        for label in classification_seasons:
            evidence = dict(row)
            evidence["salary"] = row.get(season_column(label))
            if evidence["salary"] is None and str(row.get("_season") or "") == label:
                evidence["salary"] = row.get("SALARY")
            status_by_season[label] = salary_row_cap_status(evidence, state, team, label)
        status = status_by_season.get(salary_season) or salary_row_cap_status(
            row, state, team, salary_season)
        unknown_seasons = [label for label, item in status_by_season.items()
                           if item.get("two_way_classification_unknown")]
        schedules[name.lower()] = {
            "player": name,
            "team": team,
            "salary_by_season": salary_by_season,
            "option_years": options,
            "guaranteed": row.get("GUARANTEED"),
            "cap_status": status,
            "cap_status_by_season": status_by_season,
            "classification_unknown_seasons": unknown_seasons,
            "evidence_season": salary_season,
        }
    return schedules


def _dead_money_schedules(con, team: str) -> list[dict[str, Any]]:
    team_code = canonical_team_abbr(team)
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        if "silver_salaries" not in tables:
            return []
        cols = {r[1] for r in con.execute("PRAGMA table_info(silver_salaries)").fetchall()}
        kind_column = row_kind_column(cols)
        if not kind_column:
            return []
        cur = con.execute(
            "SELECT * FROM silver_salaries WHERE " + dead_money_row_predicate(kind_column))
        names = [d[0] for d in cur.description]
        rows = [dict(zip(names, row)) for row in cur.fetchall()]
        if "_season" in cols:
            latest = con.execute("SELECT MAX(_season) FROM silver_salaries").fetchone()
            if latest and latest[0]:
                rows = [row for row in rows
                        if str(row.get("_season") or "") == str(latest[0])]
    except Exception:
        return []
    schedules = []
    for row in rows:
        if canonical_team_abbr(row.get("TEAM") or "") != team_code:
            continue
        salary_by_season: dict[str, int | None] = {}
        amount_values = [value for col, value in row.items()
                         if _re.fullmatch(r"SALARY_\d{4}_\d{2}", str(col))]
        has_known_amount = any(value is not None for value in amount_values)
        row_season = str(row.get("_season") or "")
        for col, value in row.items():
            match = _re.fullmatch(r"SALARY_(\d{4})_(\d{2})", str(col))
            if not match:
                continue
            label = f"{match.group(1)}-{match.group(2)}"
            if value is not None:
                salary_by_season[label] = int(value)
            elif not has_known_amount and (not row_season or row_season == label):
                salary_by_season[label] = None
        item = {"player": str(row.get("PLAYER_NAME") or ""),
                "team": team_code,
                "salary_by_season": salary_by_season}
        if row.get("PLAYER_ID") is not None:
            item["_player_id"] = row.get("PLAYER_ID")
        schedules.append(item)
    return schedules


def _inferred_dead_schedules(schedules: dict[str, dict[str, Any]], team: str) -> list[dict[str, Any]]:
    team_code = canonical_team_abbr(team)
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, int | None]] = set()
    for entry in schedules.values():
        dead = (entry.get("cap_status") or {}).get("dead_entry")
        if not dead or canonical_team_abbr(dead.get("team")) != team_code:
            continue
        unknown = bool(dead.get("amount_unknown"))
        try:
            amount = None if unknown else int(dead.get("salary") or 0)
        except (TypeError, ValueError):
            continue
        key = (str(dead.get("player") or "").lower(), amount)
        if (not unknown and (amount or 0) <= 0) or key in seen:
            continue
        seen.add(key)
        item = {"player": str(dead.get("player") or entry["player"]),
                "team": team_code,
                "salary_by_season": {str(entry.get("evidence_season")): amount},
                "row_kind": "dead_money",
                "basis": dead.get("basis"),
                "amount_unknown": unknown,
                "inferred": True}
        if dead.get("_player_id") is not None:
            item["_player_id"] = dead.get("_player_id")
        rows.append(item)
    return rows


def _team_baseline(con, team: str, schedules: dict[str, dict[str, Any]], seasons: list[str]) -> dict[str, dict[str, Any]]:
    team_code = canonical_team_abbr(team)
    explicit_dead = _dead_money_schedules(con, team_code)
    inferred_dead = _inferred_dead_schedules(schedules, team_code)
    baseline: dict[str, dict[str, Any]] = {}
    for season in seasons:
        players = []
        roster_total = 0
        for entry in schedules.values():
            if entry["team"] != team_code:
                continue
            status = (entry.get("cap_status_by_season") or {}).get(
                season, entry.get("cap_status") or {})
            if not status.get("counts_as_standard", True):
                continue
            salary = entry["salary_by_season"].get(season)
            if salary:
                roster_total += int(salary)
                players.append({"player": entry["player"], "salary": int(salary),
                                "option": entry["option_years"].get(season)})
        explicit_candidates = []
        inferred_candidates = []
        for entry in explicit_dead:
            if season not in entry["salary_by_season"]:
                continue
            salary = entry["salary_by_season"][season]
            item = {"player": entry["player"],
                    "salary": int(salary) if salary is not None else None,
                    "team": entry["team"]}
            if salary is None:
                item["amount_unknown"] = True
            if entry.get("_player_id") is not None:
                item["_player_id"] = entry.get("_player_id")
            explicit_candidates.append(item)
        for entry in inferred_dead:
            if season not in entry["salary_by_season"]:
                continue
            salary = entry["salary_by_season"][season]
            item = {"player": entry["player"],
                    "salary": int(salary) if salary is not None else None,
                    "team": entry["team"],
                    "row_kind": "dead_money",
                    "basis": entry.get("basis")}
            if entry.get("amount_unknown"):
                item["amount_unknown"] = True
            if entry.get("_player_id") is not None:
                item["_player_id"] = entry.get("_player_id")
            inferred_candidates.append(item)
        dead_detail = merge_dead_rows(explicit_candidates, inferred_candidates, team_code)
        dead_total = sum(int(row.get("salary") or 0) for row in dead_detail)
        dead_detail.sort(key=lambda row: -int(row.get("salary") or 0))
        baseline[season] = {"payroll": roster_total + dead_total,
                            "roster_payroll": roster_total,
                            "dead_money": dead_total,
                            "dead_money_detail": dead_detail,
                            "players": players,
                            "roster_count": len(players)}
    return baseline


def _signing_effect(raw: dict[str, Any], index: int, target: str) -> tuple[dict[str, Any] | None, str | None]:
    amount = raw.get("amount")
    if not isinstance(amount, (int, float)) or amount <= 0:
        return None, "signing needs a positive amount"
    fallback = f"${amount / 1_000_000:g}M signing"
    label = str(raw.get("label") or raw.get("player") or fallback)
    player = str(raw.get("player") or label)
    return {"move": index, "kind": "signing", "detail": f"sign {label}",
            "player": player,
            "delta": int(amount), "roster_delta": 1, "exactness": "exact",
            "term": "one_year_disclosed", "season": target}, None


def _waive_effects(con, team: str, raw: dict[str, Any], index: int, target: str,
                   seasons: list[str], schedules: dict[str, dict[str, Any]],
                   warnings: list[str]) -> tuple[list[dict[str, Any]], str | None, str | None]:
    player = str(raw.get("player") or "").strip()
    stretch = bool(raw.get("stretch"))
    total, matched, unknown = _match_trade_players(team, player, con, target)
    if unknown or not matched:
        return [], None, f"could not match {player} on {team}"
    name = matched[0]
    schedule = schedules.get(name.lower())
    salary_x = int((schedule or {}).get("salary_by_season", {}).get(target) or 0)
    tail = player_contract_tail(con, name, team, target)
    amounts = waiver_dead_money(
        salary_x, (tail or {}).get("guaranteed"),
        (tail or {}).get("years_remaining"), stretch,
        (tail or {}).get("future_years_remaining"), "pre_sep1")
    effects = [{"move": index, "kind": "waive", "detail": f"{name} dead money",
                "delta": int(amounts["dead_cap"]), "roster_delta": 0,
                "exactness": "derived", "season": target,
                "disclosure": "waiver dead money uses the remaining guaranteed pool"}]
    if stretch and amounts["stretch_years"]:
        installment = int(amounts["stretched_dead_cap"])
        spread = [s for s in seasons if s > target][:max(0, int(amounts["stretch_years"]) - 1)]
        for season in spread:
            effects.append({"move": index, "kind": "waive_stretch",
                            "detail": f"{name} stretched installment",
                            "delta": installment, "roster_delta": 0,
                            "exactness": "derived", "season": season})
        if int(amounts["stretch_years"]) - 1 > len(spread):
            warnings.append(f"{name}'s stretch installments continue beyond the projection horizon")
    elif not stretch:
        remaining = max(0, int(amounts["guaranteed"]) - int(amounts["dead_cap"]))
        future = [s for s in seasons if s > target
                  and (schedule or {}).get("salary_by_season", {}).get(s)]
        if remaining and future:
            per_year = int(round(remaining / len(future)))
            for season in future:
                effects.append({"move": index, "kind": "waive_dead",
                                "detail": f"{name} dead money (approximate allocation)",
                                "delta": per_year, "roster_delta": 0,
                                "exactness": "proxy", "season": season,
                                "disclosure": "per-year guarantee allocations unavailable; remaining guaranteed spread evenly across the contract's listed years"})
    return effects, name, None


def _trade_in_effects(con, team: str, raw: dict[str, Any], index: int, target: str,
                      seasons: list[str], schedules: dict[str, dict[str, Any]]) -> tuple[list[dict[str, Any]], str | None]:
    player = str(raw.get("player") or "").strip()
    found = _locate_player_team(player, con, target)
    if found is None:
        return [], f"could not locate {player}"
    cname, cteam, csal = found
    if canonical_team_abbr(str(cteam)) == canonical_team_abbr(team):
        return [], f"{cname} is already on {team}"
    schedule = schedules.get(cname.lower())
    if not schedule or not schedule.get("salary_by_season"):
        return [{"move": index, "kind": "trade_in", "detail": f"in {cname}",
                 "delta": int(csal or 0), "roster_delta": 1, "exactness": "unresolved",
                 "season": target,
                 "disclosure": "no contract schedule; first-season salary only"}], None
    effects = []
    for season in seasons:
        if season < target:
            continue
        salary = int(schedule["salary_by_season"].get(season) or 0)
        if salary:
            effects.append({"move": index, "kind": "trade_in",
                            "detail": f"in {cname} (from {cteam})",
                            "delta": salary, "roster_delta": 1,
                            "exactness": "exact", "season": season})
    return effects, None


def _extend_effects(raw: dict[str, Any], index: int, target: str,
                    seasons: list[str], schedules: dict[str, dict[str, Any]],
                    team: str) -> tuple[list[dict[str, Any]], str | None]:
    player = str(raw.get("player") or "").strip()
    years = raw.get("years")
    first_amount = raw.get("first_year_amount")
    if not player:
        return [], "extend needs a player"
    if not isinstance(years, int) or years < 1 or years > 5:
        return [], "extend needs years between 1 and 5"
    if not isinstance(first_amount, (int, float)) or first_amount <= 0:
        return [], "extend needs a positive first_year_amount"
    schedule = schedules.get(player.lower())
    if not schedule or canonical_team_abbr(schedule.get("team") or "") != canonical_team_abbr(team):
        return [], f"could not match {player} on {team}"
    contracted = sorted(s for s, v in schedule.get("salary_by_season", {}).items() if v)
    if not contracted:
        return [], f"{player} has no contract schedule to extend"
    last_year = contracted[-1]
    anchor = _shift_season(target, 1) or target
    start = max(_shift_season(last_year, 1) or "", anchor)
    effects = []
    for offset in range(int(years)):
        season = _shift_season(start, offset)
        if not season or season not in seasons:
            continue
        effects.append({"move": index, "kind": "extend",
                        "detail": f"{schedule['player']} extension year {offset + 1}",
                        "delta": int(first_amount), "roster_delta": 1 if season == start else 0,
                        "exactness": "unvalidated", "season": season,
                        "disclosure": "extension amounts are flat and unvalidated against max-extension rules; validation depth is a later slice"})
    return effects, None


def _season_start_year(season: str) -> int | None:
    try:
        return int(str(season)[:4])
    except (TypeError, ValueError):
        return None


def _hold_key(row: dict[str, Any]) -> str:
    return normalize_name(row.get("player") or row.get("PLAYER_NAME"))


def _hold_active_in_baseline(row: dict[str, Any]) -> bool:
    dependency = str(row.get("scenario_dependency") or "")
    if dependency == "option_decision_required":
        return False
    if "active_in_baseline" in row:
        return bool(row.get("active_in_baseline"))
    return dependency in ("active_expired_contract", "active_type_unknown")


def _option_dependent_hold(row: dict[str, Any]) -> bool:
    return str(row.get("scenario_dependency") or "") == "option_decision_required"


def _match_hold(rows: list[dict[str, Any]], player: object) -> dict[str, Any] | None:
    wanted = normalize_name(player)
    if not wanted:
        return None
    for row in rows:
        if _hold_key(row) == wanted:
            return row
    for row in rows:
        key = _hold_key(row)
        if key and (wanted in key or key in wanted):
            return row
    return None


def _option_dependency_error(hold: dict[str, Any], declined: set[str], action: str) -> str | None:
    if _option_dependent_hold(hold) and _hold_key(hold) not in declined:
        return (f"{action} {hold.get('player') or hold.get('PLAYER_NAME')} requires a prior option decision decline; "
                "the option salary is still committed")
    return None


def _season_holds(con, team: str, season: str) -> dict[str, Any]:
    year = _season_start_year(season)
    if year is None:
        return {"rows": [], "total": 0, "exactness": "unknown", "source": "invalid season"}
    payload = derive_cap_holds(con, year, team)
    meta = payload.get("meta") or {}
    rows = payload.get("rows") or []
    active = [row for row in rows if _hold_active_in_baseline(row)]
    inactive = [row for row in rows if not _hold_active_in_baseline(row)]
    total = int(payload.get("active_total") or 0)
    status = str(meta.get("derivation_status") or "unavailable")
    exactness = "estimated" if status == "calculator_derived" else "unvalidated"
    if int(payload.get("unknown_count") or 0) > 0:
        exactness = "partially_unknown"
    return {"rows": active, "inactive_rows": inactive, "all_rows": list(rows),
            "total": total, "exactness": exactness,
            "source": status,
            "unknown_count": int(payload.get("unknown_count") or 0)}


def _renounce_effect(holds: dict[str, Any], raw: dict[str, Any], index: int,
                     state: dict[str, set[str]]) -> tuple[dict[str, Any] | None, str | None]:
    player = str(raw.get("player") or "").strip()
    if not player:
        return None, "renounce needs a player"
    match = _match_hold(list(holds.get("all_rows") or holds["rows"]), player)
    if match is None:
        return None, f"{raw.get('player')} has no active cap hold to renounce. Renounce applies to expired contracts with retained rights"
    option_error = _option_dependency_error(match, state["declined"], "renouncing")
    if option_error is not None:
        return None, option_error
    key = _hold_key(match)
    active = _hold_active_in_baseline(match) or key in state["declined"]
    if key in state["renounced"]:
        return None, f"{raw.get('player')} is already renounced in this scenario"
    if not active or key in state["extinguished"]:
        return None, f"{raw.get('player')} has no active cap hold to renounce. Renounce applies to expired contracts with retained rights"
    amount = hold_amount(match)
    if not amount:
        return None, f"{match.get('PLAYER_NAME')}'s hold amount is unknown; the derivation could not price it, so renouncing is honestly unavailable rather than zero-freed"
    name = str(match.get("PLAYER_NAME") or match.get("player"))
    return {"move": index, "kind": "renounce",
            "detail": f"renounce {name}: cap hold released",
            "delta": -amount, "roster_delta": 0,
            "exactness": holds["exactness"] if holds["exactness"] in ("estimated", "partially_unknown") else "unvalidated",
            "player_key": key}, None


def _signing_hold_effect(holds: dict[str, Any], raw: dict[str, Any], index: int,
                         state: dict[str, set[str]]) -> tuple[dict[str, Any] | None, str | None]:
    player = raw.get("player") or raw.get("label")
    if not player:
        return None, None
    match = _match_hold(list(holds.get("all_rows") or holds["rows"]), player)
    if match is None:
        return None, None
    option_error = _option_dependency_error(match, state["declined"], "signing")
    if option_error is not None:
        return None, option_error
    key = _hold_key(match)
    active = _hold_active_in_baseline(match) or key in state["declined"]
    if not active or key in state["extinguished"]:
        return None, None
    amount = hold_amount(match)
    if not amount:
        return None, None
    name = str(match.get("PLAYER_NAME") or match.get("player"))
    return {"move": index, "kind": "cap_hold_extinguished",
            "detail": f"signing {name}: cap hold extinguished",
            "delta": -amount, "roster_delta": 0,
            "exactness": holds["exactness"] if holds["exactness"] in ("estimated", "partially_unknown") else "unvalidated",
            "player_key": key}, None


def _option_hold_effect(holds: dict[str, Any], player: str, index: int,
                        state: dict[str, set[str]]) -> dict[str, Any] | None:
    match = _match_hold(list(holds.get("all_rows") or holds["rows"]), player)
    if match is None or not _option_dependent_hold(match):
        return None
    key = _hold_key(match)
    if key in state["declined"] or key in state["extinguished"]:
        return None
    amount = hold_amount(match)
    state["declined"].add(key)
    if not amount:
        return None
    name = str(match.get("PLAYER_NAME") or match.get("player"))
    return {"move": index, "kind": "option_cap_hold",
            "detail": f"{name} declined-option cap hold activated",
            "delta": amount, "roster_delta": 0,
            "exactness": holds["exactness"] if holds["exactness"] in ("estimated", "partially_unknown") else "unvalidated",
            "player_key": key}


_EXCEPTION_AMOUNTS_2026_27 = {"mle": 15_044_000, "bae": 5_477_000, "room": 9_366_000}
_CAP_BASE_2026_27 = 164_961_000


def _exceptions_block(lines: dict[str, Any], effects: list[dict[str, Any]],
                      pay_after: int) -> list[dict[str, Any]]:
    ratio = lines["cap"] / _CAP_BASE_2026_27
    rows = []
    for name, base in _EXCEPTION_AMOUNTS_2026_27.items():
        amount = int(round(base * ratio, -3))
        signings = [e for e in effects
                    if e["kind"] == "signing" and e.get("exception") == name]
        used = sum(int(e["delta"]) for e in signings)
        over = next((int(e["delta"]) for e in signings if int(e["delta"]) > amount), 0)
        rows.append({
            "exception": name,
            "amount": amount,
            "used": used,
            "remaining": max(0, amount - used),
            "hard_caps": bool(signings) and name in ("mle", "bae"),
            "exceeds": over or None,
            "unavailable": pay_after > lines["apron1"] and name in ("mle", "bae"),
        })
    return rows


def _tpe_disclosures(rows: list, season: str, team: str,
                     default_origin: int | None = None) -> list[dict[str, Any]]:
    try:
        start = int(str(season)[:4])
    except (TypeError, ValueError):
        return []
    out = []
    for raw in rows:
        if not isinstance(raw, dict):
            continue
        if str(raw.get("team") or "").strip().upper() != team:
            continue
        amount = raw.get("amount")
        if not isinstance(amount, int) or amount <= 0:
            continue
        origin = raw.get("origin_year")
        origin = int(origin) if isinstance(origin, int) else (default_origin or start)
        if origin + 1 < start:
            status = "expired"
        elif origin > start:
            status = "not yet available"
        else:
            status = "active"
        out.append({
            "amount": amount,
            "kind": str(raw.get("kind") or "ordinary"),
            "exactness": str(raw.get("exactness") or "user_declared"),
            "status": status,
            "note": ("exception disclosure only, no payroll effect; season-grain expiry is "
                     "approximate, exact dates are not carried"),
        })
    return out


def project_cap_scenario(con, payload: dict[str, Any]) -> dict[str, Any]:
    team = str(payload.get("team") or "").strip().upper()
    base_season = str(payload.get("season") or "").strip() or "2026-27"
    moves_in = payload.get("moves")
    tpes_in = payload.get("tpes") or []
    if not team:
        return {"ok": False, "error": "team needed"}
    if not isinstance(moves_in, list):
        return {"ok": False, "error": "moves must be a list"}
    horizon = payload.get("horizon")
    try:
        forward = max(1, min(3, int(horizon))) if horizon is not None else 3
    except (TypeError, ValueError):
        forward = 3
    seasons = _horizon_seasons(base_season, forward + 1)
    available = set(_salary_column_seasons(con))
    coverage = [s for s in seasons if s in available]
    truncated = [s for s in seasons if s not in available]
    seasons = coverage or seasons[:1]

    schedules = _player_schedules(con, base_season, seasons)
    baseline = _team_baseline(con, team, schedules, seasons)
    holds_by_season = {season: _season_holds(con, team, season) for season in seasons}
    for season, holds in holds_by_season.items():
        if holds["total"]:
            entry = baseline.get(season)
            if entry is not None:
                entry["payroll"] = int(entry["payroll"]) + holds["total"]

    errors: list[dict[str, str]] = []
    warnings: list[str] = []
    moves_by_season: dict[str, list[tuple[int, dict[str, Any]]]] = {s: [] for s in seasons}
    for i, raw in enumerate(moves_in):
        if not isinstance(raw, dict):
            errors.append({"move": str(i), "error": "move must be an object"})
            continue
        target = str(raw.get("season") or base_season).strip() or base_season
        if target not in moves_by_season:
            errors.append({"move": str(i), "error":
                           f"move targets {target}, outside the projection horizon "
                           f"{seasons[0]}–{seasons[-1]}"})
            continue
        moves_by_season[target].append((i, raw))

    carried: dict[str, list[dict[str, Any]]] = {s: [] for s in seasons}
    removals: list[tuple[str, str]] = []
    row_additions: dict[str, list[dict[str, Any]]] = {s: [] for s in seasons}
    salary_overrides: dict[tuple[str, str], int] = {}
    hold_states = {season: {"declined": set(), "extinguished": set(), "renounced": set()} for season in seasons}

    def add_effect(season: str, effect: dict[str, Any]) -> None:
        if season in carried:
            carried[season].append(effect)

    def remove_roster_row(name: str, from_season: str) -> None:
        removals.append((name.lower(), from_season))

    def add_roster_row(season: str, row: dict[str, Any]) -> None:
        if season in row_additions:
            row_additions[season].append(row)

    def remove_player_forward(name: str, from_season: str, move_index: int, kind: str) -> None:
        remove_roster_row(name, from_season)
        schedule = schedules.get(name.lower())
        for season in seasons:
            if season < from_season:
                continue
            salary = int((schedule or {}).get("salary_by_season", {}).get(season) or 0)
            if salary:
                add_effect(season, {"move": move_index, "kind": kind,
                                    "detail": f"{name} off the books",
                                    "delta": -salary, "roster_delta": -1,
                                    "exactness": "exact" if schedule else "unresolved"})

    for i, raw in enumerate(moves_in):
        if not isinstance(raw, dict):
            continue
        kind = str(raw.get("kind") or "").strip()
        target = str(raw.get("season") or base_season).strip() or base_season
        if target not in moves_by_season:
            continue
        if kind == "signing":
            effect, error = _signing_effect(raw, i, target)
            hold_effect = None
            hold_error = None
            if effect:
                hold_effect, hold_error = _signing_hold_effect(
                    holds_by_season.get(target) or {"rows": [], "exactness": "unknown"},
                    raw, i, hold_states[target])
            if error or hold_error:
                errors.append({"move": str(i), "error": error or hold_error})
            elif effect:
                exception = str(raw.get("exception") or "cap_room").strip().lower() or "cap_room"
                if exception not in ("cap_room", "mle", "bae", "minimum", "bird"):
                    errors.append({"move": str(i), "error": f"unknown exception '{exception}'"})
                    continue
                effect["exception"] = exception
                term_years = raw.get("years")
                if isinstance(term_years, int) and term_years > 1:
                    effect["term"] = f"{term_years}_year_flat_disclosed"
                add_effect(target, {k: v for k, v in effect.items() if k != "season"})
                if hold_effect is not None:
                    add_effect(target, hold_effect)
                    hold_states[target]["extinguished"].add(hold_effect["player_key"])
                term_len = term_years if isinstance(term_years, int) and term_years > 1 else 1
                for season in [target] + [s for s in seasons if s > target][:term_len - 1]:
                    add_roster_row(season, {"player": str(effect.get("player") or effect["detail"]),
                                            "salary": int(effect["delta"]), "option": None})
                if isinstance(term_years, int) and term_years > 1:
                    forward = [s for s in seasons if s > target][:term_years - 1]
                    for year_index, season in enumerate(forward, start=2):
                        continuation = {k: v for k, v in effect.items() if k not in ("season", "exception")}
                        continuation["detail"] = f"{effect['detail']}, year {year_index} of {term_years}"
                        continuation["roster_delta"] = 0
                        continuation["continuation"] = True
                        add_effect(season, continuation)
                    if term_years - 1 > len(forward):
                        warnings.append(f"{effect['detail']} continues beyond the projection horizon")
        elif kind == "extend":
            effects, error = _extend_effects(raw, i, target, seasons, schedules, team)
            if error:
                errors.append({"move": str(i), "error": error})
            for effect in effects:
                season_key = effect.pop("season")
                player_key = str(effect.get("detail") or "").split(" extension year")[0].strip()
                if player_key:
                    salary_overrides[(player_key.lower(), season_key)] = int(effect["delta"])
                add_effect(season_key, effect)
        elif kind == "trade_out":
            player = str(raw.get("player") or "").strip()
            total, matched, unknown = _match_trade_players(team, player, con, target)
            if unknown or not matched:
                errors.append({"move": str(i), "error": f"could not match {player} on {team}"})
                continue
            remove_player_forward(matched[0], target, i, "trade_out")
        elif kind == "trade_in":
            effects, error = _trade_in_effects(con, team, raw, i, target, seasons, schedules)
            if error:
                errors.append({"move": str(i), "error": error})
            incoming_name = None
            for effect in effects:
                season_key = effect.pop("season")
                detail = str(effect.get("detail") or "")
                if detail.startswith("in "):
                    incoming_name = detail[3:].split(" (from ")[0]
                if incoming_name:
                    add_roster_row(season_key, {"player": incoming_name,
                                                "salary": int(effect["delta"]), "option": None})
                add_effect(season_key, effect)
        elif kind == "waive":
            effects, waived_name, error = _waive_effects(con, team, raw, i, target, seasons, schedules, warnings)
            if error:
                errors.append({"move": str(i), "error": error})
                continue
            remove_player_forward(waived_name, target, i, "waive")
            for effect in effects:
                season_key = effect.pop("season")
                add_effect(season_key, effect)
        elif kind == "option_decision":
            player = str(raw.get("player") or "").strip()
            exercise = bool(raw.get("exercise", True))
            if exercise:
                continue
            schedule = schedules.get(player.lower())
            if not schedule:
                errors.append({"move": str(i), "error": f"could not match {player} on {team}"})
                continue
            salary_x = int(schedule.get("salary_by_season", {}).get(target) or 0)
            if salary_x:
                remove_roster_row(schedule["player"], target)
                add_effect(target, {"move": i, "kind": "option_decision",
                                    "detail": f"{schedule['player']} option declined",
                                    "delta": -salary_x, "roster_delta": -1,
                                    "exactness": "exact"})
            hold_effect = _option_hold_effect(
                holds_by_season.get(target) or {"rows": [], "exactness": "unknown"},
                schedule["player"], i, hold_states[target])
            if hold_effect is not None:
                add_effect(target, hold_effect)
        elif kind == "renounce":
            effect, error = _renounce_effect(
                holds_by_season.get(target) or {"rows": [], "exactness": "unknown"},
                raw, i, hold_states[target])
            if error:
                errors.append({"move": str(i), "error": error})
                continue
            already = any(e.get("kind") == "renounce" and e.get("player_key") == effect["player_key"]
                          for e in carried.get(target, []))
            if already:
                errors.append({"move": str(i), "error": f"{raw.get('player')} is already renounced in this scenario"})
                continue
            add_effect(target, effect)
            hold_states[target]["extinguished"].add(effect["player_key"])
            hold_states[target]["renounced"].add(effect["player_key"])
        else:
            errors.append({"move": str(i), "error": f"unknown move kind '{kind}'"})

    def adjusted_rows(season: str, base_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        removed = {name for name, from_season in removals if season >= from_season}
        rows = []
        for row in base_rows:
            key = str(row.get("player") or "").lower()
            if key in removed:
                continue
            override = salary_overrides.get((key, season))
            if override is not None:
                rows.append({**row, "salary": override})
            else:
                rows.append(row)
        present = {str(r.get("player") or "").lower() for r in rows}
        for (name, override_season), amount in salary_overrides.items():
            if override_season == season and name not in present and name not in removed:
                canonical = next((str(r.get("player")) for r in base_rows
                                  if str(r.get("player") or "").lower() == name), name)
                rows.append({"player": canonical, "salary": amount, "option": None})
        rows.extend(row_additions.get(season, []))
        rows.sort(key=lambda r: -int(r.get("salary") or 0))
        return rows

    season_blocks: list[dict[str, Any]] = []
    for season in seasons:
        lines_res = cap_lines_for_season(con, season)
        if not lines_res["ok"]:
            return {"ok": False, "error": lines_res["error"],
                    "reason": "cap_lines_unavailable"}
        lines = lines_res["lines"]
        lines_projected = bool(lines_res["projected"])
        base = baseline.get(season, {"payroll": 0, "players": [], "roster_count": 0})
        effects = carried.get(season, [])
        pay_after = int(base["payroll"]) + sum(int(e["delta"]) for e in effects)
        roster_after = int(base["roster_count"]) + sum(int(e.get("roster_delta") or 0) for e in effects)
        state = apron_state(pay_after, lines)
        hard_cap_triggers = sorted({e.get("exception") for e in effects
                                    if e.get("exception") in ("mle", "bae")})
        hard_cap_violation = ""
        if hard_cap_triggers and pay_after > lines["apron1"]:
            hard_cap_violation = (f"{team} is hard-capped at the first apron after using "
                                  f"the {'/'.join(t.upper() for t in hard_cap_triggers)}. "
                                  f"Payroll {_fmt_money(pay_after)} exceeds {_fmt_money(lines['apron1'])}")
        exception_usage = sorted({e["exception"] for e in effects
                                  if e.get("exception") and e["exception"] != "cap_room"})
        season_moves = moves_by_season.get(season, [])
        ordering_notes = []
        signings = [e for e in effects if e["kind"] == "signing" and not e.get("continuation")
                    and e.get("exception", "cap_room") == "cap_room"]
        for effect in signings:
            prior_deltas = sum(int(e["delta"]) for e in effects if e["move"] < effect["move"])
            simultaneous_hold_delta = sum(int(e["delta"]) for e in effects
                                          if e["move"] == effect["move"]
                                          and e["kind"] == "cap_hold_extinguished")
            running_pay = int(base["payroll"]) + prior_deltas + simultaneous_hold_delta
            room_at_signing = lines["cap"] - running_pay
            if effect["delta"] > room_at_signing:
                ordering_notes.append(
                    f"move {effect['move']}: signing {_fmt_money(effect['delta'])} exceeds the "
                    f"{_fmt_money(room_at_signing)} of cap room available at that point. "
                    f"This is order-dependent: renouncing or waiving earlier in the sequence changes this")
        roster_issue_list = roster_issues(roster_after)
        season_blocks.append({
            "season": season,
            "pay_before": int(base["payroll"]),
            "pay_after": pay_after,
            "roster_payroll": int(base.get("roster_payroll") or 0),
            "dead_money": int(base.get("dead_money") or 0),
            "dead_money_detail": list(base.get("dead_money_detail") or []),
            **({"dead_money_players": [{"player": p["player"], "salary": p["salary"]}
                                       for p in base.get("dead_money_detail", [])]}
               if base.get("dead_money_detail") else {}),
            "cap_room": lines["cap"] - pay_after,
            "state": state,
            "lines": lines,
            "lines_projected": lines_projected,
            "cap_lines_source": lines_res["source"],
            "cap_lines_exact": bool(lines_res["exact"]),
            "cap_lines_approximation_basis": lines_res["approximation_basis"],
            "players": adjusted_rows(season, base["players"]),
            "roster_before": int(base["roster_count"]),
            "roster_after": roster_after,
            "roster_issues": roster_issue_list,
            "hard_cap": hard_cap_triggers[0] + " apron" if hard_cap_triggers else "",
            "hard_cap_violation": hard_cap_violation,
            "exception_usage": exception_usage,
            "effects": [{"move": e["move"], "kind": e["kind"], "detail": e["detail"],
                         "delta": int(e["delta"]), "exactness": e.get("exactness", "exact"),
                         **({"disclosure": e["disclosure"]} if e.get("disclosure") else {})}
                        for e in sorted(effects, key=lambda e: e["move"])],
            "moves_in_season": len(season_moves),
            "ordering_notes": ordering_notes,
            "exceptions": _exceptions_block(lines, effects, pay_after),
            **({"trade_exceptions": disclosed}
               if (disclosed := _tpe_disclosures(
                       tpes_in, season, team,
                       default_origin=int(str(base_season)[:4]))) else {}),
            **({"cap_holds": holds_by_season[season]["total"],
                "cap_holds_exactness": holds_by_season[season]["exactness"],
                "cap_hold_details": [{"player": str(r.get("PLAYER_NAME") or r.get("player") or ""),
                                      "amount": hold_amount(r) or None,
                                      "fa_type": str(r.get("FA_TYPE") or "")}
                                     for r in holds_by_season[season]["rows"]]}
               if holds_by_season[season]["rows"] else {}),
        })

    disclosures = [
        "signings without a stated term project as one-year deals; multi-year signings carry flat annual salary across the term. Raise structure is not modeled",
        "apron and tax comparisons use committed-payroll proxies per the cap-rules derivation contract, not full CBA Apron Team Salary",
    ]
    team_code = canonical_team_abbr(team)
    unknown_two_way = sorted({
        entry["player"] for entry in schedules.values()
        if entry["team"] == team_code
        and set(entry.get("classification_unknown_seasons") or []) & set(seasons)
    })
    if unknown_two_way:
        disclosures.append(
            "two-way formation date is unknown for "
            + ", ".join(unknown_two_way)
            + "; affected salary rows are counted as standard salary in seasons whose two-way status cannot be established")
    dead_seasons = [s for s in seasons if baseline.get(s, {}).get("dead_money")]
    if dead_seasons:
        disclosures.insert(0,
            "payroll is committed payroll including pre-existing dead-money obligations — waived players' "
            "guaranteed money counts against team salary per CBA rules. Each season row carries "
            "the dead-money component separately as dead_money with per-player detail in dead_money_detail; "
            "dead money is not a roster player and does not affect roster count")
    hold_seasons = [s for s in seasons if holds_by_season[s]["rows"]]
    if hold_seasons:
        unknown_total = sum(holds_by_season[s]["unknown_count"] for s in hold_seasons)
        disclosures.append(
            f"cap holds are included in payroll for {', '.join(hold_seasons)} ({holds_by_season[hold_seasons[0]]['source']}"
            + (f", {unknown_total} unpriced" if unknown_total else "")
            + "). A renounced hold leaves the books entirely; re-signing a renounced player at a new salary is a separate signing move")
    disclosures.append(
        "exception usage reflects scenario moves only. League-wide exception consumption "
        "is not derivable from seeded transaction data; the room exception's cap-room-first "
        "ordering and the bae consecutive-year rule are disclosed, not enforced")
    disclosures.append("incomplete-roster minimum charges are not yet projected; the cap sheet includes them for the current season")
    if truncated:
        disclosures.append(f"seasons beyond warehouse salary coverage are excluded: {', '.join(truncated)}")
    return declare_money({
        "ok": True, "team": team, "base_season": base_season,
        "seasons": season_blocks,
        "errors": errors, "warnings": warnings,
        "disclosures": [d for d in disclosures if d],
        "meta": {"horizon_seasons": seasons, "coverage": coverage,
                 "projection_basis": "silver_salaries roster and dead-money contract schedules plus silver_cap_room lines",
                 "cap_lines_by_season": {
                     block["season"]: {
                         "cap_lines_source": block["cap_lines_source"],
                         "cap_lines_exact": block["cap_lines_exact"],
                         "cap_lines_approximation_basis": block["cap_lines_approximation_basis"],
                     }
                     for block in season_blocks
                 },
                 **payroll_proxy_meta()},
    }, ["pay_before", "pay_after", "roster_payroll", "dead_money", "cap_room",
        "salary", "delta", "cap_holds", "amount"])
