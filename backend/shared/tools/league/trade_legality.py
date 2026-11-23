import json as _json
import re as _re
from typing import Any

from langchain_core.tools import tool

from ._helpers import _owned_connection, _pkg
from .cba_cap import (
    CAP,
    SalaryColumnError,
    _allowed_incoming,
    _apron_state,
    _locate_player_team,
    _match_trade_players,
    _payroll,
    _payroll_source,
    _resolve_team_abbr,
    _salary_date,
)
from .trade_value import _trade_guard_vintage_error

_STEPIEN_WINDOW = 7


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
    return (abbr or str(value or "").strip()).upper()


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


def _parse_cash(rows: Any) -> list[dict[str, Any]]:
    if isinstance(rows, dict):
        rows = [rows]
    out: list[dict[str, Any]] = []
    for raw in rows or []:
        if not isinstance(raw, dict):
            continue
        out.append({"from": _leg_team(raw.get("from")),
                    "to": _leg_team(raw.get("to")),
                    "amount": int(raw.get("amount") or 0)})
    return out


def _parse_tpe(rows: Any) -> dict[str, int]:
    if isinstance(rows, dict):
        rows = [rows]
    out: dict[str, int] = {}
    for raw in rows or []:
        if not isinstance(raw, dict):
            continue
        team = _leg_team(raw.get("team"))
        if team:
            out[team] = out.get(team, 0) + int(raw.get("amount") or 0)
    return out


def _parse_snt(value: Any) -> dict[str, Any] | None:
    if not value:
        return None
    if isinstance(value, list):
        value = value[0] if value else None
    if not isinstance(value, dict) or not str(value.get("player") or "").strip():
        return None
    return {"player": str(value["player"]).strip(),
            "new_salary": int(value.get("new_salary") or 0),
            "years": int(value.get("years") or 0)}


def _pick_inventory(con, season_start: int) -> dict[str, set[int]] | None:
    tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
    if "silver_future_picks" not in tables:
        return None
    held: dict[str, set[int]] = {}
    rows = con.execute(
        "select DRAFT_YEAR, ROUND, ORIG_TEAM, STATUS, HELD_BY "
        "from silver_future_picks where ROUND = 1").fetchall()
    for year, _rnd, orig, status, held_by in rows:
        y = int(year)
        if not (season_start < y <= season_start + _STEPIEN_WINDOW):
            continue
        owners: set[str] = set()
        status = str(status or "")
        if status in ("own", "swap"):
            owners.add(str(orig).upper())
        if status == "traded":
            owners.update(h.upper() for h in str(held_by or "").split(";") if h)
        for team in owners:
            held.setdefault(team, set()).add(y)
    return held


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


@tool(description='Trade legality verdict across 2+ teams. "legs" is a JSON array:\n'
    '[{"from":"BOS","to":"DEN","players":"Jayson Tatum, Sam Hauser",'
    '"picks":[{"year":2028,"round":1,"protection":"top-4"},{"year":2030,"round":1,"swap":true}]}].\n'
    'Optional "sign_and_trade" = {"player":"...","new_salary":0,"years":3} '
    '(3-year minimum, BYC handled), "cash" = [{"from","to","amount"}], '
    '"tpe" = [{"team","amount"}]. Checks 2023 CBA salary matching tiers, '
    'apron aggregation bans, post-trade hard caps, TPE/cash bans, the '
    'frozen second-apron pick, and Stepien consecutive-first rules. '
    'REACH FOR THIS for any trade-legality ask beyond a trivial two-team '
    'player swap: sign-and-trade, multi-team, picks/Stepien, apron '
    'aggregation, TPE or cash involved. For a simple two-team salary '
    'match get_trade_check is enough.')
