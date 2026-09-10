"""Watchlist desk. Followed players and teams for the Today view.

User data lives in a ``watchlists`` table (entity_type, entity_id,
added_at). It is not a silver_ table. Silver tables stay read-only here.
"""

from datetime import datetime, timezone
from typing import Any

from langchain_core.tools import tool

from .. import store
from ._core import SEASON


def _norm_type(entity_type: object) -> str:
    return str(entity_type or "").strip().lower()


def _norm_player(entity_id: object) -> tuple[str, int | None]:
    """Canonical full name plus id. Falls back to the raw string."""
    from ._core import coerce_player_id

    raw = str(entity_id or "").strip()
    if not raw:
        return "", None
    try:
        pid = coerce_player_id(raw)
    except ValueError:
        return raw, None
    try:
        from nba_api.stats.static import players as _players

        for p in _players.get_players():
            if p.get("id") == pid:
                return str(p.get("full_name") or raw), pid
    except Exception:
        pass
    return raw, pid


def _norm_team(entity_id: object) -> tuple[str, int | None]:
    """Uppercase abbrev plus id. Falls back to the raw string uppercased."""
    from ._core import coerce_team_id

    raw = str(entity_id or "").strip()
    if not raw:
        return "", None
    try:
        tid = coerce_team_id(raw)
    except ValueError:
        return raw.upper(), None
    try:
        from nba_api.stats.static import teams as _teams

        for t in _teams.get_teams():
            if t.get("id") == tid:
                return str(t.get("abbreviation") or raw).upper(), tid
    except Exception:
        pass
    return raw.upper(), tid


def _ensure_table(con: Any) -> None:
    con.execute(
        """CREATE TABLE IF NOT EXISTS watchlists(
        entity_type VARCHAR, entity_id VARCHAR, added_at VARCHAR)"""
    )


def _normalize(entity_type: str, entity_id: object) -> tuple[str, str]:
    if entity_type == "player":
        name, _ = _norm_player(entity_id)
        return entity_type, name
    abbrev, _ = _norm_team(entity_id)
    return entity_type, abbrev


def _player_snapshot(name: str, season: str) -> dict[str, Any]:
    con = store.connect()
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        if "silver_leaders_pts" not in tables:
            return {"found": False}
        row = con.execute(
            """SELECT PLAYER, TEAM, GP, PTS, REB, AST FROM silver_leaders_pts
            WHERE _season = ? AND LOWER(PLAYER) = LOWER(?) LIMIT 1""",
            [season, name],
        ).fetchone()
    except Exception:
        return {"found": False}
    finally:
        con.close()
    if not row:
        return {"found": False, "player": name}
    _, team, gp, pts, reb, ast = row
    gp = gp or 0
    per = lambda v: round(float(v or 0) / gp, 1) if gp else None
    return {
        "found": True, "player": row[0], "team": team, "gp": gp,
        "ppg": per(pts), "rpg": per(reb), "apg": per(ast),
    }


def _team_snapshot(abbrev: str, season: str) -> dict[str, Any]:
    tid = None
    try:
        from nba_api.stats.static import teams as _teams

        for t in _teams.get_teams():
            if str(t.get("abbreviation") or "").upper() == abbrev:
                tid = t["id"]
                break
    except Exception:
        tid = None
    con = store.connect()
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        if "silver_standings" not in tables:
            return {"found": False}
        if tid is not None:
            row = con.execute(
                """SELECT TeamCity, TeamName, WINS, LOSSES FROM silver_standings
                WHERE _season = ? AND TeamID = ? LIMIT 1""",
                [season, tid],
            ).fetchone()
        else:
            row = None
    except Exception:
        return {"found": False}
    finally:
        con.close()
    if not row:
        return {"found": False, "team": abbrev}
    city, name, wins, losses = row
    return {
        "found": True, "team": abbrev,
        "name": f"{city or ''} {name or ''}".strip(),
        "wins": wins, "losses": losses,
        "record": f"{wins}-{losses}" if wins is not None else None,
    }


