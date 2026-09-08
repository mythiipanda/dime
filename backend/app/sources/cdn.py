"""NBA CDN liveData source (keyless, bypasses stats.nba.com blocks).

Base: https://cdn.nba.com. No key. Season like 2025-26.
Schedule: /static/json/staticData/scheduleLeagueV2_1.json
Boxscore: /static/json/liveData/boxscore/boxscore_{game_id}.json
Column names UPPERCASE to match warehouse convention.
"""

import polars as pl

from .base import FetchResult, safe

SOURCE = "nba_cdn"
SCHEDULE_URL = "https://cdn.nba.com/static/json/staticData/scheduleLeagueV2_1.json"
BOXSCORE_URL = "https://cdn.nba.com/static/json/liveData/boxscore/boxscore_{gid}.json"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "application/json,text/plain,*/*",
    "Referer": "https://www.nba.com/",
    "Origin": "https://www.nba.com",
}


def _get_json(url: str) -> dict:
    import httpx

    r = httpx.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.json()


def _iso_of(game_date: str) -> str:
    m, d, y = game_date.split("/")
    return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"


def _season_for_mdy(game_date: str) -> str:
    m, _, y = game_date.split("/")
    y = int(y)
    return f"{y}-{str(y + 1)[2:]}" if int(m) >= 10 else f"{y - 1}-{str(y)[2:]}"


def _season_for_game_id(game_id: str) -> str:
    try:
        yy = int(str(game_id)[3:5])
        y = 2000 + yy
        return f"{y}-{str(y + 1)[2:]}"
    except (ValueError, IndexError):
        return ""


def _game_rows(payload: dict) -> list[dict]:
    days = payload.get("leagueSchedule", {}).get("gameDates", [])
    return [g for d in days for g in d.get("games", [])]


def _matchup(g: dict) -> tuple[str, str, str]:
    away = g.get("awayTeam", {}).get("teamTricode", "")
    home = g.get("homeTeam", {}).get("teamTricode", "")
    return away, home, f"{away} @ {home}"


def scoreboard(game_date: str) -> FetchResult:
    def run() -> pl.DataFrame:
        iso = _iso_of(game_date)
        days = _get_json(SCHEDULE_URL).get("leagueSchedule", {}).get("gameDates", [])
        rows = []
        for d in days:
            local = str(d.get("gameDate", "")).startswith(game_date)
            for g in d.get("games", []):
                utc = str(g.get("gameDateTimeUTC", "")).startswith(iso)
                if not (utc or local):
                    continue
                away, home, mu = _matchup(g)
                rows.append({"GAME_ID": str(g.get("gameId", "")),
                             "GAME_DATE": iso, "MATCHUP": mu,
                             "STATUS": str(g.get("gameStatusText", g.get("gameStatus", "")))})
        return pl.DataFrame(rows) if rows else pl.DataFrame()

    return safe(SOURCE, _season_for_mdy(game_date), run)


def boxscore(game_id: str) -> FetchResult:
    def run() -> pl.DataFrame:
        game = _get_json(BOXSCORE_URL.format(gid=game_id)).get("game", {})
        rows = []
        for side in ("awayTeam", "homeTeam"):
            team = game.get(side, {}) or {}
            tri = team.get("teamTricode", "")
            for p in team.get("players", []) or []:
                s = p.get("statistics", {}) or {}
                name = p.get("name") or f"{p.get('firstName', '')} {p.get('familyName', '')}".strip()
                rows.append({"PLAYER_ID": p.get("personId"),
                             "PLAYER_NAME": name,
                             "TEAM_ABBREVIATION": p.get("teamTricode", tri),
                             "PTS": s.get("points", 0), "REB": s.get("reboundsTotal", 0),
                             "AST": s.get("assists", 0), "MIN": s.get("minutes", "")})
        return pl.DataFrame(rows) if rows else pl.DataFrame()

    return safe(SOURCE, _season_for_game_id(str(game_id)), run)


def schedule(team_abbrev: str, season: str) -> FetchResult:
    def run() -> pl.DataFrame:
        want = team_abbrev.upper()
        rows = []
        for g in _game_rows(_get_json(SCHEDULE_URL)):
            away, home, mu = _matchup(g)
            if want not in (away.upper(), home.upper()):
                continue
            iso = str(g.get("gameDateTimeUTC", ""))[:10]
            rows.append({"GAME_ID": str(g.get("gameId", "")),
                         "GAME_DATE": iso, "MATCHUP": mu,
                         "WL": str(g.get("wl", "") or "")})
        return pl.DataFrame(rows) if rows else pl.DataFrame()

    return safe(SOURCE, season, run)
