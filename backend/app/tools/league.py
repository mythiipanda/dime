"""League desk. Standings, leaders, hustle, ratings, history, draft."""

from typing import Any
from langchain_core.tools import tool

from ..sources import nba_stats
from ._core import SEASON, TTL_LEADERS, TTL_SCOREBOARD_PAST, clamp_stat, _warehouse_or_live, is_past_game_date


@tool
def get_injuries(team: str = "", player: str = "",
                 season: str = SEASON) -> dict[str, Any]:
    """Injury report, optional team abbreviation or player filter.

    With a player name, also joins playoff inactive listings so
    'is X injured?' surfaces 'inactive for the entire playoff run'
    instead of a bare 'active' (F45)."""
    from ..sources import espn

    rows, meta = _warehouse_or_live(
        "silver_injuries", "_season = ?",
        [season], lambda: espn.injuries(season), season,
    )
    note = None
    if player:
        try:
            from ._core import coerce_player_id
            from .gamelog import playoff_inactive_note as _pin
            from .splits import _resolve_name as _rn

            pid = coerce_player_id(player)
            note = _pin(pid, season, _rn(pid, str(player)))
        except Exception:
            note = None
        low = str(player).strip().lower()
        rows = [r for r in rows
                if low in str(r.get("player") or r.get("name")
                                or "").lower()]
    if team:
        from nba_api.stats.static import teams as _teams

        want = team.strip().upper()
        full = next(
            (t["full_name"] for t in _teams.get_teams()
             if t["abbreviation"] == want or t["full_name"].upper() == want),
            want,
        )
        rows = [r for r in rows if full.lower() in str(r.get("display_name", "")).lower()]
    out = {"tool": "get_injuries", "ok": True, "rows": rows, "meta": meta}
    if player and not rows:
        out["player_note"] = (
            f"{player} is NOT on the current injury report. Report that "
            "directly; an empty list for a named player is an answer, "
            "never 'no data'.")
    if note:
        out.setdefault("rows")
        out["inactive_note"] = note
    return out


_STANDINGS_KEEP = ("TeamID", "team", "abbrev", "Conference", "WINS",
                   "LOSSES", "WinPCT", "Record", "PlayoffRank",
                   "LeagueRank", "L10", "HOME", "ROAD", "PointsPG",
                   "OppPointsPG", "DiffPointsPG", "CurrentStreak")


