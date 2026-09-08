"""Identity tools. Resolve names to canonical ids before any id tool."""

from typing import Any
from langchain_core.tools import tool


@tool
def resolve_entity(query: str) -> dict[str, Any]:
    """Resolve a player or team name to canonical ids. Call before any id tool."""
    try:
        from nba_api.stats.static import players, teams

        name = query.strip().lower()
        p = players.find_players_by_full_name(query)[:8]
        if not p:
            seen: set[int] = set()
            p = []
            for fn in (players.find_players_by_last_name,
                       players.find_players_by_first_name):
                try:
                    for x in fn(query)[:8]:
                        if x.get("id") not in seen:
                            seen.add(x.get("id"))
                            p.append(x)
                except Exception:
                    pass
        if not p:
            all_p = players.get_players()
            p = [x for x in all_p if name in x.get("full_name", "").lower()][:8]
        t = teams.find_teams_by_full_name(query)[:8]
        if not t:
            all_t = teams.get_teams()
            t = [x for x in all_t
                 if name in x.get("full_name", "").lower()
                 or name == x.get("abbreviation", "").lower()][:8]
        exact_p = [x for x in p if x.get("full_name", "").lower() == name]
        exact_t = [x for x in t if x.get("full_name", "").lower() == name]
        return {
            "tool": "resolve_entity",
            "ok": True,
            "rows": {
                "players": exact_p or p,
                "teams": exact_t or t,
                "exact": bool(exact_p or exact_t),
            },
            "meta": {"source": "nba_api_static"},
        }
    except Exception as exc:
        return {"tool": "resolve_entity", "ok": False, "error": str(exc)[:200]}


@tool
def search_nba(query: str) -> dict[str, Any]:
    """Find NBA players or teams matching a name. Input is a plain name."""
    try:
        from nba_api.stats.static import players, teams

        name = query.strip()
        return {
            "tool": "search_nba",
            "ok": True,
            "rows": {
                "players": players.find_players_by_full_name(name)[:8],
                "teams": teams.find_teams_by_full_name(name)[:8],
            },
            "meta": {"source": "nba_api_static"},
        }
    except Exception as exc:
        return {"tool": "search_nba", "ok": False, "error": str(exc)[:200]}
