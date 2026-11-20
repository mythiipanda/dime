from typing import Any

from langchain_core.tools import tool

from .. import store
from ..sources import nba_stats
from ._core import (
    _warehouse_or_live,
    clamp_scope,
    clamp_season,
    coerce_player_id,
    coerce_team_id,
    resolve_season,
)


def _coverage() -> list[str]:
    try:
        frame = store.read_frame("silver_playtypes", "1 = 1", [])
    except (FileNotFoundError, store.TableAbsent):
        return []
    if frame.height == 0 or "_season" not in frame.columns:
        return []
    return sorted({str(v) for v in frame["_season"].to_list() if v})


def _clamp_side(side: object) -> str:
    lowered = str(side or "").strip().lower()
    return lowered if lowered in ("offense", "defense") else "offense"


def _hist_season_end(season: str) -> int:
    tail = str(season).split("-")[-1]
    year = int(tail)
    return year + 2000 if len(tail) == 2 else year


def _team_display_name(con: Any, season: str, team_id: int) -> str | None:
    try:
        row = con.execute(
            "SELECT TEAM_NAME FROM silver_team_ratings WHERE TEAM_ID = ? AND _season = ? LIMIT 1",
            [team_id, season]).fetchone()
    except Exception:
        return None
    return str(row[0]) if row and row[0] else None


def _possession_proxy_profile(subject: str, team_id: int, season: str) -> dict[str, Any]:
    season_end = _hist_season_end(season)
    try:
        con = store.connect(read_only=True)
        try:
            name = _team_display_name(con, season, team_id)
            rows = con.execute(
                """
                SELECT possession_start_type, COUNT(*) AS poss, AVG(points) AS ppp
                FROM silver_hist_possessions
                WHERE season = ? AND count_as_possession = 'true' AND garbage = 0 AND offense_team_id = ?
                GROUP BY possession_start_type
                """,
                [season_end, team_id]).fetchall()
        finally:
            con.close()
    except Exception as exc:
        return {"tool": "get_playtype_profile", "ok": False, "error": str(exc)}
    if not rows:
        return {"tool": "get_playtype_profile", "ok": False,
                "error": f"no possession start-type proxy for {subject} in {season}"}
    total_poss = sum(int(r[1] or 0) for r in rows)
    play_types = [
        {"play_type": str(r[0]), "poss_pct": round(int(r[1] or 0) / total_poss, 4),
         "ppp": round(float(r[2] or 0), 4), "percentile": None, "gp": None,
         "poss": int(r[1] or 0)}
        for r in rows if total_poss
    ]
    play_types.sort(key=lambda p: (-float(p["poss_pct"] or 0), str(p["play_type"])))
    return {"tool": "get_playtype_profile", "ok": True,
            "rows": {"subject": name or str(subject), "subject_id": team_id,
                     "kind": "team", "side": "offense", "season": season,
                     "play_types": play_types},
            "meta": {"season": season, "kind": "team", "side": "offense",
                     "subject_id": team_id, "proxy": "silver_hist_possessions.possession_start_type",
                     "hist_season": season_end, "synergy_available": False}}


@tool(description="Synergy play-type profile for one player or team and season: frequency share, PPP, and percentile per play type on offense or defense. If Synergy playtypes are absent, team offense returns warehouse possession start-type PPP proxies without live endpoints.")
def get_playtype_profile(subject: str, kind: str = "player",
                         side: str = "offense",
                         season: str | None = None) -> dict[str, Any]:
    covered = _coverage()
    kind = clamp_scope(kind)
    side = _clamp_side(side)
    if not covered:
        try:
            sid = (coerce_player_id(subject) if kind == "player"
                   else coerce_team_id(subject))
        except ValueError as exc:
            return {"tool": "get_playtype_profile", "ok": False,
                    "error": str(exc)}
        if kind == "team" and side == "offense":
            resolved = resolve_season(season, table="silver_hist_possessions")
            if not resolved:
                return {"tool": "get_playtype_profile", "ok": False,
                        "error": "no playtype data in the warehouse yet"}
            try:
                season = clamp_season(resolved, coverage_start="2015-16",
                                      coverage_end=resolved)
            except Exception as exc:
                return {"tool": "get_playtype_profile", "ok": False,
                        "error": str(exc)}
            return _possession_proxy_profile(subject, sid, season)
        return {"tool": "get_playtype_profile", "ok": False,
                "error": "no playtype data in the warehouse yet"}
    try:
        season = clamp_season(season or covered[-1],
                              coverage_start=covered[0],
                              coverage_end=covered[-1])
    except Exception as exc:
        return {"tool": "get_playtype_profile", "ok": False,
                "error": str(exc)}
    try:
        sid = (coerce_player_id(subject) if kind == "player"
               else coerce_team_id(subject))
    except ValueError as exc:
        return {"tool": "get_playtype_profile", "ok": False,
                "error": str(exc)}
    rows, wmeta = _warehouse_or_live(
        "silver_playtypes",
        "_season = ? AND subject_kind = ? AND side = ? AND subject_id = ?",
        [season, kind, side, sid],
        lambda: nba_stats.synergy_playtypes(
            season, "P" if kind == "player" else "T",
            "offensive" if side == "offense" else "defensive"),
        season,
        entity=f"playtypes:{kind}:{side}:{sid}",
    )
    if not rows:
        error = ((wmeta or {}).get("error")
                 or f"no {side} playtype data for {subject} in {season}")
        return {"tool": "get_playtype_profile", "ok": False, "error": error}
    ordered = sorted(rows, key=lambda r: float(r.get("poss_pct") or 0),
                     reverse=True)
    meta = dict(wmeta or {})
    meta.update({"season": season, "kind": kind, "side": side,
                 "subject_id": sid})
    keys = ("play_type", "poss_pct", "ppp", "percentile", "gp", "poss")
    return {"tool": "get_playtype_profile", "ok": True,
            "rows": {"subject": ordered[0].get("subject_name") or str(subject),
                     "subject_id": sid, "kind": kind, "side": side,
                     "season": season,
                     "play_types": [{k: p.get(k) for k in keys}
                                    for p in ordered]},
            "meta": meta}
