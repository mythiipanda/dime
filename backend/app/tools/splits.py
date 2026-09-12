"""Situational splits plus regression checks. Warehouse first, live fallback."""

import datetime as _dt
from typing import Any

from langchain_core.tools import tool

from .. import store
from ..sources import nba_stats
from ._core import (
    SEASON,
    TTL_GAMELOG,
    _warehouse_or_live,
    clamp_season,
    clamp_stat,
    coerce_player_id,
)

VERDICT_RULES = [
    'window gp < 5 -> "too early", note "fewer than 5 games in the window".',
    'tol = max(2.0, 0.10*season_pg) if stat=="PTS" else max(1.0, 0.15*season_pg);'
    " gap = window_pg - season_pg.",
    '|gap| <= tol -> "sustainable".',
    "gap > tol and (ts_delta > 0.04 or min_delta > 3 or opp_delta < -3)"
    ' -> "likely regresses", note names which drivers are inflated.',
    "gap < -tol and (ts_delta < -0.04 or min_delta < -3)"
    ' -> "likely regresses", note "window well below season norm on'
    ' depressed drivers; expected to rebound toward baseline".',
    'gap > tol with no driver signal -> "likely regresses", note'
    ' "no underlying driver found; mean reversion favored".',
    'gap < -tol with no driver signal -> "likely regresses", note'
    ' "no underlying driver found; expected to drift back toward baseline".',
]

# QA #31: this surfaced verbatim on the waiver card - internal table
# names are plumbing, never user-facing (F25-class). Say the fact only.
CAREER_UNAVAILABLE_NOTE = (
    "Career baseline is not available for this player yet, so the "
    "verdict leans on this season's baseline plus driver analysis."
)


def parse_game_date(s: object) -> _dt.date | None:
    try:
        return _dt.datetime.strptime(str(s or "").strip(), "%b %d, %Y").date()
    except (TypeError, ValueError):
        return None


def opponent_abbr(matchup: object) -> str:
    parts = str(matchup or "").split()
    return parts[-1].upper() if parts else ""


def is_home(matchup: object) -> bool:
    return "vs." in str(matchup or "")


def _f(value: object) -> float:
    try:
        if value is None or value == "":
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    gp = len(rows or [])
    if gp == 0:
        # QA #30: an empty bucket shipped as 0.0 across the board, which
        # reads as a real (terrible) performance line. Zero games is
        # missing data: N/A, never fake-neutral 0.0.
        return {"gp": 0, "ppg": None, "rpg": None, "apg": None,
                "fg_pct": None, "plus_minus": None}
    fgm = sum(_f(r.get("FGM")) for r in rows)
    fga = sum(_f(r.get("FGA")) for r in rows)
    return {
        "gp": gp,
        "ppg": round(sum(_f(r.get("PTS")) for r in rows) / gp, 1),
        "rpg": round(sum(_f(r.get("REB")) for r in rows) / gp, 1),
        "apg": round(sum(_f(r.get("AST")) for r in rows) / gp, 1),
        "fg_pct": round(fgm / fga, 3) if fga else 0.0,
        "plus_minus": round(
            sum(_f(r.get("PLUS_MINUS")) for r in rows) / gp, 1),
    }


def ts_of(rows: list[dict[str, Any]]) -> float | None:
    try:
        items = list(rows or [])
    except TypeError:
        return None
    if not items:
        return None
    pts = sum(_f(r.get("PTS")) for r in items)
    fga = sum(_f(r.get("FGA")) for r in items)
    fta = sum(_f(r.get("FTA")) for r in items)
    denom = 2 * (fga + 0.44 * fta)
    if denom <= 0:
        return None
    return round(pts / denom, 3)


def rest_days(games_asc: list[dict[str, Any]]) -> list[tuple[dict, str]]:
    dated = [(g, parse_game_date(g.get("GAME_DATE")))
             for g in (games_asc or [])]
    dated.sort(key=lambda t: (t[1] is None, t[1]))
    out: list[tuple[dict, str]] = []
    for i in range(1, len(dated)):
        prev_d = dated[i - 1][1]
        cur_d = dated[i][1]
        if prev_d is None or cur_d is None:
            continue
        gap = (cur_d - prev_d).days - 1
        bucket = "0" if gap <= 0 else ("1" if gap == 1 else "2+")
        out.append((dated[i][0], bucket))
    return out


def defense_rank(ratings_rows: list[dict[str, Any]]) -> dict[Any, int]:
    def _rate(r: dict) -> float:
        try:
            v = r.get("DEF_RATING")
            return float(v) if v is not None else float("inf")
        except (TypeError, ValueError):
            return float("inf")

    ordered = sorted(ratings_rows or [], key=_rate)
    return {r.get("TEAM_ID"): i + 1 for i, r in enumerate(ordered)}


