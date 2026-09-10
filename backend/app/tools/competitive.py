"""Competitive ratings over warehouse game logs. Padding check before trust.

Full-season margin-of-victory mixes close games with blowouts, so a
team's net rating can flatter it (or hide grit) when a few lopsided
games dominate the average. This tool recomputes MOV after excluding
blowout games (final margin above a threshold) and reports the gap as
padding_delta. Warehouse only; nothing is estimated or fabricated.
"""

from typing import Any

import duckdb
from langchain_core.tools import tool

from ._core import SEASON, clamp_season

_TOOL_NAME = "get_competitive_ratings"

_DEFINITION = (
    "Competitive MOV is a team's average margin of victory after "
    "excluding blowout games (final margin above the threshold); "
    "padding_delta is full-season MOV minus competitive MOV."
)

_CAVEATS = (
    "Game-level exclusion, not possession-level scrubbing: garbage time "
    "within competitive games is NOT removed. MOV per game approximates "
    "net rating but is not pace-adjusted. Cleaning the Glass's exact "
    "garbage-time scrub needs play-by-play score progression and "
    "starters-on-floor data, which this warehouse does not carry."
)


def clamp_blowout_margin(value: object) -> float:
    """Clamp a blowout threshold into [1, 40]. Pure: no warehouse access."""
    try:
        margin = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 20.0
    if margin != margin:  # NaN
        return 20.0
    return min(40.0, max(1.0, margin))


def _norm_season_type(s: object) -> str:
    return "".join(
        c for c in str(s or "").strip().lower() if c.isalnum())


def map_season_type(raw: object, distinct: list[str]) -> str | None:
    """Map user season_type onto the warehouse's distinct values.

    Pure: no warehouse access. Returns the canonical warehouse value,
    "all" for no filtering, or None when the input matches nothing.
    Matching is case-insensitive over alphanumeric characters, so
    "regular" maps onto "Regular Season" or "regular-season" alike.
    """
    want = _norm_season_type(raw)
    if want in ("", "all", "both"):
        return "all"
    if want in ("regular", "regularseason", "reg"):
        for cand in distinct or []:
            if "regular" in _norm_season_type(cand):
                return cand
        return None
    if want in ("playoff", "playoffs", "postseason", "post", "po"):
        for cand in distinct or []:
            norm = _norm_season_type(cand)
            if "playoff" in norm or "post" in norm:
                return cand
        return None
    for cand in distinct or []:
        if want == _norm_season_type(cand):
            return cand
    return None


def summarize_team(
    abbr: str,
    movs: list[float],
    blowout_margin: float,
) -> dict[str, Any]:
    """One padding line over a team's game MOVs. Pure: no warehouse access.

    Games with abs(mov) > margin are blowouts and leave the competitive
    set; abs(mov) == margin stays in. padding_delta is full MOV minus
    competitive MOV, so positive means blowouts inflate the rating.
    """
    margin = clamp_blowout_margin(blowout_margin)
    movs = [float(m) for m in (movs or [])]
    gp = len(movs)
    mov_full = round(sum(movs) / gp, 2) if gp else 0.0
    comp = [m for m in movs if abs(m) <= margin]
    gp_comp = len(comp)
    mov_comp = round(sum(comp) / gp_comp, 2) if gp_comp else 0.0
    padding_delta = round(mov_full - mov_comp, 2)
    blowout_gp = gp - gp_comp
    blowout_share = round(blowout_gp / gp, 3) if gp else 0.0
    wins = sum(1 for m in comp if m > 0)
    if padding_delta > 0.5:
        verdict = "padded"
    elif padding_delta < -0.5:
        verdict = "gritty"
    else:
        verdict = "neutral"
    return {
        "team": str(abbr or "").upper(),
        "gp": gp,
        "mov_full": mov_full,
        "gp_comp": gp_comp,
        "mov_comp": mov_comp,
        "padding_delta": padding_delta,
        "blowout_gp": blowout_gp,
        "blowout_share": blowout_share,
        "comp_record": {"w": wins, "l": gp_comp - wins},
        "verdict": verdict,
    }


def _resolve_team_abbr(raw: object) -> str | None:
    """Resolve an abbrev, full name, nickname, or city to an abbreviation.

    Case-insensitive over the static tables. Returns None when nothing
    matches.
    """
    from nba_api.stats.static import teams

    s = str(raw or "").strip().lower()
    if not s:
        return None
    for t in teams.get_teams():
        if s == str(t.get("abbreviation") or "").lower():
            return str(t.get("abbreviation")).upper()
    for t in teams.get_teams():
        if s == str(t.get("full_name") or "").lower():
            return str(t.get("abbreviation")).upper()
    for t in teams.get_teams():
        if s == str(t.get("nickname") or "").lower():
            return str(t.get("abbreviation")).upper()
    for t in teams.get_teams():
        if s == str(t.get("city") or "").lower():
            return str(t.get("abbreviation")).upper()
    return None


def _takeaway(row: dict[str, Any], margin: float) -> str:
    verdict = row.get("verdict")
    if verdict == "padded":
        return (
            f"{row['team']} are padded: {row['mov_full']:+} full MOV falls "
            f"to {row['mov_comp']:+} without blowouts "
            f"(>{margin:g}-pt games excluded).")
    if verdict == "gritty":
        return (
            f"{row['team']} are gritty: {row['mov_comp']:+} in competitive "
            f"games beats their {row['mov_full']:+} full MOV "
            f"(>{margin:g}-pt games excluded).")
    return (
        f"{row['team']} are what their record says: {row['mov_comp']:+} "
        f"in competitive games vs {row['mov_full']:+} overall.")


