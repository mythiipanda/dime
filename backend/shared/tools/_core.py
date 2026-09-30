
from functools import lru_cache
from typing import Any
import polars as pl

from .. import store
from ..sources.base import FetchResult

SEASON = "2025-26"



HIST_SEASON_START = "2009-10"


COVERAGE_START = HIST_SEASON_START

COVERAGE_END = SEASON


class InvalidSeasonError(Exception):

    def __init__(self, requested: object, coverage_start: str = COVERAGE_START,
                 coverage_end: str = COVERAGE_END,
                 nearest: str | None = None) -> None:
        self.requested = "" if requested is None else str(requested)
        self.coverage_start = coverage_start
        self.coverage_end = coverage_end
        self.nearest = nearest
        super().__init__(season_error_message(
            self.requested, nearest, coverage_start, coverage_end))


def season_error_message(requested: object, nearest: str | None = None,
                         coverage_start: str = COVERAGE_START,
                         coverage_end: str = COVERAGE_END) -> str:
    raw = "" if requested is None else str(requested).strip()
    shown = raw or "that"
    if nearest is None:
        return (f"I couldn't match '{shown}' to a season "
                f"(I cover {coverage_start} through {coverage_end}). "
                f"Which season did you mean?")
    return (f"The {shown} season is not in this dataset, which covers "
            f"{coverage_start} through {coverage_end}; "
            f"nearest season with data is {nearest}.")


def _canonical_parts(text: str) -> str | None:
    s = str(text or "").strip()
    if (len(s) == 7 and s[:4].isdigit() and s[4] == "-" and s[5:].isdigit()
            and int(s[5:]) == (int(s[:4]) + 1) % 100):
        return s
    return None


def _bare_year_slug(text: str) -> str | None:
    s = str(text or "").strip()
    if len(s) == 4 and s.isdigit() and s[:2] in ("19", "20"):
        start = int(s)
        return f"{start - 1}-{start % 100:02d}"
    return None


def clamp_season(season: object, coverage_start: str = COVERAGE_START,
                 coverage_end: str = COVERAGE_END) -> str:
    raw = "" if season is None else str(season).strip()
    slug = _canonical_parts(raw)
    if slug is None:
        slug = _bare_year_slug(raw)
    if slug is None:
        raise InvalidSeasonError(
            raw, coverage_start=coverage_start, coverage_end=coverage_end)
    if slug < coverage_start:
        raise InvalidSeasonError(
            slug, coverage_start=coverage_start,
            coverage_end=coverage_end, nearest=coverage_start)
    if slug > coverage_end:
        raise InvalidSeasonError(
            slug, coverage_start=coverage_start,
            coverage_end=coverage_end, nearest=coverage_end)
    return slug


TOOL_LABELS = {
    "resolve_entity": "Identifying players and teams",
    "search_nba": "Searching league coverage",
    "get_compare": "Comparing players",
    "delegate_scout": "Scouting players",
    "delegate_team": "Scouting teams",
    "delegate_league": "Scanning league data",
    "run_python": "Crunching numbers",
    "text_to_sql": "Querying the warehouse",
    "query_warehouse": "Querying the warehouse",
    "get_playoff_intel": "Pulling playoff logs",
    "get_trade_check": "Checking trade math",
    "get_trade_value": "Grading trade value",
    "get_award_race": "Ranking award races",
    "get_matchup_preview": "Previewing the matchup",
    "get_game_prediction": "Simulating the matchup",
    "get_briefing": "Briefing the slate",
    "get_lineup_stats": "Rating lineups",
    "get_rotation_check": "Checking the rotation",
    "get_streaks": "Finding streaks",
    "get_head_to_head": "Checking head-to-head history",
    "get_season_series": "Pulling the season series",
    "get_team_shot_zones": "Mapping shot zones",
    "get_warehouse_freshness": "Checking warehouse freshness",
    "get_elo_standings": "Computing ELO ratings",
    "get_impact_estimate": "Estimating impact",
    "get_player_evaluation": "Evaluating player",
    "get_player_report": "Building player report",
    "search_game_logs": "Searching game logs",
    "get_team_game_log": "Pulling the team game log",
    "pin_team_best_player": "Reading team scoring leaders",
    "pin_game_stat_followup": "Pulling the Finals game line",
}

