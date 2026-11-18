from datetime import datetime as _dt
from typing import Any

from langchain_core.tools import tool

from .._core import coerce_team_id
from ..sim import run_playoff_sim
from ._helpers import _pkg


def _finals_game_scores(finals: list[dict[str, Any]],
                        season: str) -> dict[str, dict[str, int]]:
    pkg = _pkg()
    season = pkg.resolve_season(season)
    dates: dict[str, str] = {}
    for g in finals:
        try:
            dates[_dt.strptime(str(g.get("GAME_DATE")), "%Y-%m-%d")
                  .strftime("%b %-d, %Y")] = str(g.get("GAME_DATE"))
        except (TypeError, ValueError):
            pass
    if not dates:
        return {}
    try:
        con = pkg.store.connect(read_only=True)
        try:
            ph = ",".join("?" * len(dates))
            rows = con.execute(
                f"SELECT GAME_DATE, split_part(MATCHUP, ' ', 1), "
                f"SUM(PTS) FROM silver_playoff_gamelogs "
                f"WHERE _season = ? AND GAME_DATE IN ({ph}) "
                f"GROUP BY 1, 2",
                [season, *sorted(dates)]).fetchall()
        finally:
            con.close()
    except Exception:
        return {}
    out: dict[str, dict[str, int]] = {}
    for gdate, team, pts in rows:
        iso = dates.get(str(gdate))
        if iso and team:
            out.setdefault(iso, {})[str(team)] = int(pts or 0)
    return out


def _playoff_home_team(matchup: str) -> str:
    if " @ " in matchup:
        return matchup.split(" @ ")[1].strip()
    if " vs. " in matchup:
        return matchup.split(" vs. ")[0].strip()
    return ""


def _playoff_finals_game(g: dict, ta: str, tb: str,
                         scores: dict) -> dict[str, Any]:
    matchup = str(g.get("MATCHUP"))
    game = {"game_id": str(g.get("GAME_ID")),
            "date": str(g.get("GAME_DATE")),
            "matchup": matchup,
            "home": _playoff_home_team(matchup),
            "winner": (ta if g.get("WL") == "W" else tb)}
    sc = scores.get(str(g.get("GAME_DATE")) or "")
    if sc:
        game["score"] = sc
        game["scoreline"] = ", ".join(
            f"{t} {sc[t]}" for t in (ta, tb) if t in sc)
    return game


def _playoff_finals_games(finals: list[dict[str, Any]], ta: str, tb: str,
                          scores: dict) -> list[dict[str, Any]]:
    return [_playoff_finals_game(g, ta, tb, scores) for g in finals
            if str(g.get("TEAM_ABBREVIATION")) == ta]


def _playoff_finals_wins(finals: list[dict[str, Any]]) -> dict[str, int]:
    fwins: dict[str, int] = {}
    for r in finals:
        t = str(r.get("TEAM_ABBREVIATION") or "")
        if r.get("WL") == "W":
            fwins[t] = fwins.get(t, 0) + 1
    return fwins


def _playoff_finals_rows(finals: list[dict[str, Any]], fteams: list[str],
                         season: str) -> dict[str, Any] | None:
    if len(fteams) != 2:
        return None
    ta, tb = fteams[0], fteams[1]
    fwins = _playoff_finals_wins(finals)
    return {
        "round": "NBA Finals",
        "teams": [ta, tb],
        "series_score": (f"{ta} {fwins.get(ta, 0)} - "
                         f"{fwins.get(tb, 0)} {tb}"),
        "winner": max(fwins, key=fwins.get) if fwins else "",
        "games": _playoff_finals_games(
            finals, ta, tb, _finals_game_scores(finals, season)),
    }


def _playoff_finals_dates(finals: list[dict[str, Any]]) -> set[str]:
    fdates = set()
    for g in finals:
        try:
            fdates.add(_dt.strptime(
                str(g.get("GAME_DATE")), "%Y-%m-%d"
            ).strftime("%b %-d, %Y"))
        except (TypeError, ValueError):
            pass
    return fdates


