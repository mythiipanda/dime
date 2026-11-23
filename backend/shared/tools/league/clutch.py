from collections import Counter as _Counter
from typing import Any

from langchain_core.tools import tool

from .._core import coerce_player_id, team_error_message
from ..wpa import _display_name as _wpa_name
from ._helpers import _pkg

_CLUTCH_PBP_FIRST = 2021
_CLUTCH_PBP_LAST = 2025
_CLUTCH_SECONDS_DEFAULT = 300
_CLUTCH_MARGIN_DEFAULT = 5
_CLUTCH_SEASON_TYPE_DEFAULT = "regular"
_CLUTCH_PBP_ALIAS = {"BRK": "BKN", "CHO": "CHA", "PHO": "PHX"}


def _clutch_end_year(season: object) -> int | None:
    try:
        text = str(season or "").strip()
    except Exception:
        return None
    if len(text) == 7 and text[4] == "-":
        try:
            return 2000 + int(text[5:])
        except (TypeError, ValueError):
            return None
    return None


def _clutch_seconds_of(value: object) -> tuple[int, str | None]:
    try:
        seconds = int(value)
    except (TypeError, ValueError):
        return _CLUTCH_SECONDS_DEFAULT, (
            f"clutch_seconds '{value}' invalid, using "
            f"{_CLUTCH_SECONDS_DEFAULT}")
    if seconds < 30 or seconds > 720:
        clamped = max(30, min(720, seconds))
        return clamped, f"clutch_seconds {seconds} clamped to {clamped}"
    return seconds, None


def _clutch_margin_of(value: object) -> tuple[int, str | None]:
    try:
        margin = int(value)
    except (TypeError, ValueError):
        return _CLUTCH_MARGIN_DEFAULT, (
            f"clutch_margin '{value}' invalid, using "
            f"{_CLUTCH_MARGIN_DEFAULT}")
    if margin < 1 or margin > 30:
        clamped = max(1, min(30, margin))
        return clamped, f"clutch_margin {margin} clamped to {clamped}"
    return margin, None


def _clutch_season_type_of(value: object) -> tuple[str, str | None]:
    text = str(value or "").strip().lower()
    if text in ("regular", "reg", "002"):
        return "regular", None
    if text in ("playoffs", "playoff", "post", "004"):
        return "playoffs", None
    if text in ("both", "all"):
        return "both", None
    if text == _CLUTCH_SEASON_TYPE_DEFAULT:
        return _CLUTCH_SEASON_TYPE_DEFAULT, None
    return _CLUTCH_SEASON_TYPE_DEFAULT, (
        f"season_type '{value}' invalid, using "
        f"{_CLUTCH_SEASON_TYPE_DEFAULT}")


def _clutch_prefixes(season_type: str) -> set[str]:
    if season_type == "playoffs":
        return {"004"}
    if season_type == "both":
        return {"002", "004"}
    return {"002"}


def _clutch_clock_left(clock: object) -> float | None:
    try:
        text = str(clock)
    except Exception:
        return None
    if not text.startswith("PT") or not text.endswith("S"):
        return None
    try:
        mark = text.index("M")
        return int(text[2:mark]) * 60.0 + float(text[mark + 1:-1])
    except (ValueError, AttributeError):
        return None


def _clutch_pbp_rows(season: str, prefixes: set[str]) -> list[tuple]:
    con = _pkg().store.connect(read_only=True)
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        if "silver_hist_pbp" not in tables:
            return []
        ph = ",".join("?" * len(prefixes))
        return con.execute(
            "SELECT game_id, action_number, clock, period, team_tricode,"
            " person_id, player_name, location, score_home, score_away,"
            " action_type, sub_type, description, shot_value, shot_result"
            " FROM silver_hist_pbp WHERE _season = ? AND period >= 4"
            f" AND substr(game_id, 1, 3) IN ({ph})"
            " ORDER BY game_id, action_number",
            [season, *sorted(prefixes)],
        ).fetchall()
    finally:
        con.close()