_DESK_LABEL_OVERRIDES = {
    "run_python": "Warehouse query",
    "text_to_sql": "Warehouse query",
    "query_warehouse": "Warehouse query",
}


def tool_label(name: str, desk: bool = False) -> str:
    if not name:
        return "Checking data"
    if desk and name in _DESK_LABEL_OVERRIDES:
        return _DESK_LABEL_OVERRIDES[name]
    if name in TOOL_LABELS:
        return TOOL_LABELS[name]
    return name.replace("_", " ").strip().title() or "Checking data"

MAX_ROWS = 25



IN_SEASON_MONTHS = frozenset({10, 11, 12, 1, 2, 3, 4, 5, 6})
TTL_SCOREBOARD_PAST = 12 * 3600
TTL_GAMELOG = 6 * 3600
TTL_PBPSTATS = 24 * 3600
TTL_ROSTER = 24 * 3600
TTL_BOX = 3600
TTL_LEADERS = 12 * 3600

STAT_CATEGORIES = frozenset({
    "PTS", "REB", "AST", "STL", "BLK", "PPG", "RPG", "APG", "SPG", "BPG", "MIN", "FGM", "FGA",
    "FG_PCT", "FG3M", "FG3A", "FG3_PCT", "FTM", "FTA", "FT_PCT",
    "OREB", "DREB", "TOV", "PF", "EFF", "DD2", "TD3",
    "USG_PCT", "TOV_PCT", "TS_PCT", "SPG", "PIE",
})


def clamp_stat(stat: str) -> str:
    upper = (stat or "").strip().upper().replace("-", "_")
    aliases = {
        "3P": "FG3_PCT", "3P%": "FG3_PCT", "3PT": "FG3_PCT",
        "3PT%": "FG3_PCT", "THREE_POINT_PERCENTAGE": "FG3_PCT",
    }
    upper = aliases.get(upper, upper)
    return upper if upper in STAT_CATEGORIES else "PTS"


def clamp_scope(scope: str) -> str:
    lower = (scope or "").strip().lower()
    return lower if lower in ("player", "team") else "player"


def sample_tier(minutes: object) -> tuple[str, int]:
    try:
        mins = float(minutes or 0)
    except (TypeError, ValueError):
        return "small", 0
    est = int(round(mins * 2))
    if mins >= 100:
        return "large", est
    if mins >= 50:
        return "medium", est
    return "small", est


NICKNAMES = {
    "sga": "Shai Gilgeous-Alexander",
    "shai": "Shai Gilgeous-Alexander",
    "luka": "Luka Doncic",
    "joker": "Nikola Jokic",
    "jokic": "Nikola Jokic",
    "giannis": "Giannis Antetokounmpo",
    "bron": "LeBron James",
    "lebron": "LeBron James",
    "kd": "Kevin Durant",
    "durant": "Kevin Durant",
    "steph": "Stephen Curry",
    "curry": "Stephen Curry",
    "tatum": "Jayson Tatum",
    "embiid": "Joel Embiid",
    "dame": "Damian Lillard",
    "kyrie": "Kyrie Irving",
    "ad": "Anthony Davis",
    "kat": "Karl-Anthony Towns",
    "dbook": "Devin Booker",
    "ant": "Anthony Edwards",
    "wemby": "Victor Wembanyama",
    "celtics": "Boston Celtics",
    "lakers": "Los Angeles Lakers",
    "knicks": "New York Knicks",
    "dubs": "Golden State Warriors",
    "sixers": "Philadelphia 76ers",
}


def _norm_name(s: object) -> str:
    import unicodedata as _ud

    return "".join(
        c for c in _ud.normalize("NFKD", str(s or "").lower())
        if not _ud.combining(c)).strip()


_PLAYER_ROWS: list[dict] = []
_PLAYER_NORMS: list[str] = []


def _build_player_index() -> None:
    try:
        from nba_api.stats.static import players as _players_mod

        rows = _players_mod.get_players()
    except Exception:
        return
    try:
        norms = [_norm_name(r.get("full_name", "")) for r in rows]
    except Exception:
        return
    _PLAYER_ROWS.extend(rows)
    _PLAYER_NORMS.extend(norms)


_build_player_index()

_ID_NAME: dict[int, str] = {int(r["id"]): r.get("full_name", "")
                            for r in _PLAYER_ROWS if r.get("id")}


