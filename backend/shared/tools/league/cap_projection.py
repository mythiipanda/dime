import re as _re
from typing import Any

from ...contracts import canonical_team_abbr, salary_records
from ..cap_rules import apron_state, payroll_proxy_meta, roster_issues
from .cap_hold_derivation import derive_cap_holds, hold_amount
from ._helpers import declare_money
from .cap_sheet import cap_lines_for_season
from .cba_cap import _locate_player_team, _match_trade_players
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


def _player_schedules(con, salary_season: str) -> dict[str, dict[str, Any]]:
    schedules: dict[str, dict[str, Any]] = {}
    for row in salary_records(con, salary_season=salary_season):
        name = str(row.get("PLAYER_NAME") or "")
        if not name:
            continue
        salary_by_season: dict[str, int] = {}
        options: dict[str, str] = {}
        for col, value in row.items():
            m = _re.fullmatch(r"SALARY_(\d{4})_(\d{2})", str(col))
            if m and value:
                salary_by_season[f"{m.group(1)}-{m.group(2)}"] = int(value)
            om = _re.fullmatch(r"OPTION_(\d{4})_(\d{2})", str(col))
            if om and value:
                options[f"{om.group(1)}-{om.group(2)}"] = str(value)
        schedules[name.lower()] = {
            "player": name,
            "team": canonical_team_abbr(row.get("TEAM") or ""),
            "salary_by_season": salary_by_season,
            "option_years": options,
            "guaranteed": row.get("GUARANTEED"),
        }
    return schedules


def _team_baseline(con, team: str, schedules: dict[str, dict[str, Any]], seasons: list[str]) -> dict[str, dict[str, Any]]:
    team_code = canonical_team_abbr(team)
    roster: dict[str, dict[str, Any]] = {}
    for entry in schedules.values():
        if entry["team"] == team_code:
            roster[entry["player"]] = entry
    baseline: dict[str, dict[str, Any]] = {}
    for season in seasons:
        players = []
        total = 0
        for entry in roster.values():
            salary = entry["salary_by_season"].get(season)
            if salary:
                total += int(salary)
                players.append({"player": entry["player"], "salary": int(salary),
                                "option": entry["option_years"].get(season)})
        baseline[season] = {"payroll": total, "players": players,
                            "roster_count": len(players)}
    return baseline


def _dead_money_by_season(con, team: str, seasons: list[str]) -> dict[str, dict[str, Any]]:
    empty = {season: {"total": 0, "players": []} for season in seasons}
    team_code = canonical_team_abbr(team)
    try:
        cols = [r[1] for r in con.execute("PRAGMA table_info(silver_salaries)").fetchall()]
    except Exception:
        return empty
    if "ROW_KIND" not in cols:
        return empty
    salary_col_by_season = {}
    for col in cols:
        m = _re.fullmatch(r"SALARY_(\d{4})_(\d{2})", str(col))
        if m:
            salary_col_by_season[f"{m.group(1)}-{m.group(2)}"] = col
    try:
        cursor = con.execute(
            "SELECT * FROM silver_salaries WHERE ROW_KIND = 'dead_money'")
        names = [d[0] for d in cursor.description]
        records = [dict(zip(names, row)) for row in cursor.fetchall()]
    except Exception:
        return empty
    out = {season: {"total": 0, "players": []} for season in seasons}
    for row in records:
        if canonical_team_abbr(str(row.get("TEAM") or "")) != team_code:
            continue
        player = str(row.get("PLAYER_NAME") or "")
        for season in seasons:
            col = salary_col_by_season.get(season)
            if not col:
                continue
            amount = row.get(col)
            if not amount:
                continue
            out[season]["total"] += int(amount)
            out[season]["players"].append({"player": player, "salary": int(amount)})
    return out


