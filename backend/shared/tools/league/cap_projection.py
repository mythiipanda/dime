import re as _re
from typing import Any

from ...contracts import canonical_team_abbr, salary_records
from ..cap_rules import apron_state, payroll_proxy_meta, roster_issues
from .cap_sheet import cap_lines_for_season
from .cba_cap import _locate_player_team, _match_trade_players
from .waivers import player_contract_tail, waiver_dead_money

_SEASON_RE = _re.compile(r"^(\d{4})-(\d{2})$")


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


def _signing_effect(raw: dict[str, Any], index: int, target: str) -> tuple[dict[str, Any] | None, str | None]:
    amount = raw.get("amount")
    if not isinstance(amount, (int, float)) or amount <= 0:
        return None, "signing needs a positive amount"
    label = str(raw.get("label") or f"${amount / 1_000_000:g}M signing")
    return {"move": index, "kind": "signing", "detail": f"sign {label}",
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
                                "disclosure": "per-year guarantee allocations unavailable — remaining guaranteed spread evenly across the contract's listed years"})
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
                 "disclosure": "no contract schedule — first-season salary only"}], None
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
                        "disclosure": "extension amounts are flat and unvalidated against max-extension rules — validation depth is a later slice"})
    return effects, None


def project_cap_scenario(con, payload: dict[str, Any]) -> dict[str, Any]:
    team = str(payload.get("team") or "").strip().upper()
    base_season = str(payload.get("season") or "").strip() or "2026-27"
    moves_in = payload.get("moves")
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

    def add_effect(season: str, effect: dict[str, Any]) -> None:
        if season in carried:
            carried[season].append(effect)

    def remove_player_forward(name: str, from_season: str, move_index: int, kind: str) -> None:
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
                add_effect(target, {k: v for k, v in effect.items() if k != "season"})
        elif kind == "extend":
            effects, error = _extend_effects(raw, i, target, seasons, schedules, team)
            if error:
                errors.append({"move": str(i), "error": error})
            for effect in effects:
                season_key = effect.pop("season")
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
            for effect in effects:
                season_key = effect.pop("season")
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
                add_effect(target, {"move": i, "kind": "option_decision",
                                    "detail": f"{schedule['player']} option declined",
                                    "delta": -salary_x, "roster_delta": -1,
                                    "exactness": "exact"})
        else:
            errors.append({"move": str(i), "error": f"unknown move kind '{kind}'"})

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
                                  f"the {'/'.join(t.upper() for t in hard_cap_triggers)} — "
                                  f"payroll ${pay_after:,} exceeds ${lines['apron1']:,}")
        exception_usage = sorted({e["exception"] for e in effects
                                  if e.get("exception") and e["exception"] != "cap_room"})
        season_moves = moves_by_season.get(season, [])
        ordering_notes = []
        signings = [e for e in effects if e["kind"] == "signing" and e.get("exception", "cap_room") == "cap_room"]
        for effect in signings:
            prior_deltas = sum(int(e["delta"]) for e in effects if e["move"] < effect["move"])
            running_pay = int(base["payroll"]) + prior_deltas
            room_at_signing = lines["cap"] - running_pay
            if effect["delta"] > room_at_signing:
                ordering_notes.append(
                    f"move {effect['move']}: signing ${effect['delta']:,} exceeds cap room "
                    f"${room_at_signing:,} available at that point — order-dependent; "
                    f"renouncing or waiving earlier in the sequence changes this")
        roster_issue_list = roster_issues(roster_after)
        season_blocks.append({
            "season": season,
            "pay_before": int(base["payroll"]),
            "pay_after": pay_after,
            "cap_room": lines["cap"] - pay_after,
            "state": state,
            "lines": lines,
            "lines_projected": lines_projected,
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
        })

    disclosures = [
        "signings project as one-year deals — contract structure (years, raises) arrives with the signing move vocabulary",
        "apron and tax comparisons use committed-payroll proxies per the cap-rules derivation contract, not full CBA Apron Team Salary",
    ]
    if truncated:
        disclosures.append(f"seasons beyond warehouse salary coverage are excluded: {', '.join(truncated)}")
    return {
        "ok": True, "team": team, "base_season": base_season,
        "seasons": season_blocks,
        "errors": errors, "warnings": warnings,
        "disclosures": [d for d in disclosures if d],
        "meta": {"horizon_seasons": seasons, "coverage": coverage,
                 "projection_basis": "silver_salaries contract schedules plus silver_cap_room lines",
                 **payroll_proxy_meta()},
    }