def attach_names(rows: object) -> object:
    if not isinstance(rows, list):
        return rows
    team_by_id: dict[int, str] = {}
    out = []
    for r in rows:
        if isinstance(r, dict):
            has_name = any(k in r for k in ("name", "player", "PLAYER",
                                            "team", "TEAM"))
            if not has_name:
                pid = r.get("player_id")
                if pid is not None:
                    try:
                        nm = _ID_NAME.get(int(pid))
                    except (TypeError, ValueError):
                        nm = None
                    if nm:
                        r = {"name": nm, **r}
                tid = r.get("team_id")
                if tid is not None and "name" not in r:
                    if not team_by_id:
                        try:
                            from nba_api.stats.static import teams as _t
                            team_by_id = {int(x["id"]): x.get(
                                "abbreviation", "") for x in
                                _t.get_teams()}
                        except Exception:
                            team_by_id = {}
                    try:
                        ab = team_by_id.get(int(tid))
                    except (TypeError, ValueError):
                        ab = None
                    if ab:
                        r = {"team": ab, **r}
        out.append(r)
    return out


def score_player_candidates(raw: str) -> list[tuple[float, dict]]:
    import difflib as _dl

    from nba_api.stats.static import players

    nq = _norm_name(raw)
    qtokens = nq.split()
    scored: dict[int, tuple[float, dict]] = {}

    def _add(pid: int, score: float, row: dict) -> None:
        if pid not in scored or scored[pid][0] < score:
            scored[pid] = (score, row)

    full = NICKNAMES.get(nq)
    if full:
        for x in players.find_players_by_full_name(full)[:2]:
            if _norm_name(x.get("full_name", "")) == _norm_name(full):
                _add(x["id"], 1.0, x)
    for x in players.find_players_by_full_name(raw)[:8]:
        xn = _norm_name(x.get("full_name", ""))
        if xn == nq:
            _add(x["id"], 1.0, x)
        elif len(nq) >= 4 and xn.startswith(nq):
            _add(x["id"], 0.85, x)
        else:
            _add(x["id"], 0.7, x)
    for fn, is_last in ((players.find_players_by_last_name, True),
                         (players.find_players_by_first_name, False)):
        try:
            for x in fn(raw)[:8]:
                idx = 1 if is_last else 0
                parts = _norm_name(x.get("full_name", "")).split()
                exact = len(parts) > idx and parts[idx] == nq
                _add(x["id"], 0.9 if exact else 0.7, x)
        except Exception:
            pass
    all_p = _PLAYER_ROWS if _PLAYER_ROWS else players.get_players()
    use_cache = bool(_PLAYER_ROWS and len(_PLAYER_NORMS) == len(_PLAYER_ROWS))
    for _i, x in enumerate(all_p):
        name = _PLAYER_NORMS[_i] if use_cache else _norm_name(x.get("full_name", ""))
        if not name or x.get("id") in scored:
            continue
        ntokens = name.split()
        nospace = nq.replace(" ", "")
        if nq and nq in name:
            _add(x["id"], 0.7, x)
        if (not scored.get(x.get("id")) or scored[x["id"]][0] < 0.8) and (
                len(nospace) >= 3
                and any(t.startswith(nospace) for t in ntokens)):
            best = max(len(nospace) / max(len(t), 1) for t in ntokens
                       if t.startswith(nospace))
            _add(x["id"], round(0.7 + 0.25 * best, 2), x)
        if (not scored.get(x.get("id"))) and (
                len(nospace) >= 3 and nospace in name.replace(" ", "")):
            _add(x["id"], 0.65, x)
        elif (len(qtokens) > 1 and len(ntokens) > 1
                and all(len(q) >= 2 and any(t.startswith(q) for t in ntokens)
                        for q in qtokens)):
            _add(x["id"], 0.6, x)
        elif nq and "".join(t[0] for t in ntokens if t) == nq.replace(" ", ""):
            _add(x["id"], 0.5, x)
    if nq:
        norms = _PLAYER_NORMS if use_cache else [_norm_name(x.get("full_name", "")) for x in all_p]
        for match in _dl.get_close_matches(nq, norms, n=5, cutoff=0.6):
            for _j, x in enumerate(all_p):
                xn = _PLAYER_NORMS[_j] if use_cache else _norm_name(x.get("full_name", ""))
                if xn == match:
                    ratio = _dl.SequenceMatcher(None, nq, match).ratio()
                    _add(x["id"], round(min(ratio, 0.89), 2), x)
                    break
    return sorted(scored.values(), key=lambda t: -t[0])