def get_trade_legality(legs: str = "", sign_and_trade: str = "",
                       cash: str = "", tpe: str = "",
                       season: str | None = None) -> dict[str, Any]:
    legs_value, err = _parse_json_arg(legs, "legs")
    if err:
        return {"tool": "get_trade_legality", "ok": False, "error": err}
    cash_value, err = _parse_json_arg(cash, "cash")
    if err:
        return {"tool": "get_trade_legality", "ok": False, "error": err}
    tpe_value, err = _parse_json_arg(tpe, "tpe")
    if err:
        return {"tool": "get_trade_legality", "ok": False, "error": err}
    snt_value, err = _parse_json_arg(sign_and_trade, "sign_and_trade")
    if err:
        return {"tool": "get_trade_legality", "ok": False, "error": err}

    moves: list[dict[str, Any]] = []
    for i, leg in enumerate(legs_value, 1):
        if not isinstance(leg, dict):
            return {"tool": "get_trade_legality", "ok": False,
                    "error": f"leg {i} is not an object"}
        src = _leg_team(leg.get("from"))
        dst = _leg_team(leg.get("to"))
        if not src or not dst:
            return {"tool": "get_trade_legality", "ok": False,
                    "error": f"leg {i} needs from and to teams"}
        if src == dst:
            return {"tool": "get_trade_legality", "ok": False,
                    "error": f"leg {i} is {src} to itself - same team"}
        moves.append({"from": src, "to": dst,
                      "players": _leg_players(leg),
                      "picks": _leg_picks(leg)})
    if not any(m["players"] for m in moves) and not any(m["picks"] for m in moves):
        return {"tool": "get_trade_legality", "ok": False,
                "error": "no players or picks in the legs"}

    cash_moves = _parse_cash(cash_value)
    tpe_by_team = _parse_tpe(tpe_value)
    snt = _parse_snt(snt_value)
    if snt and not any(snt["player"].lower() in p.lower()
                       for m in moves for p in m["players"]):
        return {"tool": "get_trade_legality", "ok": False,
                "error": f"sign_and_trade player {snt['player']} is not in any leg"}

    with _owned_connection(None, read_only=True) as con:
        season = str(season or "").strip()
        if not season:
            cols = {r[1] for r in con.execute(
                "PRAGMA table_info(silver_salaries)").fetchall()}
            explicit = sorted(
                c for c in cols
                if _re.fullmatch(r"SALARY_\d{4}_\d{2}", c))
            season = (explicit[-1][len("SALARY_"):].replace("_", "-")
                      if explicit else
                      (_pkg()._salary_vintage(con)[0]
                       or _pkg().current_season()
                       or _pkg().resolve_season(None)))
        guard_error = _trade_guard_vintage_error(con, season)
        if guard_error:
            return {"tool": "get_trade_legality", "ok": False,
                    "error": guard_error}

        teams = sorted({m["from"] for m in moves} | {m["to"] for m in moves})
        side: dict[str, dict[str, Any]] = {}
        for team in teams:
            plist = ",".join(p for m in moves if m["from"] == team
                             for p in m["players"])
            try:
                out_total, out_names, out_unk = _match_trade_players(
                    team, plist, con, season)
            except SalaryColumnError as exc:
                return {"tool": "get_trade_legality", "ok": False,
                        "reason": exc.reason, "error": str(exc)}
            if out_unk:
                return {"tool": "get_trade_legality", "ok": False,
                        "error": f"{team}: unknown outgoing players "
                                 f"{'; '.join(out_unk)}"}
            try:
                pay_before, _ = _payroll(team, con, season)
            except SalaryColumnError as exc:
                return {"tool": "get_trade_legality", "ok": False,
                        "reason": exc.reason, "error": str(exc)}
            in_names: list[str] = []
            in_total = 0
            for m in moves:
                if m["to"] != team:
                    continue
                for p in m["players"]:
                    hit = _locate_player_team(p, con, season)
                    if hit is None:
                        return {"tool": "get_trade_legality", "ok": False,
                                "error": f"cannot resolve incoming player {p} "
                                         f"to {team}"}
                    cname, _cteam, csal = hit
                    in_names.append(cname)
                    if snt and cname.lower() == snt["player"].lower() \
                            and snt["new_salary"]:
                        in_total += snt["new_salary"]
                    else:
                        in_total += int(csal or 0)
            side[team] = {"out_names": out_names, "out_total": out_total,
                          "in_names": in_names, "in_total": in_total,
                          "pay_before": pay_before}

        salary_date = _salary_date(con)
        source = _payroll_source(con)
        season_start = _salary_season_start(season)
        pick_held = _pick_inventory(con, season_start) \
            if season_start else None
        snt_salary_prior = 0
        if snt:
            hit = _locate_player_team(snt["player"], con, season)
            if hit is not None:
                snt_salary_prior = int(hit[2] or 0)

    issues: list[str] = []
    checks: list[dict[str, Any]] = []
    team_rows: dict[str, Any] = {}
    snt_receiver = next((m["to"] for m in moves
                         if snt and any(p.lower() == snt["player"].lower()
                                        for p in m["players"])), None)
    for team in teams:
        s = side[team]
        out_eff = s["out_total"]
        byc_note = None
        if snt and any(p.lower() == snt["player"].lower()
                       for p in s["out_names"]) and snt["new_salary"]:
            raise_ratio = (snt["new_salary"] / snt_salary_prior
                           if snt_salary_prior else 0)
            if raise_ratio > 1.2 and s["pay_before"] > CAP["cap"]:
                byc = max(snt_salary_prior, snt["new_salary"] // 2)
                out_eff = out_eff - snt_salary_prior + byc
                byc_note = (f"{snt['player']} counts at ${byc:,} outgoing "
                            "under base-year compensation")
        pay_after = s["pay_before"] - s["out_total"] + s["in_total"]
        state_after = _apron_state(pay_after)
        state_before = _apron_state(s["pay_before"])
        room_before = max(0, CAP["cap"] - s["pay_before"])
        allow, rule = _allowed_incoming(
            out_eff, bool(state_after["over_apron1"]), room_before)
        tpe_used = tpe_by_team.get(team, 0)
        if tpe_used:
            allow += tpe_used
            rule += " + TPE"
        aggregates = len(s["out_names"]) > 1 or len(s["in_names"]) > 1
        cash_out = sum(c["amount"] for c in cash_moves if c["from"] == team)
        cash_in = sum(c["amount"] for c in cash_moves if c["to"] == team)
        picks_out = [p for m in moves if m["from"] == team for p in m["picks"]]
        picks_in = [p for m in moves if m["to"] == team for p in m["picks"]]
        hard_caps: list[str] = []
        if aggregates:
            hard_caps.append("second apron")
        if cash_out:
            hard_caps.append("second apron")
        if tpe_used:
            hard_caps.append("second apron")
        if team == snt_receiver:
            hard_caps.append("first apron")
        if state_after["over_apron2"]:
            if len(s["out_names"]) > 1:
                issues.append(f"{team} cannot aggregate outgoing salaries "
                              "above the second apron")
            if len(s["in_names"]) > 1:
                issues.append(f"{team} cannot aggregate incoming salaries "
                              "above the second apron")
            if cash_out:
                issues.append(f"{team} cannot send cash above the second apron")
            if tpe_used:
                issues.append(f"{team} cannot use a traded player exception "
                              "above the second apron")
            if season_start:
                frozen_year = season_start + _STEPIEN_WINDOW
                for p in picks_out:
                    if not p["swap"] and p["round"] == 1 and p["year"] == frozen_year:
                        issues.append(
                            f"{team}'s {frozen_year} first-round pick is "
                            "frozen above the second apron")
        if "second apron" in hard_caps and pay_after > CAP["apron2"]:
            issues.append(
                f"{team} is hard-capped at the second apron by this deal "
                f"(post-trade payroll ${pay_after:,} > ${CAP['apron2']:,})")
        if "first apron" in hard_caps and pay_after > CAP["apron1"]:
            issues.append(
                f"{team} is hard-capped at the first apron by the "
                f"sign-and-trade (post-trade payroll ${pay_after:,} > "
                f"${CAP['apron1']:,})")
        if s["in_total"] > allow:
            issues.append(
                f"{team} takes back too much "
                f"(${s['in_total']:,} vs ${allow:,} allowed under {rule})")
        if season_start:
            for p in picks_out:
                if p["year"] > season_start + _STEPIEN_WINDOW:
                    issues.append(
                        f"{team} cannot trade a {p['year']} pick - more than "
                        "7 drafts out")
        team_rows[team] = {
            "team": team,
            "payroll_before": s["pay_before"],
            "payroll_after": pay_after,
            "outgoing": s["out_total"],
            "outgoing_matching": out_eff,
            "incoming": s["in_total"],
            "players_out": s["out_names"],
            "players_in": s["in_names"],
            "picks_out": picks_out,
            "picks_in": picks_in,
            "cash_out": cash_out, "cash_in": cash_in,
            "tpe_used": tpe_used,
            "allowed_incoming": allow, "match_rule": rule,
            "matching_ok": s["in_total"] <= allow,
            "aggregates": aggregates,
            "hard_cap": "+".join(hard_caps) if hard_caps else "",
            "over_apron1": state_after["over_apron1"],
            "over_apron2": state_after["over_apron2"],
            "room_apron2": state_after["room_apron2"],
            "over_apron1_before": state_before["over_apron1"],
            "over_apron2_before": state_before["over_apron2"],
            **({"byc_note": byc_note} if byc_note else {}),
        }

    if snt:
        if snt["years"] and snt["years"] < 3:
            issues.append("sign-and-trade contracts must run at least "
                          "3 seasons")
        checks.append({"rule": "sign-and-trade", "checked": True,
                       "note": f"{snt['player']} to {snt_receiver or '?'}; "
                               f"{snt_receiver} is hard-capped at the "
                               "first apron"
                               if snt_receiver else
                               f"{snt['player']} is not moving teams"})

    if pick_held is not None and season_start:
        for team in teams:
            owned = set(pick_held.get(team, set()))
            for m in moves:
                for p in m["picks"]:
                    if p["round"] != 1:
                        continue
                    if m["from"] == team and not p["swap"]:
                        owned.discard(p["year"])
                    if m["to"] == team and not p["swap"]:
                        owned.add(p["year"])
            issues.extend(_stepien_issues(team, owned, season_start))
        checks.append({"rule": "Stepien consecutive firsts + 7-year limit",
                       "checked": True,
                       "note": "verified against silver_future_picks"})
    else:
        checks.append({"rule": "Stepien consecutive firsts + 7-year limit",
                       "checked": False,
                       "note": "silver_future_picks not seeded - pick "
                               "ownership not verified"})

    checks.insert(0, {"rule": "salary matching",
                      "checked": True,
                      "note": "; ".join(
                          f"{t} {team_rows[t]['match_rule']}"
                          for t in sorted(team_rows))})
    checks.insert(1, {"rule": "apron aggregation bans",
                      "checked": True,
                      "note": "no aggregation above the second apron; "
                              "aggregation hard-caps at the second apron"})
    checks.append({"rule": "cash in trade",
                   "checked": True,
                   "note": "apron2 ban + second-apron hard-cap trigger "
                           "checked; annual cash limit not tracked"})
    checks.append({"rule": "no-trade clauses, trade kickers, rosters "
                          "minimums, prior TPE inventory",
                   "checked": False, "note": "not modeled"})

    return {"tool": "get_trade_legality", "ok": True,
            "rows": [team_rows[t] for t in sorted(team_rows)],
            "legal": not issues,
            "issues": issues,
            "checks": checks,
            "salary_date": salary_date,
            "meta": {"source": source, "rules": "v2-2023cba-full",
                     "salary_date": salary_date, "season": season,
                     "disclaimer": "Estimate only. Covers matching, apron "
                     "aggregation, hard caps, TPE/cash bans, sign-and-trade "
                     "minimums/BYC, Stepien and frozen-pick rules. Skips "
                     "no-trade clauses, trade kickers, poison-pill and "
                     "minimum-salary exceptions. Confirm with a cap "
                     "specialist."}}