def _clutch_home_of(rows: list[tuple]) -> dict[str, str]:
    votes: dict[str, _Counter] = {}
    for r in rows:
        if (r[7] or "") == "h" and r[4]:
            votes.setdefault(str(r[0]), _Counter())[str(r[4])] += 1
    return {gid: tally.most_common(1)[0][0] for gid, tally in votes.items()
            if tally}


def _clutch_int(raw: object) -> int | None:
    try:
        if raw is None or raw == "":
            return None
        return int(str(raw))
    except (TypeError, ValueError):
        return None


def _clutch_fold(rows: list[tuple], home_of: dict[str, str],
                 seconds: int, margin: int) -> tuple[dict, dict, dict, int]:
    events: dict[str, list[tuple]] = {}
    finals: dict[str, tuple[int, int]] = {}
    scored = 0
    for r in rows:
        gid = str(r[0])
        home = home_of.get(gid)
        if home is None:
            continue
        lead = finals.get(gid)
        pending: tuple[int, int] | None = None if lead is None else lead
        sh = _clutch_int(r[8])
        sa = _clutch_int(r[9])
        if sh is not None and sa is not None:
            pending = (sh, sa)
        left = _clutch_clock_left(r[2])
        if pending is not None and left is not None:
            if left <= seconds and abs(pending[0] - pending[1]) <= margin:
                events.setdefault(gid, []).append((r, pending))
                scored += 1
        if sh is not None and sa is not None:
            finals[gid] = (sh, sa)
    return events, finals, home_of, scored


def _clutch_points(action: object, sub: object, desc: object,
                   value: object, result: object) -> tuple[int, int, int]:
    if str(action) == "Made Shot":
        try:
            pts = int(value or 0)
        except (TypeError, ValueError):
            pts = 0
        return pts, 1, 1 if pts == 3 else 0
    if str(action) == "Free Throw":
        if str(desc or "").startswith("MISS"):
            return 0, 0, 0
        return 1, 0, 0
    return 0, 0, 0


def _clutch_is_home(loc: object, tri: object, home: str) -> bool | None:
    if (loc or "") == "h":
        return True
    if (loc or "") == "v":
        return False
    if tri:
        return str(tri) == home
    return None


def _clutch_state(signed: int) -> str:
    if signed > 0:
        return "ahead"
    if signed < 0:
        return "behind"
    return "tied"


def _clutch_player_teams(events: dict[str, list]) -> dict[tuple[str, str], str]:
    per: dict[tuple[str, str], _Counter] = {}
    for gid, evts in events.items():
        for r, _ in evts:
            pid = r[5]
            if pid is None or pid == 0:
                continue
            if r[4]:
                per.setdefault((gid, str(pid)), _Counter())[str(r[4])] += 1
    return {key: tally.most_common(1)[0][0] for key, tally in per.items()
            if tally}


def _clutch_shot_slot(r: tuple) -> tuple[int, int, int, int, int, int, int]:
    action = str(r[10])
    pts, fgm, fg3m = _clutch_points(r[10], r[11], r[12], r[13], r[14])
    fga = 1 if action in ("Made Shot", "Missed Shot") else 0
    if action == "Missed Shot":
        fgm = 0
        fg3m = 0
    fg3a = 1 if _clutch_int(r[13]) == 3 and fga else 0
    ftm = fta = 0
    if action == "Free Throw":
        fta = 1
        ftm = 1 if pts else 0
    return pts, fgm, fga, fg3m, fg3a, ftm, fta


def _clutch_slot_credit(slot: dict[str, Any], r: tuple) -> None:
    pts, fgm, fga, fg3m, fg3a, ftm, fta = _clutch_shot_slot(r)
    slot["pts"] += pts
    slot["fgm"] += fgm
    slot["fga"] += fga
    slot["fg3m"] += fg3m
    slot["fg3a"] += fg3a
    slot["ftm"] += ftm
    slot["fta"] += fta


def _clutch_empty_slot(label: str, team: str) -> dict[str, Any]:
    return {"label": label, "team": team, "gp_set": set(),
            "w": 0, "l": 0, "pts": 0, "fgm": 0, "fga": 0,
            "fg3m": 0, "fg3a": 0, "ftm": 0, "fta": 0}


