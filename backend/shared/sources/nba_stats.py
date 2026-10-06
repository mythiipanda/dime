
from typing import Any
import polars as pl

from ..config import settings
from .base import FetchResult, safe

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

def career_totals(player_id: int) -> FetchResult:
    from nba_api.stats.endpoints import PlayerCareerStats

    def run() -> pl.DataFrame:
        ep = PlayerCareerStats(player_id=player_id, timeout=_t())
        return _pl(ep.career_totals_regular_season.get_data_frame())

    return safe(SOURCE, "career", run)

def player_gamelog(player_id: int, season: str) -> FetchResult:
    from nba_api.stats.endpoints import PlayerGameLog

    def run() -> pl.DataFrame:
        frames = _frames(PlayerGameLog(player_id=player_id, season=season, timeout=_t()))
        return _pl(frames[0])

    return safe(SOURCE, season, run)

def player_playoff_gamelog(player_id: int, season: str) -> FetchResult:
    from nba_api.stats.endpoints import PlayerGameLog

    def run() -> pl.DataFrame:
        frames = _frames(PlayerGameLog(
            player_id=player_id, season=season,
            season_type_all_star="Playoffs", timeout=_t()))
        return _pl(frames[0])

    return safe(SOURCE, season, run)

def team_gamelog(team_id: int, season: str) -> FetchResult:
    from nba_api.stats.endpoints import TeamGameLog

    def run() -> pl.DataFrame:
        frames = _frames(TeamGameLog(team_id=team_id, season=season, timeout=_t()))
        frame = _pl(frames[0])
        if frame.height == 0:
            from . import espn as _espn

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

def playoff_results(season: str) -> FetchResult:
    from nba_api.stats.endpoints import LeagueGameFinder

    def run() -> pl.DataFrame:
        frames = _frames(LeagueGameFinder(
            season_nullable=season or None, season_type_nullable="Playoffs",
            timeout=_t()))
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

def player_advanced(season: str) -> FetchResult:
    from nba_api.stats.endpoints import LeagueDashPlayerStats

    def run() -> pl.DataFrame:
        frames = _frames(
            LeagueDashPlayerStats(
                season=season or None,
                measure_type_detailed_defense="Advanced",
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

    return safe(SOURCE, season, run, accept_empty=True)

def shot_chart(player_id: int, season: str, team_id: int = 0) -> FetchResult:
    from nba_api.stats.endpoints import ShotChartDetail

    def run() -> pl.DataFrame:
        frames = _frames(
            ShotChartDetail(
                player_id=player_id, team_id=team_id, season_nullable=season or None,
                context_measure_simple="FGA", timeout=_t(),
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
        frame = _pl(frames[0])
        if frame.height == 0:
            from . import espn as _espn

            espn_res = _espn.team_roster(team_id, season)
            if espn_res.ok:
                return espn_res.frame
        return frame

    return safe(SOURCE, season, run)

def team_ratings(season: str) -> FetchResult:
    from nba_api.stats.endpoints import LeagueDashTeamStats

    def run() -> pl.DataFrame:
        frames = _frames(LeagueDashTeamStats(
            season=season or None,
            measure_type_detailed_defense="Advanced", timeout=_t()))
        return _pl(frames[0])

    return safe(SOURCE, season, run)

def clutch(scope: str, season: str) -> FetchResult:
    if scope == "team":
        from nba_api.stats.endpoints import LeagueDashTeamClutch as Clutch
    else:
        from nba_api.stats.endpoints import LeagueDashPlayerClutch as Clutch

    def run() -> pl.DataFrame:
        frames = _frames(Clutch(season=season or None, timeout=_t()))
        return _pl(frames[0])

    return safe(SOURCE, season, run)

PT_MEASURE_TYPES = (
    "CatchShoot",
    "Defense",
    "Drives",
    "Efficiency",
    "ElbowTouch",
    "PaintTouch",
    "Passing",
    "Possessions",
    "PostTouch",
    "PullUpShot",
    "Rebounding",
    "SpeedDistance",
)

PT_SCOPES = ("player", "team")

PT_DEFEND_CATEGORIES = ("Overall",)

_TRACKING_GAP_S = 1.5
_tracking_last = 0.0

def _tracking_wait() -> None:
    import time as _time

    global _tracking_last
    wait = _TRACKING_GAP_S - (_time.monotonic() - _tracking_last)
    if wait > 0:
        _time.sleep(wait)
    _tracking_last = _time.monotonic()

def pt_stats(scope: str, measure_type: str, season: str) -> FetchResult:
    from nba_api.stats.endpoints import LeagueDashPtStats

    def run() -> pl.DataFrame:
        if scope not in PT_SCOPES:
            raise ValueError("unknown pt scope: " + repr(scope))
        _tracking_wait()
        frames = _frames(LeagueDashPtStats(
            player_or_team="Player" if scope == "player" else "Team",
            pt_measure_type=measure_type,
            season=season or None,
            timeout=60,
        ))
        return _pl(frames[0])

    return safe(SOURCE, season, run)

def pt_defend(defense_category: str, season: str) -> FetchResult:
    from nba_api.stats.endpoints import LeagueDashPtDefend

    def run() -> pl.DataFrame:
        _tracking_wait()
        frames = _frames(LeagueDashPtDefend(
            defense_category=defense_category,
            season=season or None,
            timeout=60,
        ))
        return _pl(frames[0])

    return safe(SOURCE, season, run)

def pt_shot(season: str) -> FetchResult:
    from nba_api.stats.endpoints import LeagueDashPlayerPtShot

    def run() -> pl.DataFrame:
        _tracking_wait()
        frames = _frames(LeagueDashPlayerPtShot(
            season=season or None,
            timeout=60,
        ))
        return _pl(frames[0])

    return safe(SOURCE, season, run)
