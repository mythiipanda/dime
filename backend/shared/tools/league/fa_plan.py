from typing import Any

from langchain_core.tools import tool

from ._helpers import (_cap_season_for_fa_year, _owned_connection, _pkg,
                       _warehouse_tables, declare_money)
from .cap_hold_derivation import CAP_HOLD_CONTRACT, derive_cap_holds, hold_amount
from .._core import team_error_message
from ..competitive import _resolve_team_abbr

_FA_COLS = ["PLAYER_NAME", "FA_TYPE", "PRIOR_SALARY", "CAP_HOLD_EST",
            "BREF_SLUG"]
_ROOM_COLS = ["TEAM", "COMMITTED_SALARY", "PENDING_OPTION_SALARY",
              "FA_HOLDS_EST", "INCOMPLETE_ROSTER_CHARGES",
              "ROSTER_CHARGE_MINIMUM", "PROJECTED_ROOM", "MAX_ROOM",
              "PROJECTED_CAP",
              "PROJECTED_TAX", "PROJECTED_APRON1", "PROJECTED_APRON2",
              "NTMLE_EST", "BAE_EST", "ROOM_EST", "TMLE_EST",
              "PLAYERS_UNDER_CONTRACT", "PENDING_OPTIONS", "ESTIMATED"]

_EXTENSION_ELIGIBLE = {"ufa", "rfa"}
_ROSTER_SPOTS = 12
_FALLBACK_ROSTER_CHARGE_MINIMUM = 1_493_539


def _rows(con, sql: str, params: list, cols: list[str]) -> list[dict]:
    return [dict(zip(cols, r)) for r in con.execute(sql, params).fetchall()]


def _roster_charge_minimum(room: dict) -> int:
    value = room.get("ROSTER_CHARGE_MINIMUM")
    if value is None:
        return _FALLBACK_ROSTER_CHARGE_MINIMUM
    return int(value)


def _scenario_roster_charge(room: dict, retained_hold_count: int) -> int:
    players = int(room.get("PLAYERS_UNDER_CONTRACT") or 0)
    open_spots = max(0, _ROSTER_SPOTS - players - retained_hold_count)
    return open_spots * _roster_charge_minimum(room)


def _scenario_values(room: dict, retained_holds: int,
                     retained_hold_count: int) -> tuple[int, int]:
    projected = int(room.get("PROJECTED_ROOM") or 0)
    base_charge = int(room.get("INCOMPLETE_ROSTER_CHARGES") or 0)
    charge = _scenario_roster_charge(room, retained_hold_count)
    return projected - retained_holds + base_charge - charge, charge


def _sum_semantics(unknown_count: int) -> str:
    return "known_amounts_partial_sum" if unknown_count else "exact"


def _scenario_warning(retained_unknown: int,
                      renounced_unknown: int) -> str | None:
    parts = []
    if retained_unknown:
        parts.append(
            f"projected_room is null because {retained_unknown} retained "
            "cap-hold amount(s) are unknown; projected_room_upper_bound "
            "excludes those amounts")
    if renounced_unknown:
        parts.append(
            f"cap_holds_renounced is a known-dollar partial sum because "
            f"{renounced_unknown} renounced cap-hold amount(s) are unknown")
    return " ".join(parts) if parts else None


def _scenario_row(room: dict, scenario: str, player: str | None,
                  retained_holds: int, retained_hold_count: int,
                  total_holds: int, retained_unknown: int,
                  renounced_unknown: int,
                  player_unknown: bool | None) -> dict:
    bound, charge = _scenario_values(room, retained_holds,
                                     retained_hold_count)
    exact = retained_unknown == 0
    if exact:
        path = "under_cap" if bound > 0 else "over_cap"
    else:
        path = "unknown" if bound > 0 else "over_cap"
    return {"scenario": scenario, "player": player,
            "projected_room": bound if exact else None,
            "projected_room_upper_bound": bound,
            "arithmetic_status": "exact" if exact else "partial_unknown_holds",
            "cap_holds_retained": retained_holds,
            "cap_holds_retained_semantics": _sum_semantics(retained_unknown),
            "cap_holds_renounced": total_holds - retained_holds,
            "cap_holds_renounced_semantics": _sum_semantics(renounced_unknown),
            "unknown_holds_retained_count": retained_unknown,
            "unknown_holds_renounced_count": renounced_unknown,
            "hold_unknown": player_unknown,
            "warning": _scenario_warning(retained_unknown, renounced_unknown),
            "roster_charges": charge,
            "path": path}


