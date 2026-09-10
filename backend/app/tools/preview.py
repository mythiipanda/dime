"""Matchup previews. Narrative brief for one scheduled game."""

import asyncio
from typing import Any

from langchain_core.tools import tool

from ._core import SEASON, clamp_season, coerce_team_id, is_past_game_date


def _abbrev(who: str) -> str:
    try:
        tid = coerce_team_id(who)
    except ValueError:
        return str(who).upper()
    from nba_api.stats.static import teams

    for t in teams.get_teams():
        if t.get("id") == tid:
            return t.get("abbreviation", str(who).upper())
    return str(who).upper()


def _id_to_abbr(tid: object, fallback: str = "") -> str:
    try:
        from nba_api.stats.static import teams

        for t in teams.get_teams():
            if t.get("id") == int(str(tid)):
                return t.get("abbreviation", fallback)
    except (TypeError, ValueError):
        pass
    return fallback


def _num(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _r1(value: object) -> float | None:
    n = _num(value)
    return round(n, 1) if n is not None else None


def _row_team_ids(row: dict[str, Any]) -> tuple[int | None, int | None]:
    home, away = None, None
    try:
        home = int(row.get("HOME_TEAM_ID"))
    except (TypeError, ValueError):
        home = None
    try:
        away = int(row.get("VISITOR_TEAM_ID"))
    except (TypeError, ValueError):
        away = None
    return home, away


def _row_abbrs(row: dict[str, Any]) -> tuple[str, str]:
    home_id, away_id = _row_team_ids(row)
    home = str(row.get("HOME_TEAM_ABBREVIATION") or "") or _id_to_abbr(home_id)
    away = str(row.get("VISITOR_TEAM_ABBREVIATION") or "") or _id_to_abbr(away_id)
    return home, away


def _scoreboard_warehouse(season: str, dates: list[str]) -> list[dict[str, Any]]:
    """Warehouse-only scoreboard rows for MM/DD/YYYY date entities.

    Read-only: never triggers the live nba_api fallback. Replacing the
    old 14-sequential-scoreboard-calls schedule scan with this one query
    took that path from 329s to under a second.
    """
    from .. import store

    entities = [f"date:{d}" for d in dates]
    con = store.connect()
    try:
        cur = con.execute(
            "SELECT _entity, GAME_ID, GAME_STATUS_ID, GAME_STATUS_TEXT,"
            " HOME_TEAM_ID, VISITOR_TEAM_ID,"
            " HOME_TEAM_ABBREVIATION, VISITOR_TEAM_ABBREVIATION,"
            " HOME_TEAM_PTS, VISITOR_TEAM_PTS,"
            " NATL_TV_BROADCASTER_ABBREVIATION, ARENA_NAME"
            " FROM silver_scoreboard WHERE _season = ? AND _entity IN ("
            + ",".join("?" for _ in entities) + ")",
            [season, *entities],
        )
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]
    except Exception:
        return []
    finally:
        try:
            con.close()
        except Exception:
            pass


def _match_pair(row: dict[str, Any], ida: int, idb: int) -> bool:
    home, away = _row_team_ids(row)
    return (home is not None and away is not None
            and {home, away} == {ida, idb})


def _entity_date(row: dict[str, Any]) -> str:
    ent = str(row.get("_entity") or "")
    return ent[5:] if ent.startswith("date:") else ""


