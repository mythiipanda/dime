"""WPA-by-play leaderboard from warehouse play-by-play only."""

from collections import Counter
from typing import Any, Union

from langchain_core.tools import tool

from .. import store
from .wpamodel import TIPOFF_SEC, seconds_remaining, win_probability

MIN_YEAR, MAX_YEAR = 2021, 2025
MIN_EVENTS_DEFAULT = 100


def season_label(end_year: int) -> str:
    return f"{end_year - 1}-{str(end_year)[-2:]}"


def clamp_season_year(value: object, fallback: int = MAX_YEAR) -> tuple[int | None, str | None]:
    try:
        year = int(str(value).strip()[:4])
    except (TypeError, ValueError, AttributeError):
        return fallback, f"season '{value}' invalid, using {fallback}"
    if year > MAX_YEAR:
        return None, None
    if year < MIN_YEAR:
        return MIN_YEAR, f"season {year} clamped to {MIN_YEAR}"
    return year, None


def clamp_limit(value: object) -> int:
    try:
        return max(1, min(25, int(value)))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 10


def clamp_min_events(value: object) -> int:
    try:
        return max(1, int(value))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return MIN_EVENTS_DEFAULT


COLUMNS = ("game_id, action_number, clock, period, team_tricode,"
           " person_id, player_name, location, score_home, score_away,"
           " action_type")


def _parse_score(raw: object) -> int | None:
    try:
        return int(str(raw))
    except (TypeError, ValueError):
        return None


def _credit(players: dict[str, dict[str, Any]], gid: str,
            evt: tuple, home: str, delta: float) -> None:
    _, _, _, _, tri, pid, name, loc, _, _, _ = evt
    if not pid or not name:
        return
    loc, tri = loc or "", tri or ""
    if loc == "h":
        is_home = True
    elif loc == "v":
        is_home = False
    elif tri:
        is_home = tri == home
    else:
        return
    signed = delta if is_home else -delta
    key = str(pid)
    entry = players.setdefault(key, {
        "player_id": pid, "player": name, "wpa": 0.0,
        "events": 0, "plus_events": 0, "minus_events": 0,
        "games": set(), "teams": Counter(),
    })
    entry["wpa"] += signed
    entry["events"] += 1
    if signed > 0:
        entry["plus_events"] += 1
    elif signed < 0:
        entry["minus_events"] += 1
    entry["games"].add(gid)
    if tri:
        entry["teams"][tri] += 1


def _score_game(gid: str, grows: list[tuple],
                players: dict[str, dict[str, Any]]) -> None:
    votes: Counter = Counter()
    for row in grows:
        if (row[7] or "") == "h" and row[4]:
            votes[str(row[4])] += 1
    if not votes:
        return
    home = votes.most_common(1)[0][0]
    seen: dict[Any, tuple] = {}
    for row in grows:
        an = row[1]
        if an not in seen:
            seen[an] = row
        elif not seen[an][10] and row[10]:
            seen[an] = row
    lead_home, lead_away = 0, 0
    before = win_probability(0, TIPOFF_SEC)
    for an in sorted(seen):
        evt = seen[an]
        sh = _parse_score(evt[8])
        sa = _parse_score(evt[9])
        if sh is not None:
            lead_home = sh
        if sa is not None:
            lead_away = sa
        sec = seconds_remaining(evt[2], evt[3])
        if sec is None:
            continue
        after = win_probability(lead_home - lead_away, sec)
        delta = after - before
        before = after
        _credit(players, gid, evt, home, delta)


def score_events(rows: list) -> dict[str, dict[str, Any]]:
    """Compact ordered rows to per-player WPA.

    Rows are (game_id, action_number, clock, period, team_tricode,
    person_id, player_name, location, score_home, score_away,
    action_type) tuples ordered by game then action. Paired details
    share an action_number, so the primary row is the one carrying an
    action_type. Score state forward-fills per game and the delta is WP
    after minus WP before from the acting team's perspective.
    """
    players: dict[str, dict[str, Any]] = {}
    game = None
    grows: list[tuple] = []
    for row in rows:
        if isinstance(row, dict):
            row = (row.get("game_id"), row.get("action_number"),
                   row.get("clock"), row.get("period"),
                   row.get("team_tricode"), row.get("person_id"),
                   row.get("player_name"), row.get("location"),
                   row.get("score_home"), row.get("score_away"),
                   row.get("action_type"))
        if row[0] != game:
            if grows:
                _score_game(str(game), grows, players)
            game, grows = row[0], [row]
        else:
            grows.append(row)
    if grows:
        _score_game(str(game), grows, players)
    return players