def _scenario_hold_amount(row: dict) -> int | None:
    value = row.get("cap_hold")
    if value is None and "cap_hold" not in row:
        value = row.get("CAP_HOLD_EST")
    return int(value) if value is not None else None


def _hold_slot(amount: int | None) -> int:
    return 1 if amount is None or amount > 0 else 0


def _scenarios(room: dict, fa: list[dict]) -> list[dict]:
    holds = [{"name": str(f.get("PLAYER_NAME") or ""),
              "amount": _scenario_hold_amount(f)}
             for f in fa if f.get("active_in_baseline", True)]
    total_holds = sum(hold["amount"] or 0 for hold in holds)
    total_count = sum(_hold_slot(hold["amount"]) for hold in holds)
    total_unknown = sum(1 for hold in holds if hold["amount"] is None)
    out = [_scenario_row(room, "keep_all", None, total_holds, total_count,
                         total_holds, total_unknown, 0, None),
           _scenario_row(room, "renounce_all", None, 0, 0, total_holds,
                         0, total_unknown, None)]
    for hold in holds:
        name = hold["name"]
        amount = hold["amount"]
        unknown = amount is None
        slot = _hold_slot(amount)
        out.append(_scenario_row(
            room, "renounce", name, total_holds - (amount or 0),
            total_count - slot, total_holds,
            total_unknown - (1 if unknown else 0), 1 if unknown else 0,
            unknown))
        out.append(_scenario_row(
            room, "keep_only", name, amount or 0, slot, total_holds,
            1 if unknown else 0, total_unknown - (1 if unknown else 0),
            unknown))
    return out


def _active_unknown_hold_count(fa: list[dict]) -> int:
    active = [f for f in fa if f.get("active_in_baseline", True)]
    return sum(1 for f in active if _scenario_hold_amount(f) is None)


def _fa_plan_row(f: dict[str, Any], cap: int) -> dict[str, Any]:
    computed = f.get("cap_hold")
    if computed is None and "cap_hold" not in f:
        computed = f.get("CAP_HOLD_EST")
    hold = int(computed) if computed is not None else None
    return {
        "player": f.get("PLAYER_NAME"),
        "fa_type": f.get("FA_TYPE"),
        "prior_salary": f.get("PRIOR_SALARY"),
        "cap_hold_est": hold,
        "cap_hold": computed,
        "legacy_cap_hold_est": f.get("legacy_cap_hold_est",
                                     f.get("CAP_HOLD_EST")),
        "money_unit": f.get("money_unit", "usd_dollars"),
        "scenario_dependency": f.get("scenario_dependency",
                                     "active_expired_contract"),
        "active_in_baseline": f.get("active_in_baseline", True),
        "rights_classification": f.get("rights_classification"),
        "rookie_scale_status": f.get("rookie_scale_status"),
        "hold_rule": f.get("hold_rule"),
        "hold_exactness": f.get("hold_exactness"),
        "provenance_class": f.get("provenance_class"),
        "input_exactness": f.get("input_exactness") or {},
        "input_provenance": f.get("input_provenance") or {},
        "uncertainty": f.get("uncertainty") or [],
        "hold_share": round(hold / cap, 4) if hold is not None and cap else None,
        "extension_eligible": str(f.get("FA_TYPE") or "")
        in _EXTENSION_ELIGIBLE}


@tool(description=(
    "Free-agent / extension planning for one team's upcoming FA class: "
    "per-FA rows (type, prior salary, estimated cap hold, extension "
    "eligibility) plus a deterministic scenario table - keep all holds vs "
    "renounce all vs per-player renounce/keep-only - against the team's "
    "projected cap room and exceptions. Holds are CBA-formula estimates "
    "with per-input exactness/provenance and disclosed inference. Scenario "
    "rows expose retained/renounced unknown-hold counts, label known-dollar "
    "partial sums, and null exact projected room while unknown-amount "
    "holds remain retained. Warehouse only; refresh with seed_free_agents.py. "
    "REACH FOR THIS for any forward-looking free-agency or cap-space "
    "decision ask: 'can the Lakers keep Reaves and still sign a wing?', "
    "'what is Boston's cap room if they renounce X?', 'walk me the Knicks' "
    "2027 offseason.' It returns the answer-shaped scenario table directly, "
    "so do not rebuild hold/room arithmetic from get_cap_ledger or "
    "get_cap_table - those show current committed salary only and cannot "
    "answer keep-vs-renounce questions. Pair with get_free_agents for the "
    "league-wide class and get_cap_scenario for explicit hypothetical "
    "signing amounts."))