def _resolve_player_id_uncached(key: str) -> int:
    ranked = score_player_candidates(key)





    if " " not in key.strip():
        nq = _norm_name(key)
        act: list[str] = []
        for _sc, r in ranked:
            fn = r.get("full_name", "")
            if (r.get("is_active") and fn and nq
                    and nq in _norm_name(fn).split()
                    and fn not in act):
                act.append(fn)
        if len(act) >= 2:
            names = ", ".join(act[:3])
            raise ValueError(
                f"ambiguous name '{key}' - several active players match "
                f"({names}); ask which one or use a full name")
    if ranked and ranked[0][0] >= 0.8 and (
            len(ranked) < 2 or ranked[0][0] - ranked[1][0] >= 0.05):
        return int(ranked[0][1]["id"])
    hints = ", ".join(r[1].get("full_name", "?") for r in ranked[:3])
    raise ValueError(f"unknown player: {key}" + (f" (did you mean {hints}?)" if hints else ""))


_coerce_player_id_cached = lru_cache(maxsize=2048)(_resolve_player_id_uncached)


class PlayerNameResolutionUnavailable(ValueError):

    gap_kind = "profile/name_resolution_unavailable"

    def __init__(self, subject: object, detail: str = "") -> None:
        self.subject = str(subject)
        message = (f"unknown player: {self.subject}; "
                   f"profile/name_resolution unavailable for {self.subject!r}")
        if detail:
            message += f": {detail}"
        super().__init__(message)


def coerce_player_id(value: object) -> int:
    raw = str(value).strip()
    try:
        return int(raw)
    except (TypeError, ValueError):
        pass
    key = raw.lower()





    if "-" in key or "_" in key:
        slug_tokens = [token for token in key.replace("_", "-").split("-")
                       if token]
        candidates = [" ".join(slug_tokens)]
        if len(slug_tokens) >= 2:
            candidates.append(" ".join([*slug_tokens[1:], slug_tokens[0]]))
        for candidate in candidates:
            ranked = score_player_candidates(candidate)
            if ranked and _norm_name(ranked[0][1].get("full_name", "")) == _norm_name(candidate):
                return int(ranked[0][1]["id"])
    try:
        resolved = _coerce_player_id_cached(key)




        try:
            has_logs = store.connect(read_only=True).execute(
                "SELECT count(*) n FROM silver_player_gamelogs WHERE Player_ID=? AND _season=?",
                [resolved, SEASON]).fetchone()[0]
            if not has_logs:
                matches = store.connect(read_only=True).execute(
                    "SELECT DISTINCT s.PLAYER_ID FROM silver_player_season s "
                    "JOIN silver_player_gamelogs g ON g.Player_ID=s.PLAYER_ID AND g._season=s._season "
                    "WHERE lower(s.PLAYER)=lower(?) AND s._season=?",
                    [raw, SEASON]).fetchall()
                if len(matches) == 1:
                    return int(matches[0][0])
        except Exception:
            pass
        return resolved
    except ValueError as exc:
        msg = str(exc)
        prefix = f"unknown player: {key}"
        if msg.startswith(prefix):
            detail = msg[len(prefix):].lstrip()
            raise PlayerNameResolutionUnavailable(value, detail) from None
        raise


coerce_player_id.cache_info = _coerce_player_id_cached.cache_info  # type: ignore[attr-defined]
coerce_player_id.cache_clear = _coerce_player_id_cached.cache_clear  # type: ignore[attr-defined]


def coerce_team_id(value: object) -> int:
    raw = str(value).strip()
    try:
        return int(raw)
    except (TypeError, ValueError):
        pass
    raw = NICKNAMES.get(raw.lower(), raw)
    raw = raw.replace("-", " ").replace("_", " ")
    from nba_api.stats.static import teams

    name = raw.lower()
    all_t = teams.get_teams()
    exact = [x for x in all_t
             if name == x.get("abbreviation", "").lower()]
    if exact:
        return int(exact[0]["id"])
    found = teams.find_teams_by_full_name(raw)
    if not found:
        found = [x for x in all_t
                 if name in x.get("full_name", "").lower()]
    if not found:
        raise ValueError(f"unknown team: {value}")
    return int(found[0]["id"])


