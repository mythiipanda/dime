
from functools import lru_cache
from typing import Any
import polars as pl

from .. import store
from ..sources.base import FetchResult

HIST_SEASON_START = "2009-10"

COVERAGE_START = HIST_SEASON_START

COVERAGE_END: str | None = None

_LAST_SEASON_KEY: tuple | None = None
_LAST_SEASON_VALUE: str | None = None

def last_completed_season() -> str | None:
    global _LAST_SEASON_KEY, _LAST_SEASON_VALUE
    try:
        stat = store.DB_PATH.stat()
        key = (str(store.DB_PATH.resolve()), stat.st_mtime_ns, stat.st_size)
    except OSError:
        return None
    if _LAST_SEASON_KEY == key:
        return _LAST_SEASON_VALUE
    try:
        seasons = store.completed_seasons_across_tables()
    except Exception:
        return None
    if not seasons:
        return None
    cal = calendar_last_completed_season()
    done = [s for s in seasons if s <= cal] if cal else seasons
    value = done[-1] if done else seasons[-1]
    _LAST_SEASON_KEY = key
    _LAST_SEASON_VALUE = value
    return value

def last_completed_season_cache_clear() -> None:
    global _LAST_SEASON_KEY, _LAST_SEASON_VALUE
    _LAST_SEASON_KEY = None
    _LAST_SEASON_VALUE = None

_DATA_SEASON_KEY: tuple | None = None
_DATA_SEASON_VALUE: str | None = None

def warehouse_max_season() -> str | None:
    global _DATA_SEASON_KEY, _DATA_SEASON_VALUE
    try:
        stat = store.DB_PATH.stat()
        key = (str(store.DB_PATH.resolve()), stat.st_mtime_ns, stat.st_size)
    except OSError:
        return None
    if _DATA_SEASON_KEY == key:
        return _DATA_SEASON_VALUE
    try:
        seasons = store.completed_seasons_across_tables()
    except Exception:
        return None
    valid = [s for s in seasons if _canonical_parts(s) is not None]
    if not valid:
        return None
    value = valid[-1]
    _DATA_SEASON_KEY = key
    _DATA_SEASON_VALUE = value
    return value

def completed_season_for_date(day: object) -> str | None:
    try:
        year = int(day.year)
        month = int(day.month)
    except Exception:
        return None
    if month < 1 or month > 12:
        return None
    start = year - 1 if month >= 7 else year - 2
    return f"{start}-{(start + 1) % 100:02d}"

def current_season(today: object = None) -> str | None:
    if today is None:
        import datetime as _dt

        today = _dt.date.today()
    try:
        year = int(today.year)
        month = int(today.month)
    except Exception:
        return None
    if month < 1 or month > 12:
        return None
    start = year if month >= 7 else year - 1
    return f"{start}-{(start + 1) % 100:02d}"


def calendar_last_completed_season(today: object = None) -> str | None:
    if today is None:
        import datetime as _dt

        today = _dt.date.today()
    return completed_season_for_date(today)

def resolve_season(season: object | None = None,
                   table: str | None = None) -> str | None:
    text = "" if season is None else str(season).strip()
    if text:
        slug = _canonical_parts(text) or _bare_year_slug(text)
        return slug if slug is not None else text
    if table:
        from shared.coverage import table_max_season
        covered = table_max_season(table)
        if covered is not None:
            return covered
    return last_completed_season()

def coverage_end() -> str:
    return warehouse_max_season() or last_completed_season() or COVERAGE_START

class InvalidSeasonError(Exception):

    def __init__(self, requested: object, coverage_start: str = COVERAGE_START,
                 coverage_end: str | None = None,
                 nearest: str | None = None) -> None:
        if coverage_end is None:
            coverage_end = warehouse_max_season() or last_completed_season() or coverage_start
        self.requested = "" if requested is None else str(requested)
        self.coverage_start = coverage_start
        self.coverage_end = coverage_end
        self.nearest = nearest
        super().__init__(season_error_message(
            self.requested, nearest, coverage_start, coverage_end))