def _playoff_finals_leader(season: str, fdates: set[str]):
    con = _pkg().store.connect(read_only=True)
    try:
        ph = ",".join("?" * len(fdates))
        row = con.execute(
            f"SELECT _entity, COUNT(*), ROUND(AVG(PTS), 1) FROM "
            f"silver_playoff_gamelogs WHERE _season = ? "
            f"AND GAME_DATE IN ({ph}) GROUP BY 1 "
            f"ORDER BY 3 DESC LIMIT 1",
            [season, *sorted(fdates)]).fetchone()
        if not row or not row[1]:
            return None
        pid = str(row[0]).replace("player:", "")
        named = con.execute(
            "SELECT DISTINCT PLAYER FROM silver_leaders_pts WHERE "
            "CAST(PLAYER_ID AS VARCHAR) = ?", [pid]).fetchone()
        return (named[0] if named else pid), row[2], len(fdates)
    finally:
        con.close()


def _playoff_finals_mvp_note(finals: dict[str, Any], rows: list[dict],
                             season: str) -> None:
    try:
        fdates = _playoff_finals_dates(rows)
        if not fdates:
            return
        leader = _playoff_finals_leader(season, fdates)
        if leader is None:
            return
        name, ppg, game_count = leader
        finals["finals_mvp_note"] = (
            "The Finals MVP award is not recorded in "
            "this dataset. The leading Finals scorer "
            f"was {name} at {ppg} points per "
            f"game over the {game_count}-game series.")
    except Exception:
        pass


def _playoff_finals_answer(fin: dict[str, Any], season: str) -> str:
    from nba_api.stats.static import teams as _static

    names = {t["abbreviation"]: t["full_name"] for t in _static.get_teams()}
    winner = fin["winner"]
    loser = next((t for t in fin.get("teams", []) if t != winner), "")
    games = fin.get("games", [])
    won = sum(1 for g in games if g.get("winner") == winner)
    lost = (len(games) or 0) - won
    year = season.split("-")[0]
    year = str(int(year) + 1) if year.isdigit() else season
    return (f"The {names.get(winner, winner)} won the {year} NBA Finals, "
            f"beating the {names.get(loser, loser)} {won}-{lost}.")


def _playoff_wins_rows(rows: list[dict[str, Any]]) -> tuple[dict, dict, int]:
    wins: dict[str, int] = {}
    losses: dict[str, int] = {}
    games = 0
    for r in rows:
        team = str(r.get("TEAM_ABBREVIATION") or "")
        if not team:
            continue
        games += 1
        if r.get("WL") == "W":
            wins[team] = wins.get(team, 0) + 1
        else:
            losses[team] = losses.get(team, 0) + 1
    return wins, losses, games


