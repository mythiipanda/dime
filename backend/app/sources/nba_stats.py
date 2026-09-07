"""nba_api source. Primary client. Pinned to nba_api 1.11.x."""

from typing import Any
import polars as pl

from ..config import settings
from .base import FetchMeta, FetchResult, empty, safe

SOURCE = "nba_api"


def _pl(df: Any) -> pl.DataFrame:
    try:
        return pl.from_pandas(df)
    except Exception:
        return pl.DataFrame()


def _frames(endpoint: Any) -> list[Any]:
    return endpoint.get_data_frames()


def _t() -> int:
    return settings.default_timeout_seconds


def player_gamelog(player_id: int, season: str) -> FetchResult:
    from nba_api.stats.endpoints import PlayerGameLog

    def run() -> pl.DataFrame:
        frames = _frames(PlayerGameLog(player_id=player_id, season=season, timeout=_t()))
        return _pl(frames[0])

    return safe(SOURCE, season, run)


def team_gamelog(team_id: int, season: str) -> FetchResult:
    from nba_api.stats.endpoints import TeamGameLog

    def run() -> pl.DataFrame:
        frames = _frames(TeamGameLog(team_id=team_id, season=season, timeout=_t()))
        frame = _pl(frames[0])
        if frame.height == 0:
            from . import espn as _espn

            year = int(season.split("-")[0]) + 1 if season else 2026
            espn_res = _espn.team_schedule(team_id, year, season)
            if espn_res.ok:
                return espn_res.frame
        return frame

    return safe(SOURCE, season, run)


def standings(season: str) -> FetchResult:
    from nba_api.stats.endpoints import LeagueStandings

    def run() -> pl.DataFrame:
        frames = _frames(LeagueStandings(season=season or None, timeout=_t()))
        return _pl(frames[0])

    return safe(SOURCE, season, run)


def leaders(stat_category: str, season: str) -> FetchResult:
    from nba_api.stats.endpoints import LeagueLeaders

    def run() -> pl.DataFrame:
        frames = _frames(
            LeagueLeaders(
                season=season or None,
                stat_category_abbreviation=stat_category,
                timeout=_t(),
            )
        )
        return _pl(frames[0])

    return safe(SOURCE, season, run)


def boxscore_traditional(game_id: str, season: str) -> FetchResult:
    from nba_api.stats.endpoints import BoxScoreTraditionalV3

    def run() -> pl.DataFrame:
        frames = _frames(BoxScoreTraditionalV3(game_id=game_id, timeout=_t()))
        frame = _pl(frames[0])
        rename = {"gameId": "GAME_ID", "personId": "PLAYER_ID", "teamId": "TEAM_ID"}
        existing = {k: v for k, v in rename.items() if k in frame.columns}
        return frame.rename(existing) if existing else frame

    return safe(SOURCE, season, run)


def scoreboard(game_date: str, season: str) -> FetchResult:
    from nba_api.stats.endpoints import ScoreboardV2
    from nba_api.stats.static import teams as _teams

    def run() -> pl.DataFrame:
        frames = _frames(ScoreboardV2(game_date=game_date, timeout=_t()))
        header = _pl(frames[0])
        try:
            lines = _pl(frames[1]).select("GAME_ID", "TEAM_ID", "PTS")
            home = lines.rename({"TEAM_ID": "HOME_TEAM_ID", "PTS": "HOME_TEAM_PTS"})
            away = lines.rename({"TEAM_ID": "VISITOR_TEAM_ID",
                                 "PTS": "VISITOR_TEAM_PTS"})
            merged = header.join(home, on=["GAME_ID", "HOME_TEAM_ID"],
                                 how="left").join(
                away, on=["GAME_ID", "VISITOR_TEAM_ID"], how="left")
            tmap = pl.DataFrame(
                {"TEAM_ID": [t["id"] for t in _teams.get_teams()],
                 "ABBREV": [t["abbreviation"] for t in _teams.get_teams()]})
            merged = merged.join(
                tmap.rename({"TEAM_ID": "HOME_TEAM_ID",
                             "ABBREV": "HOME_TEAM_ABBREVIATION"}),
                on="HOME_TEAM_ID", how="left").join(
                tmap.rename({"TEAM_ID": "VISITOR_TEAM_ID",
                             "ABBREV": "VISITOR_TEAM_ABBREVIATION"}),
                on="VISITOR_TEAM_ID", how="left")
            return merged
        except Exception:
            return header

    return safe(SOURCE, season, run)