def verdict_for(gap: float, ts_delta: float, min_delta: float,
                opp_soft: float, window_gp: int,
                tol: float) -> tuple[str, str]:
    def _n(v: object) -> float:
        try:
            return float(v) if v is not None else 0.0
        except (TypeError, ValueError):
            return 0.0

    gap, ts_delta, min_delta, opp_soft, tol = (
        _n(gap), _n(ts_delta), _n(min_delta), _n(opp_soft), _n(tol))
    try:
        gp = int(window_gp or 0)
    except (TypeError, ValueError):
        gp = 0
    if gp < 5:
        return "too early", "fewer than 5 games in the window"
    if abs(gap) <= tol:
        return "sustainable", "window within tolerance of season baseline"
    if gap > tol:
        hot: list[str] = []
        if ts_delta > 0.04:
            hot.append(f"true shooting (+{ts_delta:.3f})")
        if min_delta > 3:
            hot.append(f"minutes (+{min_delta:.1f})")
        if opp_soft < -3:
            hot.append(f"softer schedule ({opp_soft:+.1f} vs avg)")
        if hot:
            return ("likely regresses",
                    "elevated " + ", ".join(hot)
                    + "; expected to regress toward baseline")
        return ("likely regresses",
                "no underlying driver found; mean reversion favored")
    if ts_delta < -0.04 or min_delta < -3:
        return ("likely regresses",
                "window well below season norm on depressed drivers;"
                " expected to rebound toward baseline")
    return ("likely regresses",
            "no underlying driver found;"
            " expected to drift back toward baseline")


def _read_df(sql: str, params: list, tries: int = 5) -> list[dict[str, Any]]:
    import time as _time

    last: Exception | None = None
    for _ in range(tries):
        try:
            con = store.connect()
            try:
                return (
                    con.execute(sql, params)
                    .fetchdf()
                    .to_dict(orient="records")
                )
            finally:
                con.close()
        except Exception as exc:
            last = exc
            _time.sleep(0.3)
    raise last or RuntimeError("warehouse read failed")


def _resolve_name(pid: int, fallback: str) -> str:
    try:
        from nba_api.stats.static import players

        for p in players.get_players():
            if p.get("id") == pid:
                return p.get("full_name") or fallback
    except Exception:
        pass
    return fallback


def _clamp_n(n: object, default: int = 15) -> int:
    try:
        return max(1, min(int(n), 25))
    except (TypeError, ValueError):
        return default


def _sort_by_date(rows: list[dict[str, Any]],
                  desc: bool = True) -> list[dict[str, Any]]:
    dated = [(parse_game_date(r.get("GAME_DATE")), i, r)
             for i, r in enumerate(rows)]
    valid = sorted((t for t in dated if t[0] is not None),
                   key=lambda t: (t[0], t[1]), reverse=desc)
    nulls = [t for t in dated if t[0] is None]
    return [r for _, _, r in valid + nulls]


def _defense_lookup(season: str) -> tuple[dict[str, Any] | None, str | None]:
    try:
        ratings = _read_df(
            "SELECT TEAM_ID, DEF_RATING FROM silver_team_ratings"
            " WHERE _season = ?",
            [season],
        )
        if not ratings:
            return None, "no ratings rows"
        from nba_api.stats.static import teams as _teams

        abbr_to_id = {str(t.get("abbreviation") or "").upper(): t.get("id")
                      for t in _teams.get_teams()}
        return {"rank": defense_rank(ratings),
                "abbr_to_id": abbr_to_id}, None
    except Exception as exc:
        return None, str(exc)[:120]


def _load_gamelogs(player: str, season: str
                   ) -> tuple[int, list[dict], dict[str, Any] | None]:
    pid = coerce_player_id(player)
    rows, meta = _warehouse_or_live(
        "silver_player_gamelogs", "_season = ? AND _entity = ?",
        [season, f"player:{pid}"],
        lambda: nba_stats.player_gamelog(pid, season), season,
        entity=f"player:{pid}", ttl_s=TTL_GAMELOG, limit=600,
    )
    return pid, rows, meta


def _split_row(label: str, games: list[dict[str, Any]]) -> dict[str, Any]:
    agg = aggregate(games)
    agg["split"] = label
    agg["low_sample"] = agg["gp"] < 5
    return agg