def _pick_marquee(rows: list[dict[str, Any]], season: str) -> dict[str, Any]:
    try:
        from .league import get_standings

        srows = get_standings.invoke({"season": season}).get("rows", []) or []
    except Exception:
        srows = []
    try:
        from nba_api.stats.static import teams as _teams

        abbr_by_id = {t["id"]: t["abbreviation"] for t in _teams.get_teams()}
    except Exception:
        abbr_by_id = {}
    pct: dict[str, float] = {}
    for s in srows:
        tid = s.get("TeamID", s.get("TEAM_ID"))
        try:
            w = float(s.get("WINS"))
            lo = float(s.get("LOSSES"))
            p = w / (w + lo) if (w + lo) else 0.0
        except (TypeError, ValueError):
            p = _num(s.get("WinPCT", s.get("WINPCT"))) or 0.0
        try:
            abbr = abbr_by_id.get(int(tid), "")
        except (TypeError, ValueError):
            abbr = ""
        if abbr:
            pct[str(abbr).upper()] = p
    best = None
    best_key = None
    for i, r in enumerate(rows):
        home, away = _row_abbrs(r)
        score = pct.get(home.upper(), 0.0) + pct.get(away.upper(), 0.0)
        tv = 1 if str(r.get("NATL_TV_BROADCASTER_ABBREVIATION") or "").strip() else 0
        key = (score, tv, -i)
        if best_key is None or key > best_key:
            best_key = key
            best = r
    return best or rows[0]


def _parse_team_date(value: object):
    from datetime import datetime as _dt

    try:
        return _dt.strptime(str(value).title(), "%b %d, %Y")
    except (TypeError, ValueError):
        return None


def _parse_gamelog_date(value: object):
    from datetime import datetime as _dt

    try:
        return _dt.strptime(str(value).title(), "%b %d, %Y")
    except (TypeError, ValueError):
        pass
    try:
        return _dt.strptime(str(value).strip(), "%Y-%m-%d")
    except (TypeError, ValueError):
        return None


def _form_card(team_id: int, season: str) -> tuple[dict[str, Any], str | None]:
    # Read the table directly: the hub only surfaces a 25-row head, which
    # would corrupt the full-season record. The hub call below is just a
    # live-fallback warm-up for teams with no cached gamelog rows yet.
    from .. import store

    def _read() -> list[tuple]:
        con = store.connect()
        try:
            return con.execute(
                "SELECT GAME_DATE, WL FROM silver_team_games"
                " WHERE _season = ? AND _entity = ?",
                [season, f"team:{team_id}"],
            ).fetchall()
        except Exception:
            return []
        finally:
            try:
                con.close()
            except Exception:
                pass

    rows = _read()
    if not rows:
        from .team import get_team_hub

        try:
            get_team_hub.invoke({"team_id": team_id, "season": season})
        except Exception:
            pass
        rows = _read()
    if not rows:
        return {"note": f"no {season} games logged yet"}, None
    wl_all = [str(r[1]).upper() for r in rows if str(r[1]).upper() in ("W", "L")]
    w_all = sum(1 for x in wl_all if x == "W")
    record = f"{w_all}-{len(wl_all) - w_all}" if wl_all else None
    dated = []
    for game_date, wl in rows:
        d = _parse_team_date(game_date)
        if d is None:
            continue
        dated.append((d, str(wl).upper()))
    dated.sort(key=lambda t: t[0], reverse=True)
    if not dated:
        return {"record": record, "last10": None, "streak": None}, record
    first10 = dated[:10]
    w10 = sum(1 for _, x in first10 if x == "W")
    last10 = f"{w10}-{len(first10) - w10}"
    first = dated[0][1]
    n = 0
    for _, x in dated:
        if x == first:
            n += 1
        else:
            break
    streak = f"{first}{n}" if first in ("W", "L") else None
    return {"record": record, "last10": last10, "streak": streak}, record