@tool
def get_wpa_leaders(season: Union[int, str, None] = 2025,
                     limit: Union[int, str, None] = 10,
                     min_events: Union[int, str, None] = MIN_EVENTS_DEFAULT) -> dict[str, Any]:
    """WPA-by-play leaderboard for one season. Season is an end-year clamped to 2021..2025.

    Deltas come from the fitted win-probability model before and after
    each play, credited to the acting player. Documented estimates.
    """
    warnings: list[str] = []
    year, season_warning = clamp_season_year(season)
    if season_warning:
        warnings.append(season_warning)
    if year is None:
        return {"tool": "get_wpa_leaders", "ok": False, "rows": {},
                "meta": {"requested_season": season},
                "error": f"no WPA coverage for season {season}; "
                         f"play-by-play covers end-years {MIN_YEAR}..{MAX_YEAR}"}
    try:
        raw_limit = int(limit)  # type: ignore[arg-type]
        limit_ok = True
    except (TypeError, ValueError):
        raw_limit, limit_ok = 10, False
    if not limit_ok:
        warnings.append(f"limit '{limit}' invalid, using 10")
    limit = max(1, min(25, raw_limit))
    if limit_ok and limit != raw_limit:
        warnings.append(f"limit {raw_limit} clamped to {limit}")
    try:
        raw_floor = int(min_events)  # type: ignore[arg-type]
        floor_ok = True
    except (TypeError, ValueError):
        raw_floor, floor_ok = MIN_EVENTS_DEFAULT, False
    if not floor_ok:
        warnings.append(f"min_events '{min_events}' invalid, using {MIN_EVENTS_DEFAULT}")
    floor = max(1, raw_floor)
    label = season_label(year)
    try:
        con = store.connect(read_only=True)
        try:
            tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
            if "silver_hist_pbp" not in tables:
                return {"tool": "get_wpa_leaders", "ok": False, "rows": {},
                        "meta": {"season": year},
                        "error": "warehouse table missing: silver_hist_pbp"}
            rows = con.execute(
                f"""SELECT {COLUMNS} FROM silver_hist_pbp WHERE _season = ?
                ORDER BY game_id, action_number""",
                [label],
            ).fetchall()
        finally:
            con.close()
    except Exception as exc:
        return {"tool": "get_wpa_leaders", "ok": False, "rows": {},
                "meta": {"season": year, "season_label": label},
                "error": f"warehouse read failed: {str(exc)[:120]}"}
    if not rows:
        return {"tool": "get_wpa_leaders", "ok": False, "rows": {},
                "meta": {"season": year, "season_label": label},
                "error": f"no play-by-play coverage for season {label}"}
    players = score_events(rows)
    leaders = []
    for entry in players.values():
        if entry["events"] < floor:
            continue
        teams = entry["teams"]
        leaders.append({
            "player": entry["player"],
            "player_id": entry["player_id"],
            "team": teams.most_common(1)[0][0] if teams else "",
            "wpa": round(entry["wpa"], 3),
            "events": entry["events"],
            "plus_events": entry["plus_events"],
            "minus_events": entry["minus_events"],
            "games": len(entry["games"]),
        })
    leaders.sort(key=lambda r: r["wpa"], reverse=True)
    if not leaders:
        return {"tool": "get_wpa_leaders", "ok": False, "rows": {},
                "meta": {"season": year, "season_label": label,
                         "min_events": floor,
                         "source": "warehouse silver_hist_pbp (documented estimates)"},
                "error": f"no players with {floor}+ events in season {label}"}
    for rank, row in enumerate(leaders[:limit], 1):
        row["rank"] = rank
    meta: dict[str, Any] = {
        "season": year, "season_label": label, "limit": limit,
        "min_events": floor, "players": len(leaders),
        "games": len({str(r[0]) for r in rows}),
        "events": len(rows),
        "model": "fitted WP sigmoid(B0+B1*lead/sqrt(sec+360)); "
                 "delta credited to the acting player",
        "source": "warehouse silver_hist_pbp (documented estimates)",
        "values": "WPA sums credit makers and debit missers; "
                  "paired details share one action_number",
    }
    if warnings:
        meta["warning"] = "; ".join(warnings)
    return {"tool": "get_wpa_leaders", "ok": True,
            "rows": {"leaders": leaders[:limit]}, "meta": meta}