def shot_chart(player_id: int, season: str, team_id: int = 0) -> FetchResult:
    from nba_api.stats.endpoints import ShotChartDetail

    def run() -> pl.DataFrame:
        frames = _frames(
            ShotChartDetail(
                player_id=player_id, team_id=team_id, season_nullable=season or None,
                timeout=_t(),
            )
        )
        return _pl(frames[0])

    return safe(SOURCE, season, run)


def lineups(team_id: int, season: str) -> FetchResult:
    from nba_api.stats.endpoints import LeagueDashLineups

    def run() -> pl.DataFrame:
        frames = _frames(
            LeagueDashLineups(
                team_id_nullable=team_id, season=season or None, timeout=_t()
            )
        )
        frame = _pl(frames[0])
        if "MIN" in frame.columns:
            frame = frame.sort("MIN", descending=True)
        return frame

    return safe(SOURCE, season, run)


def hustle(scope: str, season: str) -> FetchResult:
    from nba_api.stats.endpoints import (
        LeagueHustleStatsPlayer,
        LeagueHustleStatsTeam,
    )

    def run() -> pl.DataFrame:
        if scope == "team":
            frames = _frames(LeagueHustleStatsTeam(season=season or None, timeout=_t()))
        else:
            frames = _frames(
                LeagueHustleStatsPlayer(season=season or None, timeout=_t())
            )
        return _pl(frames[0])

    return safe(SOURCE, season, run)


def play_by_play(game_id: str, season: str) -> FetchResult:
    from nba_api.stats.endpoints import PlayByPlayV2

    def run() -> pl.DataFrame:
        frames = _frames(PlayByPlayV2(game_id=game_id, timeout=_t()))
        return _pl(frames[0])

    return safe(SOURCE, season, run)


def combine(season: str) -> FetchResult:
    from nba_api.stats.endpoints import (
        DraftCombinePlayerAnthro,
        DraftCombineSpotShooting,
    )

    def run() -> pl.DataFrame:
        kw = {"season_year": season, "timeout": _t()}
        a = _pl(_frames(DraftCombinePlayerAnthro(**kw))[0])
        try:
            s = _pl(_frames(DraftCombineSpotShooting(**kw))[0])
            key = "PLAYER_ID" if "PLAYER_ID" in s.columns else s.columns[0]
            return a.join(s, left_on="PLAYER_ID", right_on=key, how="left")
        except Exception:
            return a

    return safe(SOURCE, season, run)


def team_roster(team_id: int, season: str) -> FetchResult:
    from nba_api.stats.endpoints import CommonTeamRoster

    def run() -> pl.DataFrame:
        frames = _frames(
            CommonTeamRoster(team_id=team_id, season=season or None, timeout=_t())
        )
        frame = _pl(frames[1] if len(frames) > 1 else frames[0])
        if frame.height == 0:
            from . import espn as _espn

            year = int(season.split("-")[0]) + 1 if season else 2026
            espn_res = _espn.team_roster(team_id, season)
            if espn_res.ok:
                return espn_res.frame
        return frame

    return safe(SOURCE, season, run)


def current_season_meta() -> FetchMeta:
    from nba_api.stats.static import teams

    _ = teams.get_teams()
    from .base import FetchMeta as M

    return M(source=SOURCE, season="")