def _slim_standings(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Compact standing rows.

    QA #40: the raw 70-column row set overran the 12k-char evidence
    window after ~8 teams, so the LLM truthfully reported 'Lakers not
    in the evidence' while the card below rendered the full table.
    Slim rows keep all 30 teams inside the window, and team/abbrev
    give the narrative the full-name tokens it grounds on.
    """
    from nba_api.stats.static import teams as _static

    abbr_by_id = {t.get("id"): str(t.get("abbreviation") or "")
                  for t in _static.get_teams()}
    out = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        tid = r.get("TeamID")
        full = f"{r.get('TeamCity') or ''} {r.get('TeamName') or ''}".strip()
        slim = {k: r.get(k) for k in _STANDINGS_KEEP
                if k in r and k not in ("team", "abbrev")}
        slim["team"] = full
        slim["abbrev"] = abbr_by_id.get(tid, "")
        out.append(slim)
    return out


@tool
def get_standings(season: str = SEASON) -> dict[str, Any]:
    """League standings for one season like 2025-26."""
    rows, meta = _warehouse_or_live(
        "silver_standings", "_season = ?",
        [season], lambda: nba_stats.standings(season), season,
        limit=30,
    )
    return {"tool": "get_standings", "ok": True,
            "rows": _slim_standings(rows), "meta": meta}


@tool
def get_standings_deep(season: str = SEASON, top: int = 5) -> dict[str, Any]:
    """Standings deep cuts: clutch records, comeback kings, blown leads, monthly momentum."""
    from .. import store as _store

    season = str(season or SEASON).strip() or SEASON
    try:
        top = max(1, min(int(top or 5), 15))
    except (TypeError, ValueError):
        top = 5

    def _split(rec: object) -> tuple[int, int] | None:
        try:
            w, loss = str(rec or "").strip().split("-")
            return int(w), int(loss)
        except (TypeError, ValueError):
            return None

    def _pct(w: int, loss: int) -> float:
        return round(w / (w + loss), 3) if w + loss else 0.0

    con = _store.connect()
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        if "silver_standings" not in tables:
            return {"tool": "get_standings_deep", "ok": False,
                    "error": "standings empty"}
        rows = con.execute(
            """SELECT TeamCity, TeamName, WinPCT,
            "ThreePTSOrLess", "AheadAtHalf", "BehindAtHalf",
            "L10", "strCurrentStreak",
            "Oct", "Nov", "Dec", "Jan", "Feb", "Mar", "Apr"
            FROM silver_standings WHERE _season = ?""",
            [season],
        ).fetchall()
    finally:
        con.close()
    if not rows:
        return {"tool": "get_standings_deep", "ok": False,
                "error": f"no standings for {season}"}
    teams = []
    for city, name, winpct, clutch, ahead, behind, l10, streak, *months in rows:
        label = f"{city or ''} {name or ''}".strip()
        teams.append({
            "TEAM": label,
            "SEASON_PCT": round(float(winpct or 0), 3),
            "clutch": _split(clutch),
            "ahead": _split(ahead),
            "behind": _split(behind),
            "L10": l10,
            "STREAK": streak,
            "months": months,
        })
    clutch_rank = sorted(
        ({"TEAM": t["TEAM"], "W": t["clutch"][0], "L": t["clutch"][1],
          "PCT": _pct(*t["clutch"]), "RECORD": f"{t['clutch'][0]}-{t['clutch'][1]}"}
         for t in teams if t["clutch"]),
        key=lambda d: (d["PCT"], d["W"]), reverse=True,
    )
    comeback = sorted(
        ({"TEAM": t["TEAM"], "W": t["behind"][0], "L": t["behind"][1],
          "PCT": _pct(*t["behind"])}
         for t in teams if t["behind"]),
        key=lambda d: (d["W"], d["PCT"]), reverse=True,
    )[:top]
    blown = sorted(
        ({"TEAM": t["TEAM"], "W": t["ahead"][0], "L": t["ahead"][1],
          "PCT": _pct(*t["ahead"])}
         for t in teams if t["ahead"]),
        key=lambda d: d["L"], reverse=True,
    )[:top]
    month_names = ["Oct", "Nov", "Dec", "Jan", "Feb", "Mar", "Apr"]
    by_month = []
    for i, month in enumerate(month_names):
        entries = []
        for t in teams:
            parsed = _split(t["months"][i])
            if parsed and parsed[0] + parsed[1] >= 3:
                entries.append((t["TEAM"], parsed[0], parsed[1],
                                _pct(*parsed)))
        if not entries:
            continue
        best = max(entries, key=lambda e: (e[3], e[1]))
        worst = min(entries, key=lambda e: (e[3], -e[1]))
        by_month.append({"MONTH": month,
                         "BEST_TEAM": best[0],
                         "BEST_RECORD": f"{best[1]}-{best[2]}",
                         "BEST_PCT": best[3],
                         "WORST_TEAM": worst[0],
                         "WORST_RECORD": f"{worst[1]}-{worst[2]}",
                         "WORST_PCT": worst[3]})
    momentum = []
    for t in teams:
        mar = _split(t["months"][5])
        apr = _split(t["months"][6])
        lw = (mar[0] if mar else 0) + (apr[0] if apr else 0)
        ll = (mar[1] if mar else 0) + (apr[1] if apr else 0)
        if lw + ll < 5:
            continue
        late = _pct(lw, ll)
        momentum.append({"TEAM": t["TEAM"], "LATE": f"{lw}-{ll}",
                         "LATE_PCT": late, "SEASON_PCT": t["SEASON_PCT"],
                         "DELTA": round(late - t["SEASON_PCT"], 3),
                         "L10": t["L10"], "STREAK": t["STREAK"]})
    momentum.sort(key=lambda d: d["DELTA"], reverse=True)
    return {"tool": "get_standings_deep", "ok": True,
            "rows": {"clutch": clutch_rank[:top],
                     "clutch_cold": clutch_rank[-top:][::-1],
                     "comeback_kings": comeback,
                     "blown_leads": blown,
                     "monthly": {"by_month": by_month,
                                 "surging": momentum[:top],
                                 "fading": momentum[-top:][::-1]}},
            "meta": {"source": "warehouse", "season": season, "top": top,
                     "teams": len(teams)}}


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
    rows_out: dict[str, Any] = {"champion": champ,
            "champion_record":
                {"w": wins.get(champ, 0), "l": losses.get(champ, 0)}
                if champ else {},
            "wins": [{"team": t, "w": w, "l": losses.get(t, 0)}
                     for t, w in table[:16]],
            "games_total": games // 2}
    from ._core import season_static as _season_static
    if _season_static(season):
        # QA F36: subagent paths answer "simulate the playoffs" from
        # get_playoffs directly and the model framed these actuals as
        # simulation output. Label them AT THE SOURCE so every path is
        # honest: these are final results, not a Monte Carlo run.
        rows_out["result_kind"] = "ACTUAL_RESULTS_NOT_SIMULATION"
        rows_out["summary"] = (
            f"These are the ACTUAL final {season} playoff results"
            + (f" ({champ} champions)" if champ else "")
            + ", recorded games - not a simulation or prediction. "
              "If the ask was to simulate, say simulated odds are "
              "unavailable for a completed season.")
    return {"tool": "get_playoffs", "ok": True,
            "rows": rows_out,
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
        total = int(meta.get("rows") or len(rows) or 0)
        for r in rows:
            rank = r.get("RANK") or 0
            if rank and total:
                r["PERCENTILE"] = round(100 * (1 - (rank - 1) / total), 1)
    except Exception:
        pass
    # Pin the asked-for stat column right after the identity columns so
    # capped table renderers (12-column cap) can never cut it (QA F8:
    # the AST leaders table rendered without an AST column).
    # QA #30 nit: leaders tables carried every raw column (FGM/FGA on an
    # AST leaderboard). Keep identity + the asked stat + context only.
    pin = ["RANK", "PLAYER", "TEAM", stat_category, "GP", "MIN",
           "PERCENTILE"]
    pinned = []
    for r in rows:
        if not isinstance(r, dict):
            pinned.append(r)
            continue
        pinned.append({k: r[k] for k in pin if k in r})
    return {"tool": "get_leaders", "ok": True, "rows": pinned, "meta": meta}


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
    _rmeta: dict[str, Any] = {"source": "warehouse", "season": season}
    from ._core import season_static as _season_static
    if _season_static(season):
        # QA F17: in the offseason there are no upcoming back-to-backs;
        # these are FINAL 2025-26 splits, and the next games are preseason.
        _rmeta["offseason"] = True
        _rmeta["note"] = (f"{season} is complete; these are final "
                          "splits. No NBA games until preseason, so no "
                          "upcoming back-to-backs exist right now.")
    return {"tool": "get_rest", "ok": True,
            "rows": {"back_to_back": f"{b2b_w}-{b2b_l}",
                     "three_plus_rest": f"{rest_w}-{rest_l}"},
            "meta": _rmeta}


"""Shared ELO engine. get_win_prob and get_elo build ratings from the same
helpers so the two never drift. Build adds ELO_HCA_BUILD to each side's
rating at game time; pre-game prediction uses ELO_HCA_PREDICT instead."""

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
        (ta, _, _, ma, wa, pma), (tb, _, _, mb, wb, pmb) = pair
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


@tool
def get_win_prob(team_a: str = "", team_b: str = "", season: str = SEASON,
                 home_abbrev: str = "") -> dict[str, Any]:
    """Real ELO win probability between two abbreviations. Neutral unless home_abbrev matches a side."""
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


CAP = {"cap": 165_000_000, "tax": 201_048_000,
       "apron1": 209_661_000, "apron2": 222_372_000}


def _current_team_for_player(
    player_name: str, player_id: object = None, fallback: str = "",
    con: object = None,
) -> str:
    """Current-season team for one player, else fallback.

    Prefers silver_leaders_pts TEAM for SEASON, then the most recent
    silver_player_gamelogs MATCHUP, then the salary-sheet TEAM.
    Pass con to reuse the caller's connection (latency); otherwise opens
    and closes its own.
    """
    from .. import store as _store

    name = str(player_name or "").strip()
    own = con is None
    try:
        if own:
            con = _store.connect()
    except Exception:
        return fallback
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        from ._core import season_static as _season_static
        if _season_static(SEASON) and name and "silver_salaries" in tables:
            # Offseason: the 2026-27 contracts sheet is fresher than the
            # final 2025-26 leaders table (LeBron played 2025-26 on LAL
            # but signed with PHI for 2026-27 - QA #30 evidence dive).
            # Trades in September must price him as a 76er.
            try:
                row = con.execute(
                    "SELECT TEAM FROM silver_salaries "
                    "WHERE LOWER(PLAYER_NAME) = LOWER(?) LIMIT 1",
                    [name],
                ).fetchone()
                if row and row[0]:
                    return str(row[0])
            except Exception:
                pass
        if name and "silver_leaders_pts" in tables:
            try:
                row = con.execute(
                    "SELECT TEAM FROM silver_leaders_pts "
                    "WHERE _season = ? AND LOWER(PLAYER) = LOWER(?) LIMIT 1",
                    [SEASON, name],
                ).fetchone()
                if row and row[0]:
                    return str(row[0])
            except Exception:
                pass
        pid: object = player_id
        if pid is None and name and "silver_leaders_pts" in tables:
            try:
                found = con.execute(
                    "SELECT PLAYER_ID FROM silver_leaders_pts "
                    "WHERE LOWER(PLAYER) = LOWER(?) LIMIT 1",
                    [name],
                ).fetchone()
                if found and found[0] is not None:
                    pid = int(found[0])
            except Exception:
                pid = None
        if pid is not None and "silver_player_gamelogs" in tables:
            try:
                for where, params in (
                    ("Player_ID = ? AND _season = ?", [pid, SEASON]),
                    ("Player_ID = ?", [pid]),
                ):
                    try:
                        grow = con.execute(
                            f"SELECT MATCHUP FROM silver_player_gamelogs "
                            f"WHERE {where} LIMIT 1",
                            params,
                        ).fetchone()
                    except Exception:
                        grow = None
                    if grow and grow[0]:
                        abbr = str(grow[0]).split()[0].upper()
                        if abbr:
                            return abbr
                    if grow:
                        break
            except Exception:
                pass
    finally:
        if own:
            try:
                con.close()
            except Exception:
                pass
    return fallback


def _first_name_compatible(want: str, cand: str) -> bool:
    """Trade-match first-name guard.

    QA #32: ratio>=0.8 lets 'lebron' pass as 'bronny' (0.83) - the son
    surfaces as a suggestion for the father. Accept equal first names,
    prefix nicknames of length >= 4 ('steph'/'stephen'), or ratio >= 0.9
    ('jayson'/'jason' 0.91, 'stephan'/'stephen' 0.93); 0.83 now fails.
    """
    import difflib as _dl

    a = (want or "").lower().strip()
    b = (cand or "").lower().strip()
    if not a or not b:
        return False
    if a == b:
        return True
    if len(a) >= 4 and b.startswith(a):
        return True
    if len(b) >= 4 and a.startswith(b):
        return True
    return _dl.SequenceMatcher(None, a, b).ratio() >= 0.9


def _resolve_stale_trade_player(want: str, team: str,
                                con: object = None) -> tuple[str, int] | None:
    """Salary-sheet row for want whose current team is team, else None."""
    import difflib as _dl

    from .. import store as _store

    target = str(team or "").upper()
    w = str(want or "").strip()
    if not w or not target:
        return None
    own = con is None
    try:
        if own:
            con = _store.connect()
    except Exception:
        return None
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        if "silver_salaries" not in tables:
            return None
        try:
            rows = con.execute(
                "SELECT PLAYER_NAME, SALARY_2025_26, TEAM FROM silver_salaries"
            ).fetchall()
        except Exception:
            return None
    finally:
        if own:
            try:
                con.close()
            except Exception:
                pass
    wl = w.lower()
    exact = [r for r in rows if str(r[0]).lower() == wl]
    subs = [r for r in rows if wl in str(r[0]).lower() and r not in exact]
    lows = [str(r[0]).lower() for r in rows]
    fuzzy: list = []
    try:
        for m in _dl.get_close_matches(wl, lows, n=3, cutoff=0.8):
            for r in rows:
                if str(r[0]).lower() == m and r not in exact and r not in subs:
                    fuzzy.append(r)
    except Exception:
        fuzzy = []
    wl_first = wl.split()[0] if wl.split() else ""
    for i, cand in enumerate(exact + subs + fuzzy):
        cname, csal, cteam = str(cand[0]), cand[1] or 0, str(cand[2] or "")
        # Fuzzy candidates must also match on first name - otherwise
        # "LeBron James" silently prices as "Bronny James" (father/son
        # share the surname; seen live on the LAL trade-check path).
        if i >= len(exact) + len(subs):
            c_first = cname.lower().split()[0] if cname.split() else ""
            if not _first_name_compatible(wl_first, c_first):
                continue
        try:
            cur = _current_team_for_player(cname, None, cteam, con)
        except Exception:
            cur = cteam
        if str(cur).upper() == target:
            return cname, int(csal)
    return None


def _locate_player_team(name: str, con: object) -> tuple[str, str, int] | None:
    """(PLAYER_NAME, current TEAM, salary) for name, any team.

    QA #32: when the caller's team attribution is stale ('LAL: LeBron
    James'), locate the real team so the trade check can re-attribute
    instead of erroring. Same first-name guard as the trade matchers.
    """
    import difflib as _dl

    w = str(name or "").strip().lower()
    if not w:
        return None
    try:
        rows = con.execute(
            "SELECT PLAYER_NAME, SALARY_2025_26, TEAM FROM silver_salaries"
        ).fetchall()
    except Exception:
        return None
    exact = [r for r in rows if str(r[0]).lower() == w]
    subs = [r for r in rows if w in str(r[0]).lower() and r not in exact]
    lows = [str(r[0]).lower() for r in rows]
    fuzzy: list = []
    wf = w.split()[0] if w.split() else ""
    for m in _dl.get_close_matches(w, lows, n=3, cutoff=0.8):
        for r in rows:
            if str(r[0]).lower() == m and r not in exact and r not in subs:
                cf = str(r[0]).lower().split()[0]
                if _first_name_compatible(wf, cf):
                    fuzzy.append(r)
    for cand in (exact + subs + fuzzy)[:1]:
        cname, csal, cteam = str(cand[0]), int(cand[1] or 0), str(cand[2] or "")
        try:
            cur = _current_team_for_player(cname, None, cteam, con)
        except Exception:
            cur = cteam
        return cname, str(cur or cteam).upper(), csal
    return None


def _norm_trade_teams(team_a: str, team_b: str) -> tuple[str, str] | None:
    """Resolve abbrev/city/nickname to canonical abbreviations.

    F47: 'LAL' vs 'LAKERS' graded as two franchises with an empty side.
    Returns None when both sides resolve to the same team.
    """
    from .competitive import _resolve_team_abbr

    a = _resolve_team_abbr(team_a) or str(team_a or "").strip().upper()
    b = _resolve_team_abbr(team_b) or str(team_b or "").strip().upper()
    if a and b and a == b:
        return None
    return a, b


def _auto_correct_side(unks: list[str], old_team: str, plist: str,
                       con: object):
    """Re-attribute a side whose players are unknown on old_team.

    Returns (new_team, (out, names, unk), corrections) when every
    unknown on the side locates to one other team on the salary sheet,
    else None. QA #32: 'LAL: LeBron James' -> priced as PHI-LeBron.
    """
    located = []
    for u in unks:
        base = u.split(" (suggestions")[0].strip()
        hit = _locate_player_team(base, con)
        if hit is None:
            return None
        located.append((base,) + hit)
    new_teams = {t for _, _, t, _ in located}
    if len(new_teams) != 1:
        return None
    new_team = new_teams.pop()
    if new_team == str(old_team).upper():
        return None
    matched = _match_trade_players(new_team, plist, con)
    corrections = [
        f"{cname} is on {t} per the 2026-27 salary sheet "
        f"(not {str(old_team).upper()}); computed for the corrected team"
        for base, cname, t, _s in located
    ]
    return new_team, matched, corrections


def _payroll(team: str, con: object = None) -> tuple[int, list[dict]]:
    from .. import store as _store

    own = con is None
    if own:
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
        if own:
            con.close()
    players = [{"player": r[0], "salary": r[1]} for r in rows]
    return sum(r[1] or 0 for r in rows), players


def _apron_state(payroll: int) -> dict[str, object]:
    return {
        "over_tax": payroll > CAP["tax"],
        "over_apron1": payroll > CAP["apron1"],
        "over_apron2": payroll > CAP["apron2"],
        "room_apron1": CAP["apron1"] - payroll,
        "room_apron2": CAP["apron2"] - payroll,
    }


def _allowed_incoming(outgoing: int, over_apron1: bool) -> tuple[int, str]:
    if over_apron1:
        return outgoing, "100pct above first apron"
    return int(outgoing * 1.25 + 250_000), "125pct plus 250k below first apron"


def _salary_vintage(con: object = None) -> tuple[str, int, str | None]:
    """Stored salary vintage: (season, rows, fetched_at) from silver_salaries."""
    from .. import store as _store

    own = con is None
    if own:
        con = _store.connect()
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        if "silver_salaries" not in tables:
            return "", 0, None
        row = con.execute(
            "SELECT _season, COUNT(*), MAX(_fetched_at) FROM silver_salaries "
            "GROUP BY _season ORDER BY COUNT(*) DESC LIMIT 1"
        ).fetchone()
        if not row:
            return "", 0, None
        return str(row[0] or ""), int(row[1] or 0), row[2]
    except Exception:
        return "", 0, None
    finally:
        if own:
            con.close()


def _payroll_source(con: object = None) -> str:
    from .. import store as _store

    own = con is None
    if own:
        con = _store.connect()
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        if "silver_salaries" in tables:
            season, n, fetched = _salary_vintage(con)
            if n > 300 and season:
                date = f", fetched {str(fetched)[:10]}" if fetched else ""
                return (f"basketball-reference contracts "
                        f"({season} salaries{date}; "
                        f"some players missing or estimated)")
    finally:
        if own:
            con.close()
    return "orojas119/nba-salary-cap (estimated)"


def _salary_date(con: object = None) -> str | None:
    from .. import store as _store

    own = con is None
    if own:
        con = _store.connect()
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        for table in ("silver_salaries", "silver_cap_players"):
            if table not in tables:
                continue
            cols = [r[1] for r in con.execute(f"PRAGMA table_info({table})").fetchall()]
            if "_fetched_at" not in cols:
                continue
            row = con.execute(f"SELECT MAX(_fetched_at) FROM {table}").fetchone()
            if row and row[0]:
                return str(row[0])
    except Exception:
        return None
    finally:
        if own:
            con.close()
    return None


@tool
def get_cap_ledger(team: str = "") -> dict[str, Any]:
    """Payroll plus apron room for one abbreviation. 2026-27 thresholds."""
    if not team:
        return {"tool": "get_cap_ledger", "ok": False, "error": "abbreviation needed"}
    from .. import store as _store

    con = _store.connect()
    try:
        total, players = _payroll(team, con)
        source = _payroll_source(con)
        salary_date = _salary_date(con)
        season, _, _ = _salary_vintage(con)
    finally:
        con.close()
    return {"tool": "get_cap_ledger", "ok": True,
            "rows": {"team": team.upper(), "payroll": total,
                     "players": sorted(players, key=lambda p: p["salary"] or 0,
                                       reverse=True)[:15],
                     "room_under_apron2": CAP["apron2"] - total,
                     "over_tax": total > CAP["tax"]},
            "meta": {"source": source, "season": season or "2026-27",
                     "salary_date": salary_date,
                     **{k: v for k, v in CAP.items()}}}


def _match_trade_players(team: str, names: str,
                         con: object = None) -> tuple[int, list[str], list[str]]:
    """Match comma-separated names against team's payroll roster.

    Returns (salary_total, matched_display_names, unknown_entries).
    Pass con to reuse the caller's connection (latency); otherwise opens
    and closes its own.
    """
    import difflib as _dl

    from .. import store as _store

    own = con is None
    if own:
        con = _store.connect()
    try:
        total, roster = _payroll(team, con)
        want = [n.strip() for n in names.split(",") if n.strip()]
        lows = [p["player"].lower() for p in roster]
        by_low = {p["player"].lower(): p for p in roster}
        disp = {p["player"].lower(): p["player"] for p in roster}
        matched: list[str] = []
        unknown: list[str] = []
        total_out = 0
        for orig in want:
            w = orig.lower()
            hit = next((p for p in roster if w in p["player"].lower()), None)
            if hit is None:
                fb = _dl.get_close_matches(w, lows, n=1, cutoff=0.8)
                if fb and _first_name_compatible(
                        w.split()[0] if w.split() else "",
                        fb[0].split()[0] if fb[0].split() else ""):
                    hit = by_low[fb[0]]
            if hit:
                matched.append(hit["player"])
                total_out += hit["salary"] or 0
            else:
                stale = _resolve_stale_trade_player(orig, team, con)
                if stale:
                    matched.append(stale[0])
                    total_out += stale[1]
                else:
                    sug = [disp[s] for s in _dl.get_close_matches(w, lows, n=2, cutoff=0.6)
                           if _first_name_compatible(
                               w.split()[0] if w.split() else "",
                               s.split()[0] if s.split() else "")]
                    unknown.append(f"{orig} (suggestions: {', '.join(sug)})" if sug else orig)
    finally:
        if own:
            con.close()
    return total_out, matched, unknown


def _unknown_player_hints(unknown: list[str], con: object = None) -> list[str]:
    """'X is on BKN per salary data' hints for names missing from a roster.

    Lets the planner self-correct when its team attribution is stale
    (e.g. a player moved in the 2026 offseason).
    """
    hints: list[str] = []
    from .. import store as _store2

    own = con is None
    try:
        if own:
            con2 = _store2.connect()
        else:
            con2 = con
        try:
            for u in unknown:
                base = u.split(" (suggestions")[0].strip()
                bits = [b for b in base.split() if len(b) > 1]
                like = "%" + "%".join(bits[:2]) + "%" if bits else base
                hit = con2.execute(
                    """SELECT TEAM, PLAYER_NAME FROM silver_salaries
                    WHERE PLAYER_NAME LIKE ? LIMIT 1""",
                    [like],
                ).fetchone()
                if hit:
                    try:
                        cur = _current_team_for_player(
                            str(hit[1]), None, str(hit[0]), con2)
                    except Exception:
                        cur = hit[0]
                    hints.append(f"{base} is on {cur} per salary data")
        finally:
            if own:
                con2.close()
    except Exception:
        pass
    return hints


PICK_VALUE_M: dict[int, float] = {
    1: 45.0, 2: 38.0, 3: 32.0, 4: 28.0, 5: 25.0,
    6: 18.0, 7: 18.0, 8: 18.0, 9: 18.0, 10: 18.0,
    11: 12.0, 12: 12.0, 13: 12.0, 14: 12.0,
    15: 8.0, 16: 8.0, 17: 8.0, 18: 8.0, 19: 8.0, 20: 8.0,
    21: 5.0, 22: 5.0, 23: 5.0, 24: 5.0, 25: 5.0,
    26: 5.0, 27: 5.0, 28: 5.0, 29: 5.0, 30: 5.0,
}


def _pick_value_for_slot(slot: int, is_frp: bool) -> float:
    if is_frp:
        return PICK_VALUE_M.get(max(1, min(slot, 30)), 5.0)
    if 31 <= slot <= 40:
        return 2.5
    return 1.0


@tool
def get_trade_check(
    team_a: str = "", players_a: str = "", team_b: str = "", players_b: str = "",
) -> dict[str, Any]:
    """Trade legality check. Player names comma separated per side.

    Simplified 2023 CBA: 125 percent plus 250k matching below the first
    apron, 100 percent above it, no aggregation above the second apron.
    Picks and exceptions stay out of v1.
    """

    if not team_a or not team_b:
        return {"tool": "get_trade_check", "ok": False,
                "error": "two teams needed"}
    _norm = _norm_trade_teams(team_a, team_b)
    if _norm is None:
        return {"tool": "get_trade_check", "ok": False,
                "error": (f"both sides resolve to the same team "
                          f"({team_a} / {team_b}) - a trade needs two "
                          f"different teams; check the team names")}
    team_a, team_b = _norm
    from .. import store as _store

    con = _store.connect()
    try:
        out_a, names_a, unk_a = _match_trade_players(team_a, players_a, con)
        out_b, names_b, unk_b = _match_trade_players(team_b, players_b, con)
        corrections: list[str] = []
        if unk_a or unk_b:
            # QA #32: stale attribution is recoverable - locate each
            # unknown on the salary sheet and re-run the legality math
            # with the corrected team instead of returning a raw error.
            if unk_a:
                fix = _auto_correct_side(unk_a, team_a, players_a, con)
                if fix:
                    team_a, (out_a, names_a, unk_a), corr = fix
                    corrections.extend(corr)
            if unk_b:
                fix = _auto_correct_side(unk_b, team_b, players_b, con)
                if fix:
                    team_b, (out_b, names_b, unk_b), corr = fix
                    corrections.extend(corr)
        if unk_a or unk_b:
            parts = []
            if unk_a:
                parts.append(f"{team_a.upper()}: {'; '.join(unk_a)}")
            if unk_b:
                parts.append(f"{team_b.upper()}: {'; '.join(unk_b)}")
            hints = _unknown_player_hints(unk_a + unk_b, con)
            msg = "unknown players: " + " | ".join(parts)
            if hints:
                msg += ". " + "; ".join(hints)
            return {"tool": "get_trade_check", "ok": False, "error": msg}
        if not names_a or not names_b:
            # F47: never grade a ghost trade with an empty side.
            empty = team_a.upper() if not names_a else team_b.upper()
            return {"tool": "get_trade_check", "ok": False,
                    "error": (f"no players matched on the {empty} side - "
                              f"not grading a one-sided 'trade'. If you "
                              f"meant a past real-world trade, say which "
                              f"teams and players were in it.")}
        pay_a, _ = _payroll(team_a, con)
        pay_b, _ = _payroll(team_b, con)
        salary_date = _salary_date(con)
        source = _payroll_source(con)
    finally:
        con.close()
    state_a = _apron_state(pay_a)
    state_b = _apron_state(pay_b)
    allow_a, rule_a = _allowed_incoming(out_a, bool(state_a["over_apron1"]))
    allow_b, rule_b = _allowed_incoming(out_b, bool(state_b["over_apron1"]))
    issues = []
    if state_a["over_apron2"] and len(names_a) > 1:
        issues.append(f"{team_a.upper()} cannot aggregate above second apron")
    if state_b["over_apron2"] and len(names_b) > 1:
        issues.append(f"{team_b.upper()} cannot aggregate above second apron")
    ok_a = out_b <= allow_a
    ok_b = out_a <= allow_b
    if not ok_a:
        issues.append(f"{team_a.upper()} takes back too much")
    if not ok_b:
        issues.append(f"{team_b.upper()} takes back too much")
    checks = [
        {"rule": "salary matching", "checked": True,
         "note": f"{team_a.upper()} {rule_a}, {team_b.upper()} {rule_b}"},
        {"rule": "second apron aggregation ban", "checked": True,
         "note": "multi player out banned above second apron"},
        {"rule": "cash in trade", "checked": False, "note": "not modeled"},
        {"rule": "prior trade exceptions", "checked": False, "note": "not modeled"},
        {"rule": "taxpayer midlevel hard cap", "checked": False, "note": "not modeled"},
        {"rule": "frozen pick plus Stepien", "checked": False, "note": "not modeled"},
        {"rule": "base-year plus trade-kicker plus minimum-salary plus sign-and-trade",
         "checked": False, "note": "not modeled"},
    ]
    return {"tool": "get_trade_check", "ok": True,
            "rows": {"team_a": {"team": team_a.upper(), "out": out_a,
                                "players": names_a, "payroll": pay_a,
                                "allowed_in": allow_a, "match_rule": rule_a,
                                **{k: v for k, v in state_a.items()}},
                     "team_b": {"team": team_b.upper(), "out": out_b,
                                "players": names_b, "payroll": pay_b,
                                "allowed_in": allow_b, "match_rule": rule_b,
                                **{k: v for k, v in state_b.items()}},
                     "legal": not issues, "issues": issues, "checks": checks,
                     "salary_date": salary_date,
                     **({"attribution_corrections": corrections}
                        if corrections else {}),
                     "disclaimer": "Estimate only, rules simplified. Skips cash, "
                     "prior trade exceptions, taxpayer midlevel, frozen pick, Stepien, "
                     "base-year, trade-kicker, minimum-salary, and sign-and-trade rules. "
                     "Confirm with a cap specialist."},
            "meta": {"source": source, "rules": "v1-simplified",
                     "salary_date": salary_date}}


@tool
def get_trade_value(
    team_a: str = "", players_a: str = "", team_b: str = "",
    players_b: str = "", picks_a: str = "", picks_b: str = "",
) -> dict[str, Any]:
    """Trade value grade: estimated production value vs salary per side, plus picks.

    Reasoning layer on top of get_trade_check (which covers cap legality).
    All dollar figures are rough estimates from 2025-26 production versus
    2026-27 salaries. Picks like "2029 FRP" or "2030 FRP top-4 protected".
    """
    import re as _re
    import unicodedata as _ud

    from .. import store as _store

    if team_a and team_b:
        _norm = _norm_trade_teams(team_a, team_b)
        if _norm is None:
            return {"tool": "get_trade_value", "ok": False,
                    "error": (f"both sides resolve to the same team "
                              f"({team_a} / {team_b}) - check the team "
                              f"names")}
        team_a, team_b = _norm
    PROD_SEASON = "2025-26"
    SAL_SEASON = "2026-27"
    DISCLAIMER = ("All dollar figures are rough estimates from 2025-26 "
                  "production vs 2026-27 salary data. Not cap-legality advice; "
                  "pair with get_trade_check.")

    def _norm(s: object) -> str:
        return "".join(c for c in _ud.normalize("NFKD", str(s or ""))
                        if not _ud.combining(c)).strip().lower()

    if not team_a or not team_b:
        return {"tool": "get_trade_value", "ok": False,
                "error": "two teams needed"}
    con = _store.connect()
    try:
        _, names_a, unk_a = _match_trade_players(team_a, players_a, con)
        _, names_b, unk_b = _match_trade_players(team_b, players_b, con)
        if unk_a or unk_b:
            if unk_a:
                fix = _auto_correct_side(unk_a, team_a, players_a, con)
                if fix:
                    team_a, (_, names_a, unk_a), _c = fix
            if unk_b:
                fix = _auto_correct_side(unk_b, team_b, players_b, con)
                if fix:
                    team_b, (_, names_b, unk_b), _c = fix
        if unk_a or unk_b:
            parts = []
            if unk_a:
                parts.append(f"{team_a.upper()}: {'; '.join(unk_a)}")
            if unk_b:
                parts.append(f"{team_b.upper()}: {'; '.join(unk_b)}")
            hints = _unknown_player_hints(unk_a + unk_b, con)
            msg = "unknown players: " + " | ".join(parts)
            if hints:
                msg += ". " + "; ".join(hints)
            return {"tool": "get_trade_value", "ok": False, "error": msg}
        if not names_a or not names_b:
            # F47: 'Did the Lakers win the Luka trade?' graded Dallas's
            # empty side an F. What a past trade's other side received
            # is not in the data - refuse, don't manufacture a zero.
            empty = team_a.upper() if not names_a else team_b.upper()
            return {"tool": "get_trade_value", "ok": False,
                    "error": (f"the {empty} side has no assets in the "
                              f"data - I can only grade proposed trades "
                              f"where both sides name players. What a "
                              f"past trade's other side actually "
                              f"received is not in this dataset.")}

        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        cols = {t: {r[1] for r in con.execute(f"PRAGMA table_info({t})").fetchall()}
                for t in tables if t.startswith("silver_")}

        def _need(table: str, required: list[str]) -> list[str]:
            return [c for c in required if c not in cols.get(table, set())]

        data_gaps: list[str] = []
        if "silver_leaders_pts" not in tables:
            return {"tool": "get_trade_value", "ok": False,
                    "error": "cannot value players: silver_leaders_pts missing "
                             "from warehouse"}
        leaders_missing = _need("silver_leaders_pts",
                                ["PLAYER", "GP", "PTS", "REB", "AST", "STL",
                                 "BLK", "TOV", "FG3M", "FG3_PCT"])
        if leaders_missing:
            data_gaps.append(
                "silver_leaders_pts missing columns skipped at zero weight: "
                + ", ".join(leaders_missing))
        weights = {"PTS": 1.0, "REB": 1.2, "AST": 1.5,
                   "STL": 2.0, "BLK": 2.0, "TOV": -1.5}
        use_w = {c: (0.0 if c in leaders_missing else w)
                 for c, w in weights.items()}

        leaders: dict[str, dict] = {}
        for r in con.execute(
                "SELECT PLAYER, TEAM, GP, PTS, REB, AST, STL, BLK, TOV,"
                " FG3M, FG3_PCT FROM silver_leaders_pts WHERE _season = ?",
                [PROD_SEASON]).fetchall():
            leaders.setdefault(_norm(r[0]), {
                "name": r[0], "team": r[1], "gp": r[2] or 0,
                "tot": {"PTS": r[3] or 0, "REB": r[4] or 0, "AST": r[5] or 0,
                        "STL": r[6] or 0, "BLK": r[7] or 0, "TOV": r[8] or 0},
                "fg3m": r[9] or 0, "fg3_pct": r[10]})

        adv: dict[str, dict] = {}
        if "silver_advanced" not in tables:
            data_gaps.append("silver_advanced missing: age, TS_PCT, USG_PCT "
                             "and NET_RATING unavailable")
        else:
            adv_missing = _need("silver_advanced",
                                ["PLAYER_NAME", "AGE", "TS_PCT", "USG_PCT"])
            if adv_missing:
                data_gaps.append("silver_advanced missing columns: "
                                 + ", ".join(adv_missing))
            for r in con.execute(
                    "SELECT PLAYER_NAME, AGE, TS_PCT, USG_PCT FROM "
                    "silver_advanced WHERE _season = ?", [PROD_SEASON]).fetchall():
                adv.setdefault(_norm(r[0]), {"age": r[1], "ts": r[2],
                                             "usg": r[3]})

        salaries: dict[str, int] = {}
        if "silver_salaries" in tables:
            scols = cols.get("silver_salaries", set())
            scol = ("SALARY_2025_26" if "SALARY_2025_26" in scols
                    else next((c for c in scols if "SALARY" in c.upper()), ""))
            if scol:
                q = (f"SELECT PLAYER_NAME, {scol} FROM silver_salaries "
                     "WHERE _season = ?" if "_season" in scols
                     else f"SELECT PLAYER_NAME, {scol} FROM silver_salaries")
                params = [SAL_SEASON] if "_season" in scols else []
                for r in con.execute(q, params).fetchall():
                    if r[1] is not None:
                        salaries.setdefault(_norm(r[0]), int(r[1]))
        if "silver_cap_players" in tables:
            ccols = cols.get("silver_cap_players", set())
            q = ("SELECT player, salary FROM silver_cap_players "
                 "WHERE _season = ?" if "_season" in ccols
                 else "SELECT player, salary FROM silver_cap_players")
            params = [SAL_SEASON] if "_season" in ccols else []
            for r in con.execute(q, params).fetchall():
                if r[1] is not None:
                    salaries.setdefault(_norm(r[0]), int(r[1]))
        if not salaries:
            data_gaps.append("no 2026-27 salary rows: residuals unavailable")

        ratings: dict[str, dict] = {}
        if "silver_team_ratings" not in tables:
            data_gaps.append("silver_team_ratings missing: pick slots assumed "
                             "mid-first and team needs unavailable")
        else:
            rank_cols = ["OFF_RATING_RANK", "DEF_RATING_RANK",
                         "NET_RATING_RANK", "TS_PCT_RANK", "AST_PCT_RANK",
                         "REB_PCT_RANK"]
            have_ranks = [c for c in rank_cols
                          if c in cols.get("silver_team_ratings", set())]
            if len(have_ranks) < len(rank_cols):
                data_gaps.append("silver_team_ratings missing columns: " + ", ".join(
                    c for c in rank_cols if c not in have_ranks))
            sel = ", ".join(["TEAM_ID", "TEAM_NAME"] + have_ranks)
            id_to_abbr = {}
            try:
                from nba_api.stats.static import teams as _static

                id_to_abbr = {t["id"]: t["abbreviation"]
                              for t in _static.get_teams()}
            except Exception:
                pass
            for r in con.execute(
                    f"SELECT {sel} FROM silver_team_ratings WHERE _season = ?",
                    [PROD_SEASON]).fetchall():
                row = dict(zip(["TEAM_ID", "TEAM_NAME"] + have_ranks, r))
                abbr = id_to_abbr.get(row["TEAM_ID"], "")
                if abbr:
                    ratings[str(abbr).upper()] = row
        payroll_source = _payroll_source(con)
    finally:
        con.close()

    def _score(tot: dict, gp: int) -> float:
        return sum(tot[c] / gp * use_w[c] for c in use_w)

    dpp_total = dpp_score = 0.0
    for key, lead in leaders.items():
        gp = lead["gp"]
        if gp < 20 or key not in salaries:
            continue
        dpp_total += salaries[key]
        dpp_score += _score(lead["tot"], gp)
    dollars_per_point = (dpp_total / dpp_score) if dpp_score > 0 else 0.0
    if not dollars_per_point:
        return {"tool": "get_trade_value", "ok": False,
                "error": "cannot value players: no qualified salary plus "
                         "production overlap in warehouse"}

    def _value_player(display: str) -> dict:
        lead = leaders.get(_norm(display))
        a = adv.get(_norm(display), {})
        gp = lead["gp"] if lead else 0
        ppg = round(lead["tot"]["PTS"] / gp, 1) if lead and gp else 0.0
        out: dict[str, Any] = {
            "name": display, "salary_26_27": salaries.get(_norm(display)),
            "age": a.get("age"), "gp": gp, "ppg": ppg,
            "production_score": None, "est_market_value_m": "unknown",
            "residual_m": "unknown", "archetypes": [],
            "production_source": "2025-26 totals"}
        if not lead or gp < 10:
            data_gaps.append(
                f"{display}: unknown value treated as 0 in side total "
                "(GP < 10 or no 2025-26 production row)")
            return out
        score = round(_score(lead["tot"], gp), 2)
        est_m = round(score * dollars_per_point / 1e6, 1)
        out["production_score"] = score
        out["est_market_value_m"] = est_m
        if out["salary_26_27"] is not None:
            # QA #39: salary-minus-market read backwards (-21.1 for a
            # bargain). Flip to surplus value: positive = outperforming
            # the contract, negative = overpaid.
            out["residual_m"] = round((est_m * 1e6 - out["salary_26_27"]) / 1e6, 1)
            _rv = out["residual_m"]
            # QA #47: direction must be readable without a card legend.
            out["residual_note"] = (
                f"surplus value of about ${_rv}M (outperforming the "
                f"contract)" if _rv >= 0 else
                f"overpaid by an estimated ${abs(_rv)}M on this "
                f"production")
        per = {c: lead["tot"][c] / gp for c in lead["tot"]}
        tags = []
        if (lead["fg3m"] or 0) / gp >= 2.0:
            tags.append("spacer")
        if per["AST"] >= 5.0:
            tags.append("playmaker")
        if per["STL"] + per["BLK"] >= 1.5:
            tags.append("defensive playmaker")
        if a.get("ts") is not None and a["ts"] >= 0.60:
            tags.append("efficient scorer")
        if a.get("usg") is not None and a["usg"] >= 0.28:
            tags.append("high-usage creator")
        out["archetypes"] = tags
        return out

    def _value_picks(raw: str, giving_abbr: str) -> list[dict]:
        picks = []
        for desc in [p.strip() for p in str(raw or "").split(",") if p.strip()]:
            low = desc.lower()
            year = _re.search(r"(\d{4})", desc)
            is_frp = bool(_re.search(r"frp|first[\s-]?round", low))
            is_srp = bool(_re.search(r"\bsrp\b|second[\s-]?round", low))
            prot = _re.search(r"top[-\s]?(\d+)\s*protect", low)
            entry: dict[str, Any] = {"desc": desc, "est_slot": None,
                                     "est_value_m": 0.0, "assumptions": []}
            if not year or (not is_frp and not is_srp):
                entry["assumptions"].append("unparseable pick description")
                data_gaps.append(f"{desc}: unparseable pick, valued at 0")
                picks.append(entry)
                continue
            if is_frp:
                net_rank = (ratings.get(giving_abbr.upper(), {}) or {}).get(
                    "NET_RATING_RANK")
                if net_rank is None:
                    slot = 15
                    entry["assumptions"].append(
                        f"no ratings row for {giving_abbr.upper()}: assumed "
                        "mid-first slot 15")
                else:
                    slot = max(1, min(round(31 - net_rank * 0.85), 30))
                    entry["assumptions"].append(
                        f"slot estimated from {giving_abbr.upper()} net rank "
                        f"{net_rank}")
                if prot:
                    n = int(prot.group(1))
                    slot = max(slot, n + 1)
                    entry["assumptions"].append(
                        f"top-{n} protected: conveyance risk applied")
                value = _pick_value_for_slot(slot, True)
                if prot:
                    value = round(value * 0.8, 1)
                entry.update(est_slot=slot, est_value_m=value)
            else:
                m = _re.search(r"\b([3-5]\d)\b", desc)
                slot = int(m.group(1)) if m and 31 <= int(m.group(1)) <= 60 else 45
                entry.update(est_slot=slot,
                             est_value_m=_pick_value_for_slot(slot, False))
                entry["assumptions"].append("second-round slot estimate")
            picks.append(entry)
        return picks

    players_a = [_value_player(n) for n in names_a]
    players_b = [_value_player(n) for n in names_b]
    picks_list_a = _value_picks(picks_a, team_a)
    picks_list_b = _value_picks(picks_b, team_b)

    def _side_total(plist: list[dict], klist: list[dict]) -> float:
        return round(sum(p["est_market_value_m"] for p in plist
                         if isinstance(p["est_market_value_m"], (int, float)))
                     + sum(k["est_value_m"] for k in klist), 1)

    total_a = _side_total(players_a, picks_list_a)
    total_b = _side_total(players_b, picks_list_b)
    delta = round(total_a - total_b, 1)
    abbr_a, abbr_b = team_a.upper(), team_b.upper()
    winner = abbr_a if delta >= 0.5 else abbr_b if delta <= -0.5 else "even"

    def _grades() -> dict[str, str]:
        if winner == "even":
            return {abbr_a: "B", abbr_b: "B"}
        share = abs(delta) / max(total_a, total_b, 1)
        w = abbr_a if winner == abbr_a else abbr_b
        loser = abbr_b if w == abbr_a else abbr_a
        wg = "A" if share >= 0.25 else "A-" if share >= 0.15 else "B+"
        lg = ("F" if share >= 0.40 else "D" if share >= 0.25
              else "C+" if share >= 0.15 else "B-")
        return {w: wg, loser: lg}

    need_cols = [("need_offense", "OFF_RATING_RANK"),
                 ("need_defense", "DEF_RATING_RANK"),
                 ("need_shooting", "TS_PCT_RANK"),
                 ("need_playmaking", "AST_PCT_RANK"),
                 ("need_rebounding", "REB_PCT_RANK")]
    tag_to_need = {"spacer": "need_shooting",
                   "playmaker": "need_playmaking",
                   "defensive playmaker": "need_defense",
                   "efficient scorer": "need_offense",
                   "high-usage creator": "need_offense"}

    def _fit(team_abbr: str, received: list[dict]) -> dict:
        r = ratings.get(team_abbr.upper(), {})
        needs = [name for name, col in need_cols
                 if isinstance(r.get(col), (int, float)) and r[col] >= 20]
        net_rank = r.get("NET_RATING_RANK")
        timeline = ("unknown" if not isinstance(net_rank, (int, float))
                    else "contender" if net_rank <= 8
                    else "rebuilding" if net_rank >= 22 else "middle")
        notes = []
        for p in received:
            for tag in p.get("archetypes", []):
                need = tag_to_need.get(tag)
                if need and need in needs:
                    notes.append(f"{p['name']} fills {need} ({tag})")
            age = p.get("age")
            if (isinstance(age, (int, float)) and age >= 32
                    and timeline == "rebuilding"):
                notes.append(f"{p['name']}: timeline clash (age {age:g} "
                             "joining a rebuild)")
            if (isinstance(age, (int, float)) and age <= 23
                    and timeline == "contender"):
                notes.append(f"{p['name']}: developmental piece on a contender")
        notes.append("positional logjam not assessed: no position data "
                     "in warehouse")
        return {"needs": needs, "timeline": timeline, "notes": notes}

    fit = {abbr_a: _fit(abbr_a, players_b), abbr_b: _fit(abbr_b, players_a)}

    valued = [p for p in players_a + players_b
              if isinstance(p["est_market_value_m"], (int, float))]
    driver = (max(valued, key=lambda p: (abs(p["residual_m"])
                 if isinstance(p["residual_m"], (int, float)) else 0))
              if valued else None)
    win_side = players_b if winner == abbr_a else players_a
    win_got = [p for p in win_side
               if isinstance(p["est_market_value_m"], (int, float))]
    key_add = max(win_got, key=lambda p: p["est_market_value_m"],
                  default=None)
    key_fit_note = ""
    if key_add is not None and winner != "even":
        wfit = fit[winner]
        hit = next((n for n in wfit["notes"]
                    if n.startswith(key_add["name"])), "")
        key_fit_note = (f" {key_add['name']} {hit[len(key_add['name']) + 1:]} "
                        f"for {winner}." if hit
                        else f" {key_add['name']} headlines the return "
                             f"for {winner} ({wfit['timeline']} timeline).")
    if winner == "even":
        s1 = (f"This grades as roughly even, with {abbr_a} at an estimated "
              f"${total_a}M and {abbr_b} at an estimated ${total_b}M, "
              f"a gap of about ${abs(delta)}M.")
    else:
        s1 = (f"{winner} wins on estimated value by about ${abs(delta)}M, "
              f"${max(total_a, total_b)}M to ${min(total_a, total_b)}M.")
    if driver is not None:
        res = driver["residual_m"]
        res_txt = ("the best value in the deal"
                   if isinstance(res, (int, float)) and res < 0
                   else "the largest gap between salary and production")
        s2 = (f"The biggest driver is {driver['name']}, with an estimated "
              f"${driver['est_market_value_m']}M market value against a "
              f"${(driver['salary_26_27'] or 0) / 1e6:.1f}M salary, "
              f"{res_txt}.")
    else:
        s2 = "No player had enough production data to name a value driver."
    s3 = key_fit_note.strip() or "Fit notes are limited by missing team data."
    s4 = ("All values are rough estimates from 2025-26 production versus "
          "2026-27 salaries, so this is not cap-legality advice: pair it "
          "with get_trade_check.")
    text = " ".join([s1, s2, s3, s4])

    return {"tool": "get_trade_value", "ok": True,
            "rows": {"team_a": {"team": abbr_a, "players": players_a,
                                "picks": picks_list_a, "side_total_m": total_a},
                     "team_b": {"team": abbr_b, "players": players_b,
                                "picks": picks_list_b, "side_total_m": total_b},
                     "fit": fit,
                     "verdict": {"winner": winner, "delta_m": delta,
                                 "grades": _grades(), "text": text},
                     "data_gaps": data_gaps,
                     "disclaimer": DISCLAIMER,
                     "residual_meaning": "residual_m = estimated market "
                     "value minus salary; positive = surplus value "
                     "(outperforming the contract), negative = overpaid"},
            "meta": {"source": payroll_source,
                     "production_season": PROD_SEASON,
                     "salary_season": "2026-27 (column SALARY_2025_26)",
                     "estimates": True}}


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
def get_rookie_leaders(stat: str = "ppg", min_value: float = 0,
                       min_gp: int = 10, limit: int = 15,
                       season: str = SEASON) -> dict[str, Any]:
    """Current rookie class leaderboard (first-year NBA players only).

    Rookies are defined structurally: a player in the current-season
    stats table with NO row in any prior season (hist or warehouse).
    Never an age proxy, never historical seasons (F46: a "rookies 20+
    ppg" query answered from 2023-24 listed Edwards/LaMelo/Wemby; the
    right answer was the current draft class, e.g. Cooper Flagg).
    stat is a per-game column: ppg, rpg, apg, spg, bpg, mpg.
    """
    from .. import store as _store

    import duckdb

    col = str(stat or "ppg").strip().upper()
    allowed = {"PPG", "RPG", "APG", "SPG", "BPG", "MPG",
               "FG_PCT", "FG3_PCT", "FT_PCT", "GP"}
    if col not in allowed:
        return {"tool": "get_rookie_leaders", "ok": False,
                "error": f"stat must be one of {sorted(allowed)}"}
    sql = f"""
        WITH cur AS (
          SELECT PLAYER_ID, PLAYER, TEAM, AGE, GP, MPG, PPG, RPG, APG,
                 SPG, BPG, FG_PCT, FG3_PCT, FT_PCT
          FROM silver_player_season WHERE _season = ?
        ),
        hist AS (
          SELECT DISTINCT PLAYER_ID FROM silver_hist_player_seasons
          UNION
          SELECT DISTINCT PLAYER_ID FROM silver_player_season
          WHERE _season <> ?
        )
        SELECT c.PLAYER, c.TEAM, c.AGE, c.GP, c.MPG, c.PPG, c.RPG,
               c.APG, c.SPG, c.BPG, c.FG_PCT, c.FG3_PCT, c.FT_PCT
        FROM cur c LEFT JOIN hist h ON c.PLAYER_ID = h.PLAYER_ID
        WHERE h.PLAYER_ID IS NULL AND c.GP >= ? AND c.{col} >= ?
        ORDER BY c.{col} DESC LIMIT ?
    """
    try:
        con = duckdb.connect(str(_store.DB_PATH), read_only=True)
        try:
            rows = con.execute(
                sql, [season, season, int(min_gp), float(min_value),
                      int(limit)]).fetchdf().to_dict("records")
        finally:
            con.close()
    except Exception as exc:
        return {"tool": "get_rookie_leaders", "ok": False,
                "error": f"warehouse read failed: {str(exc)[:160]}"}
    return {
        "tool": "get_rookie_leaders", "ok": True, "rows": rows,
        "meta": {
            "season": season,
            "rookie_definition": (
                "first NBA season: no player row in any prior season"),
            "floors": f"GP >= {int(min_gp)}, {col} >= {float(min_value)}",
            "note": "current draft class only; never an age proxy"},
    }


@tool
def get_lineup_leaders(min_minutes: int = 100, limit: int = 10,
                       season: str = SEASON) -> dict[str, Any]:
    """League-wide five-man lineup net-rating leaderboard.

    Net rating is PLUS_MINUS per 48 minutes from the warehouse lineup
    table. A minimum-minutes floor (default 100) is ALWAYS applied and
    stated: a +3 in 4 minutes is a 300.0 'net rating' on a junk slice
    and never tops the board (F50).
    """
    from .. import store as _store

    import duckdb

    sql = """
        SELECT TEAM_ABBREVIATION, GROUP_NAME, GP, MIN, PLUS_MINUS,
               ROUND(PLUS_MINUS / NULLIF(MIN, 0) * 48, 1) AS NET48
        FROM silver_lineups
        WHERE _season = ? AND MIN >= ?
        ORDER BY PLUS_MINUS / NULLIF(MIN, 0) DESC NULLS LAST
        LIMIT ?
    """
    try:
        con = duckdb.connect(str(_store.DB_PATH), read_only=True)
        try:
            raw = con.execute(
                sql, [season, float(min_minutes), int(limit) * 2]
            ).fetchdf().to_dict("records")
        finally:
            con.close()
    except Exception as exc:
        return {"tool": "get_lineup_leaders", "ok": False,
                "error": f"warehouse read failed: {str(exc)[:160]}"}
    seen = set()
    rows = []
    for r in raw:
        key = (r.get("TEAM_ABBREVIATION"), r.get("GROUP_NAME"))
        if key in seen:
            continue
        seen.add(key)
        rows.append(r)
        if len(rows) >= int(limit):
            break
    return {
        "tool": "get_lineup_leaders", "ok": True, "rows": rows,
        "meta": {
            "season": season,
            "formula": "NET48 = PLUS_MINUS per 48 minutes",
            "floor": f"MIN >= {int(min_minutes)} (stated volume floor; "
                     "small-sample units are excluded, F50)"},
    }


@tool
def get_combine(season: str = "2025") -> dict[str, Any]:
    """Draft combine measurements plus shooting drills for one draft year."""
    rows, meta = _warehouse_or_live(
        "silver_combine", "_season = ?",
        [season], lambda: nba_stats.combine(season), season,
    )
    if not rows:
        return {"tool": "get_combine", "ok": False,
                "error": meta.get("error") or "empty upstream response"}
    return {"tool": "get_combine", "ok": True, "rows": rows[:25],
            "meta": meta}


@tool
def get_briefing(game_date: str = "", season: str = SEASON) -> dict[str, Any]:
    """Morning briefing: scoreboard plus top scorers. Date MM/DD/YYYY, blank means latest."""
    from datetime import datetime, timedelta

    day = game_date.strip()
    if not day:
        day = (datetime.now() - timedelta(days=1)).strftime("%m/%d/%Y")
    past = is_past_game_date(day)
    games, gmeta = _warehouse_or_live(
        "silver_scoreboard", "_season = ? AND _entity = ?",
        [season, f"date:{day}"],
        lambda: nba_stats.scoreboard(day, season), season,
        entity=f"date:{day}", live_first=(not past),
        ttl_s=(TTL_SCOREBOARD_PAST if past else None),
    )
    leaders, _ = _warehouse_or_live(
        "silver_leaders_pts", "_season = ?",
        [season], lambda: nba_stats.leaders("PTS", season), season,
        ttl_s=TTL_LEADERS,
    )
    top = [
        {"PLAYER": r.get("PLAYER"), "TEAM": r.get("TEAM"), "PTS": r.get("PTS")}
        for r in leaders[:5]
    ]
    return {"tool": "get_briefing", "ok": True,
            "rows": {"date": day, "games": games, "top_scorers": top},
            "meta": gmeta}


def _describe_warehouse_schema(cols: dict[str, list[str]]) -> str:
    return "\n".join(f"{t}: {', '.join(c[:40])}" for t, c in cols.items())


# Tables the warehouse read path (text_to_sql, rerun_sql) may query.
_SQL_TABLES = [
    "silver_standings", "silver_playoffs", "silver_team_ratings",
    "silver_clutch", "silver_player_gamelogs", "silver_team_games",
    "silver_leaders_pts", "silver_leaders_reb", "silver_leaders_ast",
    "silver_leaders_stl", "silver_leaders_blk", "silver_boxscores",
    "silver_lineups", "silver_shots", "silver_hustle_player",
    "silver_hustle_team", "silver_injuries", "silver_hist_gamelogs",
    "silver_hist_standings", "silver_hist_possessions",
    "silver_hist_shots", "silver_hist_lineups", "silver_salaries",
    "silver_hist_draft", "silver_raptor_player", "silver_raptor_team",
    "silver_hist_player_seasons",
]

# One-click re-run limits: matches text_to_sql's rows[:25] slice.
RERUN_ROW_CAP = 25
RERUN_TIMEOUT_S = 30

_SCHEMA_TTL_S = 3600.0
_schema_cache: dict[str, object] = {"at": 0.0, "present": [], "cols": {}}
_schema_cache_stats: dict[str, int] = {"hits": 0, "misses": 0}


def _clear_warehouse_schema_cache() -> None:
    _schema_cache["at"] = 0.0
    _schema_cache["present"] = []
    _schema_cache["cols"] = {}
    _schema_cache_stats["hits"] = 0
    _schema_cache_stats["misses"] = 0


def _warehouse_schema_cache_info() -> dict[str, float]:
    return {"hits": _schema_cache_stats["hits"],
            "misses": _schema_cache_stats["misses"],
            "at": _schema_cache["at"]}


def _get_warehouse_schema() -> tuple[list[str], dict[str, list[str]]]:
    import time as _time

    from .. import store as _store

    now = _time.monotonic()
    at = float(_schema_cache.get("at") or 0.0)
    if now - at < _SCHEMA_TTL_S and _schema_cache.get("present"):
        _schema_cache_stats["hits"] += 1
        return (list(_schema_cache["present"]),  # type: ignore[arg-type]
                {k: list(v) for k, v in  # type: ignore[attr-defined]
                 _schema_cache["cols"].items()})  # type: ignore[attr-defined]
    _schema_cache_stats["misses"] += 1
    con = _store.connect()
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        present = [t for t in _SQL_TABLES if t in tables]
        cols: dict[str, list[str]] = {}
        for t in present:
            cols[t] = [r[1] for r in
                       con.execute(f"PRAGMA table_info({t})").fetchall()][:40]
    finally:
        con.close()
    _schema_cache["at"] = now
    _schema_cache["present"] = present
    _schema_cache["cols"] = cols
    return (list(present), {k: list(v) for k, v in cols.items()})

import re as _re_mod


_SELECT_RE = _re_mod.compile(r"(?i)^\s*(select|with)\b")
_WRITE_RE = _re_mod.compile(
    r"(?i)\b(insert|update|delete|drop|alter|create|pragma|attach|copy|"
    r"vacuum|detach)\b")
_TABLE_REF_RE = _re_mod.compile(r"(?i)from\s+(\w+)|join\s+(\w+)")


def _validate_readonly_sql(sql: str, present: set[str]) -> str:
    """Normalize a user-supplied SQL string for read-only execution.

    Raises ValueError unless it is one SELECT/WITH statement over the
    allowlisted warehouse tables. Shared by text_to_sql and rerun_sql.
    """
    sql = (sql or "").strip().rstrip(";").strip()
    if not _SELECT_RE.match(sql):
        raise ValueError("only SELECT/WITH queries are allowed")
    if ";" in sql:
        raise ValueError("stacked statements are not allowed")
    if _WRITE_RE.search(sql):
        raise ValueError("write operations are not allowed")
    used = {a or b for a, b in _TABLE_REF_RE.findall(sql)}
    if not used or not used.issubset(set(present)):
        raise ValueError("unknown or unavailable tables")
    return sql


@tool
async def text_to_sql(question: str) -> dict[str, Any]:
    """Answer a data question with SQL over warehouse tables. SELECT only."""
    import re as _re

    from langchain_core.messages import HumanMessage, SystemMessage

    from .. import store as _store
    from ..providers import invoke_with_fallback

    present, cols = _get_warehouse_schema()
    if not present:
        return {"tool": "text_to_sql", "ok": False, "error": "warehouse empty"}
    schema = _describe_warehouse_schema(cols)
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
        "Q: How strong is the supporting cast around Shai Gilgeous-Alexander on OKC?\n"
        "SQL: SELECT AVG(l.PTS * 1.0 / l.GP) AS cast_ppg, "
        "MAX(r.NET_RATING) AS net_rating, MAX(r.PACE) AS pace "
        "FROM silver_leaders_pts l JOIN silver_team_ratings r "
        "ON r._season = l._season "
        "WHERE l.TEAM = 'OKC' AND l.PLAYER <> 'Shai Gilgeous-Alexander' "
        "AND r.TEAM_NAME LIKE '%Oklahoma%' "
        "AND l._season = '2025-26' AND l.GP >= 10\n"
        "Q: Who has the most playoff wins in 2025-26?\n"
        "SQL: SELECT TEAM_ABBREVIATION, COUNT(*) AS wins FROM silver_playoffs "
        "WHERE WL = 'W' GROUP BY TEAM_ABBREVIATION ORDER BY wins DESC LIMIT 5\n"
        "Q: Who was drafted #1 overall in the June 2003 NBA draft?\n"
        "Note: DRAFT_YEAR is the June draft year.\n"
        "SQL: SELECT OVERALL_PICK, PLAYER_NAME, TEAM_ABBREVIATION FROM silver_hist_draft "
        "WHERE OVERALL_PICK = 1 AND DRAFT_YEAR = 2003\n"
        "Q: What was Michael Jordan's peak RAPTOR season?\n"
        "SQL: SELECT _season, RAPTOR_TOTAL, WAR_TOTAL FROM silver_raptor_player "
        "WHERE PLAYER_NAME = 'Michael Jordan' ORDER BY RAPTOR_TOTAL DESC LIMIT 1\n"
        "Q: What were LeBron James' per-game stats in 2023-24?\n"
        "Note: silver_hist_player_seasons stores per-game averages already; "
        "select PTS/MIN directly, never divide by GP. "
        "Season ints are end-years, so 2023-24 = SEASON 2024 = _season '2023-24'.\n"
        "SQL: SELECT PLAYER_NAME, TEAM_ABBREVIATION, GP, PTS, AST, TS_PCT, NET_RATING "
        "FROM silver_hist_player_seasons WHERE PLAYER_NAME = 'LeBron James' "
        "AND _season = '2023-24'\n"
        "Q: Which players under 24 averaged at least 15 points and 5 assists last season?\n"
        "Note silver_hist_player_seasons stores per-game averages with AGE, PTS, AST "
        "columns and season end-year ints.\n"
        "SQL: SELECT PLAYER_NAME, TEAM_ABBREVIATION, AGE, GP, PTS, AST "
        "FROM silver_hist_player_seasons WHERE AGE < 24 AND PTS >= 15 AND AST >= 5 "
        "AND SEASON = 2024 ORDER BY PTS DESC LIMIT 10\n"
        "Q: What were the best games in March 2026?\n"
        "Note: current-season per-game logs live in silver_player_gamelogs "
        "with UPPERCASE columns (PLAYER_NAME absent - join player ids via "
        "silver_leaders_pts.PLAYER_ID/PLAYER; GAME_DATE, MATCHUP, PTS). "
        "Dates look like 'Mar 30, 2026'; filter months with ILIKE, e.g. "
        "GAME_DATE ILIKE '%Mar%2026'. A 'no such column' error means "
        "wrong table/column spelling - retry with these names, it NEVER "
        "means the games are missing.\n"
        "SQL: SELECT p.PLAYER, g.GAME_DATE, g.MATCHUP, g.PTS FROM "
        "silver_player_gamelogs g JOIN silver_leaders_pts p ON "
        "p.PLAYER_ID = g.Player_ID AND p._season = g._season "
        "WHERE g._season = '2025-26' AND g.GAME_DATE ILIKE '%Mar%2026' "
        "ORDER BY g.PTS DESC LIMIT 10\n"
        "Q: Who led the 2025-26 season in steals?\n"
        "Note: season totals come from silver_leaders_* tables; "
        "never aggregate silver_player_gamelogs for season totals.\n"
        "SQL: SELECT PLAYER, STL FROM silver_leaders_stl "
        "WHERE _season = '2025-26' ORDER BY STL DESC LIMIT 1"
    )
    feedback = ""
    for _ in range(2):  # F44: 3 retries x LLM latency fed 300s desk loops
        try:
            resp = await invoke_with_fallback(
                "mistral", "ministral-8b-2512",
                [SystemMessage(content="Reply with SQL only, no prose."),
                 HumanMessage(
                      content="Write one SQLite SELECT using only these tables "
                      "and columns. Match column case exactly as listed.\n"
                      "Rules. Ratio/percentage leaderboards MUST add a "
                      "minimum-volume floor (AST/TOV: AST >= 300; shooting "
                      "pct: attempts >= 300) or the top row is a junk "
                      "small-sample slice. Season totals and season leaders questions MUST use "
                      "the silver_leaders_* tables directly; they hold final official "
                      "season totals. silver_player_gamelogs is an incomplete per-game "
                      "sample: never SUM it to compute season totals, and never join "
                      "per-game tables to leaders tables (fan-out inflates sums).\n"
                      f"Schema:\n{schema}{examples}\nQuestion: {question}{feedback}")])
            sql = _re.sub(r"^```sql|```$", "", str(getattr(resp, "content", "") or ""),
                          flags=_re.MULTILINE).strip()
        except Exception as exc:
            return {"tool": "text_to_sql", "ok": False, "error": str(exc)[:160]}
        if not _re.match(r"(?i)^\s*select\b", sql) or _re.search(
                r"(?i)\b(insert|update|delete|drop|alter|create|pragma|attach|copy)\b", sql):
            feedback = "\nPrevious reply was not a single SELECT. Reply with SQL only."
            continue
        try:
            sql = _validate_readonly_sql(sql, set(present))
        except ValueError as vexc:
            feedback = f"\nPrevious reply was rejected: {vexc}. Reply with SQL only."
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
                "sql": sql,
                "meta": {"sql": sql[:500], "source": "warehouse"}}
    return {"tool": "text_to_sql", "ok": False,
            "error": ("the warehouse query did not succeed after several "
                      "attempts; answer from results already gathered or "
                      "state plainly that it could not be computed")}


def _execute_with_timeout(con, sql: str, timeout_s: float):
    """Run con.execute(sql) in a worker thread; close the connection to abort
    on timeout. Returns (column names, rows)."""
    import threading as _threading

    out: dict[str, Any] = {}

    def _run() -> None:
        try:
            rel = con.execute(sql)
            out["result"] = ([d[0] for d in con.description], rel.fetchall())
        except Exception as exc:  # noqa: BLE001 - surfaced to caller
            out["error"] = exc

    th = _threading.Thread(target=_run, daemon=True)
    th.start()
    th.join(timeout_s)
    if th.is_alive():
        try:
            con.close()
        except Exception:
            pass
        raise TimeoutError(f"query exceeded {timeout_s:g}s")
    if "error" in out:
        raise out["error"]
    return out["result"]


async def rerun_sql(sql: str) -> dict[str, Any]:
    """One-click re-run of the exact SQL shown behind a text_to_sql answer.

    Read-only: validated by _validate_readonly_sql (single SELECT/WITH over
    the silver_* allowlist), executed through the same warehouse read path as
    text_to_sql with a row cap and a timeout. Not an agent tool; called from
    the HTTP boundary.
    """
    import time as _time

    from .. import store as _store

    sql = (sql or "").strip()
    con = _store.connect(read_only=True)
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
    except Exception as exc:
        return {"tool": "rerun_sql", "ok": False,
                "error": str(exc)[:160]}
    finally:
        con.close()
    present = tables & set(_SQL_TABLES)
    if not present:
        return {"tool": "rerun_sql", "ok": False,
                "error": "warehouse empty"}
    try:
        sql = _validate_readonly_sql(sql, present)
    except ValueError as vexc:
        return {"tool": "rerun_sql", "ok": False, "error": str(vexc)[:160]}
    t0 = _time.time()
    con = _store.connect(read_only=True)
    try:
        names, rows = _execute_with_timeout(con, sql, RERUN_TIMEOUT_S)
    except Exception as exc:
        return {"tool": "rerun_sql", "ok": False, "error": str(exc)[:160],
                "sql": sql}
    finally:
        try:
            con.close()
        except Exception:
            pass
    capped = len(rows) > RERUN_ROW_CAP
    return {"tool": "rerun_sql", "ok": True,
            "columns": names,
            "rows": [dict(zip(names, r)) for r in rows[:RERUN_ROW_CAP]],
            "sql": sql, "capped": capped,
            "ms": int((_time.time() - t0) * 1000)}


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


@tool
def get_elo_standings(season: str = SEASON, opponent: str | None = None,
                      limit: int = 30) -> dict[str, Any]:
    """ELO power ratings as standings: implied win pct, win equivalents, and Elo-implied spreads. ROADMAP Appendix #3."""
    from .. import store as _store

    con = _store.connect()
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
    elo, wins, losses, mov_ok = _build_elo(rows)
    anchor_abbr = "AVG"
    anchor_elo = 1500
    if opponent is not None and str(opponent).strip():
        from nba_api.stats.static import teams as _teams

        from ._core import coerce_team_id

        try:
            opp_id = coerce_team_id(opponent)
        except ValueError:
            return {"tool": "get_elo_standings", "ok": False,
                    "error": f"unknown team: {opponent}"}
        by_id = {t["id"]: t["abbreviation"] for t in _teams.get_teams()}
        anchor_abbr = by_id.get(opp_id, "")
        if not anchor_abbr or anchor_abbr not in elo:
            return {"tool": "get_elo_standings", "ok": False,
                    "error": f"unknown team: {opponent}"}
        anchor_elo = round(elo[anchor_abbr])
    table = []
    for t, v in elo.items():
        e = round(v)
        w, l = wins.get(t, 0), losses.get(t, 0)
        pct = round(_elo_expected(e - ELO_START), 4)
        table.append({"abbr": t, "elo": e, "games": w + l, "W": w, "L": l,
                      "elo_win_pct": pct, "win_equiv": round(pct * 82, 1)})
    table.sort(key=lambda d: d["elo"], reverse=True)
    for i, row in enumerate(table, 1):
        row["rank"] = i
    for row in table:
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
                    "≈ elo_diff/28"),
                "data_note": (
                    f"ELO computed from {n_games} real games in "
                    f"silver_hist_gamelogs for season {season} (5 seasons "
                    "2021-22 through 2025-26 live in the table; this run "
                    f"used {season} only). plus_minus present on 100% of "
                    "rows, so every game is MOV-adjusted. No games "
                    "fabricated; teams with no games get no rating.")}}