def _clutch_player_totals(events: dict[str, list], teams: dict, names_out: dict):
    agg: dict[str, dict[str, Any]] = {}
    game_of: dict[str, set[str]] = {}
    for gid, evts in events.items():
        for r, _ in evts:
            pid = r[5]
            if pid is None or pid == 0:
                continue
            key = str(pid)
            tri = teams.get((gid, key), "")
            if not tri and r[4]:
                tri = str(r[4])
            label = _wpa_name(pid, str(r[6] or key))
            names_out[key] = label
            if key not in agg:
                agg[key] = _clutch_empty_slot(label, tri)
            _clutch_slot_credit(agg[key], r)
            game_of.setdefault(key, set()).add(gid)
    return agg, game_of


def _clutch_player_records(teams: dict, home_of: dict, finals: dict,
                           events: dict[str, list]) -> tuple[dict, dict]:
    won: dict[str, int] = {}
    lost: dict[str, int] = {}
    for (gid, key), tri in teams.items():
        if gid not in events:
            continue
        home = home_of.get(gid)
        final = finals.get(gid)
        if home is None or final is None or not tri:
            continue
        if (final[0] > final[1]) == (tri == home):
            won[key] = won.get(key, 0) + 1
        else:
            lost[key] = lost.get(key, 0) + 1
    return won, lost


def _clutch_shooting_row(fga: int, fgm: int, fg3a: int, fg3m: int) -> dict:
    return {"FGA": fga, "FG_PCT": round(fgm / fga, 3) if fga else 0.0,
            "FG3M": fg3m, "FG3A": fg3a,
            "FG3_PCT": round(fg3m / fg3a, 3) if fg3a else 0.0}


def _clutch_team_totals(events: dict[str, list], home_of: dict,
                        finals: dict):
    team_agg: dict[str, dict[str, Any]] = {}
    team_games: dict[str, set[str]] = {}
    team_wins: dict[str, int] = {}
    team_losses: dict[str, int] = {}
    for gid, evts in events.items():
        seen: set[str] = set()
        for r, _ in evts:
            tri = str(r[4] or "")
            if not tri:
                continue
            slot = team_agg.setdefault(
                tri, {"pts": 0, "fgm": 0, "fga": 0, "fg3m": 0, "fg3a": 0,
                      "ftm": 0, "fta": 0})
            _clutch_slot_credit(slot, r)
            seen.add(tri)
        for tri in seen:
            team_games.setdefault(tri, set()).add(gid)
        _clutch_team_records(seen, home_of.get(gid), finals.get(gid),
                             team_wins, team_losses)
    return team_agg, team_games, team_wins, team_losses


def _clutch_team_records(seen: set[str], home: str | None,
                         final: tuple[int, int] | None,
                         team_wins: dict[str, int],
                         team_losses: dict[str, int]) -> None:
    if home is None or final is None:
        return
    home_won = final[0] > final[1]
    for tri in seen:
        if (tri == home) == home_won:
            team_wins[tri] = team_wins.get(tri, 0) + 1
        else:
            team_losses[tri] = team_losses.get(tri, 0) + 1


def _clutch_players(agg: dict, game_of: dict, names: dict,
                    won: dict, lost: dict) -> list[dict[str, Any]]:
    players = []
    for key, slot in agg.items():
        players.append({
            "PLAYER_ID": int(key) if key.isdigit() else key,
            "PLAYER_NAME": names.get(key, slot["label"]),
            "TEAM_ABBREVIATION": slot["team"],
            "GP": len(game_of.get(key, set())),
            "W": won.get(key, 0), "L": lost.get(key, 0),
            "PTS": slot["pts"],
            "FGM": slot["fgm"],
            **_clutch_shooting_row(slot["fga"], slot["fgm"],
                                   slot["fg3a"], slot["fg3m"]),
            "FTM": slot["ftm"], "FTA": slot["fta"],
            "PLUS_MINUS": None,
        })
    return players


