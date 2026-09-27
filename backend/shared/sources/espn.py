"""ESPN source via sportsdataverse. Keyless. Complements nba_api."""

import polars as pl

from .base import FetchResult, empty, safe

SOURCE = "espn"

_espn_ids: dict[str, int] | None = None


def espn_team_id(abbrev: str) -> int | None:
    """Translate a team abbreviation to the ESPN numeric id. Cached."""
    global _espn_ids
    if _espn_ids is None:
        from sportsdataverse.nba import espn_nba_teams

        frame = _pl(espn_nba_teams())
        _espn_ids = {
            str(r["team_abbreviation"]): int(r["team_id"]) for r in frame.to_dicts()
        }
    return _espn_ids.get(abbrev)


def nba_to_espn_team(nba_team_id: int) -> int | None:
    from nba_api.stats.static import teams

    found = teams.find_team_name_by_id(nba_team_id)
    if not found:
        return None
    return espn_team_id(found.get("abbreviation", ""))


def _pl(obj: object) -> pl.DataFrame:
    if isinstance(obj, pl.DataFrame):
        return obj
    try:
        import pandas as pd

        if isinstance(obj, pd.DataFrame):
            return pl.from_pandas(obj)
    except Exception:
        pass
    return pl.DataFrame()


def scoreboard(date_yyyymmdd: str, season: str) -> FetchResult:
    from sportsdataverse.nba import espn_nba_scoreboard

    def run() -> pl.DataFrame:
        return _pl(espn_nba_scoreboard(dates=date_yyyymmdd))

    return safe(SOURCE, season, run)


def standings(season_year: int, season: str) -> FetchResult:
    from sportsdataverse.nba import espn_nba_standings

    def run() -> pl.DataFrame:
        return _pl(espn_nba_standings(season=season_year))

    return safe(SOURCE, season, run)


def team_roster(team_id: int, season: str) -> FetchResult:
    from sportsdataverse.nba import espn_nba_team_roster

    def run() -> pl.DataFrame:
        eid = nba_to_espn_team(team_id)
        if eid is None:
            return pl.DataFrame()
        return _pl(espn_nba_team_roster(team_id=eid))

    return safe(SOURCE, season, run)


def team_schedule(team_id: int, season_year: int, season: str) -> FetchResult:
    from sportsdataverse.nba import espn_nba_team_schedule

    def run() -> pl.DataFrame:
        eid = nba_to_espn_team(team_id)
        if eid is None:
            return pl.DataFrame()
        return _pl(espn_nba_team_schedule(team_id=eid, season=season_year))

    return safe(SOURCE, season, run)


def player_gamelog(athlete_id: int, season: str) -> FetchResult:
    from sportsdataverse.nba import espn_nba_player_gamelog

    def run() -> pl.DataFrame:
        return _pl(espn_nba_player_gamelog(athlete_id=athlete_id))

    return safe(SOURCE, season, run)


def injuries(season: str) -> FetchResult:
    from sportsdataverse.nba import espn_nba_injuries

    def run() -> pl.DataFrame:
        return _pl(espn_nba_injuries())

    return safe(SOURCE, season, run)
