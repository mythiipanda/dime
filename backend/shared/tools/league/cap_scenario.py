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
    _salary_date,
)
from .._core import coerce_team_id
from .trade_value import _trade_guard_vintage_error, _trade_unknown_message

_AMOUNT_RE = _re.compile(r"^\$?([\d,]+(?:\.\d+)?)\s*([mMkK])?$")
_SPLIT_RE = _re.compile(r"(?<!\d),(?!\d)|(?<=\d),(?=\s*\D)")

_FROZEN_PICK_OFFSET = 7


def _parse_amount(text: str) -> int | None:
    m = _AMOUNT_RE.fullmatch(str(text).strip())
    if not m:
        return None
    value = float(m.group(1).replace(",", ""))
    suffix = (m.group(2) or "").lower()
    if suffix == "m":
        value *= 1_000_000
    elif suffix == "k":
        value *= 1_000
    return int(round(value))


def _parse_signings(text: str) -> tuple[list[tuple[str, int]], list[str]]:
    signings: list[tuple[str, int]] = []
    bad: list[str] = []
    for i, item in enumerate(
            [x.strip() for x in _SPLIT_RE.split(str(text or "")) if x.strip()], 1):
        name, amount_text = (item.split("=", 1) + [""])[:2] if "=" in item else ("", item)
        amount = _parse_amount(amount_text)
        if amount is None:
            bad.append(item)
        else:
            signings.append((str(name).strip()
                             or f"${amount / 1_000_000:g}M signing", amount))
    return signings, bad


def _frozen_pick_year(season: str) -> int | None:
    m = _re.match(r"(\d{4})", str(season or ""))
    return int(m.group(1)) + _FROZEN_PICK_OFFSET + 1 if m else None


def _scenario_restrictions(state: dict[str, Any], season: str) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    if state["over_apron2"]:
        out.append({"threshold": "second apron", "status": "active",
                    "rule": "trade take-back limited to 100% of outgoing salary"})
        out.append({"threshold": "second apron", "status": "active",
                    "rule": "cannot aggregate player salaries in a trade"})
        out.append({"threshold": "second apron", "status": "active",
                    "rule": "cannot send cash in a trade"})
        out.append({"threshold": "second apron", "status": "active",
                    "rule": "cannot use a traded player exception"})
        out.append({"threshold": "second apron", "status": "active",
                    "rule": "no mid-level or bi-annual exception; veteran minimums only"})
        out.append({"threshold": "second apron", "status": "active",
                    "rule": "cannot sign a player waived during the season whose "
                            "pre-waiver salary exceeded the non-taxpayer mid-level"})
        pick = _frozen_pick_year(season)
        if pick:
            out.append({"threshold": "second apron", "status": "active",
                        "rule": f"{pick} first-round pick is frozen and cannot be traded"})
    elif state["over_apron1"]:
        out.append({"threshold": "first apron", "status": "active",
                    "rule": "trade take-back limited to 100% of outgoing salary"})
        out.append({"threshold": "first apron", "status": "active",
                    "rule": "cannot sign a player waived during the season whose "
                            "pre-waiver salary exceeded the non-taxpayer mid-level"})
    if state["over_tax"]:
        out.append({"threshold": "tax", "status": "active",
                    "rule": "luxury tax payer; taxpayer mid-level only "
                            "(no non-taxpayer MLE, no bi-annual)"})
    if not state["over_apron2"]:
        out.append({"threshold": "second apron", "status": "trigger",
                    "rule": "aggregating salaries, sending cash, or using a "
                            "sign-and-trade generated exception in a deal "
                            "hard-caps the team at the second apron"})
    if not state["over_apron1"]:
        out.append({"threshold": "first apron", "status": "trigger",
                    "rule": "acquiring a sign-and-traded player or using the "
                            "non-taxpayer mid-level or bi-annual exception "
                            "hard-caps the team at the first apron"})
    if state["cap_room"] > 0:
        out.append({"threshold": "cap", "status": "active",
                    "rule": "operating with cap room; exceptions unavailable "
                            "until room is used"})
    return out


def _roster_issues(roster_after: int) -> list[str]:
    if roster_after > 15:
        return [f"roster would be {roster_after} players - must trim to 15"]
    if roster_after < 14:
        return [f"roster would be {roster_after} players - must be at 14 "
                "within two weeks"]
    return []


@tool(description='Cap-scenario arithmetic for one team. "signings" takes '
    'comma-separated amounts or name=amount pairs like "Player=12M, 3000000". '
    '"in_players" adds real contracts by name (league-wide lookup), '
    '"out_players" removes roster salaries. Returns the arithmetic trace, '
    'post-move payroll vs cap/tax/first/second apron, the 2023 CBA '
    'restrictions that trigger, and the matching verdict when a trade '
    'portion is present.')