def _clutch_squads(team_agg: dict, team_games: dict, team_wins: dict,
                   team_losses: dict) -> list[dict[str, Any]]:
    squads = []
    for tri, slot in team_agg.items():
        squads.append({
            "TEAM_ABBREVIATION": tri,
            "GP": len(team_games.get(tri, set())),
            "W": team_wins.get(tri, 0), "L": team_losses.get(tri, 0),
            "PTS": slot["pts"],
            "FGM": slot["fgm"],
            **_clutch_shooting_row(slot["fga"], slot["fgm"],
                                   slot["fg3a"], slot["fg3m"]),
            "FTM": slot["ftm"], "FTA": slot["fta"],
            "PLUS_MINUS": None,
        })
    return squads


def _clutch_hist_meta(season: str, seconds: int, margin: int,
                      season_type: str, games: int,
                      scored: int) -> dict[str, Any]:
    return {"source": "warehouse:silver_hist_pbp", "season": season,
            "clutch_definition": {"seconds": seconds, "margin": margin,
                                  "season_type": season_type},
            "games": games, "clutch_events": scored,
            "coverage": "clutch events use the score before each play; "
                        "wins follow the final score of games with a clutch "
                        "appearance; plus-minus needs on-court lineups and "
                        "is not derivable from play-by-play"}


def _derive_hist_clutch(season: str, scope: str, seconds: int, margin: int,
                        season_type: str) -> tuple[list | None, dict]:
    rows = _clutch_pbp_rows(season, _clutch_prefixes(season_type))
    if not rows:
        return None, {"source": "warehouse:silver_hist_pbp",
                      "season": season,
                      "error": f"no play-by-play coverage for season {season}"}
    home_of = _clutch_home_of(rows)
    events, finals, _, scored = _clutch_fold(rows, home_of, seconds, margin)
    if not events:
        return [], {"source": "warehouse:silver_hist_pbp", "season": season,
                    "clutch_definition": {"seconds": seconds, "margin": margin,
                                          "season_type": season_type},
                    "games": 0, "clutch_events": 0}
    if scope == "team":
        team_agg, team_games, team_wins, team_losses = _clutch_team_totals(
            events, home_of, finals)
        meta = _clutch_hist_meta(season, seconds, margin, season_type,
                                 len(events), scored)
        return _clutch_squads(team_agg, team_games, team_wins,
                              team_losses), meta
    teams = _clutch_player_teams(events)
    names: dict[str, str] = {}
    agg, game_of = _clutch_player_totals(events, teams, names)
    won, lost = _clutch_player_records(teams, home_of, finals, events)
    meta = _clutch_hist_meta(season, seconds, margin, season_type,
                             len(events), scored)
    return _clutch_players(agg, game_of, names, won, lost), meta


def _clutch_row_common(row: dict[str, Any]) -> dict[str, Any]:
    return {"GP": row.get("GP"), "W": row.get("W"), "L": row.get("L"),
            "PTS": row.get("PTS"), "FG_PCT": row.get("FG_PCT"),
            "FG3_PCT": row.get("FG3_PCT"), "PLUS_MINUS": row.get("PLUS_MINUS")}


def _clutch_player_row(row: dict[str, Any]) -> dict[str, Any]:
    return {"PLAYER_ID": row.get("PLAYER_ID"),
            "PLAYER_NAME": row.get("PLAYER_NAME"),
            **_clutch_row_common(row)}


def _clutch_team_row(row: dict[str, Any]) -> dict[str, Any]:
    return {"TEAM_ABBREVIATION": row.get("TEAM_ABBREVIATION"),
            **_clutch_row_common(row)}


