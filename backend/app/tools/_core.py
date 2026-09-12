"""Shared warehouse-first fetch helper plus registry constants."""

from functools import lru_cache
from typing import Any
import polars as pl

from .. import store
from ..sources.base import FetchResult

SEASON = "2025-26"
MAX_ROWS = 25
TTL_SCOREBOARD_PAST = 12 * 3600
TTL_GAMELOG = 6 * 3600
TTL_PBPSTATS = 24 * 3600
TTL_ROSTER = 24 * 3600
TTL_BOX = 3600
TTL_LEADERS = 12 * 3600

STAT_CATEGORIES = frozenset({
    "PTS", "REB", "AST", "STL", "BLK", "MIN", "FGM", "FGA",
    "FG_PCT", "FG3M", "FG3A", "FG3_PCT", "FTM", "FTA", "FT_PCT",
    "OREB", "DREB", "TOV", "PF", "EFF", "DD2", "TD3",
    "USG_PCT", "TOV_PCT", "PIE",
})


def clamp_season(season: object) -> str:
    import re as _re

    s = str(season or "").strip()
    if _re.fullmatch(r"20\d{2}-\d{2}", s):
        return s
    m = _re.fullmatch(r"20(\d{2})", s)
    if m:
        y = int(m.group(1))
        return f"20{y}-{y + 1:02d}" if y < 50 else f"19{y}-{y + 1:02d}"
    return SEASON


def clamp_stat(stat: str) -> str:
    upper = (stat or "").strip().upper()
    return upper if upper in STAT_CATEGORIES else "PTS"


def clamp_scope(scope: str) -> str:
    lower = (scope or "").strip().lower()
    return lower if lower in ("player", "team") else "player"


def trust_tier(minutes: object) -> tuple[str, int]:
    try:
        mins = float(minutes or 0)
    except (TypeError, ValueError):
        return "SMALL", 0
    est = int(round(mins * 2))
    if mins >= 100:
        return "TRUSTED", est
    if mins >= 50:
        return "FRAGILE", est
    return "SMALL", est


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


def score_player_candidates(raw: str) -> list[tuple[float, dict]]:
    """Scored general matcher over static players. No network.

    Exact full name, nickname map, first/last name, substring,
    token prefixes, initials, fuzzy ratio. Sorted best first.
    """
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
    # QA #59/#60: a loose SINGLE-TOKEN name must not silently pick one
    # active namesake ("James" -> LeBron, ignoring James Harden). Match
    # on whole name tokens only - fuzzy scorer noise (Jaylen Brown for
    # "lebron") is not ambiguity. Multi-word and single-active names
    # resolve as before.
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


def coerce_player_id(value: object) -> int:
    """Accept an id or a name. Names resolve through scored static matching.

    Name results are cached process-local by stripped lowercase input.
    """
    raw = str(value).strip()
    try:
        return int(raw)
    except (TypeError, ValueError):
        pass
    key = raw.lower()
    try:
        return _coerce_player_id_cached(key)
    except ValueError as exc:
        msg = str(exc)
        prefix = f"unknown player: {key}"
        if msg.startswith(prefix):
            msg = f"unknown player: {value}" + msg[len(prefix):]
        raise ValueError(msg) from None


coerce_player_id.cache_info = _coerce_player_id_cached.cache_info  # type: ignore[attr-defined]
coerce_player_id.cache_clear = _coerce_player_id_cached.cache_clear  # type: ignore[attr-defined]


def coerce_team_id(value: object) -> int:
    """Accept an id or a name. Names resolve through static tables."""
    raw = str(value).strip()
    try:
        return int(raw)
    except (TypeError, ValueError):
        pass
    raw = NICKNAMES.get(raw.lower(), raw)
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
    """True when the season is complete and its tables never change again.

    NBA seasons end in June; give a grace buffer to July 15 of the end
    year. In the 2026 offseason, 2025-26 is static: live refetch only
    multiplies blocked-endpoint timeouts without fresher data.
    """
    import datetime as _dt

    m = _re_match(r"^20(\d{2})-(\d{2})$", str(season or ""))
    if not m:
        return False
    end_year = 2000 + int(m.group(2))
    return _dt.date.today() > _dt.date(end_year, 7, 15)


def _re_match(pattern: str, text: str):
    import re as _re

    return _re.match(pattern, text)


def _warehouse_or_live(
    table: str,
    where: str,
    params: list[object],
    fetch: Any,
    season: str,
    entity: str = "",
    limit: int = MAX_ROWS,
    live_first: bool = False,
    ttl_s: float | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    frame = None
    if not live_first:
        frame = store.read_frame(table, where, params)
        if frame is not None and frame.height > 0 and ttl_s is not None:
            age = _cache_age_s(frame)
            if age is not None and age > ttl_s:
                frame = None
    if frame is None or frame.height == 0:
        if season_static(season):
            # Static season: never burn ~24s on a blocked live refetch.
            frame = store.read_frame(table, where, params)
            if frame is not None and frame.height > 0:
                meta: dict[str, Any] = {"rows": frame.height, "cached": True,
                                        "static_season": True}
                if "_source" in frame.columns:
                    meta["source"] = frame["_source"][0]
                    meta["fetched_at"] = frame["_fetched_at"][0]
                return frame.head(limit).to_dicts(), meta
            return [], {"source": "warehouse", "static_season": True,
                        "error": f"no seeded rows for {table} ({season}); "
                                 "season complete, live refetch disabled"}
        live: FetchResult = fetch()
        if not live.ok or live.frame.height == 0:
            frame = store.read_frame(table, where, params)
            if frame is not None and frame.height > 0:
                meta: dict[str, Any] = {
                    "rows": frame.height, "cached": True, "stale": True,
                    "live_error": live.error or "empty upstream response",
                }
                if "_source" in frame.columns:
                    meta["source"] = frame["_source"][0]
                    meta["fetched_at"] = frame["_fetched_at"][0]
                return frame.head(limit).to_dicts(), meta
            return [], {"source": live.meta.source,
                        "error": live.error or "empty upstream response"}
        store.save_frame(table, live, entity)
        frame = store.read_frame(table, where, params)
        if frame.height == 0:
            frame = live.frame.with_columns(
                [
                    pl.lit(live.meta.source).alias("_source"),
                    pl.lit(live.meta.season).alias("_season"),
                    pl.lit(live.meta.fetched_at).alias("_fetched_at"),
                ]
            )
        return frame.head(limit).to_dicts(), {
            "rows": frame.height, "cached": False,
            "source": live.meta.source, "fetched_at": live.meta.fetched_at,
        }
    meta: dict[str, Any] = {"rows": frame.height, "cached": True}
    if "_source" in frame.columns:
        meta["source"] = frame["_source"][0]
        meta["fetched_at"] = frame["_fetched_at"][0]
    return frame.head(limit).to_dicts(), meta
