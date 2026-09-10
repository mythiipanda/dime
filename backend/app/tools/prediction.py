"""Pre-game Monte Carlo game prediction.

Analyst-currency estimates (538-style): win probability, projected
score/total, confidence intervals from warehouse ratings, pace, home
court, and injuries. Not a betting pick. `get_matchup_preview` keeps
its no-score-prediction rule; `get_win_prob` stays in-game ELO.
"""

import ast
from typing import Any

import numpy as np
from langchain_core.tools import tool

from ._core import SEASON, clamp_season, coerce_team_id, is_past_game_date
from .preview import (
    _abbrev,
    _entity_date,
    _match_pair,
    _row_abbrs,
    _row_team_ids,
    _scoreboard_warehouse,
)

HOME_COURT_PTS = 3.0
SCORING_SD = 12.5
DEFAULT_SIMS = 10_000
DEFAULT_SEED = 7
STATUS_PENALTY = {
    "OUT": 1.0,
    "IR": 1.0,
    "SEASON": 1.0,
    "DOUBTFUL": 0.6,
    "QUESTIONABLE": 0.3,
    "DAY-TO-DAY": 0.3,
}
MAX_INJURY_PENALTY = 3.0
STALE_HOURS = 72


def _err(message: str) -> dict[str, Any]:
    return {"tool": "get_game_prediction", "ok": False, "error": message}