def get_cap_scenario(team: str = "", signings: str = "",
                     in_players: str = "", out_players: str = "",
                     season: str | None = None) -> dict[str, Any]:
    team = str(team or "").strip()
    if not team:
        return {"tool": "get_cap_scenario", "ok": False, "error": "team needed"}
    if not (signings or in_players or out_players):
        return {"tool": "get_cap_scenario", "ok": False,
                "error": "no moves given - pass signings, in_players or out_players"}
    from nba_api.stats.static import teams as _teams
    try:
        team_id = coerce_team_id(team)
        team = next(
            item["abbreviation"] for item in _teams.get_teams()
            if item["id"] == team_id)
    except (ValueError, StopIteration):
        return {"tool": "get_cap_scenario", "ok": False,
                "error": f"unknown team: {team}"}
    season = str(season or "").strip()
    sign_rows, bad_signings = _parse_signings(signings)
    if bad_signings:
        return {"tool": "get_cap_scenario", "ok": False,
                "error": "unparseable signing amounts: "
                         + "; ".join(bad_signings)
                         + " (use amounts like 12000000, 12M or $12M)"}
    with _owned_connection(None, read_only=True) as con:
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
        if season:
            guard_error = _trade_guard_vintage_error(con, season)
            if guard_error:
                return {"tool": "get_cap_scenario", "ok": False,
                        "error": guard_error}
        try:
            pay_before, roster = _payroll(team, con, season)
        except SalaryColumnError as exc:
            return {"tool": "get_cap_scenario", "ok": False,
                    "reason": exc.reason, "error": str(exc)}
        out_total, out_names, out_unknown = _match_trade_players(
            team, out_players, con, season)
        in_names: list[str] = []
        in_unknown: list[str] = []
        in_total = 0
        in_sides: list[dict[str, Any]] = []
        for raw in [x.strip() for x in str(in_players or "").split(",") if x.strip()]:
            hit = _locate_player_team(raw, con, season)
            if hit is None:
                in_unknown.append(raw)
                continue
            cname, cteam, csal = hit
            if str(cteam).upper() == team.upper():
                in_unknown.append(f"{cname} is already on {team.upper()}")
                continue
            in_names.append(cname)
            in_total += int(csal or 0)
            in_sides.append({"player": cname, "from": cteam, "salary": csal})
        if out_unknown or in_unknown:
            return {"tool": "get_cap_scenario", "ok": False,
                    "error": _trade_unknown_message(
                        team, out_unknown, team, in_unknown, con)}
        salary_date = _salary_date(con)
        source = _payroll_source(con)
    state_before = _apron_state(pay_before)
    room_before = max(0, CAP["cap"] - pay_before)
    pay = pay_before
    rows = [{"step": 0, "kind": "payroll",
             "detail": f"{team.upper()} committed payroll", "delta": 0,
             "payroll": pay_before}]
    step = 1
    for name in out_names:
        row = next((p for p in roster if p["player"] == name), None)
        amount = int((row or {}).get("salary") or 0)
        pay -= amount
        rows.append({"step": step, "kind": "trade_out",
                     "detail": f"out {name}", "delta": -amount,
                     "payroll": pay})
        step += 1
    for name, amount in sign_rows:
        pay += amount
        rows.append({"step": step, "kind": "signing",
                     "detail": f"sign {name}", "delta": amount,
                     "payroll": pay})
        step += 1
    for side in in_sides:
        pay += int(side["salary"] or 0)
        rows.append({"step": step, "kind": "trade_in",
                     "detail": f"in {side['player']} (from {side['from']})",
                     "delta": int(side["salary"] or 0), "payroll": pay})
        step += 1
    pay_after = pay
    state_after = _apron_state(pay_after)
    issues: list[str] = []
    matching: dict[str, Any] | None = None
    if out_names and in_names:
        aggregates = len(out_names) > 1 or len(in_names) > 1
        if state_before["over_apron2"] and aggregates:
            issues.append("cannot aggregate salaries above the second apron")
            matching = {"incoming": in_total, "outgoing": out_total,
                        "legal": False, "match_rule": "no aggregation (above the second apron)",
                        "allowed_incoming": 0}
        else:
            allow, rule = _allowed_incoming(
                out_total, bool(state_before["over_apron1"]), room_before)
            matching = {"incoming": in_total, "outgoing": out_total,
                        "allowed_incoming": allow, "match_rule": rule,
                        "legal": in_total <= allow}
            if not matching["legal"]:
                issues.append(
                    f"{team.upper()} takes back too much "
                    f"(${in_total:,} vs {allow:,} allowed under {rule})")
        if aggregates and pay_after > CAP["apron2"]:
            issues.append("aggregation would hard-cap the team at the second apron")
    roster_before = len(roster)
    roster_after = roster_before - len(out_names) + len(in_names) + len(sign_rows)
    issues.extend(_roster_issues(roster_after))
    rows.append({"step": step, "kind": "post_move",
                 "detail": "post-move payroll", "delta": 0,
                 "payroll": pay_after})
    res = {
        "tool": "get_cap_scenario", "ok": True,
        "rows": rows,
        "summary": {
            "team": team.upper(), "season": season,
            "payroll_before": pay_before, "payroll_after": pay_after,
            "delta": pay_after - pay_before,
            "cap_room": CAP["cap"] - pay_after,
            "tax_room": CAP["tax"] - pay_after,
            "room_apron1": state_after["room_apron1"],
            "room_apron2": state_after["room_apron2"],
            "over_tax": state_after["over_tax"],
            "over_apron1": state_after["over_apron1"],
            "over_apron2": state_after["over_apron2"],
            "roster_before": roster_before, "roster_after": roster_after,
        },
        "restrictions": _scenario_restrictions({**state_after, "cap_room": CAP["cap"] - pay_after}, season),
        "issues": issues,
        "meta": {"source": source, "rules": "v2-2023cba",
                 "salary_date": salary_date, "season": season,
                 "roster_note": "player counts come from the salary sheet and "
                                "may include dead money; confirm against the "
                                "roster table",
                 **{k: v for k, v in CAP.items()}},
    }
    if matching is not None:
        res["matching"] = matching
    return res
