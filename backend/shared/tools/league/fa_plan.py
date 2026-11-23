from typing import Any

from langchain_core.tools import tool

from ._helpers import _owned_connection, _pkg, _warehouse_tables
from .._core import team_error_message
from ..competitive import _resolve_team_abbr

_FA_COLS = ["PLAYER_NAME", "FA_TYPE", "PRIOR_SALARY", "CAP_HOLD_EST",
            "BREF_SLUG"]
_ROOM_COLS = ["TEAM", "COMMITTED_SALARY", "PENDING_OPTION_SALARY",
              "FA_HOLDS_EST", "INCOMPLETE_ROSTER_CHARGES",
              "PROJECTED_ROOM", "MAX_ROOM", "PROJECTED_CAP",
              "PROJECTED_TAX", "PROJECTED_APRON1", "PROJECTED_APRON2",
              "NTMLE_EST", "BAE_EST", "ROOM_EST",
              "PLAYERS_UNDER_CONTRACT", "PENDING_OPTIONS", "ESTIMATED"]

_EXTENSION_ELIGIBLE = {"ufa", "rfa"}
_BIRD_HOLD_PCT = 1.5


def _rows(con, sql: str, params: list, cols: list[str]) -> list[dict]:
    return [dict(zip(cols, r)) for r in con.execute(sql, params).fetchall()]


def _scenarios(room: dict, fa: list[dict]) -> list[dict]:
    proj = int(room.get("PROJECTED_ROOM") or 0)
    maxr = int(room.get("MAX_ROOM") or 0)
    out = [{"scenario": "keep_all", "player": None,
            "projected_room": proj,
            "path": "under_cap" if proj > 0 else "over_cap"},
           {"scenario": "renounce_all", "player": None,
            "projected_room": maxr,
            "path": "under_cap" if maxr > 0 else "over_cap"}]
    for f in fa:
        hold = int(f.get("CAP_HOLD_EST") or 0)
        name = str(f.get("PLAYER_NAME") or "")
        out.append({"scenario": "renounce", "player": name,
                    "projected_room": proj + hold,
                    "path": "under_cap" if proj + hold > 0 else "over_cap"})
        out.append({"scenario": "keep_only", "player": name,
                    "projected_room": maxr - hold,
                    "path": "under_cap" if maxr - hold > 0 else "over_cap"})
    return out


def _fa_plan_core(con, abbr: str, fa_year: str) -> dict[str, Any] | None:
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
        rows = _rows(con,
                     f"SELECT {', '.join(chr(34) + c + chr(34) for c in pick)}"
                     " FROM silver_cap_room WHERE TEAM = ?"
                     + (" AND CAP_SEASON = ?"
                        if "CAP_SEASON" in have else ""),
                     [abbr] + (["2027-28"]
                               if "CAP_SEASON" in have else []),
                     pick)
        room = rows[0] if rows else None
    if not fa and room is None:
        return None
    cap = int(room.get("PROJECTED_CAP") or 0) if room else 0
    fa_rows = []
    for f in fa:
        hold = int(f.get("CAP_HOLD_EST") or 0)
        fa_rows.append({
            "player": f.get("PLAYER_NAME"),
            "fa_type": f.get("FA_TYPE"),
            "prior_salary": f.get("PRIOR_SALARY"),
            "cap_hold_est": hold,
            "hold_share": round(hold / cap, 4) if cap else None,
            "extension_eligible": str(f.get("FA_TYPE") or "")
            in _EXTENSION_ELIGIBLE})
    scenarios = _scenarios(room, fa) if room else []
    if not room:
        checks.append({"rule": "cap room", "checked": False,
                       "note": "silver_cap_room row absent for team - "
                               "scenarios omitted"})
    checks += [
        {"rule": "cap holds", "checked": True,
         "note": f"holds are flat {int(_BIRD_HOLD_PCT * 100)}% of prior "
                 "salary - real Bird/early-Bird/non-Bird and rookie-scale "
                 "hold rules not modeled"},
        {"rule": "pending options", "checked": True,
         "note": "option-year salary counts as committed in keep_all and "
                 "is shed in renounce_all per seed arithmetic; per-option "
                 "outcomes not modeled"},
        {"rule": "roster charges", "checked": True,
         "note": "per-player scenarios reuse stored roster-charge totals; "
                 "incomplete-roster charge recomputation approximated"},
        {"rule": "rights not modeled", "checked": True,
         "note": "RFA offer-sheet matching, extension deadlines, BYC and "
                 "sign-and-trade mechanics out of scope; "
                 "extension_eligible flags ufa/rfa only"},
    ]
    return {"team": abbr, "fa_year": str(fa_year), "rows": fa_rows,
            "scenarios": scenarios, "checks": checks,
            "exceptions": {
                "ntmle": room.get("NTMLE_EST") if room else None,
                "bae": room.get("BAE_EST") if room else None,
                "room": room.get("ROOM_EST") if room else None,
                "note": "under_cap path uses room exception; "
                        "over_cap path uses ntmle+bae"},
            "context": {
                "committed_salary": room.get("COMMITTED_SALARY")
                if room else None,
                "pending_option_salary":
                    room.get("PENDING_OPTION_SALARY") if room else None,
                "fa_holds_est": room.get("FA_HOLDS_EST") if room else None,
                "roster_charges":
                    room.get("INCOMPLETE_ROSTER_CHARGES")
                    if room else None,
                "players_under_contract":
                    room.get("PLAYERS_UNDER_CONTRACT") if room else None,
                "pending_options": room.get("PENDING_OPTIONS")
                if room else None,
                "projected_cap": cap or None,
                "projected_tax": room.get("PROJECTED_TAX") if room else None,
                "projected_apron1": room.get("PROJECTED_APRON1")
                if room else None,
                "projected_apron2": room.get("PROJECTED_APRON2")
                if room else None}}


@tool(description=(
    "Free-agent / extension planning for one team's upcoming FA class: "
    "per-FA rows (type, prior salary, estimated cap hold, extension "
    "eligibility) plus a deterministic scenario table - keep all holds vs "
    "renounce all vs per-player renounce/keep-only - against the team's "
    "projected cap room and exceptions. Holds are CBA-formula estimates "
    "(150% of prior salary), marked ESTIMATED. Warehouse only; refresh "
    "with seed_free_agents.py. "
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
    try:
        with _owned_connection(None, read_only=True) as con:
            core = _fa_plan_core(con, abbr, fa_year)
    except FileNotFoundError:
        return {"tool": "get_fa_plan", "ok": False,
                "error": "warehouse absent; run seed_free_agents.py first."}
    if core is None:
        return {"tool": "get_fa_plan", "ok": False,
                "error": "no free-agent data; run seed_free_agents.py"}
    out = {"tool": "get_fa_plan", "ok": True, **core,
           "meta": {"source": "warehouse", "estimated": True,
                    "tables": {"free_agents": "silver_free_agents",
                               "cap_room": "silver_cap_room"},
                    "formula": "renounce X: projected_room + cap_hold(X); "
                               "keep_only X: max_room - cap_hold(X); "
                               "hold = 150% x prior salary",
                    "disclaimer": "Planning-grade estimates - hold, room "
                    "and exception figures are CBA-formula estimates, not "
                    "official numbers."}}
    return out
