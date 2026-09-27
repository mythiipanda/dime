"""Competitive ratings over warehouse game logs. Descriptive, not judgmental.

Full-season margin-of-victory mixes close games with blowouts. This tool
recomputes MOV after excluding blowout games (final margin above a
threshold) and reports the gap as padding_delta -- a "what happens if you
drop the tails" lens over the numbers. It ships the numbers and their
sensitivity to the threshold; it does not label teams padded/gritty or
assert causal stories about garbage time. Warehouse only; nothing is
estimated or fabricated.
"""

from collections import Counter
from typing import Any

import duckdb
from langchain_core.tools import tool

from ._core import SEASON, clamp_season

_TOOL_NAME = "get_competitive_ratings"

# Thresholds at which padding_delta is re-reported so the output itself
# shows how threshold-dependent the number is.
_MARGIN_SWEEP = (10, 20, 30)

_DEFINITION = (
    "Competitive MOV is a team's average margin of victory after "
    "excluding blowout games (final margin above the threshold); "
    "padding_delta is full-season MOV minus competitive MOV. The tool is "
    "descriptive only: it reports the numbers, the win/loss split of the "
    "excluded games, and padding_delta's sensitivity to the threshold. It "
    "does not judge whether a team's rating is 'real'."
)

_CAVEATS = (
    "Game-level exclusion, not possession-level scrubbing: garbage time "
    "within competitive games is NOT removed, and the final-margin proxy "
    "misclassifies in both directions -- a hard-fought game that ends +21 "
    "on a late free-throw parade is excluded as a 'blowout', while a game "
    "that was decided early but finished +18 stays in. Exclusion is a "
    "lens, not purification: blowout wins carry real dominance signal "
    "(consistently beating weak teams by 25 is evidence of strength), so "
    "competitive MOV systematically underrates teams that dominate weak "
    "opponents. MOV per game approximates net rating but is not "
    "pace-adjusted. Cleaning the Glass's exact garbage-time scrub needs "
    "play-by-play score progression and starters-on-floor data, which this "
    "warehouse does not carry."
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


def _scope_stats(movs: list[float], margin: float) -> dict[str, Any]:
    """MOV numbers at one blowout threshold. Pure: no warehouse access."""
    gp = len(movs)
    mov_full = round(sum(movs) / gp, 2) if gp else None
    comp = [m for m in movs if abs(m) <= margin]
    gp_comp = len(comp)
    mov_comp = round(sum(comp) / gp_comp, 2) if gp_comp else None
    padding_delta = (
        round(mov_full - mov_comp, 2)
        if mov_full is not None and mov_comp is not None
        else None
    )
    return {
        "blowout_margin": margin,
        "gp": gp,
        "mov_full": mov_full,
        "gp_comp": gp_comp,
        "mov_comp": mov_comp,
        "padding_delta": padding_delta,
    }


def summarize_team(
    abbr: str,
    movs: list[float],
    blowout_margin: float,
    min_games: int = 10,
) -> dict[str, Any]:
    """One descriptive padding line over a team's game MOVs.

    Pure: no warehouse access. Games with abs(mov) > margin are blowouts
    and leave the competitive set; abs(mov) == margin stays in.
    competitive_record is the W-L record over competitive games ONLY, not
    the team's full record. When competitive games fall below min_games
    the row is flagged low_sample and carries no interpretation. An empty
    competitive set yields null mov_comp/padding_delta, never zeros.
    sensitivity re-reports the numbers at margins 10/20/30 so
    threshold-dependence is visible in the output itself.
    """
    margin = clamp_blowout_margin(blowout_margin)
    movs = [float(m) for m in (movs or [])]
    try:
        floor = int(min_games)
    except (TypeError, ValueError):
        floor = 10
    floor = max(0, floor)
    gp = len(movs)
    main = _scope_stats(movs, margin)
    blowout_wins_gp = sum(1 for m in movs if m > margin)
    blowout_losses_gp = sum(1 for m in movs if m < -margin)
    comp = [m for m in movs if abs(m) <= margin]
    wins = sum(1 for m in comp if m > 0)
    sensitivity = [
        {k: v for k, v in _scope_stats(movs, float(m)).items()
         if k in ("blowout_margin", "gp_comp", "mov_comp", "padding_delta")}
        for m in _MARGIN_SWEEP
    ]
    return {
        "team": str(abbr or "").upper(),
        "gp": gp,
        "mov_full": main["mov_full"],
        "gp_comp": main["gp_comp"],
        "mov_comp": main["mov_comp"],
        "padding_delta": main["padding_delta"],
        "blowout_gp": blowout_wins_gp + blowout_losses_gp,
        "blowout_wins_gp": blowout_wins_gp,
        "blowout_losses_gp": blowout_losses_gp,
        "blowout_wins_share": round(blowout_wins_gp / gp, 3) if gp else 0.0,
        "blowout_losses_share": (
            round(blowout_losses_gp / gp, 3) if gp else 0.0),
        "competitive_record": {"w": wins, "l": len(comp) - wins},
        "low_sample": main["gp_comp"] < floor,
        "sensitivity": sensitivity,
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


def _read(row: dict[str, Any], margin: float) -> str | None:
    """Plain descriptive read of one row. None when there is nothing
    to describe (low-sample or degenerate inputs get numbers only)."""
    if row.get("low_sample"):
        return None
    delta = row.get("padding_delta")
    if delta is None:
        return None
    if delta > 0:
        return (
            f"competitive MOV is {delta:g} pts lower than full-season MOV "
            f"(margin threshold {margin:g})")
    if delta < 0:
        return (
            f"competitive MOV is {abs(delta):g} pts higher than full-season "
            f"MOV (margin threshold {margin:g})")
    return (
        f"competitive MOV matches full-season MOV "
        f"(margin threshold {margin:g})")


@tool
def get_competitive_ratings(
    team: str = "league",
    season: str = SEASON,
    season_type: str = "regular",
    blowout_margin: float = 20,
    min_games: int = 10,
) -> dict[str, Any]:
    """Competitive MOV: what happens to a team's MOV when blowouts are dropped.

    team: 3-letter abbrev, full name, nickname, city, or "league"/"" for
    all teams. season: "YYYY-YY" or "all" for every warehouse season
    (multi-season output is pooled across seasons, not a single
    team-season -- see meta.season_note). season_type: regular (default),
    playoffs, or all; matched against the actual distinct warehouse values
    before aggregating. NOTE: the default changed from "all" to "regular"
    on 2026-09-10 so season-scoped queries no longer silently mix playoff
    games in; pass "all" explicitly to include playoffs.
    blowout_margin: games with abs(plus_minus) above this are excluded from
    the competitive set (clamped to [1, 40]). min_games: floor on
    competitive games; rows below it are flagged low_sample and carry
    numbers with no interpretation. Warehouse only; plus_minus is each
    team's own MOV per game.
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
    type_split = dict(Counter(str(r[4] or "unknown") for r in fetched))
    n_seasons = len(seasons) if seasons else 0
    if n_seasons > 1:
        season_scope = "pooled"
        season_note = (
            f"pooled across {n_seasons} seasons "
            f"({seasons[0]}-{seasons[-1]}), not a single team-season")
    elif n_seasons == 1:
        season_scope = "single"
        season_note = f"single season {seasons[0]}"
    else:
        season_scope = "unknown"
        season_note = "no seasons in scope"
    meta: dict[str, Any] = {
        "source": "warehouse",
        "seasons": seasons if seasons is not None else [],
        "season_scope": season_scope,
        "season_note": season_note,
        "season_type": mapped,
        "season_type_split": type_split,
        "blowout_margin": margin,
        "min_games": floor,
    }
    if want_all:
        rows: list[dict[str, Any]] = []
        for key in sorted(by_team):
            slot = by_team[key]
            row = summarize_team(key, slot["movs"], margin, floor)
            row["team_name"] = slot["name"]
            rows.append(row)
        rows.sort(key=lambda r: (r["padding_delta"] is None,
                                 -(r["padding_delta"] or 0.0)))
        low_n = sum(1 for r in rows if r["low_sample"])
        note = (f"{low_n} team(s) below the {floor}-game competitive "
                "floor; flagged low_sample with no interpretation."
                if low_n else "")
        return {"tool": _TOOL_NAME, "ok": True, "rows": rows,
                "note": note, "definition": _DEFINITION,
                "caveats": _CAVEATS, "meta": meta}
    assert abbr is not None
    slot = by_team.get(abbr)
    if slot is None:
        return {"tool": _TOOL_NAME, "ok": False,
                "error": f"no games for {abbr} in scope"}
    row = summarize_team(abbr, slot["movs"], margin, floor)
    row["team_name"] = slot["name"]
    read = _read(row, margin)
    if row["gp_comp"] == 0:
        note = (f"no competitive games at margin threshold {margin:g}; "
                "mov_comp and padding_delta are null")
    elif row["low_sample"]:
        note = (f"low-sample: {row['gp_comp']} competitive game(s), below "
                f"the {floor}-game floor; numbers reported with no "
                "interpretation")
    elif (row["blowout_wins_share"] + row["blowout_losses_share"]) > 0.5:
        note = ("over half of this team's games were excluded as blowouts; "
                "the 'competitive' set is a minority of the schedule")
    else:
        note = ""
    return {"tool": _TOOL_NAME, "ok": True, "rows": [row], "read": read,
            "note": note, "definition": _DEFINITION, "caveats": _CAVEATS,
            "meta": meta}