def _clutch_slim(scope: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    shape = _clutch_team_row if scope == "team" else _clutch_player_row
    return sorted((shape(r) for r in rows),
                  key=lambda d: (d.get("PTS") or 0), reverse=True)


def _clutch_team_abbr(value: object) -> str | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        from nba_api.stats.static import teams as _teams
        low = raw.lower()
        for t in _teams.get_teams():
            if low == str(t.get("abbreviation") or "").lower():
                return str(t.get("abbreviation")).upper()
        for t in _teams.get_teams():
            if low == str(t.get("full_name") or "").lower():
                return str(t.get("abbreviation")).upper()
        for t in _teams.get_teams():
            if low == str(t.get("nickname") or "").lower():
                return str(t.get("abbreviation")).upper()
    except Exception:
        pass
    upper = raw.upper()
    alias = {"BRK": "BKN", "CHO": "CHA", "PHO": "PHX"}
    upper = alias.get(upper, upper)
    if upper in {"ATL", "BKN", "BOS", "CHA", "CHI", "CLE", "DAL", "DEN",
                 "DET", "GSW", "HOU", "IND", "LAC", "LAL", "MEM", "MIA",
                 "MIL", "MIN", "NOP", "NYK", "OKC", "ORL", "PHI", "PHX",
                 "POR", "SAC", "SAS", "TOR", "UTA", "WAS"}:
        return upper
    return None


@tool(description='Clutch stats (last 5 min, margin 5 or less), player or team scope. '
                  'For league-wide clutch leaderboards or qualifying counts, run one '
                  'sql_exec GROUP BY over silver_clutch with GROUP_SET=\'Players\' '
                  '(the table multiplexes group sets) — never loop this tool per player.')
def get_clutch(scope: str = "player", season: str | None = None,
               player: str = "",
               clutch_seconds: int = _CLUTCH_SECONDS_DEFAULT,
               clutch_margin: int = _CLUTCH_MARGIN_DEFAULT,
               season_type: str = _CLUTCH_SEASON_TYPE_DEFAULT
               ) -> dict[str, Any]:
    pkg = _pkg()
    season = pkg.resolve_season(season)
    scope = "team" if str(scope).lower().startswith("team") else "player"
    seconds, seconds_warning = _clutch_seconds_of(clutch_seconds)
    margin, margin_warning = _clutch_margin_of(clutch_margin)
    stype, stype_warning = _clutch_season_type_of(season_type)
    warnings = [w for w in
                (seconds_warning, margin_warning, stype_warning) if w]
    year = _clutch_end_year(season)
    standard = (seconds == _CLUTCH_SECONDS_DEFAULT
                and margin == _CLUTCH_MARGIN_DEFAULT
                and stype == _CLUTCH_SEASON_TYPE_DEFAULT)
    if year is not None and _CLUTCH_PBP_FIRST <= year <= _CLUTCH_PBP_LAST:
        derived, meta = pkg._derive_hist_clutch(season, scope, seconds, margin,
                                                stype)
        if derived is None:
            return {"tool": "get_clutch", "ok": False, "rows": [],
                    "error": str(meta.get("error") or "no coverage"),
                    "meta": meta}
        if warnings:
            meta = dict(meta)
            meta["warning"] = "; ".join(warnings)
        if player and scope == "player":
            want = str(player).strip().lower()
            derived = [r for r in derived
                       if str(r.get("PLAYER_NAME") or "").strip().lower()
                       == want]
        return {"tool": "get_clutch", "ok": True,
                "rows": _clutch_slim(scope, derived)[:30], "meta": meta}
    if not standard:
        return {
            "tool": "get_clutch", "ok": False, "rows": [],
            "error": (f"custom clutch definition (last {seconds}s, margin "
                      f"{margin}) needs play-by-play, which covers "
                      f"{_CLUTCH_PBP_FIRST - 1}-{str(_CLUTCH_PBP_FIRST)[-2:]} "
                      f"through {_CLUTCH_PBP_LAST - 1}-"
                      f"{str(_CLUTCH_PBP_LAST)[-2:]} only; season {season} "
                      f"is outside that range"),
            "meta": {"season": season,
                     "clutch_definition": {"seconds": seconds,
                                           "margin": margin,
                                           "season_type": stype}},
        }
    entity = f"{scope}-clutch"
    rows, meta = pkg._warehouse_or_live(
        "silver_clutch", "_season = ? AND _entity = ?",
        [season, entity], lambda: pkg.nba_stats.clutch(scope, season), season,
        entity=entity, limit=600,
    )
    if scope == "team" and not rows:
        return {
            "tool": "get_clutch", "ok": False, "rows": [],
            "error": ("team-level clutch records are unavailable; "
                      "player clutch wins and losses cannot be aggregated"),
            "meta": meta,
        }
    if player and scope == "player":
        _want = str(player).strip().lower()
        rows = [r for r in rows
                if str(r.get("PLAYER_NAME") or "").strip().lower() == _want]
    if warnings:
        meta = dict(meta)
        meta["warning"] = "; ".join(warnings)
    slim = _clutch_slim(scope, rows)
    if not slim and year is not None and year < _CLUTCH_PBP_FIRST:
        return {"tool": "get_clutch", "ok": False, "rows": [],
                "error": (f"no clutch coverage for season {season}; "
                          f"play-by-play covers "
                          f"{_CLUTCH_PBP_FIRST - 1}-"
                          f"{str(_CLUTCH_PBP_FIRST)[-2:]} through "
                          f"{_CLUTCH_PBP_LAST - 1}-"
                          f"{str(_CLUTCH_PBP_LAST)[-2:]} and the clutch "
                          f"table covers 2025-26 only"),
                "meta": meta}
    return {"tool": "get_clutch", "ok": True, "rows": slim[:30], "meta": meta}


get_clutch_stats = get_clutch


def _split_bucket(label: str) -> dict[str, Any]:
    return {"split": label, "GP": 0, "FGM": 0, "FGA": 0, "FG_PCT": 0.0,
            "FG3M": 0, "FG3A": 0, "FG3_PCT": 0.0,
            "FTM": 0, "FTA": 0, "PTS": 0}


def _split_credit(bucket: dict[str, Any], pts: int, fgm: int, fga: int,
                  fg3m: int, fg3a: int, ftm: int, fta: int) -> None:
    bucket["PTS"] += pts
    bucket["FGM"] += fgm
    bucket["FGA"] += fga
    bucket["FG3M"] += fg3m
    bucket["FG3A"] += fg3a
    bucket["FTM"] += ftm
    bucket["FTA"] += fta


def _split_finalize(bucket: dict[str, Any]) -> None:
    fga = bucket["FGA"]
    fg3a = bucket["FG3A"]
    bucket["FG_PCT"] = round(bucket["FGM"] / fga, 3) if fga else 0.0
    bucket["FG3_PCT"] = round(bucket["FG3M"] / fg3a, 3) if fg3a else 0.0


_SPLIT_ORDER = ["overall", "ahead", "tied", "behind", "home", "away"]


def _split_definition(seconds: int, margin: int, stype: str) -> dict[str, Any]:
    return {"seconds": seconds, "margin": margin, "season_type": stype}


def _split_failure(season: str, error: str,
                   definition: dict[str, Any] | None = None) -> dict[str, Any]:
    meta: dict[str, Any] = {"season": season}
    if definition is not None:
        meta["clutch_definition"] = definition
    return {"tool": "get_situational_splits", "ok": False, "rows": {},
            "error": error, "meta": meta}


def _split_entity_id(scope: str, name: str) -> tuple[int | None, str | None]:
    if scope != "player":
        abbr = _clutch_team_abbr(name)
        return None, (None if abbr is None else abbr)
    return coerce_player_id(name), None


def _split_event_tricode(scope: str, r: tuple, gid: str, home: str | None,
                         pid: int | None, abbr: str | None,
                         fallbacks: dict) -> str | None:
    if scope == "player":
        try:
            if pid is None or int(r[5] or 0) != pid:
                return None
        except (TypeError, ValueError):
            return None
        return str(r[4] or "") or fallbacks.get((gid, str(pid)), "")
    tri_raw = _CLUTCH_PBP_ALIAS.get(str(r[4] or ""), str(r[4] or ""))
    return None if tri_raw != abbr else tri_raw


def _split_credit_event(buckets: dict[str, Any], state: str,
                        is_home: bool, r: tuple) -> None:
    pts, fgm, fga, fg3m, fg3a, ftm, fta = _clutch_shot_slot(r)
    for label in ("overall", state, "home" if is_home else "away"):
        _split_credit(buckets[label], pts, fgm, fga, fg3m, fg3a, ftm, fta)


def _split_events(scope: str, events: dict[str, list], home_of: dict,
                  pid: int | None, abbr: str | None,
                  fallbacks: dict) -> tuple[dict[str, Any], set[str], str]:
    buckets = {label: _split_bucket(label) for label in _SPLIT_ORDER}
    games: set[str] = set()
    resolved = ""
    for gid, evts in events.items():
        home = home_of.get(gid)
        for r, pending in evts:
            tri_raw = _split_event_tricode(scope, r, gid, home, pid, abbr,
                                           fallbacks)
            if tri_raw is None:
                continue
            if scope == "player" and r[6]:
                resolved = _wpa_name(pid, str(r[6]))
            is_home = _clutch_is_home(r[7], tri_raw, str(home or ""))
            if is_home is None:
                continue
            signed = pending[0] - pending[1]
            if not is_home:
                signed = -signed
            games.add(gid)
            _split_credit_event(buckets, _clutch_state(signed), is_home, r)
    return buckets, games, resolved


def _split_rows_out(scope: str, name: str, resolved: str, pid: int | None,
                    abbr: str | None, season: str,
                    buckets: dict[str, Any]) -> dict[str, Any]:
    if scope == "player":
        return {"player": resolved or name, "player_id": pid,
                "season": season,
                "splits": [buckets[label] for label in _SPLIT_ORDER]}
    return {"team": abbr, "season": season,
            "splits": [buckets[label] for label in _SPLIT_ORDER]}


@tool(description='Clutch situational splits for one player or team: score state plus venue.')
def get_situational_splits(scope: str = "player", entity: str = "",
                           season: str | None = None,
                           clutch_seconds: int = _CLUTCH_SECONDS_DEFAULT,
                           clutch_margin: int = _CLUTCH_MARGIN_DEFAULT,
                           season_type: str = _CLUTCH_SEASON_TYPE_DEFAULT
                           ) -> dict[str, Any]:
    season = _pkg().resolve_season(season)
    scope = "team" if str(scope).lower().startswith("team") else "player"
    seconds, seconds_warning = _clutch_seconds_of(clutch_seconds)
    margin, margin_warning = _clutch_margin_of(clutch_margin)
    stype, stype_warning = _clutch_season_type_of(season_type)
    warnings = [w for w in
                (seconds_warning, margin_warning, stype_warning) if w]
    definition = _split_definition(seconds, margin, stype)
    year = _clutch_end_year(season)
    if year is None or not (_CLUTCH_PBP_FIRST <= year <= _CLUTCH_PBP_LAST):
        return _split_failure(
            season,
            (f"no play-by-play coverage for season {season}; "
             f"situational splits cover "
             f"{_CLUTCH_PBP_FIRST - 1}-"
             f"{str(_CLUTCH_PBP_FIRST)[-2:]} through "
             f"{_CLUTCH_PBP_LAST - 1}-"
             f"{str(_CLUTCH_PBP_LAST)[-2:]} only"),
            definition)
    name = str(entity or "").strip()
    if not name:
        return _split_failure(season, "pass one player or team entity")
    try:
        pid, abbr = _split_entity_id(scope, name)
    except ValueError as exc:
        return _split_failure(season, str(exc)[:160])
    if abbr is None and scope != "player":
        return _split_failure(season, team_error_message(name))
    rows = _clutch_pbp_rows(season, _clutch_prefixes(stype))
    home_of = _clutch_home_of(rows)
    events, _, _, scored = _clutch_fold(rows, home_of, seconds, margin)
    fallbacks = _clutch_player_teams(events) if scope == "player" else {}
    buckets, games, resolved = _split_events(scope, events, home_of, pid,
                                             abbr, fallbacks)
    for bucket in buckets.values():
        _split_finalize(bucket)
    buckets["overall"]["GP"] = len(games)
    if not games:
        return _split_failure(
            season, f"no clutch appearances for {name} in {season}",
            definition)
    meta: dict[str, Any] = {
        "source": "warehouse:silver_hist_pbp", "season": season,
        "clutch_definition": definition,
        "clutch_events": scored,
        "state_rule": "score state from the entity side at each play, "
                      "using the score before the play",
    }
    if warnings:
        meta["warning"] = "; ".join(warnings)
    return {"tool": "get_situational_splits", "ok": True,
            "rows": _split_rows_out(scope, name, resolved, pid, abbr, season,
                                    buckets),
            "meta": meta}
