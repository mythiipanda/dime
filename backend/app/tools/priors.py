"""RAPM prior estimates. Current season blended with multi-season priors."""

from typing import Any

from langchain_core.tools import tool

from ._core import SEASON

PRIOR_SEASONS = {2022: "2021-22", 2023: "2022-23",
                 2024: "2023-24", 2025: "2024-25"}
PRIOR_FLOOR, PRIOR_CAP = 2022, 2025
ESTIMATE_LABEL = ("documented-estimate: possession-weighted mean of "
                  "current-season RAPM plus prior-season RAPM")


def season_label(end_year: object) -> str:
    return PRIOR_SEASONS[int(str(end_year).strip())]


def clamp_prior_seasons(seasons: object) -> list[int]:
    if seasons is None:
        return sorted(PRIOR_SEASONS)
    if isinstance(seasons, (int, str)):
        seasons = [seasons]
    out: list[int] = []
    for s in list(seasons):
        try:
            year = int(str(s).strip()[:4])
        except (TypeError, ValueError):
            continue
        out.append(max(PRIOR_FLOOR, min(PRIOR_CAP, year)))
    return sorted(set(out))


def blend_estimate(current: dict[str, Any] | None,
                   priors: list[dict[str, Any]]) -> dict[str, Any] | None:
    parts = ([current] if current else []) + list(priors or [])
    weighted = [(float(p["rapm"]), int(p["possessions"])) for p in parts
                if p.get("rapm") is not None and (p.get("possessions") or 0) > 0]
    if not weighted:
        return None
    total = sum(w for _, w in weighted)
    return {"estimate": round(sum(r * w for r, w in weighted) / total, 2),
            "total_possessions": total}


@tool
def get_rapm_prior(player: str = "", seasons: object = None) -> dict[str, Any]:
    """Prior-informed RAPM for one player.

    Blends current-season silver_rapm with silver_rapm_prior seasons.
    Returns a documented estimate, or an honest empty when missing.
    """
    from .. import store as _store

    name = str(player or "").strip()
    if not name:
        return {"tool": "get_rapm_prior", "ok": False, "rows": {},
                "meta": {}, "error": "player needed"}
    want = clamp_prior_seasons(seasons)
    if not want:
        return {"tool": "get_rapm_prior", "ok": False, "rows": {},
                "meta": {}, "error": "no usable prior seasons"}
    labels = [PRIOR_SEASONS[y] for y in want]
    con = _store.connect()
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        if "silver_rapm_prior" not in tables:
            return {"tool": "get_rapm_prior", "ok": False, "rows": {},
                    "meta": {"estimate": ESTIMATE_LABEL},
                    "error": "rapm priors not seeded yet"}
        like = f"%{name.lower()}%"
        cur = None
        if "silver_rapm" in tables:
            row = con.execute(
                """SELECT player_id, name, rapm, possessions FROM silver_rapm
                WHERE _season = ? AND LOWER(name) LIKE ?
                ORDER BY possessions DESC LIMIT 1""",
                [SEASON, like],
            ).fetchone()
            if row:
                cur = {"player_id": str(row[0]), "name": row[1],
                       "rapm": row[2], "possessions": row[3] or 0,
                       "season": SEASON}
        placeholders = ", ".join("?" * len(labels))
        prior_rows = con.execute(
            f"""SELECT player_id, name, rapm, possessions, _season
            FROM silver_rapm_prior
            WHERE LOWER(name) LIKE ? AND _season IN ({placeholders})
            ORDER BY _season""",
            [like, *labels],
        ).fetchall()
    finally:
        con.close()
    priors = [{"player_id": str(r[0]), "name": r[1], "rapm": r[2],
               "possessions": r[3] or 0, "season": r[4]} for r in prior_rows]
    if cur is None and not priors:
        return {"tool": "get_rapm_prior", "ok": False, "rows": {},
                "meta": {"estimate": ESTIMATE_LABEL, "seasons": labels},
                "error": f"no RAPM rows for '{name}'"}
    blended = blend_estimate(cur, priors)
    head = cur or (priors[-1] if priors else {})
    return {"tool": "get_rapm_prior", "ok": True,
            "rows": {"player": head.get("name"), "player_id": head.get("player_id"),
                     "estimate": (blended or {}).get("estimate"),
                     "current": cur, "priors": priors,
                     "seasons_used": sorted({p["season"] for p in priors})},
            "meta": {"estimate": ESTIMATE_LABEL, "source": "rapm-lite plus rapm-prior",
                     "seasons": labels}}