@tool
def get_playoff_sim(season: str = SEASON, sims: int = 2000) -> dict[str, Any]:
    """Simulated title and finals odds from ratings, Monte Carlo brackets."""
    from .sim import run_playoff_sim

    try:
        sims = max(100, min(int(sims or 2000), 10000))
    except (TypeError, ValueError):
        sims = 2000
    from ._core import season_static as _season_static
    if _season_static(season):
        # QA F10: simulating a completed season yields degenerate odds
        # (1 = already happened). Answer with the actual playoff results
        # instead of an error the asker cannot use.
        _po = get_playoffs.invoke({"season": season})
        if _po.get("ok"):
            _rows = dict(_po.get("rows") or {})
            # QA F36: the LLM narrates from ROWS, not meta - it framed
            # these actuals as "simulation output" despite the meta note.
            # Put the honesty where the model reads: inside the payload.
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


@tool
def get_risers(season: str = "2025-26", weeks: int = 4) -> dict[str, Any]:
    """Risers and fallers: last-N win pct vs season win pct, warehouse only."""
    from .. import store as _store

    season = str(season or "2025-26").strip() or "2025-26"
    try:
        weeks = max(1, min(int(weeks or 4), 8))
    except (TypeError, ValueError):
        weeks = 4
    n = max(5, min(round(weeks * 2.5), 15))
    con = _store.connect()
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        if "silver_hist_gamelogs" not in tables:
            return {"tool": "get_risers", "ok": False, "error": "history empty"}
        cols = {r[1] for r in
                con.execute("PRAGMA table_info(silver_hist_gamelogs)").fetchall()}
        q = """SELECT team_abbreviation, game_date, wl FROM silver_hist_gamelogs
               WHERE _season = ?"""
        if "season_type" in cols:
            q += " AND season_type = 'regular-season'"
        rows = con.execute(q + " ORDER BY team_abbreviation, game_date",
                           [season]).fetchall()
    finally:
        con.close()
    if not rows:
        return {"tool": "get_risers", "ok": False,
                "error": f"no games for {season}"}
    from ._core import season_static as _season_static
    offseason = _season_static(season)
    by_team: dict[str, list] = {}
    for t, _, w in rows:
        if t:
            by_team.setdefault(t, []).append(w)
    table = []
    for t, ws in by_team.items():
        w_all = sum(1 for w in ws if w == "W")
        last = ws[-n:]
        w_last = sum(1 for w in last if w == "W")
        sp = w_all / len(ws)
        lp = w_last / len(last)
        table.append({"TEAM": t, "LAST10": f"{w_last}-{len(last) - w_last}",
                      "LAST10_PCT": round(lp, 3), "SEASON_PCT": round(sp, 3),
                      "DELTA": round(lp - sp, 3)})
    table.sort(key=lambda d: d["DELTA"], reverse=True)
    meta = {"source": "warehouse", "season": season,
            "window": n, "weeks": weeks}
    if offseason:
        # QA F12: in the offseason these are FINAL season windows (form at
        # the end of a completed season), not current risers - no games
        # exist to rise in. Say so in-band so desks cannot misframe it.
        meta["offseason"] = True
        meta["note"] = (f"{season} is complete; these are end-of-season "
                        f"form windows, not current risers. No NBA games "
                        f"until preseason.")
    return {"tool": "get_risers", "ok": True,
            "rows": {"risers": table[:5], "fallers": table[-5:][::-1]},
            "meta": meta}


