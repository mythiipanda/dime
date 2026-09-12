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
    "combine": "silver_combine",
    "ratings": "silver_team_ratings",
    "playoffs": "silver_playoffs",
    "playoff_gamelogs": "silver_playoff_gamelogs",
    "draft": "silver_hist_draft",
    "raptor": "silver_raptor_player",
    "player_seasons": "silver_hist_player_seasons",
}


@router.get("/datasets/freshness")
def freshness() -> dict:
    con = store.connect()
    try:
        tables = [r[0] for r in
                  con.execute("SHOW TABLES").fetchall()]
        rows = []
        for t in sorted(tables):
            if not t.startswith("silver_"):
                continue
            cols = [r[1] for r in
                    con.execute(f"PRAGMA table_info({t})").fetchall()]
            n = con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            last = None
            if "_fetched_at" in cols:
                last = con.execute(
                    f"SELECT MAX(_fetched_at) FROM {t}").fetchone()[0]
            rows.append({"table": t, "rows": n, "last_fetch": last})
    finally:
        con.close()
    return {"ok": True, "rows": rows}


def _envelope(table: str, season: str, frame: object, cached: bool) -> dict:
    import polars as pl

    assert isinstance(frame, pl.DataFrame)
    meta = {"season": season, "rows": frame.height, "cached": cached}
    if frame.height and "_source" in frame.columns:
        meta["source"] = frame["_source"][0]
        meta["fetched_at"] = frame["_fetched_at"][0]
    rows = frame.to_dicts()
    if table == "silver_lineups":
        from .tools._core import trust_tier

        for r in rows:
            tier, est = trust_tier(r.get("MIN"))
            r["TRUST"] = tier
            r["EST_POSS"] = est
            if tier == "SMALL" and not r.get("SAMPLE"):
                r["SAMPLE"] = "small: under ~100 possessions, do not trust"
    return {"data": rows, "meta": meta}


def _fetch_live(
    name: str, season: str, player_id: int, team_id: int,
    game_id: str, game_date: str, stat: str,
) -> FetchResult | None:
    if name == "standings":
        return nba_stats.standings(season)
    if name == "leaders":
        from .tools import clamp_stat

        return nba_stats.leaders(clamp_stat(stat), season)
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
    if name == "combine":
        return nba_stats.combine(season)
    if name == "ratings":
        return nba_stats.team_ratings(season)
    if name == "playoffs":
        return nba_stats.playoff_results(season)
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
    player_a: str = Query(""),
    player_b: str = Query(""),
    fmt: str = Query("json"),
):
    if name == "wowy" and (player_a or ids):
        from .tools.player import get_wowy

        res = get_wowy.invoke(
            {"player_a": player_a or ids, "player_b": player_b, "team_id": team_id, "season": season}
        )
        if not res.get("ok"):
            return {"ok": False, "error": res.get("error", "wowy failed")}
        rows = res.get("rows", [])
        if fmt == "csv":
            df = pl.DataFrame(rows)
            return Response(df.write_csv(), media_type="text/csv")
        return {"ok": True, "data": rows, "verdict": res.get("verdict"), "meta": res.get("meta")}

    if name not in TABLES:
        return {"ok": False, "error": f"unknown dataset, pick one of {sorted(TABLES)}"}
    table = TABLES[name]
    if name == "leaders":
        from .tools import clamp_stat

        table = f"silver_leaders_{clamp_stat(stat).lower()}"
    entity_scoped = name in ("player_gamelogs", "team_games", "shots", "scoreboard", "lineups", "on_off", "wowy", "four_factors")
    entity = ""
    if player_id:
        entity = f"player:{player_id}"
    elif team_id:
        entity = f"team:{team_id}"
    elif game_id:
        entity = f"game:{game_id}"
    elif game_date:
        entity = f"date:{game_date}"
    elif ids:
        entity = f"wowy:{ids}"
    frame = store.read_frame(table, "_season = ?", [season])
    if entity_scoped:
        # Warehouse-first per entity; never force a live call when seeded.
        if entity:
            try:
                frame = store.read_frame(
                    table, "_season = ? AND _entity = ?", [season, entity])
            except Exception:
                frame = frame.clear()
        else:
            frame = frame.clear()
    cached = frame.height > 0
    if not cached:
        live = _fetch_live(name, season, player_id, team_id, game_id, game_date, stat)
        if live is None:
            return {"ok": False, "error": "missing id param for this dataset"}
        if not live.ok:
            # Honest attribution: name the failed live source, then stale-fallback.
            stale = None
            if entity_scoped and entity:
                try:
                    stale = store.read_frame(table, "_entity = ?", [entity])
                except Exception:
                    stale = None
            if stale is not None and stale.height > 0:
                out = _envelope(table, season, stale, True)
                out["ok"] = True
                out["meta"]["stale"] = True
                out["meta"]["live_error"] = live.error or "empty upstream response"
                out["meta"]["live_source"] = live.meta.source
                return out
            return {"ok": False, "error": live.error,
                    "source": live.meta.source,
                    "detail": "live source failed and no cached rows for this entity"}
        store.save_frame(table, live, entity)
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