def get_fa_plan(team: str = "", fa_year: str = "2027") -> dict[str, Any]:
    _pkg()
    raw_team = str(team or "").strip()
    abbr = _resolve_team_abbr(raw_team.upper())
    if not abbr:
        return {"tool": "get_fa_plan", "ok": False,
                "error": "team needed" if not raw_team
                         else team_error_message(raw_team)}
    cap_season = _cap_season_for_fa_year(fa_year)
    if cap_season is None:
        return {"tool": "get_fa_plan", "ok": False,
                "error": "fa_year must be a four-digit calendar year "
                         f"such as 2027; received {fa_year!r}"}
    try:
        with _owned_connection(None, read_only=True) as con:
            tables = _warehouse_tables(con)
            checks = []
            fa = []
            if "silver_free_agents" in tables:
                fa = _rows(con,
                           'SELECT "PLAYER_NAME", "FA_TYPE", "PRIOR_SALARY",'
                           ' "CAP_HOLD_EST", "BREF_SLUG"'
                           " FROM silver_free_agents"
                           " WHERE FA_YEAR = ? AND TEAM = ?"
                           " ORDER BY CAP_HOLD_EST DESC",
                           [fa_year, abbr], _FA_COLS)
            room = None
            if "silver_cap_room" in tables:
                have = {r[1] for r in con.execute(
                    "PRAGMA table_info(silver_cap_room)").fetchall()}
                pick = [c for c in _ROOM_COLS if c in have]
                rows = []
                if "CAP_SEASON" in have:
                    rows = _rows(
                        con,
                        f"SELECT {', '.join(chr(34) + c + chr(34) for c in pick)}"
                        " FROM silver_cap_room"
                        " WHERE TEAM = ? AND CAP_SEASON = ?",
                        [abbr, cap_season], pick)
                room = rows[0] if rows else None
            if not fa and room is None:
                return {"tool": "get_fa_plan", "ok": False,
                        "error": f"no free-agent data for FA year {fa_year} "
                                 f"or cap season {cap_season}; "
                                 "run seed_free_agents.py"}
            hold_payload = derive_cap_holds(con, fa_year, abbr)
            if hold_payload.get("rows"):
                fa = list(hold_payload["rows"])
    except FileNotFoundError:
        return {"tool": "get_fa_plan", "ok": False,
                "error": "warehouse absent; run seed_free_agents.py first."}
    cap = int(room.get("PROJECTED_CAP") or 0) if room else 0
    fa_rows = [_fa_plan_row(f, cap) for f in fa]
    scenarios = _scenarios(room, fa) if room else []
    active_holds = sum(hold_amount(f) for f in fa if f.get("active_in_baseline", True))
    potential_holds = sum(hold_amount(f) for f in fa)
    unknown_holds = sum(1 for f in fa if _scenario_hold_amount(f) is None)
    active_unknown_holds = _active_unknown_hold_count(fa)
    if not room:
        checks.append({"rule": "cap room", "checked": False,
                       "note": "silver_cap_room row absent for team - "
                               "scenarios omitted"})
    checks += [
        {"rule": "cap holds", "checked": True,
         "note": "holds use the CBA calculator when supporting warehouse inputs "
                 "are present; rights, rookie-scale status and service time are "
                 "disclosed inferences rather than facts, unknown amounts stay "
                 "null and are excluded from known-dollar totals, scenario rows "
                 "disclose retained/renounced unknown counts, and legacy "
                 "fallback rows are labeled"},
        {"rule": "pending options", "checked": True,
         "note": "option-year salary stays exercised in these scenarios; "
                 "player/team-option rows are shown as option-dependent "
                 "potential holds but are not active baseline holds and are "
                 "not renounce scenarios until an option decline is modeled"},
        {"rule": "roster charges", "checked": True,
         "note": "scenario charges fill offseason rosters to 12 at the "
                 "target-season rookie minimum salary used for "
                 "incomplete-roster charges stored in silver_cap_room "
                 "and count each retained active cap hold, including an "
                 "unknown-amount hold, as one occupied roster spot; legacy "
                 "rows without that column use the 1,493,539 projection "
                 "as an approximation"},
        {"rule": "rights not modeled", "checked": True,
         "note": "RFA offer-sheet matching, extension deadlines, BYC and "
                 "sign-and-trade mechanics out of scope; "
                 "extension_eligible flags ufa/rfa only"},
    ]
    out = {"tool": "get_fa_plan", "ok": True, "team": abbr,
           "fa_year": str(fa_year), "cap_season": cap_season,
           "rows": fa_rows,
           "scenarios": scenarios, "checks": checks,
           "exceptions": {
               "ntmle": room.get("NTMLE_EST") if room else None,
               "tmle": room.get("TMLE_EST") if room else None,
               "bae": room.get("BAE_EST") if room else None,
               "room": room.get("ROOM_EST") if room else None,
               "note": "under_cap path uses room exception; over_cap "
                       "exception depends on tax/apron position"},
           "context": {
               "committed_salary": room.get("COMMITTED_SALARY")
               if room else None,
               "pending_option_salary":
                   room.get("PENDING_OPTION_SALARY") if room else None,
               "fa_holds_est": room.get("FA_HOLDS_EST") if room else None,
               "fa_holds_derived": potential_holds,
               "fa_holds_derived_semantics": _sum_semantics(unknown_holds),
               "fa_holds_active_derived": active_holds,
               "fa_holds_active_derived_semantics":
                   _sum_semantics(active_unknown_holds),
               "fa_holds_unknown_count": unknown_holds,
               "fa_holds_active_unknown_count": active_unknown_holds,
               "fa_holds_unit": "usd_dollars",
               "roster_charges":
                   room.get("INCOMPLETE_ROSTER_CHARGES")
               if room else None,
               "roster_charge_minimum": _roster_charge_minimum(room)
               if room else None,
               "roster_charge_minimum_source": (
                   "warehouse"
                   if room and room.get("ROSTER_CHARGE_MINIMUM") is not None
                   else "legacy_approximation" if room else None),
               "max_room": room.get("MAX_ROOM") if room else None,
               "players_under_contract":
                   room.get("PLAYERS_UNDER_CONTRACT") if room else None,
               "pending_options": room.get("PENDING_OPTIONS")
               if room else None,
               "projected_cap": cap or None,
               "projected_tax": room.get("PROJECTED_TAX") if room else None,
               "projected_apron1": room.get("PROJECTED_APRON1")
               if room else None,
               "projected_apron2": room.get("PROJECTED_APRON2")
               if room else None},
           "meta": {"source": "warehouse", "estimated": True,
                    "cap_hold_contract": CAP_HOLD_CONTRACT,
                    "tables": {"free_agents": "silver_free_agents",
                               "cap_room": "silver_cap_room"},
                    "formula": "scenario room = PROJECTED_ROOM - retained "
                               "known active cap holds + stored base roster "
                               "charges - scenario roster charges; "
                               "PROJECTED_ROOM already excludes free-agent "
                               "holds; pending options stay exercised; "
                               "option-dependent potential holds are excluded "
                               "from active scenarios until a decline is "
                               "explicit; retained active holds, including "
                               "unknown-amount holds, count as occupied "
                               "roster spots; projected_room is null when "
                               "unknown-amount holds remain retained and "
                               "projected_room_upper_bound is the labeled "
                               "ceiling excluding those unknown amounts",
                    "cap_hold_derivation": hold_payload.get("meta") or {},
                    "disclaimer": "Planning-grade estimates - hold, room "
                    "and exception figures are CBA-formula estimates, not "
                    "official numbers."}}
    return declare_money(out, ["amount", "salary", "ntmle", "tmle", "bae", "room", "committed_salary", "pending_option_salary", "fa_holds_est", "roster_charges", "roster_charge_minimum", "max_room", "projected_cap", "projected_tax", "projected_apron1", "projected_apron2", "cap_room"])