def _num(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _full_name(team_id: int) -> str:
    from nba_api.stats.static import teams

    for t in teams.get_teams():
        if t.get("id") == team_id:
            return str(t.get("full_name", ""))
    return ""


def _rating_row(con: Any, team_id: int,
                season: str) -> dict[str, Any] | None:
    rows = con.execute(
        """SELECT OFF_RATING, DEF_RATING, NET_RATING, PACE, GP, W, L,
                  _fetched_at FROM silver_team_ratings
           WHERE TEAM_ID = ? AND _season = ?""",
        [team_id, season],
    ).fetchall()
    if not rows:
        return None
    r = rows[0]
    vals = {k: _num(v) for k, v in
            zip(("off", "def", "net", "pace"), r[:4])}
    if any(v is None for v in vals.values()):
        return None
    return {**vals, "gp": r[4], "w": r[5], "l": r[6],
            "fetched_at": r[7]}


def _injury_penalty(con: Any, full_name: str,
                    season: str) -> dict[str, Any]:
    out = {"penalty": 0.0, "players": [], "fetched_at": None,
           "note": "no injury data in warehouse; no adjustment applied"}
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
    except Exception:
        return out
    if "silver_injuries" not in tables:
        return out
    rows = con.execute(
        "SELECT injuries, _fetched_at FROM silver_injuries "
        "WHERE display_name = ? AND _season = ?",
        [full_name, season],
    ).fetchall()
    if not rows or rows[0][0] is None:
        return out
    raw = rows[0][0]
    try:
        items = ast.literal_eval(str(raw))
    except (ValueError, SyntaxError):
        out["note"] = "injury blob unparseable; no adjustment applied"
        return out
    penalty = 0.0
    players = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        status = str(item.get("status") or "").strip().upper()
        adj = STATUS_PENALTY.get(status, 0.0)
        name = str((item.get("athlete") or {}).get("displayName") or "")
        if adj > 0 and name:
            penalty += adj
            players.append({"player": name, "status": status,
                            "penalty_pts": adj})
    out["penalty"] = round(min(penalty, MAX_INJURY_PENALTY), 2)
    out["players"] = players
    out["fetched_at"] = rows[0][1]
    out["note"] = (f"{len(players)} affected players; capped at "
                   f"{MAX_INJURY_PENALTY} pts") if players else \
        "no players listed out; no adjustment applied"
    return out


def _simulate(home_ppg: float, away_ppg: float,
              n_sims: int, seed: int) -> dict[str, Any]:
    rng = np.random.default_rng(seed)
    home = rng.normal(home_ppg, SCORING_SD, n_sims)
    away = rng.normal(away_ppg, SCORING_SD, n_sims) + rng.normal(0, 0.5, n_sims)
    p_home = float(np.mean(home > away))
    total = home + away
    margin = home - away
    z = 1.645
    se = z * (p_home * (1 - p_home) / n_sims) ** 0.5
    return {
        "p_home": p_home,
        "p_home_ci90": [max(0.0, p_home - se), min(1.0, p_home + se)],
        "home_mean": float(np.mean(home)),
        "away_mean": float(np.mean(away)),
        "total_mean": float(np.mean(total)),
        "total_ci90": [float(np.percentile(total, 5)),
                       float(np.percentile(total, 95))],
        "margin_ci90": [float(np.percentile(margin, 5)),
                        float(np.percentile(margin, 95))],
    }


def _find_meeting(season: str, ida: int, idb: int,
                  game_date: str) -> tuple[int | None, int | None, str, bool]:
    from datetime import timedelta as _td
    from datetime import datetime as _dt
    from zoneinfo import ZoneInfo

    if game_date:
        days = [game_date]
    else:
        now = _dt.now(ZoneInfo("America/New_York"))
        days = [(now + _td(days=i)).strftime("%m/%d/%Y") for i in range(14)]
    cands = sorted(
        (r for r in _scoreboard_warehouse(season, days)
         if _match_pair(r, ida, idb)),
        key=_entity_date,
    )
    if not cands:
        return None, None, "", False
    row = cands[0]
    home, away = _row_team_ids(row)
    return home, away, _entity_date(row) or days[0], True


@tool
def get_game_prediction(a: str = "", b: str = "", game_date: str = "",
                        season: str = SEASON, n_sims: int = DEFAULT_SIMS,
                        seed: int = DEFAULT_SEED) -> dict[str, Any]:
    """Pre-game Monte Carlo prediction: win probability, projected score/total, and confidence intervals. Model estimates with documented methodology, not betting picks. Two team names/abbrevs/ids; optional game_date (MM/DD/YYYY), n_sims, seed for reproducibility."""
    from .. import store

    season = clamp_season(season)
    a = str(a or "").strip()
    b = str(b or "").strip()
    game_date = str(game_date or "").strip()
    try:
        n_sims = max(1000, min(int(n_sims or DEFAULT_SIMS), 100_000))
    except (TypeError, ValueError):
        n_sims = DEFAULT_SIMS
    try:
        seed = int(seed)
    except (TypeError, ValueError):
        seed = DEFAULT_SEED
    if game_date:
        from datetime import datetime as _dt
        try:
            _dt.strptime(game_date, "%m/%d/%Y")
        except (TypeError, ValueError):
            return _err("game_date must be MM/DD/YYYY")
    if not a or not b:
        return _err("pass two teams (a, b)")
    try:
        ida = coerce_team_id(a)
    except ValueError:
        return _err(f"unknown team: {a}")
    try:
        idb = coerce_team_id(b)
    except ValueError:
        return _err(f"unknown team: {b}")
    if ida == idb:
        return _err("a and b must be different teams")

    home_id, away_id, resolved, found = _find_meeting(season, ida, idb,
                                                     game_date)
    if found and is_past_game_date(resolved):
        return _err("that game already played; pre-game estimates only")
    if found and game_date and resolved != game_date:
        return _err(f"{_abbrev(a)} and {_abbrev(b)} do not play on {game_date}")

    con = store.connect()
    try:
        ratings = {r[0]: r[1:] for r in con.execute(
            "SELECT TEAM_ID, AVG(OFF_RATING), AVG(DEF_RATING), AVG(PACE) "
            "FROM silver_team_ratings WHERE _season = ? GROUP BY TEAM_ID",
            [season]).fetchall()}
        lg_off = float(np.mean([r[0] for r in ratings.values()]))
        lg_def = float(np.mean([r[1] for r in ratings.values()]))
        home_r = _rating_row(con, home_id or ida, season)
        away_r = _rating_row(con, away_id or idb, season)
        home_inj = _injury_penalty(con, _full_name(home_id or ida), season)
        away_inj = _injury_penalty(con, _full_name(away_id or idb), season)
    finally:
        con.close()

    if home_r is None or away_r is None:
        missing = []
        if home_r is None:
            missing.append(_abbrev(str(home_id or ida)))
        if away_r is None:
            missing.append(_abbrev(str(away_id or idb)))
        return _err("ratings missing for " + ", ".join(missing) +
                    f" (season {season}); cannot simulate without them")

    # Neutral site when the warehouse has no scheduled meeting for the pair.
    neutral = not found
    h_id, aw_id = (home_id or ida), (away_id or idb)
    home_abbr, away_abbr = _abbrev(str(h_id)), _abbrev(str(aw_id))

    pace = (home_r["pace"] + away_r["pace"]) / 2
    home_per100 = lg_off + (home_r["off"] - lg_off) + (away_r["def"] - lg_def)
    away_per100 = lg_off + (away_r["off"] - lg_off) + (home_r["def"] - lg_def)
    home_ppg = home_per100 * pace / 100
    away_ppg = away_per100 * pace / 100
    hca = 0.0 if neutral else HOME_COURT_PTS
    # Injury penalty shifts net margin: half off the hurt team's scoring,
    # half onto the opponent's scoring.
    hp, ap = home_inj["penalty"], away_inj["penalty"]
    home_ppg = home_ppg + hca / 2 - hp / 2 + ap / 2
    away_ppg = away_ppg - hca / 2 + hp / 2 - ap / 2

    sim = _simulate(home_ppg, away_ppg, n_sims, seed)
    p_home = round(sim["p_home"], 3)
    p_away = round(1 - sim["p_home"], 3)

    def _card(abbr, r, inj):
        return {"abbr": abbr, "off_rating": round(r["off"], 1),
                "def_rating": round(r["def"], 1),
                "net_rating": round(r["net"], 1), "pace": round(r["pace"], 1),
                "record": f"{r['w']}-{r['l']}",
                "injury_penalty_pts": inj["penalty"],
                "injury_note": inj["note"],
                "injured_players": inj["players"],
                "ratings_fetched_at": inj.get("fetched_at") or r["fetched_at"]}

    assumptions = []
    if neutral:
        assumptions.append(
            "No scheduled meeting found in the warehouse cache for the next "
            "14 days (or on the given date), so this is a neutral-site "
            "simulation with zero home-court adjustment.")
    else:
        assumptions.append(
            f"Home court for {home_abbr} worth {HOME_COURT_PTS:.1f} points, "
            "split evenly into both teams' projected scoring.")
    if hp or ap:
        assumptions.append(
            "Injury adjustment is a documented heuristic: Out/IR cost "
            "1.0 net pt, Doubtful 0.6, Questionable/Day-To-Day 0.3, capped "
            "at 3.0 pts per team. It ignores player quality and minutes.")
    for tag, inj in (("home", home_inj), ("away", away_inj)):
        if "no injury data" in inj["note"]:
            assumptions.append(
                f"Injury data missing for the {tag} team; no injury "
                "adjustment was applied.")

    methodology = [
        "Team ratings come from warehouse silver_team_ratings (offensive and "
        "defensive rating per 100 possessions, season averages).",
        "Each team's per-100 scoring is adjusted for opponent strength "
        "relative to the league average, then scaled by the average of the "
        "two teams' paces.",
        f"{n_sims:,} Monte Carlo simulations draw each team's points from a "
        f"normal distribution (sd {SCORING_SD}) around the projected mean; "
        "tiny tie-break noise reflects that NBA games cannot end tied.",
        "Win probability is the simulated home-win share; the 90% interval "
        "is binomial sampling error. Total/margin intervals are the 5th and "
        "95th simulated percentiles.",
        f"Seed {seed} makes the draw sequence reproducible: identical inputs "
        "and seed always produce identical output.",
    ]
    limitations = [
        "Ratings are season averages; they miss recent form, rest, travel, "
        "and matchup-specific tactics.",
        "Injuries ignore which players are out and how many minutes they "
        "play; a star and a deep-bench player count the same.",
        "The scoring distribution is symmetric and independent; it does not "
        "model pace shifts, foul trouble, or overtime effects.",
        "Model estimates only. They are not betting picks or advice.",
    ]

    venue = (f"{resolved} at {home_abbr} (warehouse schedule)"
             if found and not neutral
             else "neutral site (no scheduled meeting in warehouse cache)")
    return {
        "tool": "get_game_prediction",
        "ok": True,
        "matchup": {"home": home_abbr, "away": away_abbr,
                    "game_date": resolved or None, "venue": venue},
        "estimate": {
            "win_prob": {home_abbr: p_home, away_abbr: p_away},
            "win_prob_ci90": {home_abbr: [round(x, 3) for x in sim["p_home_ci90"]],
                              away_abbr: [round(1 - sim["p_home_ci90"][1], 3),
                                           round(1 - sim["p_home_ci90"][0], 3)]},
            "projected_score": {home_abbr: round(sim["home_mean"], 1),
                                away_abbr: round(sim["away_mean"], 1)},
            "projected_total": round(sim["total_mean"], 1),
            "total_ci90": [round(x, 1) for x in sim["total_ci90"]],
            "margin_ci90": [round(x, 1) for x in sim["margin_ci90"]],
            "note": "Model estimates, not a prediction of the actual result.",
        },
        "inputs": {
            "home": _card(home_abbr, home_r, home_inj),
            "away": _card(away_abbr, away_r, away_inj),
            "game_pace": round(pace, 1),
            "league_avg_off": round(lg_off, 1),
            "league_avg_def": round(lg_def, 1),
            "home_court_pts": hca,
            "n_sims": n_sims,
            "seed": seed,
        },
        "methodology": methodology,
        "assumptions": assumptions,
        "limitations": limitations,
        "meta": {"source": "warehouse", "season": season,
                 "ratings_fetched_at": home_r["fetched_at"]},
    }