def season_error_message(requested: object, nearest: str | None = None,
                         coverage_start: str = COVERAGE_START,
                         coverage_end: str | None = None) -> str:
    if coverage_end is None:
        coverage_end = warehouse_max_season() or last_completed_season() or coverage_start
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
                 coverage_end: str | None = None,
                 table: str | None = None) -> str:
    if coverage_end is None:
        coverage_end = warehouse_max_season() or last_completed_season() or coverage_start
        from shared.coverage import extend_coverage_end
        coverage_end = extend_coverage_end(coverage_end, table)
    if season is None:
        from shared.coverage import table_max_season
        derived = table_max_season(table) or last_completed_season()
        if derived is None:
            raise InvalidSeasonError(
                season, coverage_start=coverage_start,
                coverage_end=coverage_end)
        raw = derived
    else:
        raw = str(season).strip()
        if not raw:
            raise InvalidSeasonError(
                season, coverage_start=coverage_start,
                coverage_end=coverage_end)
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
    "get_draft_capital": "Checking future pick ownership",
    "get_award_race": "Ranking award races",
    "get_award_results": "Reading award results",
    "get_last_x": "Pulling recent game logs",
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
    "get_team_hub": "Building team hub",
    "get_lineups": "Pulling team lineups",
    "get_splits": "Splitting player game logs",
    "get_recap": "Pulling the game recap",
    "get_scouting_report": "Building scouting report",
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
        "POINT": "PTS", "POINTS": "PTS",
        "REBOUND": "REB", "REBOUNDS": "REB",
        "ASSIST": "AST", "ASSISTS": "AST",
        "STEAL": "STL", "STEALS": "STL",
        "BLOCK": "BLK", "BLOCKS": "BLK",
    }
    upper = aliases.get(upper, upper)
    if upper not in STAT_CATEGORIES:
        raise ValueError(f"unknown stat_category: {stat!r}")
    return upper

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

    return " ".join("".join(
        c for c in _ud.normalize("NFKD", str(s or "").lower())
        if c.isalnum() or c == " ").split())

_PLAYER_ROWS: list[dict] = []
_PLAYER_NORMS: list[str] = []

def _warehouse_player_rows(known_ids: set[int]) -> list[dict]:
    rows: list[dict] = []
    try:
        con = store.read_connect()
    except Exception:
        return rows
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        salary_sources = [t for t in ("silver_salaries", "silver_contracts")
                          if t in tables]
        active_ids: set[int] = set()
        for table in salary_sources:
            columns = {r[1] for r in con.execute(
                f"PRAGMA table_info({table})").fetchall()}
            if "PLAYER_ID" not in columns or "PLAYER_NAME" not in columns:
                continue
            for pid, name in con.execute(
                    f"SELECT DISTINCT PLAYER_ID, PLAYER_NAME FROM {table}"
                    " WHERE PLAYER_ID IS NOT NULL").fetchall():
                active_ids.add(int(pid))
                if int(pid) not in known_ids:
                    rows.append({"id": int(pid), "full_name": str(name or ""),
                                 "_active": True})
        try:
            from ..contracts import warehouse_player_ids

            for rec in warehouse_player_ids(con):
                pid = rec.get("PLAYER_ID")
                if pid is None or int(pid) in known_ids:
                    continue
                if any(int(r["id"]) == int(pid) for r in rows):
                    continue
                rows.append({"id": int(pid),
                             "full_name": str(rec.get("PLAYER_NAME") or ""),
                             "_active": int(pid) in active_ids})
        except Exception:
            pass
    except Exception:
        return rows
    finally:
        try:
            con.close()
        except Exception:
            pass
    return rows

def _build_player_index() -> None:
    try:
        from nba_api.stats.static import players as _players_mod

        rows = list(_players_mod.get_players())
    except Exception:
        return
    try:
        known_ids = {int(r["id"]) for r in rows if r.get("id") is not None}
        for extra in _warehouse_player_rows(known_ids):
            active = bool(extra.pop("_active", False))
            full = extra.get("full_name", "")
            parts = full.split()
            extra["first_name"] = parts[0] if parts else ""
            extra["last_name"] = " ".join(parts[1:]) if len(parts) > 1 else ""
            extra["is_active"] = active
            rows.append(extra)
        norms = [_norm_name(r.get("full_name", "")) for r in rows]
    except Exception:
        return
    _PLAYER_ROWS.extend(rows)
    _PLAYER_NORMS.extend(norms)

_build_player_index()

_ID_NAME: dict[int, str] = {int(r["id"]): r.get("full_name", "")
                            for r in _PLAYER_ROWS if r.get("id")}

_EXACT_NAME_INDEX: dict[str, list[dict]] = {}
for _r, _n in zip(_PLAYER_ROWS, _PLAYER_NORMS):
    _EXACT_NAME_INDEX.setdefault(_n, []).append(_r)