@tool
def add_watchlist_item(entity_type: str, entity_id: str) -> dict[str, Any]:
    """Follow a player (full name) or team (abbrev). Idempotent."""
    etype = _norm_type(entity_type)
    if etype not in ("player", "team"):
        return {"tool": "add_watchlist_item", "ok": False,
                "error": "entity_type must be 'player' or 'team'"}
    _, canonical = _normalize(etype, entity_id)
    if not canonical:
        return {"tool": "add_watchlist_item", "ok": False,
                "error": "entity_id is empty"}
    now = datetime.now(timezone.utc).isoformat()
    con = store.connect()
    try:
        with store.write_guard():
            _ensure_table(con)
            hit = con.execute(
                """SELECT added_at FROM watchlists
                WHERE entity_type = ? AND entity_id = ?""",
                [etype, canonical],
            ).fetchone()
            if hit:
                return {"tool": "add_watchlist_item", "ok": True,
                        "rows": {"entity_type": etype, "entity_id": canonical,
                                 "added_at": hit[0], "added": False},
                        "meta": {"source": "watchlists"}}
            con.execute(
                "INSERT INTO watchlists VALUES (?,?,?)",
                [etype, canonical, now],
            )
    finally:
        con.close()
    return {"tool": "add_watchlist_item", "ok": True,
            "rows": {"entity_type": etype, "entity_id": canonical,
                     "added_at": now, "added": True},
            "meta": {"source": "watchlists"}}


@tool
def remove_watchlist_item(entity_type: str, entity_id: str) -> dict[str, Any]:
    """Unfollow a player or team. Removing a missing entry is a no-op."""
    etype = _norm_type(entity_type)
    if etype not in ("player", "team"):
        return {"tool": "remove_watchlist_item", "ok": False,
                "error": "entity_type must be 'player' or 'team'"}
    _, canonical = _normalize(etype, entity_id)
    if not canonical:
        return {"tool": "remove_watchlist_item", "ok": False,
                "error": "entity_id is empty"}
    con = store.connect()
    try:
        with store.write_guard():
            _ensure_table(con)
            hit = con.execute(
                """SELECT COUNT(*) FROM watchlists
                WHERE entity_type = ? AND entity_id = ?""",
                [etype, canonical],
            ).fetchone()
            existed = bool(hit and hit[0])
            if existed:
                con.execute(
                    """DELETE FROM watchlists
                    WHERE entity_type = ? AND entity_id = ?""",
                    [etype, canonical],
                )
            removed = existed
    finally:
        con.close()
    return {"tool": "remove_watchlist_item", "ok": True,
            "rows": {"entity_type": etype, "entity_id": canonical,
                     "removed": bool(removed)},
            "meta": {"source": "watchlists"}}


@tool
def get_watchlist(season: str = SEASON) -> dict[str, Any]:
    """List followed entities with their latest snapshot.

    Players carry per-game PTS/REB/AST from silver_leaders_pts.
    Teams carry W/L from silver_standings.
    """
    season = str(season or SEASON).strip() or SEASON
    con = store.connect()
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        if "watchlists" not in tables:
            entries: list = []
        else:
            entries = con.execute(
                """SELECT entity_type, entity_id, added_at FROM watchlists
                ORDER BY added_at ASC"""
            ).fetchall()
    finally:
        con.close()
    rows = []
    for etype, eid, added in entries:
        snap = _player_snapshot(eid, season) if etype == "player" \
            else _team_snapshot(eid, season)
        rows.append({"entity_type": etype, "entity_id": eid,
                     "added_at": added, "snapshot": snap})
    return {"tool": "get_watchlist", "ok": True, "rows": rows,
            "meta": {"source": "warehouse", "season": season,
                     "count": len(rows)}}