def _cache_age_s(frame) -> float | None:
    if "_fetched_at" not in frame.columns:
        return None
    try:
        vals = [v for v in frame["_fetched_at"].to_list() if v]
    except Exception:
        return None
    if not vals:
        return None
    from datetime import datetime as _dt
    from datetime import timezone as _tz

    try:
        newest = max(
            _dt.fromisoformat(str(v).replace("Z", "+00:00")) for v in vals)
    except (TypeError, ValueError):
        return None
    if newest.tzinfo is None:
        newest = newest.replace(tzinfo=_tz.utc)
    return (_dt.now(_tz.utc) - newest).total_seconds()


def is_past_game_date(game_date: str) -> bool:
    try:
        from zoneinfo import ZoneInfo
        from datetime import datetime as _dt

        day = _dt.strptime(str(game_date).strip(), "%m/%d/%Y").date()
        return day < _dt.now(ZoneInfo("America/New_York")).date()
    except (TypeError, ValueError):
        return False


def season_static(season: str) -> bool:
    import datetime as _dt

    s = str(season or "")
    if (len(s) != 7 or not s[:4].isdigit() or s[4] != "-"
            or not s[5:].isdigit()):
        return False
    end_year = 2000 + int(s[5:])
    return _dt.date.today() > _dt.date(end_year, 7, 15)


def _bound_warehouse_read(table, where, params):



    with store.write_guard():
        before = store.warehouse_identity()
        frame = store.read_frame(table, where, params)
        if store.warehouse_identity() != before:
            raise RuntimeError("warehouse identity changed during query")
        return frame, before


def _warehouse_or_live(table: str, where: str, params: list[object], fetch: Any, season: str,
    entity: str = "", limit: int = MAX_ROWS, live_first: bool = False, ttl_s: float | None = None):
    frame = None; identity = None
    if not live_first:
        frame, identity = _bound_warehouse_read(table, where, params)
        if frame is not None and frame.height > 0 and ttl_s is not None:
            age = _cache_age_s(frame)
            if age is not None and age > ttl_s: frame = None
    if frame is None or frame.height == 0:
        if season_static(season):
            frame, identity = _bound_warehouse_read(table, where, params)
            if frame is not None and frame.height > 0:
                meta = {"rows": frame.height, "cached": True, "static_season": True, **identity}
                if "_source" in frame.columns: meta.update(source=frame["_source"][0], fetched_at=frame["_fetched_at"][0])
                return frame.head(limit).to_dicts(), meta
            return [], {"source":"warehouse","static_season":True,"error":f"no seeded rows for {table} ({season}); season complete, live refetch disabled", **(identity or {})}
        live: FetchResult = fetch()
        if not live.ok or live.frame.height == 0:
            frame, identity = _bound_warehouse_read(table, where, params)
            if frame is not None and frame.height > 0:
                meta={"rows":frame.height,"cached":True,"stale":True,"live_error":live.error or "empty upstream response",**identity}
                if "_source" in frame.columns:meta.update(source=frame["_source"][0],fetched_at=frame["_fetched_at"][0])
                return frame.head(limit).to_dicts(),meta
            return [],{"source":live.meta.source,"error":live.error or "empty upstream response",**(identity or {})}
        store.save_frame(table, live, entity)
        frame, identity = _bound_warehouse_read(table, where, params)
        if frame.height == 0:
            frame=live.frame.with_columns([pl.lit(live.meta.source).alias("_source"),pl.lit(live.meta.season).alias("_season"),pl.lit(live.meta.fetched_at).alias("_fetched_at")])
            return frame.head(limit).to_dicts(),{"rows":frame.height,"cached":False,"source":live.meta.source,"fetched_at":live.meta.fetched_at,"lineage_kind":"live"}
        return frame.head(limit).to_dicts(),{"rows":frame.height,"cached":False,"source":live.meta.source,"fetched_at":live.meta.fetched_at,**identity}
    meta={"rows":frame.height,"cached":True,**(identity or {})}
    if "_source" in frame.columns:meta.update(source=frame["_source"][0],fetched_at=frame["_fetched_at"][0])
    return frame.head(limit).to_dicts(),meta