class _CandidateScores:

    __slots__ = ("by_id",)

    def __init__(self) -> None:
        self.by_id: dict[int, tuple[float, dict]] = {}

    def add(self, pid: int, score: float, row: dict) -> None:
        current = self.by_id.get(pid)
        if current is None or current[0] < score:
            self.by_id[pid] = (score, row)

    def holds_below(self, pid: object, ceiling: float) -> bool:
        current = self.by_id.get(pid)
        return current is None or current[0] < ceiling

    def holds(self, pid: object) -> bool:
        return pid not in self.by_id

def _indexed_player_norm(index: int, row: dict, use_cache: bool) -> str:
    if use_cache:
        return _PLAYER_NORMS[index]
    return _norm_name(row.get("full_name", ""))

def _score_nickname_matches(scores: _CandidateScores, players, nq: str) -> None:
    full = NICKNAMES.get(nq)
    if not full:
        return
    for x in players.find_players_by_full_name(full)[:2]:
        if _norm_name(x.get("full_name", "")) == _norm_name(full):
            scores.add(x["id"], 1.0, x)

def _score_full_name_matches(scores: _CandidateScores, players, raw: str,
                             nq: str) -> None:
    for x in players.find_players_by_full_name(raw)[:8]:
        xn = _norm_name(x.get("full_name", ""))
        if xn == nq:
            scores.add(x["id"], 1.0, x)
        elif len(nq) >= 4 and xn.startswith(nq):
            scores.add(x["id"], 0.85, x)
        else:
            scores.add(x["id"], 0.7, x)

def _score_surname_matches(scores: _CandidateScores, players, raw: str,
                           nq: str) -> None:
    for finder, is_last in ((players.find_players_by_last_name, True),
                            (players.find_players_by_first_name, False)):
        try:
            for x in finder(raw)[:8]:
                idx = 1 if is_last else 0
                parts = _norm_name(x.get("full_name", "")).split()
                exact = len(parts) > idx and parts[idx] == nq
                scores.add(x["id"], 0.9 if exact else 0.7, x)
        except Exception:
            pass

def _score_prefix_overlap(scores: _CandidateScores, pid: int, nospace: str,
                          ntokens: list[str], x: dict) -> None:
    if not scores.holds_below(pid, 0.8):
        return
    if len(nospace) < 3:
        return
    if not any(t.startswith(nospace) for t in ntokens):
        return
    best = max(len(nospace) / max(len(t), 1) for t in ntokens
               if t.startswith(nospace))
    scores.add(pid, round(0.7 + 0.25 * best, 2), x)

def _score_token_alias(scores: _CandidateScores, pid: int, nospace: str,
                       qtokens: list[str], ntokens: list[str], name: str,
                       x: dict) -> None:
    if scores.holds(pid) and len(nospace) >= 3 and nospace in name.replace(" ", ""):
        scores.add(pid, 0.65, x)
        return
    if (len(qtokens) > 1 and len(ntokens) > 1
            and all(len(q) >= 2 and any(t.startswith(q) for t in ntokens)
                    for q in qtokens)):
        scores.add(pid, 0.6, x)
    elif nospace and "".join(t[0] for t in ntokens if t) == nospace:
        scores.add(pid, 0.5, x)

def _score_roster_matches(scores: _CandidateScores, nq: str, qtokens: list[str],
                          all_p: list[dict], use_cache: bool) -> None:
    for index, x in enumerate(all_p):
        name = _indexed_player_norm(index, x, use_cache)
        if not name or x.get("id") in scores.by_id:
            continue
        pid = x.get("id")
        ntokens = name.split()
        nospace = nq.replace(" ", "")
        if nq and nq in name:
            scores.add(x["id"], 0.7, x)
        _score_prefix_overlap(scores, pid, nospace, ntokens, x)
        _score_token_alias(scores, pid, nospace, qtokens, ntokens, name, x)

def _score_close_matches(scores: _CandidateScores, nq: str, all_p: list[dict],
                         use_cache: bool) -> None:
    import difflib as _dl

    if not nq:
        return
    norms = (_PLAYER_NORMS if use_cache
             else [_norm_name(x.get("full_name", "")) for x in all_p])
    for match in _dl.get_close_matches(nq, norms, n=5, cutoff=0.6):
        for index, x in enumerate(all_p):
            if _indexed_player_norm(index, x, use_cache) != match:
                continue
            ratio = _dl.SequenceMatcher(None, nq, match).ratio()
            scores.add(x["id"], round(min(ratio, 0.89), 2), x)
            break