def _leaders_card(abbr: str, team_id: int, season: str) -> list[dict[str, Any]]:
    from .. import store

    con = store.connect()
    try:
        try:
            rows = con.execute(
                "SELECT PLAYER, PLAYER_ID, PTS, AST, REB, GP, MIN"
                " FROM silver_leaders_pts"
                " WHERE _season = ? AND TEAM = ? ORDER BY PTS DESC LIMIT 8",
                [season, abbr],
            ).fetchall()
        except Exception:
            rows = []
        if not rows:
            try:
                rows = con.execute(
                    "SELECT PLAYER, PLAYER_ID, PTS, AST, REB, GP, MIN"
                    " FROM silver_leaders_pts"
                    " WHERE _season = ? AND TEAM_ID = ? ORDER BY PTS DESC LIMIT 8",
                    [season, team_id],
                ).fetchall()
            except Exception:
                rows = []
    finally:
        try:
            con.close()
        except Exception:
            pass
    out = []
    for name, pid, pts, ast, reb, gp, _min in rows:
        try:
            pid_int = int(pid)
        except (TypeError, ValueError):
            continue
        try:
            gp_int = int(gp or 0)
        except (TypeError, ValueError):
            gp_int = 0
        # silver_leaders_pts stores season TOTALS; per-game drives every
        # downstream number (matchup ppg, injury impact, x-factor baseline).
        div = gp_int or 1
        out.append({
            "name": str(name or ""),
            "player_id": pid_int,
            "pts": round((_num(pts) or 0.0) / div, 1),
            "ast": round((_num(ast) or 0.0) / div, 1),
            "reb": round((_num(reb) or 0.0) / div, 1),
            "gp": gp_int,
        })
    return out


def _net_card(abbr: str, season: str) -> tuple[float | None, Any]:
    try:
        from .league import get_ratings

        rows = get_ratings.invoke({"season": season}).get("rows", []) or []
    except Exception:
        return None, None
    for r in rows:
        if str(r.get("TEAM", "")).upper() == abbr.upper():
            return _num(r.get("NET_RATING")), r.get("NET_RATING_RANK")
    return None, None


def _injury_rank(out_name: str, leaders: list[dict[str, Any]]) -> int | None:
    parts = str(out_name or "").strip().split()
    last = parts[-1].lower() if parts else ""
    if not last:
        return None
    for i, lead in enumerate(leaders):
        if last in str(lead.get("name", "")).lower():
            return i + 1
    return None


async def _injuries_card(abbr: str, season: str,
                         leaders: list[dict[str, Any]]) -> dict[str, Any]:
    try:
        from .team import get_injury_impact as _tool

        res = await _tool.ainvoke({"team": abbr, "season": season})
    except Exception:
        return {"note": "injury data unavailable"}
    rows = res.get("rows", {}) or {}
    outs = []
    for name in (rows.get("out", []) or [])[:2]:
        rank = _injury_rank(str(name), leaders)
        ppg = None
        if rank is not None and 1 <= rank <= len(leaders):
            ppg = _r1(leaders[rank - 1].get("pts"))
        if rank is not None and rank <= 3:
            impact = f"top-{rank} scorer at {ppg} ppg — major offensive hole"
        elif rank is not None and rank <= 8:
            impact = f"rotation regular ({ppg} ppg) — depth gets tested"
        else:
            impact = "depth piece — next man up"
        outs.append({"name": str(name), "impact": impact})
    questionable = [str(n) for n in (rows.get("questionable", []) or [])[:3]]
    return {"out": outs, "questionable": questionable}


def _xfactor_card(leaders: list[dict[str, Any]], season: str) -> dict[str, Any]:
    from .. import store

    cands = [lead for lead in leaders[2:8] if lead.get("gp", 0) >= 10]
    best = None
    for lead in cands:
        con = store.connect()
        try:
            try:
                grows = con.execute(
                    "SELECT GAME_DATE, PTS FROM silver_player_gamelogs"
                    " WHERE _season = ? AND _entity = ?",
                    [season, f"player:{lead['player_id']}"],
                ).fetchall()
            except Exception:
                grows = []
        finally:
            try:
                con.close()
            except Exception:
                pass
        dated = []
        for game_date, pts in grows:
            d = _parse_gamelog_date(game_date)
            if d is None:
                continue
            n = _num(pts)
            if n is None:
                continue
            dated.append((d, n))
        if not dated:
            continue
        dated.sort(key=lambda t: t[0], reverse=True)
        last5 = [p for _, p in dated[:5]]
        if not last5:
            continue
        l5 = sum(last5) / len(last5)
        delta = l5 - (lead.get("pts") or 0.0)
        if best is None or delta > best[0]:
            best = (delta, lead, l5)
    if best is None:
        return {"note": "no recent gamelogs"}
    delta, lead, l5 = best
    l5r = round(l5, 1)
    sr = round(lead.get("pts") or 0.0, 1)
    dr = round(delta, 1)
    if dr >= 2.0:
        tail = " — heating up at the right time."
    elif dr <= -2.0:
        tail = " — cooling off lately."
    else:
        tail = "."
    return {
        "player": lead["name"],
        "last5_ppg": l5r,
        "season_ppg": sr,
        "delta": dr,
        "line": f"Averaging {l5r} ppg over his last 5 (season {sr})" + tail,
    }


