"""League desk. Standings, leaders, hustle, ratings, history, draft."""

from typing import Any
from langchain_core.tools import tool

from ..sources import nba_stats
from ._core import SEASON, clamp_stat, _warehouse_or_live


@tool
def get_injuries(team: str = "", season: str = SEASON) -> dict[str, Any]:
    """Injury report, optional team abbreviation filter."""
    from ..sources import espn

    rows, meta = _warehouse_or_live(
        "silver_injuries", "_season = ?",
        [season], lambda: espn.injuries(season), season,
    )
    if team:
        from nba_api.stats.static import teams as _teams

        want = team.strip().upper()
        full = next(
            (t["full_name"] for t in _teams.get_teams()
             if t["abbreviation"] == want or t["full_name"].upper() == want),
            want,
        )
        rows = [r for r in rows if full.lower() in str(r.get("display_name", "")).lower()]
    return {"tool": "get_injuries", "ok": True, "rows": rows, "meta": meta}


@tool
def get_standings(season: str = SEASON) -> dict[str, Any]:
    """League standings for one season like 2025-26."""
    rows, meta = _warehouse_or_live(
        "silver_standings", "_season = ?",
        [season], lambda: nba_stats.standings(season), season,
        limit=30,
    )
    return {"tool": "get_standings", "ok": True, "rows": rows, "meta": meta}


@tool
def get_ratings(season: str = SEASON) -> dict[str, Any]:
    """Team offensive, defensive, and net ratings plus pace and ranks."""
    from nba_api.stats.static import teams as _teams

    abbrev = {t["id"]: t["abbreviation"] for t in _teams.get_teams()}
    rows, meta = _warehouse_or_live(
        "silver_team_ratings", "_season = ?",
        [season], lambda: nba_stats.team_ratings(season), season,
        limit=30,
    )
    keep = ["TEAM_NAME", "GP", "W", "L",
            "OFF_RATING", "DEF_RATING", "NET_RATING", "PACE",
            "OFF_RATING_RANK", "DEF_RATING_RANK", "NET_RATING_RANK"]
    slim = []
    for r in rows:
        d = {k: r.get(k) for k in keep if k in r}
        d["TEAM"] = abbrev.get(r.get("TEAM_ID"), str(r.get("TEAM_NAME") or ""))
        slim.append(d)
    return {"tool": "get_ratings", "ok": True, "rows": slim, "meta": meta}


@tool
def get_clutch(scope: str = "player", season: str = SEASON) -> dict[str, Any]:
    """Clutch stats (last 5 min, margin 5 or less), player or team scope."""
    scope = "team" if str(scope).lower().startswith("team") else "player"
    entity = f"{scope}-clutch"
    rows, meta = _warehouse_or_live(
        "silver_clutch", "_season = ? AND _entity = ?",
        [season, entity], lambda: nba_stats.clutch(scope, season), season,
        entity=entity, limit=600,
    )
    name_col = "TEAM_ABBREVIATION" if scope == "team" else "PLAYER_NAME"
    slim = sorted(
        ({name_col: r.get(name_col), "GP": r.get("GP"), "W": r.get("W"),
          "L": r.get("L"), "PTS": r.get("PTS"),
          "FG_PCT": r.get("FG_PCT"), "FG3_PCT": r.get("FG3_PCT"),
          "PLUS_MINUS": r.get("PLUS_MINUS")} for r in rows),
        key=lambda d: (d.get("PTS") or 0), reverse=True,
    )
    return {"tool": "get_clutch", "ok": True, "rows": slim[:30], "meta": meta}