def _score_player_candidates_uncached(raw: str) -> list[tuple[float, dict]]:
    nq = _norm_name(raw)
    exact = _EXACT_NAME_INDEX.get(nq) if nq else None
    if exact is not None and len(exact) == 1:
        return [(1.0, exact[0])]
    from nba_api.stats.static import players

    scores = _CandidateScores()
    _score_nickname_matches(scores, players, nq)
    _score_full_name_matches(scores, players, raw, nq)
    _score_surname_matches(scores, players, raw, nq)
    all_p = _PLAYER_ROWS if _PLAYER_ROWS else players.get_players()
    use_cache = bool(_PLAYER_ROWS and len(_PLAYER_NORMS) == len(_PLAYER_ROWS))
    _score_roster_matches(scores, nq, nq.split(), all_p, use_cache)
    _score_close_matches(scores, nq, all_p, use_cache)
    return sorted(scores.by_id.values(), key=lambda t: -t[0])

score_player_candidates = lru_cache(maxsize=2048)(_score_player_candidates_uncached)

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
    import re as _re

    prefix_id = _re.fullmatch(r"[A-Za-z]{3}:(\d+)", raw)
    if prefix_id:
        return int(prefix_id.group(1))
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
            _vintage = last_completed_season()
            has_logs = store.connect(read_only=True).execute(
                "SELECT count(*) n FROM silver_player_gamelogs WHERE Player_ID=? AND _season=?",
                [resolved, _vintage]).fetchone()[0]
            if not has_logs:
                matches = store.connect(read_only=True).execute(
                    "SELECT DISTINCT s.PLAYER_ID FROM silver_player_season s "
                    "JOIN silver_player_gamelogs g ON g.Player_ID=s.PLAYER_ID AND g._season=s._season "
                    "WHERE lower(s.PLAYER)=lower(?) AND s._season=?",
                    [raw, _vintage]).fetchall()
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

coerce_player_id.cache_info = _coerce_player_id_cached.cache_info
coerce_player_id.cache_clear = _coerce_player_id_cached.cache_clear

_STATIC_TEAMS = (
    ("ATL", "Atlanta Hawks", 1610612737),
    ("BKN", "Brooklyn Nets", 1610612751),
    ("BOS", "Boston Celtics", 1610612738),
    ("CHA", "Charlotte Hornets", 1610612766),
    ("CHI", "Chicago Bulls", 1610612741),
    ("CLE", "Cleveland Cavaliers", 1610612739),
    ("DAL", "Dallas Mavericks", 1610612742),
    ("DEN", "Denver Nuggets", 1610612743),
    ("DET", "Detroit Pistons", 1610612765),
    ("GSW", "Golden State Warriors", 1610612744),
    ("HOU", "Houston Rockets", 1610612745),
    ("IND", "Indiana Pacers", 1610612754),
    ("LAC", "Los Angeles Clippers", 1610612746),
    ("LAL", "Los Angeles Lakers", 1610612747),
    ("MEM", "Memphis Grizzlies", 1610612763),
    ("MIA", "Miami Heat", 1610612748),
    ("MIL", "Milwaukee Bucks", 1610612749),
    ("MIN", "Minnesota Timberwolves", 1610612750),
    ("NOP", "New Orleans Pelicans", 1610612740),
    ("NYK", "New York Knicks", 1610612752),
    ("OKC", "Oklahoma City Thunder", 1610612760),
    ("ORL", "Orlando Magic", 1610612753),
    ("PHI", "Philadelphia 76ers", 1610612755),
    ("PHX", "Phoenix Suns", 1610612756),
    ("POR", "Portland Trail Blazers", 1610612757),
    ("SAC", "Sacramento Kings", 1610612758),
    ("SAS", "San Antonio Spurs", 1610612759),
    ("TOR", "Toronto Raptors", 1610612761),
    ("UTA", "Utah Jazz", 1610612762),
    ("WAS", "Washington Wizards", 1610612764),
)

def _team_alias_index() -> dict[str, list[int]]:
    index: dict[str, list[int]] = {}
    for abbr, full, team_id in _STATIC_TEAMS:
        words = full.lower().split()
        keys = {abbr.lower(), full.lower()}
        for i in range(1, len(words)):
            keys.add(" ".join(words[:i]))
            keys.add(" ".join(words[i:]))
        for key in keys:
            index.setdefault(key, []).append(team_id)
    return index