@tool
def get_competitive_ratings(
    team: str = "league",
    season: str = SEASON,
    season_type: str = "all",
    blowout_margin: float = 20,
    min_games: int = 10,
) -> dict[str, Any]:
    """Competitive MOV: is this team's net rating real or padded by blowouts.

    team: 3-letter abbrev, full name, nickname, city, or "league"/"" for
    all teams. season: "YYYY-YY" or "all" for every warehouse season.
    season_type: regular, playoffs, or all; matched against the actual
    distinct warehouse values before aggregating. blowout_margin: games
    with abs(plus_minus) above this are excluded from the competitive
    set (clamped to [1, 40]). min_games: league-mode floor on
    competitive games; clubs below it move to below_floor with counts.
    Warehouse only; plus_minus is each team's own MOV per game.
    """
    margin = clamp_blowout_margin(blowout_margin)
    try:
        floor = int(min_games)
    except (TypeError, ValueError):
        floor = 10
    floor = max(0, floor)
    want_all = (not str(team or "").strip()
                or str(team).strip().lower() == "league")
    abbr: str | None = None
    if not want_all:
        abbr = _resolve_team_abbr(team)
        if abbr is None:
            return {"tool": _TOOL_NAME, "ok": False,
                    "error": f"unknown team: {team}"}
    season_raw = str(season or "").strip()
    if season_raw.lower() == "all" or not season_raw:
        seasons: list[str] | None = None
    else:
        seasons = [clamp_season(season_raw)]
    try:
        from .. import store as _store

        con = _store.connect(read_only=True)
        try:
            tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
            if "silver_hist_gamelogs" not in tables:
                return {"tool": _TOOL_NAME, "ok": False,
                        "error": "warehouse is empty "
                                 "(silver_hist_gamelogs missing)"}
            distinct = [r[0] for r in con.execute(
                "SELECT DISTINCT season_type "
                "FROM silver_hist_gamelogs").fetchall() if r[0]]
            mapped = map_season_type(season_type, distinct)
            if mapped is None:
                return {"tool": _TOOL_NAME, "ok": False,
                        "error": f"bad season_type: {season_type} "
                                 "(use regular, playoffs, or all)"}
            q = ("SELECT game_id, team_abbreviation, team_name, "
                 "plus_minus, season_type, _season, wl "
                 "FROM silver_hist_gamelogs")
            clauses: list[str] = []
            params: list[object] = []
            if seasons is not None:
                clauses.append("_season = ?")
                params.append(seasons[0])
            if mapped != "all":
                clauses.append("season_type = ?")
                params.append(mapped)
            if abbr is not None:
                clauses.append("team_abbreviation = ?")
                params.append(abbr)
            if clauses:
                q += " WHERE " + " AND ".join(clauses)
            fetched = con.execute(q, params).fetchall()
            if seasons is None:
                seasons = sorted(
                    {r[0] for r in con.execute(
                        "SELECT DISTINCT _season "
                        "FROM silver_hist_gamelogs").fetchall() if r[0]})
        finally:
            con.close()
    except (duckdb.IOException, duckdb.ConnectionException, duckdb.Error):
        return {"tool": _TOOL_NAME, "ok": False,
                "error": "warehouse temporarily unavailable "
                         "(file lock contention); retry shortly"}
    if not fetched:
        detail = f"no games for {season_raw or 'league'}"
        if seasons is not None:
            detail = f"no games for {seasons[0]}"
        return {"tool": _TOOL_NAME, "ok": False, "error": detail}
    by_team: dict[str, dict[str, Any]] = {}
    for _, tabbr, tname, mov, _st, _seas, _wl in fetched:
        if mov is None:
            continue
        key = str(tabbr or "").upper()
        if not key:
            continue
        slot = by_team.setdefault(
            key, {"name": str(tname or ""), "movs": []})
        try:
            slot["movs"].append(float(mov))
        except (TypeError, ValueError):
            continue
        if tname and not slot["name"]:
            slot["name"] = str(tname)
    if not by_team:
        return {"tool": _TOOL_NAME, "ok": False,
                "error": "no usable MOV rows in scope"}
    meta: dict[str, Any] = {
        "source": "warehouse",
        "seasons": seasons if seasons is not None else [],
        "season_type": mapped,
        "blowout_margin": margin,
        "min_games": floor,
    }
    if want_all:
        rows: list[dict[str, Any]] = []
        below: list[dict[str, Any]] = []
        for key in sorted(by_team):
            slot = by_team[key]
            row = summarize_team(key, slot["movs"], margin)
            row["team_name"] = slot["name"]
            if row["gp_comp"] >= floor:
                rows.append(row)
            else:
                below.append({"team": key,
                              "team_name": slot["name"],
                              "gp": row["gp"],
                              "gp_comp": row["gp_comp"]})
        rows.sort(key=lambda r: r["padding_delta"], reverse=True)
        note = (f"{len(below)} team(s) below the {floor}-game "
                "competitive floor; see below_floor.") if below else ""
        return {"tool": _TOOL_NAME, "ok": True, "rows": rows,
                "below_floor": below, "note": note,
                "definition": _DEFINITION, "caveats": _CAVEATS,
                "meta": meta}
    assert abbr is not None
    slot = by_team.get(abbr)
    if slot is None:
        return {"tool": _TOOL_NAME, "ok": False,
                "error": f"no games for {abbr} in scope"}
    row = summarize_team(abbr, slot["movs"], margin)
    row["team_name"] = slot["name"]
    return {"tool": _TOOL_NAME, "ok": True, "rows": [row],
            "takeaway": _takeaway(row, margin),
            "definition": _DEFINITION, "caveats": _CAVEATS, "meta": meta}