@tool
def get_playoffs(season: str = SEASON) -> dict[str, Any]:
    """Playoff wins per team plus champion for one season."""
    rows, meta = _warehouse_or_live(
        "silver_playoffs", "_season = ?",
        [season], lambda: nba_stats.playoff_results(season), season,
        limit=600,
    )
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
    table = sorted(
        ((t, w) for t, w in wins.items()), key=lambda x: x[1], reverse=True)
    champ = table[0][0] if table and table[0][1] >= 12 else ""
    return {"tool": "get_playoffs", "ok": True,
            "rows": {"champion": champ,
                     "champion_record":
                         {"w": wins.get(champ, 0), "l": losses.get(champ, 0)}
                         if champ else {},
                     "wins": [{"team": t, "w": w, "l": losses.get(t, 0)}
                              for t, w in table[:16]],
                     "games_total": games // 2},
            "meta": meta}


@tool
def get_leaders(stat_category: str = "PTS", season: str = SEASON) -> dict[str, Any]:
    """League leaders for one stat category like PTS, REB, AST."""
    stat_category = clamp_stat(stat_category)
    table = f"silver_leaders_{stat_category.lower()}"
    rows, meta = _warehouse_or_live(
        table, "_season = ?",
        [season], lambda: nba_stats.leaders(stat_category, season), season,
    )
    meta["stat_category"] = stat_category
    try:
        from .. import store as _store

        total = len(_store.read_frame(table, "_season = ?", [season]))
        for r in rows:
            rank = r.get("RANK") or 0
            if rank and total:
                r["PERCENTILE"] = round(100 * (1 - (rank - 1) / total), 1)
    except Exception:
        pass
    return {"tool": "get_leaders", "ok": True, "rows": rows, "meta": meta}


@tool
def get_hustle(scope: str = "player", season: str = SEASON) -> dict[str, Any]:
    """Hustle leaders, player or team scope. Contests, deflections, charges."""
    from ._core import clamp_scope

    scope = clamp_scope(scope)
    rows, meta = _warehouse_or_live(
        f"silver_hustle_{scope}", "_season = ?",
        [season], lambda: nba_stats.hustle(scope, season), season,
    )
    return {"tool": "get_hustle", "ok": True, "rows": rows, "meta": meta}


@tool
def get_rapm(player: str = "", top: int = 10, season: str = SEASON) -> dict[str, Any]:
    """RAPM-lite ratings. Blank player returns top list, else one row."""
    from .. import store as _store

    con = _store.connect()
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        if "silver_rapm" not in tables:
            return {"tool": "get_rapm", "ok": False, "error": "rapm empty"}
        if player:
            rows = con.execute(
                """SELECT player_id, name, rapm, possessions FROM silver_rapm
                WHERE _season = ? AND LOWER(name) LIKE ?""",
                [season, f"%{player.lower()}%"],
            ).fetchall()
        else:
            rows = con.execute(
                """SELECT player_id, name, rapm, possessions FROM silver_rapm
                WHERE _season = ? ORDER BY rapm DESC LIMIT ?""",
                [season, max(top, 1)],
            ).fetchall()
    finally:
        con.close()
    out = [{"player_id": r[0], "name": r[1], "rapm": r[2], "possessions": r[3]}
           for r in rows]
    return {"tool": "get_rapm", "ok": True, "rows": out,
            "meta": {"source": "rapm-lite", "season": season}}


@tool
def get_finder(
    mode: str = "streak", team_abbrev: str = "", opponent: str = "",
    season: str = SEASON, window: int = 5,
) -> dict[str, Any]:
    """Team finder across history seasons. Modes: streak, versus, span,
    player_streak, head2head."""
    from .. import store as _store

    con = _store.connect()
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        if "silver_hist_gamelogs" not in tables:
            return {"tool": "get_finder", "ok": False, "error": "history empty"}
        q = """SELECT team_abbreviation, game_date, matchup, wl, pts
               FROM silver_hist_gamelogs WHERE _season = ?"""
        params: list[object] = [season]
        if team_abbrev:
            q += " AND team_abbreviation = ?"
            params.append(team_abbrev.upper())
        rows = con.execute(q + " ORDER BY game_date", params).fetchall()
    finally:
        con.close()
    if mode == "player_streak":
        from datetime import datetime as _dt

        from ._core import coerce_player_id as _cpid

        if not team_abbrev:
            return {"tool": "get_finder", "ok": False, "error": "player needed"}
        try:
            _pid = _cpid(team_abbrev)
        except ValueError as exc:
            return {"tool": "get_finder", "ok": False, "error": str(exc)[:160]}
        _con = _store.connect()
        try:
            _tables = {r[0] for r in _con.execute("SHOW TABLES").fetchall()}
            if "silver_player_gamelogs" not in _tables:
                return {"tool": "get_finder", "ok": False,
                        "error": "player gamelogs empty"}
            _prows = _con.execute(
                """SELECT GAME_DATE, PTS FROM silver_player_gamelogs
                WHERE _season = ? AND Player_ID = ?""",
                [season, _pid],
            ).fetchall()
        finally:
            _con.close()
        if not _prows:
            return {"tool": "get_finder", "ok": False,
                    "error": f"no cached games for player {_pid}"}

        def _dkey(d: object) -> object:
            try:
                return _dt.strptime(str(d), "%b %d, %Y")
            except (TypeError, ValueError):
                return _dt.min

        _prows = sorted(_prows, key=lambda r: _dkey(r[0]))
        _best = _cur = 0
        for _, _pts in _prows:
            if (_pts or 0) >= 20:
                _cur += 1
                _best = max(_best, _cur)
            else:
                _cur = 0
        return {"tool": "get_finder", "ok": True,
                "rows": {"player_id": _pid, "longest_20pt_streak": _best,
                         "games": len(_prows)},
                "meta": {"source": "warehouse", "season": season}}
    if mode == "head2head":
        from ._core import coerce_player_id as _cpid2

        if not team_abbrev or not opponent:
            return {"tool": "get_finder", "ok": False,
                    "error": "two players needed"}
        try:
            _pa = _cpid2(team_abbrev)
            _pb = _cpid2(opponent)
        except ValueError as exc:
            return {"tool": "get_finder", "ok": False, "error": str(exc)[:160]}

        def _pts_for(_pid: int) -> list:
            _c = _store.connect()
            try:
                return _c.execute(
                    """SELECT PTS FROM silver_player_gamelogs
                    WHERE _season = ? AND Player_ID = ?""",
                    [season, _pid],
                ).fetchall()
            finally:
                _c.close()

        _ra = _pts_for(_pa)
        _rb = _pts_for(_pb)
        if not _ra:
            return {"tool": "get_finder", "ok": False,
                    "error": f"no cached games for player {team_abbrev}"}
        if not _rb:
            return {"tool": "get_finder", "ok": False,
                    "error": f"no cached games for player {opponent}"}
        _ga, _gb = len(_ra), len(_rb)
        _pa_avg = round(sum((_x[0] or 0) for _x in _ra) / _ga, 1)
        _pb_avg = round(sum((_x[0] or 0) for _x in _rb) / _gb, 1)
        return {"tool": "get_finder", "ok": True,
                "rows": {"a": {"player_id": _pa, "gp": _ga, "ppg": _pa_avg},
                         "b": {"player_id": _pb, "gp": _gb, "ppg": _pb_avg}},
                "meta": {"source": "warehouse", "season": season}}
    if not rows:
        return {"tool": "get_finder", "ok": False, "error": "no games found"}
    if mode == "versus" and opponent:
        opp = opponent.upper()
        rel = [r for r in rows if opp in (r[2] or "")]
        w = sum(1 for r in rel if r[3] == "W")
        return {"tool": "get_finder", "ok": True,
                "rows": {"record": f"{w}-{len(rel) - w}", "games": len(rel)},
                "meta": {"source": "warehouse", "season": season}}
    if mode == "span":
        best = None
        for i in range(len(rows) - window + 1):
            chunk = rows[i:i + window]
            if len({c[0] for c in chunk}) > 1:
                continue
            total = sum(c[4] or 0 for c in chunk)
            if best is None or total > best[0]:
                best = (total, chunk[0][0], chunk[0][1], chunk[-1][1])
        if best is None:
            return {"tool": "get_finder", "ok": False, "error": "no span found"}
        return {"tool": "get_finder", "ok": True,
                "rows": {"team": best[1], "window": window, "points": best[0],
                         "from": best[2], "to": best[3]},
                "meta": {"source": "warehouse", "season": season}}
    best_w = best_l = cur_w = cur_l = 0
    for r in rows:
        if r[3] == "W":
            cur_w += 1
            cur_l = 0
        else:
            cur_l += 1
            cur_w = 0
        best_w = max(best_w, cur_w)
        best_l = max(best_l, cur_l)
    return {"tool": "get_finder", "ok": True,
            "rows": {"longest_win_streak": best_w, "longest_loss_streak": best_l,
                     "games": len(rows)},
            "meta": {"source": "warehouse", "season": season}}


@tool
def get_rest(team_abbrev: str = "", season: str = SEASON) -> dict[str, Any]:
    """Back-to-back plus rest-day splits from history game dates."""
    from datetime import datetime

    from .. import store as _store

    con = _store.connect()
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        if "silver_hist_gamelogs" not in tables:
            return {"tool": "get_rest", "ok": False, "error": "history empty"}
        q = """SELECT team_abbreviation, game_date, wl FROM silver_hist_gamelogs
               WHERE _season = ?"""
        params: list[object] = [season]
        if team_abbrev:
            q += " AND team_abbreviation = ?"
            params.append(team_abbrev.upper())
        rows = con.execute(q + " ORDER BY team_abbreviation, game_date",
                           params).fetchall()
    finally:
        con.close()
    try:
        parsed = [(t, datetime.strptime(d, "%Y-%m-%d").date(), w)
                  for t, d, w in rows if d]
    except (TypeError, ValueError):
        return {"tool": "get_rest", "ok": False, "error": "bad dates"}
    b2b_w = b2b_l = rest_w = rest_l = 0
    prev = None
    for t, d, w in parsed:
        if prev and prev[0] == t:
            gap = (d - prev[1]).days
            if gap <= 1:
                b2b_w += w == "W"
                b2b_l += w != "W"
            elif gap >= 3:
                rest_w += w == "W"
                rest_l += w != "W"
        prev = (t, d)
    return {"tool": "get_rest", "ok": True,
            "rows": {"back_to_back": f"{b2b_w}-{b2b_l}",
                     "three_plus_rest": f"{rest_w}-{rest_l}"},
            "meta": {"source": "warehouse", "season": season}}


@tool
def get_win_prob(team_a: str = "", team_b: str = "", season: str = SEASON,
                 home_abbrev: str = "") -> dict[str, Any]:
    """Real ELO win probability between two abbreviations. Neutral unless home_abbrev matches a side."""
    import math

    from .. import store as _store

    if not team_a or not team_b:
        return {"tool": "get_win_prob", "ok": False, "error": "two abbreviations needed"}
    a, b = team_a.upper(), team_b.upper()
    home = (home_abbrev or "").upper()
    con = _store.connect()
    try:
        rows = con.execute(
            """SELECT team_abbreviation, game_id, game_date, matchup, wl,
            plus_minus FROM silver_hist_gamelogs
            WHERE _season = ? ORDER BY game_date, game_id""",
            [season],
        ).fetchall()
    finally:
        con.close()
    games: dict[str, list] = {}
    for r in rows:
        games.setdefault(r[1], []).append(r)
    # Mirrors get_elo below. Same constants so the two never drift.
    elo: dict[str, float] = {}
    for _, pair in sorted(games.items()):
        if len(pair) != 2:
            continue
        (ta, _, _, ma, wa, pma), (tb, _, _, mb, wb, pmb) = pair
        if (wa == "W") == (wb == "W"):
            continue
        wrow, lrow = (pair[0], pair[1]) if wa == "W" else (pair[1], pair[0])
        wteam, lteam = wrow[0], lrow[0]
        margin = wrow[5]
        if margin is None:
            margin = -(lrow[5]) if lrow[5] is not None else None
        mov_mult = 1.0
        if margin is not None:
            margin = abs(margin)
        elo.setdefault(wteam, 1500.0)
        elo.setdefault(lteam, 1500.0)
        w_home = "vs." in str(wrow[3])
        l_home = "vs." in str(lrow[3])
        w_adj = elo[wteam] + (100 if w_home else 0)
        l_adj = elo[lteam] + (100 if l_home else 0)
        diff = w_adj - l_adj
        expected_w = 1 / (1 + 10 ** (-diff / 400))
        if margin is not None:
            mov_mult = ((margin + 3) ** 0.8) / (7.5 + 0.006 * abs(diff))
        shift = 20 * mov_mult * (1 - expected_w)
        elo[wteam] += shift
        elo[lteam] -= shift
    ra, rb = elo.get(a, 1500.0), elo.get(b, 1500.0)
    ra_adj, rb_adj = ra, rb
    if home == a:
        ra_adj += 65
    elif home == b:
        rb_adj += 65
    pa = 1 / (1 + 10 ** ((rb_adj - ra_adj) / 400))
    return {"tool": "get_win_prob", "ok": True,
            "rows": {"win_prob": {a: round(pa, 3), b: round(1 - pa, 3)},
                     "elo_a": round(ra), "elo_b": round(rb)},
            "meta": {"source": "warehouse", "season": season,
                     "elo": "538-style MOV-adjusted (K20, HCA100 in build)",
                     "home_edge": 65 if home in (a, b) else 0}}


CAP = {"cap": 165_000_000, "tax": 201_048_000,
       "apron1": 209_661_000, "apron2": 222_372_000}


def _payroll(team: str) -> tuple[int, list[dict]]:
    from .. import store as _store

    con = _store.connect()
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        if "silver_salaries" in tables:
            rows = con.execute(
                """SELECT PLAYER_NAME, SALARY_2025_26 FROM silver_salaries
                WHERE TEAM = ?""",
                [team.upper()],
            ).fetchall()
            if rows:
                players = [{"player": r[0], "salary": r[1]} for r in rows]
                return sum(r[1] or 0 for r in rows), players
        rows = con.execute(
            """SELECT player, salary FROM silver_cap_players
            WHERE team = ?""",
            [team.upper()],
        ).fetchall()
    finally:
        con.close()
    players = [{"player": r[0], "salary": r[1]} for r in rows]
    return sum(r[1] or 0 for r in rows), players


def _payroll_source() -> str:
    from .. import store as _store

    con = _store.connect()
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        if "silver_salaries" in tables:
            n = con.execute("SELECT COUNT(*) FROM silver_salaries").fetchone()[0]
            if n > 300:
                return "basketball-reference contracts (real 2026-27 salaries)"
    finally:
        con.close()
    return "orojas119/nba-salary-cap (estimated)"


@tool
def get_cap_ledger(team: str = "") -> dict[str, Any]:
    """Payroll plus apron room for one abbreviation. 2026-27 thresholds."""
    if not team:
        return {"tool": "get_cap_ledger", "ok": False, "error": "abbreviation needed"}
    total, players = _payroll(team)
    return {"tool": "get_cap_ledger", "ok": True,
            "rows": {"team": team.upper(), "payroll": total,
                     "players": sorted(players, key=lambda p: p["salary"] or 0,
                                       reverse=True)[:15],
                     "room_under_apron2": CAP["apron2"] - total,
                     "over_tax": total > CAP["tax"]},
            "meta": {"source": _payroll_source(), "season": "2026-27",
                     **{k: v for k, v in CAP.items()}}}


@tool
def get_trade_check(
    team_a: str = "", players_a: str = "", team_b: str = "", players_b: str = "",
) -> dict[str, Any]:
    """Trade legality check. Player names comma separated per side.

    Simplified 2023 CBA: 125 percent plus 250k matching for non-apron
    teams, 100 percent for second-apron teams, no aggregation above
    the second apron. Picks and exceptions stay out of v1.
    """
    import math as _math

    def salaries(team: str, names: str) -> tuple[int, list[str]]:
        total, roster = _payroll(team)
        want = [n.strip().lower() for n in names.split(",") if n.strip()]
        matched = []
        total_out = 0
        for w in want:
            hit = next((p for p in roster if w in p["player"].lower()), None)
            if hit:
                matched.append(hit["player"])
                total_out += hit["salary"] or 0
        return total_out, matched

    if not team_a or not team_b:
        return {"tool": "get_trade_check", "ok": False,
                "error": "two teams needed"}
    out_a, names_a = salaries(team_a, players_a)
    out_b, names_b = salaries(team_b, players_b)
    pay_a, _ = _payroll(team_a)
    pay_b, _ = _payroll(team_b)
    over2 = lambda p: p > CAP["apron2"]
    issues = []
    if over2(pay_a) and len(names_a) > 1:
        issues.append(f"{team_a.upper()} cannot aggregate above second apron")
    if over2(pay_b) and len(names_b) > 1:
        issues.append(f"{team_b.upper()} cannot aggregate above second apron")
    ok_a = out_b <= (out_a if over2(pay_a) else out_a * 1.25 + 250_000)
    ok_b = out_a <= (out_b if over2(pay_b) else out_b * 1.25 + 250_000)
    if not ok_a:
        issues.append(f"{team_a.upper()} takes back too much")
    if not ok_b:
        issues.append(f"{team_b.upper()} takes back too much")
    return {"tool": "get_trade_check", "ok": True,
            "rows": {"team_a": {"team": team_a.upper(), "out": out_a,
                                "players": names_a, "payroll": pay_a},
                     "team_b": {"team": team_b.upper(), "out": out_b,
                                "players": names_b, "payroll": pay_b},
                     "legal": not issues, "issues": issues,
                     "disclaimer": "Rules simplified. Skips base-year, trade-kicker, "
                     "cash, minimum-salary, Stepien, pick, exception, and "
                     "sign-and-trade rules. Confirm with a cap specialist."},
            "meta": {"source": _payroll_source(), "rules": "v1-simplified"}}


@tool
def get_draft_board(season: str = "2025") -> dict[str, Any]:
    """Draft board: college production plus combine measurements, blended rank."""
    import unicodedata as _ud

    from ..sources import cbb as _cbb

    def norm(s: object) -> str:
        return "".join(c for c in _ud.normalize("NFKD", str(s or ""))
                       if not _ud.combining(c)).lower().strip()

    prod = _cbb.get_player_stats(2025 if season == "2025" else int(season))
    if not prod.ok or prod.frame.height == 0:
        return {"tool": "get_draft_board", "ok": False,
                "error": prod.error or "college stats empty"}
    rows, meta = _warehouse_or_live(
        "silver_combine", "_season = ?",
        [season], lambda: nba_stats.combine(season), season,
    )
    meas = {norm(r.get("PLAYER_NAME")): r for r in rows}
    board = []
    for p in prod.frame.to_dicts():
        m = meas.get(norm(p.get("PLAYER_NAME")), {})
        try:
            score = (float(p.get("PTS") or 0) * 2
                     + float(p.get("TS_PCT") or 0) * 50
                     + float(p.get("USG") or 0))
        except (TypeError, ValueError):
            continue
        board.append({"PLAYER": p.get("PLAYER_NAME"), "TEAM": p.get("TEAM"),
                      "PTS": p.get("PTS"), "TS_PCT": p.get("TS_PCT"),
                      "USG": p.get("USG"),
                      "HEIGHT": m.get("HEIGHT_WO_SHOES_FT_IN"),
                      "WINGSPAN": m.get("WINGSPAN_FT_IN"),
                      "SCORE": round(score, 1)})
    board.sort(key=lambda d: d["SCORE"], reverse=True)
    return {"tool": "get_draft_board", "ok": True, "rows": board[:30],
            "meta": {"source": "barttorvik+nba_api", "season": season,
                     "matched_measurements": sum(1 for b in board[:30]
                                                 if b["HEIGHT"]),
                     "formula": "2*PTS + 50*TS + USG"}}


@tool
def get_combine(season: str = "2025") -> dict[str, Any]:
    """Draft combine measurements plus shooting drills for one draft year."""
    res = nba_stats.combine(season)
    if not res.ok or res.frame.height == 0:
        return {"tool": "get_combine", "ok": False,
                "error": res.error or "empty upstream response"}
    return {"tool": "get_combine", "ok": True,
            "rows": res.frame.head(25).to_dicts(),
            "meta": {"source": res.meta.source, "fetched_at": res.meta.fetched_at,
                     "rows": res.frame.height, "cached": False}}


@tool
def get_briefing(game_date: str = "", season: str = SEASON) -> dict[str, Any]:
    """Morning briefing: scoreboard plus top scorers. Date MM/DD/YYYY, blank means latest."""
    from datetime import datetime, timedelta

    day = game_date.strip()
    if not day:
        day = (datetime.now() - timedelta(days=1)).strftime("%m/%d/%Y")
    games, gmeta = _warehouse_or_live(
        "silver_scoreboard", "_season = ? AND _entity = ?",
        [season, f"date:{day}"],
        lambda: nba_stats.scoreboard(day, season), season,
        entity=f"date:{day}", live_first=True,
    )
    leaders, _ = _warehouse_or_live(
        "silver_leaders_pts", "_season = ?",
        [season], lambda: nba_stats.leaders("PTS", season), season,
    )
    top = [
        {"PLAYER": r.get("PLAYER"), "TEAM": r.get("TEAM"), "PTS": r.get("PTS")}
        for r in leaders[:5]
    ]
    return {"tool": "get_briefing", "ok": True,
            "rows": {"date": day, "games": games, "top_scorers": top},
            "meta": gmeta}


@tool
async def text_to_sql(question: str) -> dict[str, Any]:
    """Answer a data question with SQL over warehouse tables. SELECT only."""
    import re as _re

    from langchain_core.messages import HumanMessage, SystemMessage

    from .. import store as _store
    from ..providers import invoke_with_fallback

    allowed = ["silver_standings", "silver_playoffs", "silver_team_ratings",
               "silver_clutch", "silver_player_gamelogs", "silver_team_games",
               "silver_leaders_pts", "silver_leaders_reb", "silver_leaders_ast",
               "silver_leaders_stl", "silver_leaders_blk", "silver_boxscores",
               "silver_lineups", "silver_shots", "silver_hustle_player",
                "silver_hustle_team", "silver_injuries", "silver_hist_gamelogs",
                "silver_hist_standings", "silver_hist_possessions",
                "silver_hist_shots", "silver_hist_lineups", "silver_salaries"]
    con = _store.connect()
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        present = [t for t in allowed if t in tables]
        cols: dict[str, list[str]] = {}
        for t in present:
            cols[t] = [r[1] for r in
                       con.execute(f"PRAGMA table_info({t})").fetchall()][:20]
    finally:
        con.close()
    if not present:
        return {"tool": "text_to_sql", "ok": False, "error": "warehouse empty"}
    schema = "\n".join(f"{t}: {', '.join(c)}" for t, c in cols.items())
    examples = (
        "\nExamples.\nQ: Thunder record this season?\n"
        "SQL: SELECT WINS, LOSSES FROM silver_standings "
        "WHERE TeamCity = 'Oklahoma City' AND _season = '2025-26'\n"
        "Q: OKC wins per season, last 3 seasons?\n"
        "SQL: SELECT _season, SUM(CASE WHEN wl = 'W' THEN 1 ELSE 0 END) AS wins "
        "FROM silver_hist_gamelogs WHERE team_abbreviation = 'OKC' "
        "AND _season IN ('2025-26', '2024-25', '2023-24') GROUP BY _season\n"
        "Q: Which 5 teams have the highest total payroll?\n"
        "SQL: SELECT TEAM, SUM(SALARY_2025_26) AS payroll FROM silver_salaries "
        "GROUP BY TEAM ORDER BY payroll DESC LIMIT 5\n"
        "Q: Who has the best clutch FG% with at least 10 GP?\n"
        "SQL: SELECT PLAYER_NAME, FG_PCT FROM silver_clutch "
        "WHERE GP >= 10 ORDER BY FG_PCT DESC LIMIT 5\n"
        "Q: Which top-10 net-rating team plays fastest?\n"
        "SQL: SELECT TEAM_NAME, PACE, NET_RATING FROM silver_team_ratings "
        "WHERE NET_RATING_RANK <= 10 ORDER BY PACE DESC LIMIT 1\n"
        "Q: Who has the most playoff wins in 2025-26?\n"
        "SQL: SELECT TEAM_ABBREVIATION, COUNT(*) AS wins FROM silver_playoffs "
        "WHERE WL = 'W' GROUP BY TEAM_ABBREVIATION ORDER BY wins DESC LIMIT 5"
    )
    feedback = ""
    for _ in range(3):
        try:
            resp = await invoke_with_fallback(
                "mistral", "ministral-8b-2512",
                [SystemMessage(content="Reply with SQL only, no prose."),
                 HumanMessage(
                     content="Write one SQLite SELECT using only these tables "
                     "and columns. Match column case exactly as listed.\n"
                     f"Schema:\n{schema}{examples}\nQuestion: {question}{feedback}")])
            sql = _re.sub(r"^```sql|```$", "", str(getattr(resp, "content", "") or ""),
                          flags=_re.MULTILINE).strip()
        except Exception as exc:
            return {"tool": "text_to_sql", "ok": False, "error": str(exc)[:160]}
        if not _re.match(r"(?i)^\s*select\b", sql) or _re.search(
                r"(?i)\b(insert|update|delete|drop|alter|create|pragma|attach|copy)\b", sql):
            feedback = "\nPrevious reply was not a single SELECT. Reply with SQL only."
            continue
        used = set(_re.findall(r"(?i)from\s+(\w+)|join\s+(\w+)", sql))
        used_tables = {a or b for a, b in used}
        if not used_tables or not used_tables.issubset(set(present)):
            feedback = "\nPrevious reply used unknown tables. Use only listed tables."
            continue
        con = _store.connect()
        try:
            rows = con.execute(sql).fetchall()
            names = [d[0] for d in con.description]
        except Exception as exc:
            feedback = f"\nPrevious SQL failed: {str(exc)[:200]} Fix it."
            continue
        finally:
            con.close()
        if not rows:
            feedback = (
                "\nPrevious SQL ran but returned 0 rows. "
                "A literal value is probably wrong. Query again with "
                "different literals or look at the table first "
                "(SELECT DISTINCT col FROM table LIMIT 20)."
            )
            continue
        return {"tool": "text_to_sql", "ok": True,
                "rows": [dict(zip(names, r)) for r in rows[:25]],
                "meta": {"sql": sql[:500], "source": "warehouse"}}
    return {"tool": "text_to_sql", "ok": False,
            "error": "sql failed after retries" + feedback[-160:]}


@tool
def get_elo(season: str = SEASON) -> dict[str, Any]:
    """ELO power ratings from warehouse game results for one season."""
    from .. import store as _store

    con = _store.connect()
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
        (ta, _, _, ma, wa, pma), (tb, _, _, mb, wb, pmb) = pair
        if (wa == "W") == (wb == "W"):
            continue
        wrow, lrow = (pair[0], pair[1]) if wa == "W" else (pair[1], pair[0])
        wteam, lteam = wrow[0], lrow[0]
        margin = wrow[5]
        if margin is None:
            margin = -(lrow[5]) if lrow[5] is not None else None
        mov_mult = 1.0
        if margin is not None:
            margin = abs(margin)
            mov_ok = True
        elo.setdefault(wteam, 1500.0)
        elo.setdefault(lteam, 1500.0)
        wins[wteam] = wins.get(wteam, 0) + 1
        losses[lteam] = losses.get(lteam, 0) + 1
        w_home = "vs." in str(wrow[3])
        l_home = "vs." in str(lrow[3])
        w_adj = elo[wteam] + (100 if w_home else 0)
        l_adj = elo[lteam] + (100 if l_home else 0)
        diff = w_adj - l_adj
        expected_w = 1 / (1 + 10 ** (-diff / 400))
        if margin is not None:
            mov_mult = ((margin + 3) ** 0.8) / (7.5 + 0.006 * abs(diff))
        shift = 20 * mov_mult * (1 - expected_w)
        elo[wteam] += shift
        elo[lteam] -= shift
    table = sorted(
        ({"TEAM": t, "ELO": round(v), "W": wins.get(t, 0),
          "L": losses.get(t, 0)} for t, v in elo.items()),
        key=lambda d: d["ELO"], reverse=True,
    )
    return {"tool": "get_elo", "ok": True, "rows": table,
            "meta": {"source": "warehouse", "mov": mov_ok, "season": season}}


@tool
def get_playoff_sim(season: str = SEASON, sims: int = 2000) -> dict[str, Any]:
    """Simulated title and finals odds from ratings, Monte Carlo brackets."""
    from .sim import run_playoff_sim

    try:
        sims = max(100, min(int(sims or 2000), 10000))
    except (TypeError, ValueError):
        sims = 2000
    out = run_playoff_sim(season, sims)
    if not out.get("teams"):
        return {"tool": "get_playoff_sim", "ok": False,
                "error": out.get("meta", {}).get("error", "no field")}
    return {"tool": "get_playoff_sim", "ok": True, "rows": out,
            "meta": {**out.get("meta", {}), "season": season, "sims": sims}}


@tool
def get_contract_value(season: str = "2025-26", min_gp: int = 20) -> dict[str, Any]:
    """Contract value residuals: 2026-27 salary vs OLS prediction from per-game production. Ten most overpaid plus ten most underpaid."""
    import unicodedata as _ud

    from .. import store as _store

    season = str(season or "2025-26").strip() or "2025-26"
    try:
        min_gp = max(0, min(int(min_gp), 82))
    except (TypeError, ValueError):
        min_gp = 20

    weights = {"PTS": 1.0, "REB": 1.2, "AST": 1.5,
               "STL": 2.0, "BLK": 2.0, "TOV": -1.5}

    def _norm(s: object) -> str:
        return "".join(
            c for c in _ud.normalize("NFKD", str(s or ""))
            if not _ud.combining(c)
        ).strip().lower()

    con = _store.connect()
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        if "silver_cap_players" not in tables or "silver_leaders_pts" not in tables:
            return {"tool": "get_contract_value", "ok": False,
                    "error": "warehouse empty"}
        have = {r[1] for r in
                con.execute("PRAGMA table_info(silver_leaders_pts)").fetchall()}
        prod = con.execute(
            """SELECT PLAYER, TEAM, GP, PTS, REB, AST, STL, BLK, TOV
            FROM silver_leaders_pts WHERE _season = ?""",
            [season],
        ).fetchall()
        cap = con.execute(
            "SELECT player, team, salary FROM silver_cap_players"
        ).fetchall()
        try:
            prod_date = con.execute(
                "SELECT MAX(_fetched_at) FROM silver_leaders_pts").fetchall()[0][0]
            cap_date = con.execute(
                "SELECT MAX(_fetched_at) FROM silver_cap_players").fetchall()[0][0]
        except Exception:
            prod_date = cap_date = None
    finally:
        con.close()
    if not prod:
        return {"tool": "get_contract_value", "ok": False,
                "error": f"no production rows for {season}"}
    missing = [c for c in weights if c not in have]
    use_w = {c: (0.0 if c in missing else w) for c, w in weights.items()}
    by_name: dict[str, tuple] = {}
    for r in prod:
        by_name.setdefault(_norm(r[0]), r)
    fitted = []
    for player, team, salary in cap:
        r = by_name.get(_norm(player))
        if r is None:
            continue
        _, lteam, gp, pts, reb, ast, stl, blk, tov = r
        gp = gp or 0
        if gp < min_gp or gp <= 0:
            continue
        vals = {"PTS": pts or 0, "REB": reb or 0, "AST": ast or 0,
                "STL": stl or 0, "BLK": blk or 0, "TOV": tov or 0}
        score = sum(vals[c] / gp * use_w[c] for c in use_w)
        fitted.append({"PLAYER": player, "TEAM": team or lteam,
                       "SALARY": salary or 0, "GP": gp, "SCORE": score})
    n = len(fitted)
    if n < 2:
        return {"tool": "get_contract_value", "ok": False,
                "error": "not enough qualified players"}
    mx = sum(f["SCORE"] for f in fitted) / n
    my = sum(f["SALARY"] for f in fitted) / n
    var = sum((f["SCORE"] - mx) ** 2 for f in fitted)
    if var <= 0:
        return {"tool": "get_contract_value", "ok": False,
                "error": "no production variance"}
    cov = sum((f["SCORE"] - mx) * (f["SALARY"] - my) for f in fitted)
    slope = cov / var
    intercept = my - slope * mx
    for f in fitted:
        f["PREDICTED"] = int(round(slope * f["SCORE"] + intercept))
        f["RESIDUAL"] = int(f["SALARY"]) - int(f["PREDICTED"])
        f["SCORE"] = round(f["SCORE"], 2)
    over = sorted(fitted, key=lambda f: f["RESIDUAL"], reverse=True)[:10]
    under = sorted(fitted, key=lambda f: f["RESIDUAL"])[:10]
    rows = over + under
    formula = ("score = PTS + 1.2*REB + 1.5*AST + 2*STL + 2*BLK - 1.5*TOV "
               "(per game); salary_hat = slope*score + intercept (OLS by hand); "
               "residual = salary - salary_hat")
    return {"tool": "get_contract_value", "ok": True, "rows": rows,
            "meta": {"formula": formula, "weights": weights,
                     "missing_columns_zero_weight": missing,
                     "slope": round(slope, 2), "intercept": round(intercept, 2),
                     "n_qualified": n, "min_gp": min_gp,
                     "production_season": season, "salary_season": "2026-27",
                     "production_date": prod_date, "salary_date": cap_date,
                     "overpaid_first": True}}


@tool
def get_draft_model(season: str = "2025") -> dict[str, Any]:
    """Star-probability classifier from college production (honest proxy)."""
    try:
        from ..sources import cbb as _cbb
        from sklearn.linear_model import LogisticRegression
        yr = 2025 if str(season) == "2025" else int(str(season))
        prod = _cbb.get_player_stats(yr)
        if not prod.ok or prod.frame.height == 0:
            return {"tool": "get_draft_model", "ok": False,
                    "error": prod.error or "college stats empty"}
        feats = ["PTS", "TS_PCT", "USG", "REB", "AST"]
        pls = [p for p in prod.frame.to_dicts()
               if all(p.get(k) is not None for k in feats)]
        if len(pls) < 50:
            return {"tool": "get_draft_model", "ok": False,
                    "error": "not enough rows"}
        scores = [float(p["PTS"]) * 2 + float(p["TS_PCT"]) * 50
                  + float(p["USG"]) for p in pls]
        cut = sorted(scores, reverse=True)[max(0, len(scores) // 10 - 1)]
        y = [1 if s >= cut else 0 for s in scores]
        mus = [sum(float(p[f]) for p in pls) / len(pls) for f in feats]
        sds = []
        for j, f in enumerate(feats):
            v = sum((float(p[f]) - mus[j]) ** 2 for p in pls) / len(pls)
            sds.append(v ** 0.5 or 1.0)
        X = [[(float(p[f]) - mus[j]) / sds[j] for j, f in enumerate(feats)]
             for p in pls]
        clf = LogisticRegression(max_iter=1000).fit(X, y)
        proba = [float(v) for v in clf.predict_proba(X)[:, 1]]
        acc = sum((pr >= 0.5) == bool(t) for pr, t in zip(proba, y)) / len(y)
        top = sorted(range(len(pls)), key=lambda i: proba[i], reverse=True)[:20]
        rows = [{"PLAYER": pls[i].get("PLAYER_NAME"), "TEAM": pls[i].get("TEAM"),
                 "PTS": pls[i].get("PTS"), "TS_PCT": pls[i].get("TS_PCT"),
                 "USG": pls[i].get("USG"), "STAR_P": round(proba[i], 3)}
                for i in top]
        meta = {"source": "barttorvik+sklearn", "season": str(season),
                "n": len(pls), "features": feats,
                "label": "top-decile of 2*PTS+50*TS+USG",
                "accuracy": round(acc, 3),
                "disclaimer": "Label is a production proxy, not real NBA "
                "outcomes. In-sample accuracy only, no cross-validation."}
        return {"tool": "get_draft_model", "ok": True, "rows": rows, "meta": meta}
    except Exception as exc:
        return {"tool": "get_draft_model", "ok": False,
                "error": str(exc)[:200]}