_TEAM_ABBR_ALIASES = {"brk": "bkn", "pho": "phx", "phc": "phx"}

_TEAM_ALIAS_INDEX = _team_alias_index()

_TEAM_INPUT_GUIDE = ("pass an NBA abbreviation like 'BOS', a numeric "
                     "team_id, or a full team name like 'Boston Celtics'")

_LEAGUE_SCOPE_TOKENS = {"all", "league", "nba", "every", "league-wide",
                        "league_wide", "any"}

_HISTORICAL_TEAMS = {
    "SEA": "the Seattle SuperSonics, who relocated to Oklahoma City in 2008 (use OKC)",
    "NJN": "the New Jersey Nets, who relocated to Brooklyn in 2012 (use BKN)",
    "NOH": "the New Orleans Hornets, renamed the Pelicans in 2013 (use NOP)",
    "NOK": "the New Orleans/Oklahoma City Hornets, a temporary 2005-07 relocation (use NOP)",
    "CHO": "the Charlotte Hornets, who relocated to New Orleans in 2002; "
           "the current Charlotte franchise began as the 2004-05 Bobcats (use CHA)",
    "VAN": "the Vancouver Grizzlies, who relocated to Memphis in 2001 (use MEM)",
    "SDC": "the San Diego Clippers, who relocated to Los Angeles in 1984 (use LAC)",
    "KCK": "the Kansas City Kings, who relocated to Sacramento in 1985 (use SAC)",
}

_HISTORICAL_TEAM_NAMES = {
    "seattle": "SEA", "supersonics": "SEA", "sonics": "SEA",
    "seattle supersonics": "SEA",
    "new jersey": "NJN", "new jersey nets": "NJN",
    "vancouver": "VAN", "vancouver grizzlies": "VAN",
    "charlotte bobcats": "CHO", "bobcats": "CHO",
    "new orleans hornets": "NOH",
    "new orleans oklahoma city hornets": "NOK",
    "san diego clippers": "SDC", "kansas city kings": "KCK",
    "kansas city": "KCK",
}

_TEAM_ID_ABBR = {tid: abbr for abbr, _full, tid in _STATIC_TEAMS}


def _historical_team_note(raw: str) -> str:
    key = " ".join(str(raw or "").lower().replace("-", " ")
                   .replace("_", " ").split())
    abbr = _HISTORICAL_TEAM_NAMES.get(key)
    if abbr is None and key.upper() in _HISTORICAL_TEAMS:
        abbr = key.upper()
    return _HISTORICAL_TEAMS.get(abbr or "", "")


def _suggest_teams(raw: str, limit: int = 3) -> list[str]:
    import difflib as _dl
    key = " ".join(str(raw or "").lower().replace("-", " ")
                   .replace("_", " ").split())
    if not key:
        return []
    matches = _dl.get_close_matches(key, sorted(_TEAM_ALIAS_INDEX), n=limit * 2,
                                    cutoff=0.6)
    seen = []
    for match in matches:
        for tid in _TEAM_ALIAS_INDEX.get(match, []):
            abbr = _TEAM_ID_ABBR.get(tid)
            if abbr and abbr not in seen:
                seen.append(abbr)
    return seen[:limit]


def team_error_message(value: object) -> str:
    raw = str(value or "").strip()
    key = " ".join(raw.lower().split())
    if not key or key in _LEAGUE_SCOPE_TOKENS:
        return (f"unknown team: {raw or 'empty team'} is not a team: this "
                f"tool needs one specific team ({_TEAM_INPUT_GUIDE}). For a "
                "league-wide ranking, use a leaders tool or one sql_exec "
                "over the silver_hist_* tables instead of per-team calls.")
    hist = _historical_team_note(raw)
    if hist:
        return f"{raw} is {hist}; it has no rows for current-season data"
    suggestions = _suggest_teams(raw)
    hint = (f" Closest current teams: {', '.join(suggestions)}."
            if suggestions else "")
    return f"unknown team: {value!r}.{hint} {_TEAM_INPUT_GUIDE}"


def covered_seasons(con: object, table: str) -> list[str]:
    try:
        rows = con.execute(
            f"SELECT DISTINCT _season FROM {table} ORDER BY 1").fetchall()
    except Exception:
        return []
    return [str(r[0]) for r in rows if r and r[0]]