@tool
def get_matchup_splits(player: str, n: int = 15,
                       season: str = SEASON) -> dict[str, Any]:
    """Situational splits over the last N games: defense tier, home/away, rest."""
    season = clamp_season(season)
    n = _clamp_n(n)
    try:
        pid, rows, wmeta = _load_gamelogs(player, season)
    except ValueError:
        return {"tool": "get_matchup_splits", "ok": False,
                "error": f"unknown player: {player}"}
    ordered = _sort_by_date(rows, desc=True)
    window = ordered[:n]
    if not window:
        return {"tool": "get_matchup_splits", "ok": False,
                "error": f"no games for {player} in {season}"}
    defense, derr = _defense_lookup(season)
    splits: list[dict[str, Any]] = []
    if defense is not None:
        rank, abbr_to_id = defense["rank"], defense["abbr_to_id"]

        def _rank_of(g: dict) -> int | None:
            tid = abbr_to_id.get(opponent_abbr(g.get("MATCHUP")))
            return rank.get(tid) if tid is not None else None

        splits.append(_split_row(
            "vs top-10 defenses",
            [g for g in window if (_rank_of(g) or 99) <= 10]))
        splits.append(_split_row(
            "vs bottom-10 defenses",
            [g for g in window if (_rank_of(g) or 0) >= 21]))
        defense_status = "ok"
    else:
        defense_status = f"unavailable: {derr}"
    splits.append(_split_row(
        "home", [g for g in window if is_home(g.get("MATCHUP"))]))
    splits.append(_split_row(
        "away", [g for g in window if not is_home(g.get("MATCHUP"))]))
    by_rest: dict[str, list] = {"0": [], "1": [], "2+": []}
    for g, bucket in rest_days(_sort_by_date(window, desc=False)):
        by_rest[bucket].append(g)
    for label in ("rest 0 days", "rest 1 day", "rest 2+ days"):
        key = label.split("rest ")[1].split(" day")[0]
        splits.append(_split_row(label, by_rest[key]))
    meta = dict(wmeta or {})
    meta.update({"season": season,
                 "low_sample_rule": "gp < 5",
                 "rest_rule": "days between consecutive games minus 1;"
                 " first window game excluded"})
    if defense_status != "ok":
        meta["defense"] = defense_status
    return {"tool": "get_matchup_splits", "ok": True,
            "rows": {"player": _resolve_name(pid, str(player)),
                     "player_id": pid,
                     "window_games": len(window),
                     "splits": splits,
                     "defense_splits": defense_status},
            "meta": meta}


def _summarize(games: list[dict[str, Any]],
               stat: str) -> dict[str, Any]:
    gp = len(games or [])
    if gp == 0:
        return {"gp": 0, "per_game": 0.0, "mpg": 0.0,
                "fga_pg": 0.0, "ts_pct": None}
    return {
        "gp": gp,
        "per_game": round(sum(_f(g.get(stat)) for g in games) / gp, 1),
        "mpg": round(sum(_f(g.get("MIN")) for g in games) / gp, 1),
        "fga_pg": round(sum(_f(g.get("FGA")) for g in games) / gp, 1),
        "ts_pct": ts_of(games),
    }


def _career_baseline(pid: int, stat: str) -> dict[str, Any]:
    try:
        con = store.connect()
        try:
            tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        finally:
            con.close()
        if "silver_hist_player_seasons" not in tables:
            raise LookupError("missing")
        rows = _read_df(
            "SELECT * FROM silver_hist_player_seasons"
            " WHERE _entity = 'league' AND player_id = ?",
            [pid],
        )
        if not rows:
            raise LookupError("empty")
        # QA #31b: len(rows) is SEASONS, not games - the card printed
        # "22.9 PTS/game over 2 games" for a 2-season baseline. Use the
        # real gp column for games, weight the average by it, and flag
        # thin samples so a 2-season career is not presented as signal.
        seasons = len(rows)
        key = stat.lower()
        games = int(sum(_f(r.get("gp")) for r in rows)) or seasons
        wsum = sum(_f(r.get(key)) * max(_f(r.get("gp")), 1.0) for r in rows)
        wgp = sum(max(_f(r.get("gp")), 1.0) for r in rows)
        per_game = round(wsum / wgp, 1) if wgp else 0.0
        out = {"available": True, "gp": games, "seasons": seasons,
               "per_game": per_game, "stat": stat}
        if games < 82 or seasons < 3:
            out["small_sample"] = True
            out["note"] = (
                f"Thin career baseline ({games} games over {seasons} "
                f"season{'s' if seasons != 1 else ''}); treat as "
                f"directional, not a settled norm.")
        return out
    except Exception:
        return {"available": False, "note": CAREER_UNAVAILABLE_NOTE}