@tool(description='Playoff wins per team plus champion for one season.')
def get_playoffs(season: str | None = None) -> dict[str, Any]:
    pkg = _pkg()
    season = pkg.resolve_season(season)
    rows, meta = pkg._warehouse_or_live(
        "silver_playoffs", "_season = ?",
        [season], lambda: pkg.nba_stats.playoff_results(season), season,
        limit=600,
    )
    wins, losses, games = _playoff_wins_rows(rows)
    if not rows and meta.get("error"):
        return {"tool": "get_playoffs", "ok": False,
                "error": str(meta["error"])}
    table = sorted(
        ((t, w) for t, w in wins.items()), key=lambda x: x[1], reverse=True)
    champ = table[0][0] if table and table[0][1] >= 12 else ""
    rows_out: dict[str, Any] = {
        "champion": champ,
        "champion_record":
            {"w": wins.get(champ, 0), "l": losses.get(champ, 0)}
            if champ else {},
        "wins": [{"team": t, "w": w, "l": losses.get(t, 0)}
                 for t, w in table[:16]],
        "games_total": games // 2}

    finals_rows = [r for r in rows if str(r.get("GAME_ID") or "")[7:8] == "4"]
    if finals_rows:
        fteams = sorted({str(r.get("TEAM_ABBREVIATION") or "")
                         for r in finals_rows} - {""})
        finals = _playoff_finals_rows(finals_rows, fteams, season)
        if finals is not None:
            rows_out["finals"] = finals
            _playoff_finals_mvp_note(finals, finals_rows, season)
    if pkg.season_static(season):
        rows_out["result_kind"] = "ACTUAL_RESULTS_NOT_SIMULATION"
        rows_out["summary"] = (
            f"These are the ACTUAL final {season} playoff results"
            + (f" ({champ} champions)" if champ else "")
            + ", recorded games - not a simulation or prediction. "
              "If the ask was to simulate, say simulated odds are "
              "unavailable for a completed season.")

    fin = rows_out.get("finals")
    if isinstance(fin, dict) and fin.get("winner"):
        try:
            meta["deterministic_answer"] = _playoff_finals_answer(fin, season)
        except Exception:
            pass
    return {"tool": "get_playoffs", "ok": True,
            "rows": rows_out,
            "meta": meta}


ELO_START = 1500.0
ELO_K = 20.0
ELO_HCA_BUILD = 100
ELO_HCA_PREDICT = 65
ELO_PER_POINT = 28.0


def _elo_expected(diff: float) -> float:
    return 1 / (1 + 10 ** (-diff / 400))


def _elo_mov_mult(margin: float | None, diff: float) -> float:
    if margin is None:
        return 1.0
    return ((abs(margin) + 3) ** 0.8) / (7.5 + 0.006 * abs(diff))


def _elo_game_shift(w_elo: float, l_elo: float, w_home: bool,
                    l_home: bool, margin: float | None,
                    k: float = ELO_K) -> float:
    w_adj = w_elo + (ELO_HCA_BUILD if w_home else 0)
    l_adj = l_elo + (ELO_HCA_BUILD if l_home else 0)
    diff = w_adj - l_adj
    return k * _elo_mov_mult(margin, diff) * (1 - _elo_expected(diff))


def _build_elo(rows: list) -> tuple:
    games: dict[str, list] = {}
    for r in rows:
        games.setdefault(r[1], []).append(r)
    elo: dict[str, float] = {}
    wins: dict[str, int] = {}
    losses: dict[str, int] = {}
    mov_ok = False
    for _, pair in sorted(games.items()):
        if len(pair) != 2:
            continue
        (_, _, _, _, wa, _), (_, _, _, _, wb, _) = pair
        if (wa == "W") == (wb == "W"):
            continue
        wrow, lrow = (pair[0], pair[1]) if wa == "W" else (pair[1], pair[0])
        wteam, lteam = wrow[0], lrow[0]
        margin = wrow[5]
        if margin is None:
            margin = -(lrow[5]) if lrow[5] is not None else None
        if margin is not None:
            margin = abs(margin)
            mov_ok = True
        elo.setdefault(wteam, ELO_START)
        elo.setdefault(lteam, ELO_START)
        wins[wteam] = wins.get(wteam, 0) + 1
        losses[lteam] = losses.get(lteam, 0) + 1
        shift = _elo_game_shift(elo[wteam], elo[lteam],
                                "vs." in str(wrow[3]),
                                "vs." in str(lrow[3]), margin)
        elo[wteam] += shift
        elo[lteam] -= shift
    return elo, wins, losses, mov_ok


@tool(description='Real ELO win probability between two abbreviations. Neutral unless home_abbrev matches a side.')
def get_win_prob(team_a: str = "", team_b: str = "", season: str | None = None,
                 home_abbrev: str = "") -> dict[str, Any]:
    pkg = _pkg()
    season = pkg.resolve_season(season)
    if not team_a or not team_b:
        return {"tool": "get_win_prob", "ok": False, "error": "two abbreviations needed"}
    a, b = team_a.upper(), team_b.upper()
    home = (home_abbrev or "").upper()
    con = pkg.store.connect()
    try:
        rows = con.execute(
            """SELECT team_abbreviation, game_id, game_date, matchup, wl,
            plus_minus FROM silver_hist_gamelogs
            WHERE _season = ? ORDER BY game_date, game_id""",
            [season],
        ).fetchall()
    finally:
        con.close()
    rows = [r for r in rows if pkg.is_scope_game(r[1], "regular")]
    elo, _, _, _ = _build_elo(rows)
    ra, rb = elo.get(a, ELO_START), elo.get(b, ELO_START)
    ra_adj, rb_adj = ra, rb
    if home == a:
        ra_adj += ELO_HCA_PREDICT
    elif home == b:
        rb_adj += ELO_HCA_PREDICT
    pa = _elo_expected(ra_adj - rb_adj)
    return {"tool": "get_win_prob", "ok": True,
            "rows": {"win_prob": {a: round(pa, 3), b: round(1 - pa, 3)},
                     "elo_a": round(ra), "elo_b": round(rb)},
            "meta": {"source": "warehouse", "season": season,
                     "elo": "538-style MOV-adjusted (K20, HCA100 in build)",
                     "home_edge": 65 if home in (a, b) else 0}}


@tool(description='ELO power ratings from warehouse game results for one season.')
def get_elo(season: str | None = None) -> dict[str, Any]:
    pkg = _pkg()
    season = pkg.resolve_season(season)
    con = pkg.store.connect()
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        if "silver_hist_gamelogs" not in tables:
            return {"tool": "get_elo", "ok": False, "error": "history empty"}
        rows = con.execute(
            """SELECT team_abbreviation, game_id, game_date, matchup, wl,
            plus_minus FROM silver_hist_gamelogs
            WHERE _season = ? ORDER BY game_date, game_id""",
            [season],
        ).fetchall()
    finally:
        con.close()
    rows = [r for r in rows if pkg.is_scope_game(r[1], "regular")]
    elo, wins, losses, mov_ok = _build_elo(rows)
    table = sorted(
        ({"TEAM": t, "ELO": round(v), "W": wins.get(t, 0),
          "L": losses.get(t, 0)} for t, v in elo.items()),
        key=lambda d: d["ELO"], reverse=True,
    )
    for i, row in enumerate(table, 1):
        row["rank"] = i
    return {"tool": "get_elo", "ok": True, "rows": table,
            "meta": {"source": "warehouse", "mov": mov_ok, "season": season}}


def _resolve_elo_anchor(elo: dict[str, float],
                        opponent: str | None) -> tuple[str, int, str | None]:
    if opponent is None or not str(opponent).strip():
        return "AVG", 1500, None
    from nba_api.stats.static import teams as _teams

    try:
        opp_id = coerce_team_id(opponent)
    except ValueError:
        return "", 1500, f"unknown team: {opponent}"
    by_id = {t["id"]: t["abbreviation"] for t in _teams.get_teams()}
    anchor_abbr = by_id.get(opp_id, "")
    if not anchor_abbr or anchor_abbr not in elo:
        return "", 1500, f"unknown team: {opponent}"
    return anchor_abbr, round(elo[anchor_abbr]), None


@tool(description='ELO power ratings as standings: implied win pct, win equivalents, and Elo-implied spreads. ROADMAP Appendix #3.')
def get_elo_standings(season: str | None = None, opponent: str | None = None,
                      limit: int = 30) -> dict[str, Any]:
    pkg = _pkg()
    season = pkg.resolve_season(season)
    con = pkg.store.connect()
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        if "silver_hist_gamelogs" not in tables:
            rows = []
        else:
            rows = con.execute(
                """SELECT team_abbreviation, game_id, game_date, matchup, wl,
                plus_minus FROM silver_hist_gamelogs
                WHERE _season = ? ORDER BY game_date, game_id""",
                [season],
            ).fetchall()
    finally:
        con.close()
    if not rows:
        return {"tool": "get_elo_standings", "ok": True, "rows": [],
                "meta": {"source": "warehouse", "season": season,
                         "data_note": (
                             f"no games in the warehouse for season {season}; "
                             "nothing fabricated")}}
    rows = [r for r in rows if pkg.is_scope_game(r[1], "regular")]
    elo, wins, losses, mov_ok = _build_elo(rows)
    anchor_abbr, anchor_elo, anchor_err = _resolve_elo_anchor(elo, opponent)
    if anchor_err is not None:
        return {"tool": "get_elo_standings", "ok": False, "error": anchor_err}
    table = []
    for t, v in elo.items():
        e = round(v)
        w, loss = wins.get(t, 0), losses.get(t, 0)
        pct = round(_elo_expected(e - ELO_START), 4)
        table.append({"abbr": t, "elo": e, "games": w + loss, "W": w, "L": loss,
                      "elo_win_pct": pct, "win_equiv": round(pct * 82, 1)})
    table.sort(key=lambda d: d["elo"], reverse=True)
    for i, row in enumerate(table, 1):
        row["rank"] = i
        row["elo_implied_spread"] = round(
            (row["elo"] - anchor_elo) / ELO_PER_POINT, 1)
    try:
        limit = max(0, int(limit))
    except (TypeError, ValueError):
        limit = 30
    n_games = sum(wins.values())
    return {"tool": "get_elo_standings", "ok": True, "rows": table[:limit],
            "anchor": {"abbr": anchor_abbr, "elo": anchor_elo},
            "meta": {
                "source": "warehouse", "season": season,
                "games": n_games, "teams": len(table), "mov": mov_ok,
                "constants": (
                    "start 1500, K=20, build HCA=100, MOV mult "
                    "((margin+3)^0.8)/(7.5+0.006*|diff|), implied spread "
                    "\u2248 elo_diff/28"),
                "data_note": (
                    f"ELO computed from {n_games} real games in "
                    f"silver_hist_gamelogs for season {season} (5 seasons "
                    "2021-22 through 2025-26 live in the table; this run "
                    f"used {season} only). plus_minus present on 100% of "
                    "rows, so every game is MOV-adjusted. No games "
                    "fabricated; teams with no games get no rating.")}}


@tool(description='Simulated title and finals odds from ratings, Monte Carlo brackets.')
def get_playoff_sim(season: str | None = None, sims: int = 2000) -> dict[str, Any]:
    pkg = _pkg()
    season = pkg.resolve_season(season)
    try:
        sims = max(100, min(int(sims or 2000), 10000))
    except (TypeError, ValueError):
        sims = 2000
    if pkg.season_static(season):
        _po = pkg.get_playoffs.invoke({"season": season})
        if _po.get("ok"):
            _rows = dict(_po.get("rows") or {})
            _champ = _rows.get("champion")
            _rec = _rows.get("champion_record") or {}
            _rows["result_kind"] = "ACTUAL_RESULTS_NOT_SIMULATION"
            _rows["summary"] = (
                f"The {season} season is complete - these are the ACTUAL "
                f"playoff results, not a simulation"
                + (f": {_champ} won the championship "
                   f"{_rec.get('w')}-{_rec.get('l')}. " if _champ else ". ")
                + "Monte Carlo simulated odds are unavailable for a "
                  "completed season; they return when the next season "
                  "begins. Present these numbers as final results only.")
            return {"tool": "get_playoff_sim", "ok": True,
                    "rows": _rows,
                    "meta": {"season": season, "offseason": True,
                             "note": (f"{season} is complete - these are "
                                      "the ACTUAL playoff results, not "
                                      "simulations. Simulated odds return "
                                      "when the next season begins.")}}
        return {"tool": "get_playoff_sim", "ok": False,
                "error": f"{season} is complete - simulations are "
                         f"meaningless for a finished season.",
                "meta": {"season": season, "offseason": True}}
    out = run_playoff_sim(season, sims)
    if not out.get("teams"):
        return {"tool": "get_playoff_sim", "ok": False,
                "error": out.get("meta", {}).get("error", "no field")}
    return {"tool": "get_playoff_sim", "ok": True, "rows": out,
            "meta": {**out.get("meta", {}), "season": season, "sims": sims}}