def season_rows_error(con: object, table: str, season: str,
                      team: str = "") -> str:
    owned = con is None
    if owned:
        try:
            con = store.connect(read_only=True)
        except Exception:
            con = None
    try:
        available = covered_seasons(con, table) if con is not None else []
    finally:
        if owned and con is not None:
            try:
                con.close()
            except Exception:
                pass
    subject = f"{team} {season}" if team else str(season)
    if available:
        return (f"no rows for {subject} in {table} - "
                f"available seasons: {', '.join(available)}")
    return f"no rows for {subject} in {table}"


def _unknown_team(value: object) -> ValueError:
    return ValueError(team_error_message(value))

def _static_team_id(value: object, raw: str) -> int:
    name = " ".join(raw.lower().replace("-", " ").replace("_", " ").split())
    name = _TEAM_ABBR_ALIASES.get(name, name)
    if not name:
        raise _unknown_team(value)
    hits = _TEAM_ALIAS_INDEX.get(name, [])
    if len(hits) == 1:
        return hits[0]
    raise _unknown_team(value)

def coerce_team_id(value: object) -> int:
    raw = str(value).strip()
    try:
        return int(raw)
    except (TypeError, ValueError):
        pass
    if not raw:
        raise _unknown_team(value)
    raw = NICKNAMES.get(raw.lower(), raw)
    raw = raw.replace("-", " ").replace("_", " ")
    name = raw.lower()
    if not name.strip():
        raise _unknown_team(value)
    if len(name) < 3:
        raise _unknown_team(value)
    return _static_team_id(value, raw)


REGULAR_SEASON_GAME_PREFIX = "002"
PLAYOFF_GAME_PREFIX = "004"


def is_scope_game(game_id: object, scope: str) -> bool:
    text = str(game_id or "").strip()
    if not text.isdigit():
        return True
    if scope.startswith("playoff"):
        return text.startswith(PLAYOFF_GAME_PREFIX)
    return text.startswith(REGULAR_SEASON_GAME_PREFIX)


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

def league_games_played_baseline(season: str) -> int | None:
    season = resolve_season(season)
    if not season:
        return None
    try:
        con = store.connect(read_only=True)
        try:
            tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
            row = None
            if "silver_hist_gamelogs" in tables:
                row = con.execute(
                    "SELECT MAX(cnt) FROM (SELECT COUNT(*) AS cnt FROM "
                    "silver_hist_gamelogs WHERE _season = ? "
                    "AND season_type = 'regular-season' GROUP BY team_id)",
                    [season]).fetchone()
            elif "silver_team_games" in tables:
                row = con.execute(
                    "SELECT MAX(cnt) FROM (SELECT COUNT(DISTINCT Game_ID) AS cnt "
                    "FROM silver_team_games WHERE _season = ? GROUP BY _entity)",
                    [season]).fetchone()
        finally:
            con.close()
    except Exception:
        return None
    if not row or row[0] is None:
        return None
    return int(row[0])


def season_to_date_meta(season: str | None,
                        games_played: object = None,
                        prior_full_season: dict | None = None) -> dict[str, Any]:
    resolved = resolve_season(season)
    out: dict[str, Any] = {"season": resolved}
    try:
        gp = int(games_played) if games_played is not None else None
    except (TypeError, ValueError):
        gp = None
    baseline = league_games_played_baseline(resolved) if resolved else None
    if gp is not None:
        out["games_played"] = gp
    if baseline is not None:
        out["league_games_played_baseline"] = baseline
    if gp is not None:
        in_progress = not season_static(resolved)
        early = gp < 30
        behind = baseline is not None and gp < 0.7 * baseline
        out["small_sample"] = bool(early or behind)
        if out["small_sample"]:
            out["small_sample_reason"] = (
                "early in the season" if early and in_progress
                else "well under the league games-played baseline" if behind
                else "fewer than 30 games played")
    if prior_full_season:
        out["prior_full_season"] = prior_full_season
    return out


def warehouse_identity_meta() -> dict[str, str]:
    try:
        return store.warehouse_identity()
    except Exception:
        return {}


def _bound_warehouse_read(table, where, params):

    with store.write_guard():
        before = store.warehouse_identity()
        frame = store.read_frame_optional(table, where, params)
        if store.warehouse_identity() != before:
            raise RuntimeError("warehouse identity changed during query")
        return frame, before