@tool
def get_player_risers(season: str = "2025-26", n: int = 10) -> dict[str, Any]:
    """Player risers and fallers: last-N games scoring/efficiency vs the
    player's own season average, warehouse only. Use this for
    player-level 'who is rising/falling/hot' asks; get_risers is the
    TEAM version (win-rate windows)."""
    from .. import store as _store

    season = str(season or "2025-26").strip() or "2025-26"
    try:
        n = max(5, min(int(n or 10), 15))
    except (TypeError, ValueError):
        n = 10
    con = _store.connect()
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        if "silver_player_gamelogs" not in tables:
            return {"tool": "get_player_risers", "ok": False,
                    "error": "player gamelogs empty"}
        rows = con.execute(
            """SELECT g._entity, g.GAME_DATE, g.PTS, g.FG_PCT, g.FG3_PCT
               FROM silver_player_gamelogs g
               WHERE g._season = ?
               ORDER BY g._entity,
                        strptime(g.GAME_DATE, '%b %d, %Y')""",
            [season]).fetchall()
        names = {}
        try:
            for pid, pname in con.execute(
                    "SELECT PLAYER_ID, PLAYER FROM silver_player_season "
                    "WHERE _season = ?", [season]).fetchall():
                names[f"player:{pid}"] = pname
        except Exception:
            pass
        teams = {}
        try:
            for pid, team in con.execute(
                    "SELECT PLAYER_ID, TEAM FROM silver_player_season "
                    "WHERE _season = ?", [season]).fetchall():
                teams[f"player:{pid}"] = team
        except Exception:
            pass
    finally:
        con.close()
    if not rows:
        return {"tool": "get_player_risers", "ok": False,
                "error": f"no player games for {season}"}
    by_player: dict[str, list] = {}
    for ent, _d, pts, fg, fg3 in rows:
        if pts is None:
            continue
        by_player.setdefault(ent, []).append((pts, fg, fg3))
    table = []
    for ent, games in by_player.items():
        if len(games) < 25:
            continue
        season_pts = sum(g[0] for g in games) / len(games)
        last = games[-n:]
        last_pts = sum(g[0] for g in last) / len(last)
        fg_season = [g[1] for g in games if g[1] is not None]
        fg_last = [g[1] for g in last if g[1] is not None]
        table.append({
            "PLAYER": names.get(ent, ent.replace("player:", "id ")),
            "TEAM": teams.get(ent, ""),
            "GP": len(games),
            "SEASON_PPG": round(season_pts, 1),
            f"LAST{n}_PPG": round(last_pts, 1),
            "PPG_DELTA": round(last_pts - season_pts, 1),
            "SEASON_FG_PCT": round(sum(fg_season) / len(fg_season), 3)
                if fg_season else None,
            f"LAST{n}_FG_PCT": round(sum(fg_last) / len(fg_last), 3)
                if fg_last else None,
        })
    table.sort(key=lambda d: d["PPG_DELTA"], reverse=True)
    meta = {"source": "warehouse", "season": season, "window": n,
            "definition": "last-N scoring vs own season average, min 25 GP"}
    from ._core import season_static as _season_static
    if _season_static(season):
        # Offseason honesty, same rule as get_risers (QA F12/F18): these
        # are FINAL end-of-season form windows, not live risers.
        meta["offseason"] = True
        meta["note"] = (f"{season} is complete; these are end-of-season "
                        f"form windows, not current risers. No NBA games "
                        f"until preseason.")
    return {"tool": "get_player_risers", "ok": True,
            "rows": {"risers": table[:8], "fallers": table[-8:][::-1]},
            "meta": meta}