def _signing_effect(raw: dict[str, Any], index: int, target: str) -> tuple[dict[str, Any] | None, str | None]:
    amount = raw.get("amount")
    if not isinstance(amount, (int, float)) or amount <= 0:
        return None, "signing needs a positive amount"
    label = str(raw.get("label") or f"${amount / 1_000_000:g}M signing")
    return {"move": index, "kind": "signing", "detail": f"sign {label}",
            "player": label,
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


def _season_holds(con, team: str, season: str) -> dict[str, Any]:
    year = _season_start_year(season)
    if year is None:
        return {"rows": [], "total": 0, "exactness": "unknown", "source": "invalid season"}
    payload = derive_cap_holds(con, year, team)
    meta = payload.get("meta") or {}
    rows = payload.get("rows") or []
    active = [row for row in rows
              if str(row.get("dependency") or "") == "active_expired_contract"
              or str(row.get("dependency") or "") == "active_type_unknown"]
    if not active:
        active = rows
    total = int(payload.get("active_total") or 0)
    status = str(meta.get("derivation_status") or "unavailable")
    exactness = "estimated" if status == "calculator_derived" else "unvalidated"
    if int(payload.get("unknown_count") or 0) > 0:
        exactness = "partially_unknown"
    return {"rows": active, "total": total, "exactness": exactness,
            "source": status,
            "unknown_count": int(payload.get("unknown_count") or 0)}


def _renounce_effect(holds: dict[str, Any], raw: dict[str, Any], index: int) -> tuple[dict[str, Any] | None, str | None]:
    player = str(raw.get("player") or "").strip().lower()
    if not player:
        return None, "renounce needs a player"
    match = None
    for row in holds["rows"]:
        name = str(row.get("PLAYER_NAME") or row.get("player") or "").lower()
        if player in name or name in player:
            match = row
            break
    if match is None:
        return None, f"{raw.get('player')} has no active cap hold to renounce. Renounce applies to expired contracts with retained rights"
    amount = hold_amount(match)
    if not amount:
        return None, f"{match.get('PLAYER_NAME')}'s hold amount is unknown; the derivation could not price it, so renouncing is honestly unavailable rather than zero-freed"
    name = str(match.get("PLAYER_NAME") or match.get("player"))
    return {"move": index, "kind": "renounce",
            "detail": f"renounce {name}: cap hold released",
            "delta": -amount, "roster_delta": 0,
            "exactness": holds["exactness"] if holds["exactness"] in ("estimated", "partially_unknown") else "unvalidated",
            "player_key": name.lower()}, None


_EXCEPTION_AMOUNTS_2026_27 = {"mle": 15_044_000, "bae": 5_477_000, "room": 9_366_000}
_CAP_BASE_2026_27 = 164_961_000


def _exceptions_block(lines: dict[str, Any], effects: list[dict[str, Any]],
                      pay_after: int) -> list[dict[str, Any]]:
    ratio = lines["cap"] / _CAP_BASE_2026_27 if lines.get("cap") else 1.0
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

    schedules = _player_schedules(con, base_season)
    baseline = _team_baseline(con, team, schedules, seasons)
    dead_by_season = _dead_money_by_season(con, team, seasons)
    for season, dead in dead_by_season.items():
        entry = baseline.get(season)
        if entry is not None and dead["total"]:
            entry["payroll"] = int(entry["payroll"]) + dead["total"]
            entry["dead_money"] = dead["total"]
            entry["dead_players"] = dead["players"]
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
            if error:
                errors.append({"move": str(i), "error": error})
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
        elif kind == "renounce":
            effect, error = _renounce_effect(holds_by_season.get(target) or {"rows": [], "exactness": "unknown"}, raw, i)
            if error:
                errors.append({"move": str(i), "error": error})
                continue
            already = any(e.get("kind") == "renounce" and e.get("player_key") == effect["player_key"]
                          for e in carried.get(target, []))
            if already:
                errors.append({"move": str(i), "error": f"{raw.get('player')} is already renounced in this scenario"})
                continue
            add_effect(target, effect)
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
        lines, lines_projected = cap_lines_for_season(con, season)
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
            running_pay = int(base["payroll"]) + prior_deltas
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
            **({"dead_money": int(base["dead_money"]),
                "dead_money_players": [{"player": p["player"], "salary": p["salary"]}
                                       for p in base.get("dead_players", [])]}
               if base.get("dead_money") else {}),
            "cap_room": lines["cap"] - pay_after,
            "state": state,
            "lines": lines,
            "lines_projected": lines_projected,
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
    dead_seasons = [s for s in seasons if baseline.get(s, {}).get("dead_money")]
    if dead_seasons:
        disclosures.insert(0,
            "payroll is committed payroll including dead-money obligations — waived players' "
            "guaranteed money counts against team salary per CBA rules. Each season row carries "
            "the dead-money component separately as dead_money with per-player detail in dead_money_players")
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
    if len(seasons) > 1:
        disclosures.append("incomplete-roster minimum charges are not yet projected; the cap sheet includes them for the current season")
    if truncated:
        disclosures.append(f"seasons beyond warehouse salary coverage are excluded: {', '.join(truncated)}")
    return declare_money({
        "ok": True, "team": team, "base_season": base_season,
        "seasons": season_blocks,
        "errors": errors, "warnings": warnings,
        "disclosures": [d for d in disclosures if d],
        "meta": {"horizon_seasons": seasons, "coverage": coverage,
                 "projection_basis": "silver_salaries contract schedules plus silver_cap_room lines",
                 **payroll_proxy_meta()},
    }, ["pay_before", "pay_after", "cap_room", "salary", "delta", "cap_holds", "amount"])
