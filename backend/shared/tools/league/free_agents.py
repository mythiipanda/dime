from typing import Any

from langchain_core.tools import tool

from ._helpers import (_cap_season_for_fa_year, _owned_connection, _pkg,
                       _warehouse_tables, declare_money)
from .cap_hold_derivation import CAP_HOLD_CONTRACT, derive_cap_holds, hold_amount
from .._core import team_error_message
from ..competitive import _resolve_team_abbr

_FA_COLS = ["PLAYER_NAME", "TEAM", "FA_TYPE", "PRIOR_SALARY",
            "CAP_HOLD_EST", "BREF_SLUG", "_fetched_at"]
_ROOM_COLS = ["TEAM", "CAP_SEASON", "COMMITTED_SALARY",
              "PENDING_OPTION_SALARY", "FA_HOLDS_EST",
              "INCOMPLETE_ROSTER_CHARGES", "ROSTER_CHARGE_MINIMUM",
              "PROJECTED_ROOM", "MAX_ROOM",
              "PROJECTED_CAP", "PROJECTED_TAX", "PROJECTED_APRON1",
              "PROJECTED_APRON2", "NTMLE_EST", "BAE_EST", "ROOM_EST",
              "TMLE_EST", "PLAYERS_UNDER_CONTRACT", "PENDING_OPTIONS",
              "ESTIMATED"]


def _rows(con, sql: str, params: list, cols: list[str]) -> list[dict]:
    return [dict(zip(cols, r)) for r in con.execute(sql, params).fetchall()]


def _cap_room_rows(con, abbr: str, cap_season: str) -> list[dict]:
    have = {r[1] for r in con.execute(
        "PRAGMA table_info(silver_cap_room)").fetchall()}
    pick = [c for c in _ROOM_COLS if c in have]
    if not pick or "CAP_SEASON" not in have:
        return []
    cols = ", ".join(chr(34) + c + chr(34) for c in pick)
    where = ["CAP_SEASON = ?"]
    params = [cap_season]
    if abbr:
        where.append("TEAM = ?")
        params.append(abbr)
    sql = (f"SELECT {cols} FROM silver_cap_room WHERE "
           + " AND ".join(where))
    if not abbr and "PROJECTED_ROOM" in have:
        sql += " ORDER BY PROJECTED_ROOM DESC"
    return _rows(con, sql, params, pick)


def _normalize_hold_rows(rows: list[dict]) -> None:
    for row in rows:
        if "cap_hold" in row:
            row["cap_hold_est"] = row.get("cap_hold")
            continue
        seed = row.get("CAP_HOLD_EST")
        row["cap_hold"] = seed
        row["cap_hold_est"] = seed
        row["legacy_cap_hold_est"] = seed
        row["provenance_class"] = "legacy_seed_estimate"
        row["money_unit"] = "usd_dollars"


def _enrich_cap_room(cap_room: list[dict], hold_rows: list[dict]) -> None:
    grouped: dict[str, list[dict]] = {}
    for row in hold_rows:
        grouped.setdefault(str(row.get("TEAM") or "").upper(), []).append(row)
    for row in cap_room:
        team_rows = grouped.get(str(row.get("TEAM") or "").upper(), [])
        row["fa_holds_derived"] = sum(hold_amount(item) for item in team_rows)
        row["fa_holds_active_derived"] = sum(
            hold_amount(item) for item in team_rows if item.get("active_in_baseline"))
        row["fa_holds_unit"] = "usd_dollars"
        row["cap_hold_provenance_classes"] = sorted(
            {str(item.get("provenance_class") or "") for item in team_rows
             if item.get("provenance_class")})


@tool(description=(
    "Free agency and cap planning: the upcoming free agent class by team "
    "or league-wide (UFA, player/team options, two-way), estimated cap "
    "holds, and each team's projected cap room and exceptions for the "
    "next cap season. Warehouse only; refresh with seed_free_agents.py. "
    "Hold and cap figures are CBA-formula estimates, marked ESTIMATED. "
    "REACH FOR THIS for any 'who is a free agent' or 'who has cap space' "
    "ask: 'top 2027 free agents', 'which teams can offer a max slot?', "
    "'who are the Nets' free agents?' It returns the FA list plus each "
    "team's projected room/tax/apron lines in one call - do not assemble "
    "this from get_cap_ledger, which only shows one team's current "
    "committed salary. For one team's keep-vs-renounce decision tree use "
    "get_fa_plan; for hypothetical signing amounts use get_cap_scenario."))
def get_free_agents(team: str = "", fa_year: str = "2027") -> dict[str, Any]:
    _pkg()
    raw_team = str(team or "").strip()
    abbr = _resolve_team_abbr(raw_team.upper()) if raw_team else ""
    if raw_team and not abbr:
        return {"tool": "get_free_agents", "ok": False,
                "error": team_error_message(raw_team)}
    cap_season = _cap_season_for_fa_year(fa_year)
    if cap_season is None:
        return {"tool": "get_free_agents", "ok": False,
                "error": "fa_year must be a four-digit calendar year "
                         f"such as 2027; received {fa_year!r}"}
    try:
        with _owned_connection(None, read_only=True) as con:
            tables = _warehouse_tables(con)
            fa = []
            if "silver_free_agents" in tables:
                if abbr:
                    fa = _rows(con,
                               'SELECT "PLAYER_NAME", "TEAM", "FA_TYPE",'
                               ' "PRIOR_SALARY", "CAP_HOLD_EST", "BREF_SLUG",'
                               ' "_fetched_at" FROM silver_free_agents'
                               " WHERE FA_YEAR = ? AND TEAM = ?"
                               " ORDER BY PRIOR_SALARY DESC",
                               [fa_year, abbr], _FA_COLS)
                else:
                    fa = _rows(con,
                               'SELECT "PLAYER_NAME", "TEAM", "FA_TYPE",'
                               ' "PRIOR_SALARY", "CAP_HOLD_EST", "BREF_SLUG",'
                               ' "_fetched_at" FROM silver_free_agents'
                               " WHERE FA_YEAR = ?"
                               " ORDER BY TEAM, PRIOR_SALARY DESC",
                               [fa_year], _FA_COLS)
            cap_room = []
            if "silver_cap_room" in tables:
                cap_room = _cap_room_rows(con, abbr, cap_season)
            if not fa and not cap_room:
                return {"tool": "get_free_agents", "ok": False,
                        "error": f"no free-agent data for FA year {fa_year} "
                                 f"or cap season {cap_season}; "
                                 "run seed_free_agents.py"}
            hold_payload = derive_cap_holds(con, fa_year, abbr)
            if hold_payload.get("rows"):
                fa = list(hold_payload["rows"])
                _enrich_cap_room(cap_room, fa)
    except FileNotFoundError:
        return {"tool": "get_free_agents", "ok": False,
                "error": "warehouse absent; run seed_free_agents.py first."}
    _normalize_hold_rows(fa)
    return declare_money({
        "tool": "get_free_agents",
        "ok": True,
        "team": abbr or "league",
        "fa_year": fa_year,
        "cap_season": cap_season,
        "free_agents": fa,
        "cap_room": cap_room,
        "meta": {
            "source": "warehouse",
            "tables": {"free_agents": "silver_free_agents",
                       "cap_room": "silver_cap_room"},
            "sources": ["bref_contracts", "nba_cba"],
            "estimated": True,
            "cap_hold_contract": CAP_HOLD_CONTRACT,
            "cap_hold_derivation": hold_payload.get("meta") or {},
        },
    }, ["cap_room", "salary", "amount"])