def _ensure_leaderboard_snapshots(con: Any) -> None:
    con.execute(
        """CREATE TABLE IF NOT EXISTS leaderboard_snapshots(
        snapshot_date VARCHAR, player VARCHAR, team VARCHAR,
        pts INTEGER, rank INTEGER)"""
    )
    cols = {r[0].lower() for r in con.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'leaderboard_snapshots'").fetchall()}
    if "season" not in cols:
        con.execute("ALTER TABLE leaderboard_snapshots ADD COLUMN season VARCHAR")
    # Backfill: rows captured before the season column existed belong to the
    # current season.
    con.execute(
        "UPDATE leaderboard_snapshots SET season = ? WHERE season IS NULL",
        [SEASON],
    )


@tool
def snapshot_leaderboard(season: str = SEASON) -> dict[str, Any]:
    """Capture today's top-50 scoring leaderboard. Idempotent per date."""
    from datetime import datetime, timezone

    from .. import store as _store

    season = str(season or SEASON).strip() or SEASON
    today = datetime.now(timezone.utc).date().isoformat()
    con = _store.connect()
    try:
        with _store.write_guard():
            _ensure_leaderboard_snapshots(con)
            hit = con.execute(
                """SELECT COUNT(*) FROM leaderboard_snapshots
                WHERE snapshot_date = ? AND season = ?""",
                [today, season],
            ).fetchone()
            if hit and hit[0]:
                return {"tool": "snapshot_leaderboard", "ok": True,
                        "rows": {"snapshot_date": today,
                                 "captured": int(hit[0]), "added": False},
                        "meta": {"source": "leaderboard_snapshots",
                                 "season": season}}
            leaders = con.execute(
                """SELECT PLAYER, TEAM, PTS, RANK FROM silver_leaders_pts
                WHERE _season = ? ORDER BY RANK ASC LIMIT 50""",
                [season],
            ).fetchall()
            if not leaders:
                return {"tool": "snapshot_leaderboard", "ok": False,
                        "error": f"no scoring leaders for {season}"}
            con.execute(
                "DELETE FROM leaderboard_snapshots WHERE snapshot_date = ? AND season = ?",
                [today, season],
            )
            for player, team, pts, rank in leaders:
                con.execute(
                    "INSERT INTO leaderboard_snapshots VALUES (?,?,?,?,?,?)",
                    [today, player, team, pts, rank, season],
                )
            captured = len(leaders)
    finally:
        con.close()
    return {"tool": "snapshot_leaderboard", "ok": True,
            "rows": {"snapshot_date": today, "captured": captured,
                     "added": True},
            "meta": {"source": "leaderboard_snapshots", "season": season}}


@tool
def get_leaderboard_deltas(season: str = SEASON, days: int = 7) -> dict[str, Any]:
    """Scoring leaderboard movers: latest snapshot vs the one from days ago."""
    from datetime import date as _date
    from datetime import timedelta as _td

    from .. import store as _store

    season = str(season or SEASON).strip() or SEASON
    try:
        days = max(1, int(days or 7))
    except (TypeError, ValueError):
        days = 7
    con = _store.connect()
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        if "leaderboard_snapshots" not in tables:
            return {"tool": "get_leaderboard_deltas", "ok": False,
                    "error": "not enough snapshots — run snapshot_leaderboard daily"}
        dates = [r[0] for r in con.execute(
            """SELECT DISTINCT snapshot_date FROM leaderboard_snapshots
            WHERE season = ? ORDER BY snapshot_date DESC""",
            [season]).fetchall()]
        if len(dates) < 2:
            return {"tool": "get_leaderboard_deltas", "ok": False,
                    "error": "not enough snapshots — run snapshot_leaderboard daily"}
        latest = dates[0]
        try:
            cutoff = _date.fromisoformat(str(latest)) - _td(days=days)
            base = next((d for d in dates[1:]
                         if _date.fromisoformat(str(d)) <= cutoff), dates[-1])
        except (TypeError, ValueError):
            base = dates[-1]
        now_rows = con.execute(
            """SELECT player, team, pts, rank FROM leaderboard_snapshots
            WHERE snapshot_date = ? AND season = ?""",
            [latest, season],
        ).fetchall()
        base_rows = con.execute(
            """SELECT player, team, pts, rank FROM leaderboard_snapshots
            WHERE snapshot_date = ? AND season = ?""",
            [base, season],
        ).fetchall()
    finally:
        con.close()
    now = {str(r[0]).lower(): r for r in now_rows}
    was = {str(r[0]).lower(): r for r in base_rows}
    climbers, fallers, new_entries = [], [], []
    for key, (player, team, pts, rank) in now.items():
        old = was.get(key)
        if old is None:
            new_entries.append({"player": player, "team": team,
                                "pts": pts, "rank": rank})
            continue
        change = (old[3] or 0) - (rank or 0)
        if change > 0:
            climbers.append({"player": player, "team": team,
                             "rank_base": old[3], "rank_now": rank,
                             "rank_change": change,
                             "pts_base": old[2], "pts_now": pts,
                             "pts_change": (pts or 0) - (old[2] or 0)})
        elif change < 0:
            fallers.append({"player": player, "team": team,
                            "rank_base": old[3], "rank_now": rank,
                            "rank_change": change,
                            "pts_base": old[2], "pts_now": pts,
                            "pts_change": (pts or 0) - (old[2] or 0)})
    climbers.sort(key=lambda d: d["rank_change"], reverse=True)
    fallers.sort(key=lambda d: d["rank_change"])
    new_entries.sort(key=lambda d: d["rank"] or 999)
    try:
        span = (_date.fromisoformat(str(latest))
                - _date.fromisoformat(str(base))).days
    except (TypeError, ValueError):
        span = 0
    return {"tool": "get_leaderboard_deltas", "ok": True,
            "rows": {"climbers": climbers[:10], "fallers": fallers[:10],
                     "new_entries": new_entries},
            "meta": {"source": "leaderboard_snapshots", "season": season,
                     "current_date": latest, "base_date": base,
                     "days_requested": days, "days_actual": span}}


_DAY = 24 * 3600
_IN_SEASON_MONTHS = frozenset({10, 11, 12, 1, 2, 3, 4, 5, 6})

# table -> (expected-cadence label, max age seconds; None = static, never stale)
FRESHNESS_RULES: dict[str, tuple[str, float | None]] = {
    "silver_scoreboard": ("daily in season", 36 * 3600),
    "silver_standings": ("daily in season", 36 * 3600),
    "silver_injuries": ("daily in season", 36 * 3600),
    "silver_leaders_pts": ("daily in season", 36 * 3600),
    "silver_leaders_ast": ("daily in season", 36 * 3600),
    "silver_leaders_reb": ("daily in season", 36 * 3600),
    "silver_leaders_stl": ("daily in season", 36 * 3600),
    "silver_leaders_blk": ("daily in season", 36 * 3600),
    "silver_leaders_dreb": ("daily in season", 36 * 3600),
    "silver_leaders_fg_pct": ("daily in season", 36 * 3600),
    "silver_player_gamelogs": ("daily in season", 36 * 3600),
    "silver_player_season": ("static seed (bbref per-game)", None),
    "silver_zone_splits": ("static seed (bbref shooting)", None),
    "silver_team_games": ("daily in season", 36 * 3600),
    "silver_boxscores": ("daily in season", 36 * 3600),
    "silver_shots": ("daily in season", 36 * 3600),
    "silver_schedule": ("daily in season", 36 * 3600),
    "silver_hustle_player": ("daily in season", 36 * 3600),
    "silver_hustle_team": ("daily in season", 36 * 3600),
    "silver_advanced": ("daily in season", 36 * 3600),
    "silver_four_factors": ("daily in season", 36 * 3600),
    "silver_clutch": ("daily in season", 36 * 3600),
    "silver_team_ratings": ("daily in season", 36 * 3600),
    "silver_on_off": ("daily in season", 36 * 3600),
    "silver_lineups": ("daily in season", 36 * 3600),
    "silver_wowy": ("daily in season", 36 * 3600),
    "silver_rosters": ("daily in season", 36 * 3600),
    "silver_salaries": ("weekly", 7 * _DAY),
    "silver_cap_players": ("weekly", 7 * _DAY),
    "silver_combine": ("weekly", 7 * _DAY),
    "silver_playoffs": ("seasonal", 400 * _DAY),
    "silver_playoff_gamelogs": ("seasonal", 400 * _DAY),
    "silver_hist_gamelogs": ("static", None),
    "silver_hist_draft": ("static", None),
    "silver_hist_hustle": ("static", None),
    "silver_hist_lineups": ("static", None),
    "silver_hist_possessions": ("static", None),
    "silver_hist_shots": ("static", None),
    "silver_hist_standings": ("static", None),
    "silver_hist_player_seasons": ("static", None),
    "silver_raptor_player": ("static", None),
    "silver_raptor_team": ("static", None),
    "silver_rapm": ("static", None),
    "silver_rapm_prior": ("static", None),
    "silver_hist_pbp": ("static", None),
    "silver_bbref_gamelogs_2024_25": ("static", None),
}


def _parse_ts(raw: object):
    from datetime import datetime as _dt, timezone as _tz

    try:
        ts = _dt.fromisoformat(str(raw).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=_tz.utc)
    return ts


def _freshness_row(table: str, rows: int, last_fetch: object,
                   now) -> dict[str, Any]:
    """One freshness panel row. Unknown timestamps stay unknown, never invented."""
    label, max_age = FRESHNESS_RULES.get(table, ("unknown", None))
    known = table in FRESHNESS_RULES
    expected, threshold = label, max_age
    if label == "daily in season" and now.month not in _IN_SEASON_MONTHS:
        expected, threshold = "weekly (offseason)", 7 * _DAY
    ts = _parse_ts(last_fetch) if last_fetch else None
    age_hours: float | None = None
    stale: bool | None = None
    if ts is not None:
        age_hours = round((now - ts).total_seconds() / 3600, 1)
        if known:
            stale = threshold is not None and age_hours * 3600 > threshold
    return {"table": table, "rows": rows,
            "last_fetch": str(last_fetch) if ts is not None else "unknown",
            "age_hours": age_hours, "expected": expected, "stale": stale}


def _warehouse_table_meta() -> list[tuple[str, int, str | None]]:
    """Read-only scan: (table, row count, max _fetched_at) per silver_* table."""
    from .. import store as _store

    import duckdb

    last: Exception | None = None
    for _ in range(5):
        try:
            con = duckdb.connect(str(_store.DB_PATH), read_only=True)
            break
        except Exception as exc:
            last = exc
            import time as _time

            _time.sleep(0.3)
    else:
        raise last or RuntimeError("warehouse read failed")
    try:
        tables = sorted(
            r[0] for r in con.execute("SHOW TABLES").fetchall()
            if r[0].startswith("silver_"))
        if not tables:
            return []
        has_ts = {}
        for t in tables:
            has_ts[t] = any(
                r[1] == "_fetched_at"
                for r in con.execute(f"PRAGMA table_info({t})").fetchall())
        parts = []
        for t in tables:
            mx = "MAX(_fetched_at)" if has_ts[t] else "CAST(NULL AS VARCHAR)"
            parts.append(f"SELECT '{t}' AS t, COUNT(*) AS n, {mx} AS mx FROM {t}")
        return [(r[0], r[1], r[2]) for r in
                con.execute(" UNION ALL ".join(parts)).fetchall()]
    finally:
        con.close()


@tool
def get_warehouse_freshness() -> dict[str, Any]:
    """Warehouse freshness panel: every silver table, row count, last fetch, stale flag."""
    from datetime import datetime as _dt, timezone as _tz

    now = _dt.now(_tz.utc)
    try:
        meta = _warehouse_table_meta()
    except Exception as exc:
        return {"tool": "get_warehouse_freshness", "ok": False,
                "error": str(exc)[:200]}
    rows = [_freshness_row(t, n, last, now) for t, n, last in meta]
    stale_n = sum(1 for r in rows if r["stale"])
    unknown_n = sum(1 for r in rows if r["stale"] is None)
    return {"tool": "get_warehouse_freshness", "ok": True, "rows": rows,
            "meta": {"tables": len(rows), "stale": stale_n, "unknown": unknown_n,
                     "in_season": now.month in _IN_SEASON_MONTHS}}
