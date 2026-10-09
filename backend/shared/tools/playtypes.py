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


@tool(description="Synergy play-type profile for one player or team and season: frequency share, PPP, and percentile per play type on offense or defense.")
def get_playtype_profile(subject: str, kind: str = "player",
                         side: str = "offense",
                         season: str | None = None) -> dict[str, Any]:
    covered = _coverage()
    if not covered:
        return {"tool": "get_playtype_profile", "ok": False,
                "error": "no playtype data in the warehouse yet"}
    try:
        season = clamp_season(season or covered[-1],
                              coverage_start=covered[0],
                              coverage_end=covered[-1])
    except Exception as exc:
        return {"tool": "get_playtype_profile", "ok": False,
                "error": str(exc)}
    kind = clamp_scope(kind)
    side = _clamp_side(side)
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