async def _team_card(team_id: int, abbr: str, season: str) -> dict[str, Any]:
    form, record = _form_card(team_id, season)
    leaders = _leaders_card(abbr, team_id, season)
    net, net_rank = _net_card(abbr, season)
    stars = [{
        "name": lead["name"],
        "ppg": round(lead["pts"], 1),
        "apg": round(lead["ast"], 1),
        "rpg": round(lead["reb"], 1),
    } for lead in leaders[:2]]
    injuries = await _injuries_card(abbr, season, leaders)
    xfactor = _xfactor_card(leaders, season)
    return {
        "abbr": abbr,
        "team_id": team_id,
        "form": form,
        "record": record,
        "net": net,
        "net_rank": net_rank,
        "stars": stars,
        "leaders": leaders,
        "injuries": injuries,
        "xfactor": xfactor,
    }


def _build_matchups(card_a: dict[str, Any],
                    card_b: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    sa = card_a.get("stars", []) or []
    sb = card_b.get("stars", []) or []
    if sa and sb:
        out.append({"a": sa[0], "b": sb[0],
                    "angle": "best-on-best: the two leading scorers"})
    if len(sa) > 1 and len(sb) > 1:
        out.append({"a": sa[1], "b": sb[1], "angle": "secondary scoring"})
    used = {str(s.get("name", "")).lower()
            for s in (sa[:2] + sb[:2]) if s.get("name")}
    la = card_a.get("leaders", []) or []
    lb = card_b.get("leaders", []) or []
    if la and lb:
        top_a = max(la, key=lambda lead: lead.get("ast") or 0.0)
        top_b = max(lb, key=lambda lead: lead.get("ast") or 0.0)
        if (str(top_a.get("name", "")).lower() not in used
                and str(top_b.get("name", "")).lower() not in used):
            out.append({
                "a": {"name": top_a["name"], "ppg": round(top_a["pts"], 1),
                      "apg": round(top_a["ast"], 1), "rpg": round(top_a["reb"], 1)},
                "b": {"name": top_b["name"], "ppg": round(top_b["pts"], 1),
                      "apg": round(top_b["ast"], 1), "rpg": round(top_b["reb"], 1)},
                "angle": "playmaking: top distributors",
            })
    return out


def _side_label(abbr: str, rec: str | None, net: float | None) -> str:
    inner: list[str] = []
    if rec:
        inner.append(rec)
    if net is not None:
        inner.append(f"net {net:+.1f}")
    return f"{abbr} ({', '.join(inner)})" if inner else abbr


def _why_watch(away_abbr: str, home_abbr: str, date: str,
               card_a: dict[str, Any], card_b: dict[str, Any],
               matchups: list[dict[str, Any]]) -> str:
    s1 = (f"{_side_label(away_abbr, card_a.get('record'), card_a.get('net'))}"
          f" visit {_side_label(home_abbr, card_b.get('record'), card_b.get('net'))}"
          f" on {date}.")
    if matchups:
        m1 = matchups[0]
        s2 = (f"Headliner: {m1['a'].get('name')} ({m1['a'].get('ppg')} ppg)"
              f" vs {m1['b'].get('name')} ({m1['b'].get('ppg')} ppg).")
    else:
        s2 = "No star matchup data available for this one."
    xfa = card_a.get("xfactor", {}) or {}
    xfb = card_b.get("xfactor", {}) or {}
    pick = xfa if xfa.get("player") else (xfb if xfb.get("player") else None)
    if pick:
        s3 = f"X-factor: {pick.get('player')} — {pick.get('line')}"
    else:
        outs: list[str] = []
        for card in (card_a, card_b):
            inj = card.get("injuries", {}) or {}
            for o in (inj.get("out", []) or []):
                if isinstance(o, dict) and o.get("name"):
                    outs.append(f"{o['name']} ({card.get('abbr')}: {o.get('impact')})")
        if outs:
            s3 = f"Injury watch: {'; '.join(outs[:2])}."
        elif len(matchups) > 1:
            s3 = f"{matchups[1].get('angle', 'bench play')} decides the margins."
        else:
            s3 = "The bench minutes decide the margins."
    return f"{s1} {s2} {s3}"


def _err(message: str) -> dict[str, Any]:
    return {"tool": "get_matchup_preview", "ok": False, "error": message}


def _already_played(row: dict[str, Any], resolved: str,
                    season: str) -> dict[str, Any]:
    from datetime import datetime as _dt

    gid = row.get("GAME_ID")
    home_abbr, away_abbr = _row_abbrs(row)
    if not home_abbr:
        home_abbr = _abbrev(str(row.get("HOME_TEAM_ID", "")))
    if not away_abbr:
        away_abbr = _abbrev(str(row.get("VISITOR_TEAM_ID", "")))
    hp = _num(row.get("HOME_TEAM_PTS"))
    ap = _num(row.get("VISITOR_TEAM_PTS"))
    score = None
    if hp is not None and ap is not None:
        try:
            winner = away_abbr if ap > hp else home_abbr
        except TypeError:
            winner = home_abbr
        score = f"{int(ap)}-{int(hp)} ({winner})"
    try:
        _dt.strptime(resolved.strip(), "%m/%d/%Y")
        date = resolved.strip()
    except (TypeError, ValueError):
        date = resolved
    return {
        "tool": "get_matchup_preview", "ok": True,
        "rows": {
            "already_played": True,
            "game_id": gid,
            "date": date,
            "matchup": f"{away_abbr} @ {home_abbr}",
            "score": score,
            "suggestion": "This one already tipped off — call get_recap"
                          f" with game_id {gid} for the post-game recap.",
        },
        "meta": {"season": season, "source": "warehouse"},
    }


@tool
async def get_matchup_preview(a: str = "", b: str = "",
                              game_date: str = "",
                              season: str = SEASON) -> dict[str, Any]:
    """Narrative preview of a scheduled NBA game: recent form, key player matchups, injury impact, x-factors, why-watch. Pass two team names/abbrevs/ids, or a date (MM/DD/YYYY) to preview that day's marquee game. Never predicts scores."""
    from datetime import datetime as _dt

    season = clamp_season(season)
    a = str(a or "").strip()
    b = str(b or "").strip()
    game_date = str(game_date or "").strip()

    from .team import get_games_on_date

    row: dict[str, Any] | None = None
    resolved = ""
    live_used = False

    if game_date:
        try:
            _dt.strptime(game_date, "%m/%d/%Y")
        except (TypeError, ValueError):
            return _err("game_date must be MM/DD/YYYY")
        # Warehouse first: the scoreboard table is authoritative for cached
        # dates. Exactly one live call, only when the date was never cached.
        rows = _scoreboard_warehouse(season, [game_date])
        if not rows:
            try:
                rows = get_games_on_date.invoke(
                    {"game_date": game_date,
                     "season": season}).get("rows", []) or []
                live_used = True
            except Exception:
                rows = []
        if a and b:
            try:
                ida = coerce_team_id(a)
            except ValueError:
                return _err(f"unknown team: {a}")
            try:
                idb = coerce_team_id(b)
            except ValueError:
                return _err(f"unknown team: {b}")
            for r in rows:
                home, away = _row_team_ids(r)
                if {home, away} == {ida, idb}:
                    row = r
                    break
            if row is None:
                return _err(f"{_abbrev(a)} and {_abbrev(b)}"
                            f" do not play on {game_date}")
            resolved = game_date
        elif a or b:
            who = a or b
            try:
                tid = coerce_team_id(who)
            except ValueError:
                return _err(f"unknown team: {who}")
            for r in rows:
                home, away = _row_team_ids(r)
                if tid in (home, away):
                    row = r
                    break
            if row is None:
                return _err(f"{_abbrev(who)} does not play on {game_date}")
            resolved = game_date
        else:
            if not rows:
                return _err(f"no games scheduled on {game_date}")
            row = _pick_marquee(rows, season)
            resolved = game_date
    elif a and b:
        try:
            ida = coerce_team_id(a)
        except ValueError:
            return _err(f"unknown team: {a}")
        try:
            idb = coerce_team_id(b)
        except ValueError:
            return _err(f"unknown team: {b}")
        from datetime import timedelta as _td
        from zoneinfo import ZoneInfo

        now = _dt.now(ZoneInfo("America/New_York"))
        days = [(now + _td(days=i)).strftime("%m/%d/%Y") for i in range(14)]
        # One warehouse query over the whole window: the 14 sequential
        # scoreboard calls this replaced took 329s in a smoke test.
        cands = sorted(
            (r for r in _scoreboard_warehouse(season, days)
             if _match_pair(r, ida, idb)),
            key=_entity_date,
        )
        if cands:
            row = cands[0]
            resolved = _entity_date(row) or days[0]
        if row is None:
            return _err(f"no scheduled {_abbrev(a)} vs {_abbrev(b)}"
                        " in the next 14 days")
    else:
        return _err("pass two teams (a, b) or a game_date")

    if row is None:
        return _err("pass two teams (a, b) or a game_date")
    if (is_past_game_date(resolved)
            or str(row.get("GAME_STATUS_TEXT") or "") == "Final"
            or str(row.get("GAME_STATUS_ID") or "") == "3"):
        return _already_played(row, resolved, season)

    home_id, away_id = _row_team_ids(row)
    home_abbr, away_abbr = _row_abbrs(row)
    if home_id is None or away_id is None:
        return _err("scoreboard row missing team ids")
    if not home_abbr:
        home_abbr = _abbrev(str(home_id))
    if not away_abbr:
        away_abbr = _abbrev(str(away_id))

    # The two team cards are independent warehouse reads; run them together.
    card_away, card_home = await asyncio.gather(
        _team_card(away_id, away_abbr, season),
        _team_card(home_id, home_abbr, season),
    )
    matchups = _build_matchups(card_away, card_home)
    why = _why_watch(away_abbr, home_abbr, resolved,
                     card_away, card_home, matchups)
    return {
        "tool": "get_matchup_preview", "ok": True,
        "rows": {
            "game": {
                "game_id": row.get("GAME_ID"),
                "date": resolved,
                "home": home_abbr,
                "away": away_abbr,
                "arena": row.get("ARENA_NAME"),
            },
            "form": {"away": card_away.get("form", {}),
                     "home": card_home.get("form", {})},
            "matchups": matchups,
            "injuries": {"away": card_away.get("injuries", {}),
                         "home": card_home.get("injuries", {})},
            "xfactors": {"away": card_away.get("xfactor", {}),
                         "home": card_home.get("xfactor", {})},
            "why_watch": why,
        },
        "meta": {
            "season": season,
            "source": "nba_api+warehouse" if live_used else "warehouse",
            "note": "for head-to-head situational splits call get_matchup_splits;"
                    " no score predictions by design",
        },
    }