def _live_fallback_marker(table: str, season: str, live: FetchResult,
                          outcome: str) -> dict[str, str]:
    return {"table": table, "requested_season": season,
            "live_source": str(live.meta.source), "outcome": outcome}

def _frame_meta(frame, identity: dict | None, base: dict) -> dict:
    meta = {**base, **(identity or {})}
    if "_source" in frame.columns:
        meta.update(source=frame["_source"][0],
                    fetched_at=frame["_fetched_at"][0])
    return meta

def _cached_season_frame(table: str, where: str, params: list[object],
                         ttl_s: float | None):
    frame, identity = _bound_warehouse_read(table, where, params)
    if frame is None or frame.height == 0 or ttl_s is None:
        return frame, identity
    age = _cache_age_s(frame)
    if age is not None and age > ttl_s:
        return None, identity
    return frame, identity

def _static_season_miss(table: str, where: str, params: list[object],
                        season: str, limit: int):
    frame, identity = _bound_warehouse_read(table, where, params)
    if frame is not None and frame.height > 0:
        meta = _frame_meta(frame, identity,
                           {"rows": frame.height, "cached": True,
                            "static_season": True})
        return frame.head(limit).to_dicts(), meta
    return [], {"source": "warehouse", "static_season": True,
                "error": (f"no seeded rows for {table} ({season}); season "
                          "complete, live refetch disabled"),
                **(identity or {})}

def _empty_live_fallback(table: str, where: str, params: list[object],
                         season: str, limit: int, live: FetchResult):
    frame, identity = _bound_warehouse_read(table, where, params)
    if frame is not None and frame.height > 0:
        meta = _frame_meta(
            frame, identity,
            {"rows": frame.height, "cached": True, "stale": True,
             "live_error": live.error or "empty upstream response",
             "live_fallback": _live_fallback_marker(
                 table, season, live, "stale")})
        return frame.head(limit).to_dicts(), meta
    return [], {"source": live.meta.source,
                "error": live.error or "empty upstream response",
                "live_fallback": _live_fallback_marker(
                    table, season, live, "empty"),
                **(identity or {})}

def _served_live_frame(frame, limit: int, live: FetchResult, table: str,
                       season: str):
    annotated = frame.with_columns([
        pl.lit(live.meta.source).alias("_source"),
        pl.lit(live.meta.season).alias("_season"),
        pl.lit(live.meta.fetched_at).alias("_fetched_at")])
    return annotated.head(limit).to_dicts(), {
        "rows": annotated.height, "cached": False,
        "source": live.meta.source, "fetched_at": live.meta.fetched_at,
        "lineage_kind": "live",
        "live_fallback": _live_fallback_marker(table, season, live, "served")}

def _live_result(table: str, where: str, params: list[object], limit: int,
                 live: FetchResult, static: bool, season: str,
                 entity: str):
    frame = None
    identity = None
    if not static:
        store.save_frame(table, live, entity)
        frame, identity = _bound_warehouse_read(table, where, params)
    if frame is not None and frame.height > 0:
        return frame.head(limit).to_dicts(), {
            "rows": frame.height, "cached": False,
            "source": live.meta.source, "fetched_at": live.meta.fetched_at,
            "live_fallback": _live_fallback_marker(
                table, season, live, "served"), **identity}
    return _served_live_frame(live.frame, limit, live, table, season)

def _warehouse_or_live(table: str, where: str, params: list[object], fetch: Any, season: str | None,
    entity: str = "", limit: int = MAX_ROWS, live_first: bool = False, ttl_s: float | None = None,
    live_on_static_miss: bool = False):
    season = resolve_season(season)
    if not season:
        return [], {"source": "warehouse",
                    "error": "warehouse has no season with data"}
    frame = None
    identity = None
    if not live_first:
        frame, identity = _cached_season_frame(table, where, params, ttl_s)
    if frame is None or frame.height == 0:
        static = season_static(season)
        if static and not live_on_static_miss:
            return _static_season_miss(table, where, params, season, limit)
        live: FetchResult = fetch()
        if not live.ok or live.frame.height == 0:
            return _empty_live_fallback(table, where, params, season, limit,
                                        live)
        return _live_result(table, where, params, limit, live, static, season,
                            entity)
    meta = _frame_meta(frame, identity, {"rows": frame.height, "cached": True})
    return frame.head(limit).to_dicts(), meta
