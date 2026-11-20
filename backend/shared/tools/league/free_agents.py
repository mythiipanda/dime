from typing import Any

from langchain_core.tools import tool

from ._helpers import _owned_connection, _pkg, _warehouse_tables
from ..competitive import _resolve_team_abbr

_FA_COLS = ["PLAYER_NAME", "TEAM", "FA_TYPE", "PRIOR_SALARY",
            "CAP_HOLD_EST", "BREF_SLUG", "_fetched_at"]
_ROOM_COLS = ["TEAM", "COMMITTED_SALARY", "PENDING_OPTION_SALARY",
              "FA_HOLDS_EST", "INCOMPLETE_ROSTER_CHARGES",
              "PROJECTED_ROOM", "PROJECTED_CAP", "PROJECTED_TAX",
              "PROJECTED_APRON1", "PROJECTED_APRON2", "NTMLE_EST",
              "BAE_EST", "ROOM_EST", "PLAYERS_UNDER_CONTRACT",
              "PENDING_OPTIONS", "ESTIMATED"]


def _rows(con, sql: str, params: list, cols: list[str]) -> list[dict]:
    return [dict(zip(cols, r)) for r in con.execute(sql, params).fetchall()]


@tool(description=(
    "Free agency and cap planning: the upcoming free agent class by team "
    "or league-wide (UFA, player/team options, two-way), estimated cap "
    "holds, and each team's projected cap room and exceptions for the "
    "next cap season. Warehouse only; refresh with seed_free_agents.py. "
    "Hold and cap figures are CBA-formula estimates, marked ESTIMATED."))
def get_free_agents(team: str = "", fa_year: str = "2027") -> dict[str, Any]:
    _pkg()
    abbr = _resolve_team_abbr(str(team or "").strip().upper()) \
        if str(team or "").strip() else ""
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
                if abbr:
                    cap_room = _rows(con,
                                     'SELECT "TEAM", "COMMITTED_SALARY",'
                                     ' "PENDING_OPTION_SALARY", "FA_HOLDS_EST",'
                                     ' "INCOMPLETE_ROSTER_CHARGES",'
                                     ' "PROJECTED_ROOM", "PROJECTED_CAP",'
                                     ' "PROJECTED_TAX", "PROJECTED_APRON1",'
                                     ' "PROJECTED_APRON2", "NTMLE_EST",'
                                     ' "BAE_EST", "ROOM_EST",'
                                     ' "PLAYERS_UNDER_CONTRACT",'
                                     ' "PENDING_OPTIONS", "ESTIMATED"'
                                     " FROM silver_cap_room WHERE TEAM = ?",
                                     [abbr], _ROOM_COLS)
                else:
                    cap_room = _rows(con,
                                     'SELECT "TEAM", "COMMITTED_SALARY",'
                                     ' "PENDING_OPTION_SALARY", "FA_HOLDS_EST",'
                                     ' "INCOMPLETE_ROSTER_CHARGES",'
                                     ' "PROJECTED_ROOM", "PROJECTED_CAP",'
                                     ' "PROJECTED_TAX", "PROJECTED_APRON1",'
                                     ' "PROJECTED_APRON2", "NTMLE_EST",'
                                     ' "BAE_EST", "ROOM_EST",'
                                     ' "PLAYERS_UNDER_CONTRACT",'
                                     ' "PENDING_OPTIONS", "ESTIMATED"'
                                     " FROM silver_cap_room"
                                     " ORDER BY PROJECTED_ROOM DESC",
                                     [], _ROOM_COLS)
            if not fa and not cap_room:
                return {"tool": "get_free_agents", "ok": False,
                        "error": "no free-agent data; run seed_free_agents.py"}
    except FileNotFoundError:
        return {"tool": "get_free_agents", "ok": False,
                "error": "warehouse absent; run seed_free_agents.py first."}
    return {
        "tool": "get_free_agents",
        "ok": True,
        "team": abbr or "league",
        "fa_year": fa_year,
        "free_agents": fa,
        "cap_room": cap_room,
        "meta": {
            "source": "warehouse",
            "tables": {"free_agents": "silver_free_agents",
                       "cap_room": "silver_cap_room"},
            "sources": ["bref_contracts", "nba_cba"],
            "estimated": True,
        },
    }