@tool
def get_regression_check(player: str, stat: str = "PTS", n: int = 10,
                         season: str = SEASON) -> dict[str, Any]:
    """Sustainability check on a hot stat line: window vs season plus drivers."""
    stat = clamp_stat(stat)
    season = clamp_season(season)
    n = _clamp_n(n, default=10)
    try:
        pid, rows, wmeta = _load_gamelogs(player, season)
    except ValueError:
        return {"tool": "get_regression_check", "ok": False,
                "error": f"unknown player: {player}"}
    ordered = _sort_by_date(rows, desc=True)
    if not ordered:
        return {"tool": "get_regression_check", "ok": False,
                "error": f"no games for {player} in {season}"}
    window = ordered[:n]
    win_sum, sea_sum = _summarize(window, stat), _summarize(rows, stat)
    defense, _ = _defense_lookup(season)
    opp_rank_avg: float | None = None
    if defense is not None:
        rank, abbr_to_id = defense["rank"], defense["abbr_to_id"]
        ranks = []
        for g in window:
            tid = abbr_to_id.get(opponent_abbr(g.get("MATCHUP")))
            r = rank.get(tid) if tid is not None else None
            if r is not None:
                ranks.append(r)
        if ranks:
            opp_rank_avg = round(sum(ranks) / len(ranks), 1)
    opp_delta = round(15.5 - opp_rank_avg, 1) if opp_rank_avg is not None else 0.0
    wts = win_sum["ts_pct"] if win_sum["ts_pct"] is not None else 0.0
    sts = sea_sum["ts_pct"] if sea_sum["ts_pct"] is not None else 0.0
    ts_delta = round(wts - sts, 3)
    min_delta = round(win_sum["mpg"] - sea_sum["mpg"], 1)
    fga_delta = round(win_sum["fga_pg"] - sea_sum["fga_pg"], 1)
    drivers_all = [
        {"factor": "true_shooting", "window": win_sum["ts_pct"],
         "baseline": sea_sum["ts_pct"], "delta": ts_delta},
        {"factor": "minutes", "window": win_sum["mpg"],
         "baseline": sea_sum["mpg"], "delta": min_delta},
        {"factor": "shot_volume", "window": win_sum["fga_pg"],
         "baseline": sea_sum["fga_pg"], "delta": fga_delta},
        {"factor": "opponent_defense", "window": opp_rank_avg,
         "baseline": 15.5, "delta": opp_delta},
    ]
    scales = {"true_shooting": 20.0, "minutes": 0.25, "shot_volume": 1.0 / 3.0,
              "opponent_defense": 0.25}
    # QA #31: the waiver card printed raw decimals ("true shooting 0.5
    # vs 0.5 -0.05") with no units. Scale percents to 0-100 and tag
    # every driver with an explicit unit.
    _UNITS = {"true_shooting": "pct", "minutes": "min", "shot_volume": "fga",
              "opponent_defense": "rank"}
    for d in drivers_all:
        d["unit"] = _UNITS.get(d.get("factor"), "")
        if d.get("factor") == "true_shooting":
            for k in ("window", "baseline", "delta"):
                v = d.get(k)
                if isinstance(v, (int, float)) and abs(v) <= 1.5:
                    d[k] = round(v * 100, 1)
    drivers = sorted(drivers_all,
                     key=lambda d: abs(_f(d.get("delta"))
                                       * scales.get(d.get("factor"), 1.0)),
                     reverse=True)[:3]
    season_pg = sea_sum["per_game"]
    tol = (max(2.0, 0.10 * season_pg) if stat == "PTS"
           else max(1.0, 0.15 * season_pg))
    gap = round(win_sum["per_game"] - season_pg, 1)
    verdict, note = verdict_for(gap, ts_delta, min_delta, opp_delta,
                                win_sum["gp"], tol)
    meta = dict(wmeta or {})
    meta.update({"season": season, "stat": stat,
                 "verdict_rules": VERDICT_RULES,
                 "driver_scaling": "ts*20, minutes/4, fga/3, opponent/4"
                 " so factors are comparable; drivers ranked by scaled |delta|",
                 # QA #31b: QA's narrative listed per-game ranges instead
                 # of using the verdict, and misread the defense rank.
                 "opponent_defense_meaning":
                 "average defensive rank of opponents faced, 1 = best "
                 "defense, 30 = worst; negative delta = tougher slate",
                 "narrative_guidance":
                 "lead with the verdict and verdict_note, cite the top "
                 "drivers with their units, and honor any career-baseline "
                 "small_sample note; do not just list per-game ranges"})
    return {"tool": "get_regression_check", "ok": True,
            "rows": {"player": _resolve_name(pid, str(player)),
                     "player_id": pid, "stat": stat,
                     "window_n": win_sum["gp"],
                     "window": win_sum, "season": sea_sum,
                     "career": _career_baseline(pid, stat),
                     "drivers": drivers, "drivers_all": drivers_all,
                     "verdict": verdict, "verdict_note": note},
            "meta": meta}
