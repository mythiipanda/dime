"""Dataset boundary. Warehouse first, live on miss, provenance always."""

import io
from fastapi import APIRouter, Query
from fastapi.responses import Response

from . import store
from .sources import espn, nba_stats
from .sources.base import FetchResult

router = APIRouter()

TABLES = {
    "standings": "silver_standings",
    "leaders": "silver_leaders_pts",
    "injuries": "silver_injuries",
    "player_gamelogs": "silver_player_gamelogs",
    "team_games": "silver_team_games",
    "scoreboard": "silver_scoreboard",
    "shots": "silver_shots",
    "lineups": "silver_lineups",
    "on_off": "silver_on_off",
    "wowy": "silver_wowy",
    "four_factors": "silver_four_factors",
    "hustle": "silver_hustle_player",
}


def _envelope(table: str, season: str, frame: object, cached: bool) -> dict:
    import polars as pl

    assert isinstance(frame, pl.DataFrame)
    meta = {"season": season, "rows": frame.height, "cached": cached}
    if frame.height and "_source" in frame.columns:
        meta["source"] = frame["_source"][0]
        meta["fetched_at"] = frame["_fetched_at"][0]
    return {"data": frame.to_dicts(), "meta": meta}


def _fetch_live(
    name: str, season: str, player_id: int, team_id: int,
    game_id: str, game_date: str, stat: str,
) -> FetchResult | None:
    if name == "standings":
        return nba_stats.standings(season)
    if name == "leaders":
        return nba_stats.leaders(stat, season)
    if name == "injuries":
        return espn.injuries(season)
    if name == "player_gamelogs" and player_id:
        return nba_stats.player_gamelog(player_id, season)
    if name == "team_games" and team_id:
        return nba_stats.team_gamelog(team_id, season)
    if name == "scoreboard" and game_date:
        return nba_stats.scoreboard(game_date, season)
    if name == "shots" and player_id:
        return nba_stats.shot_chart(player_id, season, team_id)
    if name == "lineups" and team_id:
        return nba_stats.lineups(team_id, season)
    if name in ("on_off", "four_factors") and player_id and team_id:
        from .sources import pbpstats

        if name == "on_off":
            return pbpstats.on_off(player_id, team_id, season)
        return pbpstats.four_factors(player_id, team_id, season)
    if name == "wowy" and team_id and ids:
        from .sources import pbpstats

        parsed = [int(x) for x in ids.split(",") if x.strip().isdigit()]
        return pbpstats.wowy(parsed, team_id, season)
    if name == "hustle":
        return nba_stats.hustle("player", season)
    return None


@router.get("/datasets/{name}")
def dataset(
    name: str,
    season: str = Query("2025-26"),
    player_id: int = Query(0),
    team_id: int = Query(0),
    game_id: str = Query(""),
    game_date: str = Query(""),
    stat: str = Query("PTS"),
    ids: str = Query(""),
    fmt: str = Query("json"),
):
    if name not in TABLES:
        return {"ok": False, "error": f"unknown dataset, pick one of {sorted(TABLES)}"}
    table = TABLES[name]
    entity_scoped = name in ("player_gamelogs", "team_games", "shots", "scoreboard", "lineups", "on_off", "wowy", "four_factors")
    frame = store.read_frame(table, "_season = ?", [season])
    if entity_scoped:
        frame = frame.clear()
    cached = frame.height > 0
    if not cached:
        live = _fetch_live(name, season, player_id, team_id, game_id, game_date, stat)
        if live is None:
            return {"ok": False, "error": "missing id param for this dataset"}
        if not live.ok:
            return {"ok": False, "error": live.error}
        store.save_frame(table, live)
        if entity_scoped:
            frame = store.read_frame(
                table, "_fetched_at = ?", [live.meta.fetched_at]
            )
        else:
            frame = store.read_frame(table, "_season = ?", [season])
    if fmt == "csv":
        return Response(frame.write_csv(), media_type="text/csv")
    if fmt == "parquet":
        buf = io.BytesIO()
        frame.write_parquet(buf)
        return Response(buf.getvalue(), media_type="application/octet-stream")
    out = _envelope(table, season, frame, cached)
    out["ok"] = True
    return out
