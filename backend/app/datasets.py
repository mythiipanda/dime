
import io
import time

import polars as pl
from fastapi import APIRouter, Query
from fastapi.responses import Response

from shared import store
from shared.freshness import table_data_through
from shared.sources import espn, nba_stats
from shared.sources.base import FetchResult

router = APIRouter()






_FRESHNESS_TTL_S = 300
_FRESHNESS_CACHE = {"at": 0.0, "payload": None}


def _freshness_payload() -> dict:
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
            rows.append({"table": t, "rows": n, "last_fetch": last,
                         "data_through": table_data_through(con, t, cols)})
    finally:
        con.close()
    return {"ok": True, "rows": rows}

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
    now = time.monotonic()
    cached = _FRESHNESS_CACHE
    if cached["payload"] is not None and now - cached["at"] < _FRESHNESS_TTL_S:
        return cached["payload"]
    payload = _freshness_payload()
    cached["payload"] = payload
    cached["at"] = now
    return payload


def _envelope(table: str, season: str, frame: object, cached: bool) -> dict:
    import polars as pl

    assert isinstance(frame, pl.DataFrame)
    meta = {"season": season, "rows": frame.height, "cached": cached}
    if frame.height and "_source" in frame.columns:
        meta["source"] = frame["_source"][0]
        meta["fetched_at"] = frame["_fetched_at"][0]
    rows = frame.to_dicts()
    if table.startswith("silver_leaders_"):


        stat_col = table.rsplit("_", 1)[-1].upper()
        if stat_col == "FG":
            stat_col = "FG_PCT"
        pin = ["RANK", "PLAYER", "TEAM", stat_col, "GP", "MIN"]
        pinned = []
        for r in rows:
            keyed = {k: r[k] for k in pin if k in r}
            keyed.update({k: v for k, v in r.items() if k not in keyed})
            pinned.append(keyed)
        rows = pinned
    if table == "silver_standings":




        pin = ["TeamCity", "TeamName", "Conference", "Record",
               "WINS", "LOSSES", "WinPCT", "PlayoffRank",
               "ClinchIndicator"]
        pinned = []
        for r in rows:
            keyed = {k: r[k] for k in pin if k in r}
            keyed.update({k: v for k, v in r.items() if k not in keyed})
            pinned.append(keyed)
        rows = pinned
    if table == "silver_lineups":
        from shared.tools._core import sample_tier

        for r in rows:
            tier, est = sample_tier(r.get("MIN"))
            r["SAMPLE_TIER"] = tier
            r["EST_POSS"] = est
            if tier == "small" and not r.get("SAMPLE"):
                r["SAMPLE"] = "small: under ~100 possessions"
    return {"data": rows, "meta": meta}


_LINEUP_SUM_KEYS = ("PTS", "PLUS_MINUS", "FGA", "OREB", "TOV", "FTA", "MIN")


def _aggregate_lineup_rows(rows: list) -> list:
    agg: dict = {}
    for r in rows:
        ids = [x for x in str(r.get("GROUP_ID") or "").split("-") if x]
        if len(ids) != 5:
            continue
        if r.get("PTS") is None:
            continue
        try:
            vals = {k: float(r.get(k)) for k in _LINEUP_SUM_KEYS}
        except (TypeError, ValueError):
            continue
        key = (str(r.get("GROUP_ID")), str(r.get("TEAM_ABBREVIATION")))
        slot = agg.get(key)
        if slot is None:
            agg[key] = {"name": r.get("GROUP_NAME"), "vals": vals}
        else:
            if vals["MIN"] > slot["vals"]["MIN"]:
                slot["name"] = r.get("GROUP_NAME")
            for k in _LINEUP_SUM_KEYS:
                slot["vals"][k] += vals[k]
    out = []
    for (gid, team), slot in agg.items():
        vals = slot["vals"]
        poss = vals["FGA"] - vals["OREB"] + vals["TOV"] + 0.44 * vals["FTA"]
        if poss <= 0:
            continue
        out.append((gid, team, slot["name"], vals, poss))
    return out


def _lineup_stints(season: str) -> list:
    frame = store.read_frame("silver_lineups", "_season = ?", [season])
    return _aggregate_lineup_rows(frame.to_dicts())


def _sanitize_live_error(err: object) -> str:
    text = "" if err is None else str(err).strip()
    if not text:
        return "live source failed and no cached rows for this team and season"
    low = text.lower()
    if "httpsconnectionpool" in low or "httpconnectionpool" in low:
        return "live source timed out and no cached rows for this team and season"
    if "max retries exceeded" in low:
        return "live source timed out and no cached rows for this team and season"
    if "read timed out" in low or "timed out" in low:
        return "live source timed out and no cached rows for this team and season"
    return text[:300]


def _team_lineup_frame(season: str, team_id: int) -> object:
    return store.read_frame(
        "silver_lineups",
        "_season = ? AND CAST(TEAM_ID AS VARCHAR) = CAST(? AS VARCHAR)",
        [season, str(team_id)],
    )


def _lineup_leaders(season: str, min_poss: int) -> dict:
    try:
        stints = _lineup_stints(season)
    except Exception as exc:
        return {"ok": False,
                "error": f"warehouse read failed: {str(exc)[:160]}"}
    if not stints:
        return {"ok": False, "error":
                f"no rated 5-man lineup stints for {season} in silver_lineups"}
    rows = []
    for gid, team, name, vals, poss in stints:
        if poss < min_poss:
            continue
        off = round(100.0 * vals["PTS"] / poss, 1)
        net = round(100.0 * vals["PLUS_MINUS"] / poss, 1)
        rows.append({"lineup": name, "team": team,
                     "MIN": vals["MIN"], "OFF_RTG": off,
                     "DEF_RTG": round(off - net, 1),
                     "NET_RTG": net, "possessions": round(poss, 1)})
    rows.sort(key=lambda d: d["NET_RTG"], reverse=True)
    return {"ok": True, "data": rows,
            "meta": {"season": season, "rows": len(rows), "cached": True,
                     "source": "silver_lineups",
                     "method": "lineup stats summed per (GROUP_ID, TEAM_ABBREVIATION) across stints; possessions estimated as FGA - OREB + TOV + 0.44 * FTA; OFF_RTG = 100 * PTS / POSS; NET_RTG = 100 * PLUS_MINUS / POSS; DEF_RTG derived as OFF_RTG - NET_RTG",
                     "min_poss": min_poss}}


def _table_leaders(table: str, season: str, sort_col: str) -> dict:
    try:
        frame = store.read_frame(table, "_season = ?", [season])
    except Exception as exc:
        return {"ok": False,
                "error": f"warehouse read failed: {str(exc)[:160]}"}
    if frame.height == 0:
        return {"ok": False, "error":
                f"no rows for {season} in {table}"}
    if sort_col in frame.columns:
        frame = frame.sort(sort_col, descending=True, nulls_last=True)
    out = _envelope(table, season, frame, True)
    out["ok"] = True
    return out


_HIST_ZONE_LABELS = {
    "rim": "Rim (<8 ft)",
    "corner_3": "Corner 3",
    "atb_3": "Above-Break 3",
    "short_mid": "Short Mid (8-14 ft)",
    "long_mid": "Long Mid (14 ft+)",
}


def _hist_zone(value, dist, x):
    try:
        three = int(value or 0) == 3
    except (TypeError, ValueError):
        three = False
    try:
        d = float(dist)
    except (TypeError, ValueError):
        d = 999.0
    try:
        ax = abs(float(x))
    except (TypeError, ValueError):
        ax = 0.0
    from shared.tools.zone import ZONE_RULES

    for key, rule in ZONE_RULES:
        if rule(d, ax, three):
            return _HIST_ZONE_LABELS[key]
    return _HIST_ZONE_LABELS["long_mid"]


def _zone_splits(season: str, player_id: int) -> dict:
    if not player_id:
        return {"ok": False, "error":
                "zone_splits is player-scoped: pass player_id"}
    zones: dict = {}
    sources = []
    cur = store.read_frame(
        "silver_shots", "_season = ? AND CAST(PLAYER_ID AS VARCHAR) = CAST(? AS VARCHAR)",
        [season, str(player_id)])
    if cur.height > 0:
        sources.append("silver_shots")
        for r in cur.to_dicts():
            z = r.get("SHOT_ZONE_BASIC")
            if z is None:
                continue
            slot = zones.setdefault(str(z), [0, 0])
            slot[1] += 1
            if str(r.get("SHOT_MADE_FLAG")) == "1":
                slot[0] += 1
    if not zones:
        hist = store.read_frame(
            "silver_hist_shots", "_season = ? AND CAST(person_id AS VARCHAR) = CAST(? AS VARCHAR)",
            [season, str(player_id)])
        if hist.height > 0:
            sources.append("silver_hist_shots")
            for r in hist.to_dicts():
                z = _hist_zone(r.get("shot_value"), r.get("shot_distance"),
                               r.get("x_legacy"))
                if z is None:
                    continue
                slot = zones.setdefault(z, [0, 0])
                slot[1] += 1
                if str(r.get("shot_result")) == "Made":
                    slot[0] += 1
    if not zones:
        return {"ok": False, "error":
                f"no shot rows for player {player_id} in {season} (silver_shots, silver_hist_shots)"}
    rows = [{"zone": z, "FGM": m, "FGA": a,
             "FG_PCT": round(m / a, 3) if a else 0.0}
            for z, (m, a) in zones.items()]
    rows.sort(key=lambda d: d["FGA"], reverse=True)
    return {"ok": True, "data": rows,
            "meta": {"season": season, "rows": len(rows), "cached": True,
                     "player_id": player_id, "sources": sources,
                      "zone_definition": "silver_shots uses native SHOT_ZONE_BASIC; silver_hist_shots rows use the same play-level zone definitions as the zone tool: rim is shot_distance under 8 ft, corner 3 is a 3pt shot with |x_legacy| at or above 220 tenths of feet, above-break 3 is any other 3pt shot, short mid is a 2pt shot under 14 ft, long mid is any other 2pt shot"}}


def _fetch_live(
    name: str, season: str, player_id: int, team_id: int,
    game_id: str, game_date: str, stat: str,
) -> FetchResult | None:
    if name == "standings":
        return nba_stats.standings(season)
    if name == "leaders":
        from shared.tools import clamp_stat

        try:
            stat = clamp_stat(stat)
        except ValueError:
            stat = "PTS"
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
        from shared.sources import pbpstats

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
        from shared.sources import pbpstats

        parsed = [int(x) for x in ids.split(",") if x.strip().isdigit()]
        return pbpstats.wowy(parsed, team_id, season)
    if name == "hustle":
        return nba_stats.hustle("player", season)
    return None


@router.get("/datasets/{name}")
def dataset(
    name: str,
    season: str | None = Query(None),
    player_id: int = Query(0),
    team_id: int = Query(0),
    game_id: str = Query(""),
    game_date: str = Query(""),
    stat: str = Query("PTS"),
    ids: str = Query(""),
    player_a: str = Query(""),
    player_b: str = Query(""),
    min_poss: int = Query(200),
    fmt: str = Query("json"),
):
    raw_season = season if isinstance(season, str) else ""
    raw_season = raw_season.strip()
    if raw_season:
        season = raw_season
    else:
        resolved = None
        try:
            from shared.tools._core import resolve_season as _resolve_season
            probe = TABLES.get(name, None) if name in TABLES else None
            if name in ("rapm", "lineup_leaders", "clutch", "zone_splits"):
                probe = "silver_lineups" if name == "lineup_leaders" else probe
            resolved = _resolve_season(None, probe)
        except Exception:
            resolved = None
        if not resolved:
            return {"ok": False, "error": "no season provided and warehouse has no season with data"}
        season = resolved
    if name in ("rapm", "lineup_leaders", "clutch", "zone_splits"):
        if name == "lineup_leaders":
            res = _lineup_leaders(season, min_poss)
        elif name == "rapm":
            res = _table_leaders("silver_rapm", season, "rapm")
        elif name == "clutch":
            res = _table_leaders("silver_clutch", season, "PTS")
        else:
            res = _zone_splits(season, player_id)
        if not res.get("ok"):
            return res
        if fmt == "csv":
            df = pl.DataFrame(res["data"])
            return Response(df.write_csv(), media_type="text/csv")
        return res
    if name == "wowy" and (player_a or ids):
        from shared.tools.player import get_wowy

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
        from shared.tools import clamp_stat

        try:
            stat = clamp_stat(stat)
        except ValueError:
            stat = "PTS"
        table = f"silver_leaders_{stat.lower()}"
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
    if name == "lineups" and team_id:
        team_frame = _team_lineup_frame(season, team_id)
        if team_frame is not None and team_frame.height > 0:
            if fmt == "csv":
                return Response(team_frame.write_csv(), media_type="text/csv")
            if fmt == "parquet":
                buf = io.BytesIO()
                team_frame.write_parquet(buf)
                return Response(buf.getvalue(), media_type="application/octet-stream")
            out = _envelope(table, season, team_frame, True)
            out["ok"] = True
            return out
    frame = store.read_frame(table, "_season = ?", [season])
    if name == "leaders" and frame.height > 0:


        stat_col = clamp_stat(stat)
        if stat_col in frame.columns:
            frame = frame.sort(stat_col, descending=True, nulls_last=True)
    if entity_scoped:

        if entity:
            frame = store.read_frame(
                table, "_season = ? AND _entity = ?", [season, entity])
        else:
            frame = frame.clear()
    cached = frame.height > 0
    if not cached:
        live = _fetch_live(name, season, player_id, team_id, game_id, game_date, stat)
        if live is None:
            return {"ok": False, "error": "missing id param for this dataset"}
        if not live.ok:

            stale = None
            if entity_scoped and entity:
                stale = store.read_frame(table, "_entity = ?", [entity])
            if stale is not None and stale.height > 0:
                out = _envelope(table, season, stale, True)
                out["ok"] = True
                out["meta"]["stale"] = True
                out["meta"]["live_error"] = _sanitize_live_error(live.error or "empty upstream response")
                out["meta"]["live_source"] = live.meta.source
                return out
            return {"ok": False, "error": _sanitize_live_error(live.error),
                    "source": live.meta.source,
                    "detail": "live source failed and no cached rows for this entity"}
        store.save_frame(table, live, entity)
        if entity_scoped:
            frame = store.read_frame(
                table, "_fetched_at = ?", [live.meta.fetched_at]
            )
        else:
            frame = store.read_frame(table, "_season = ?", [season])
    if (name in ("player_gamelogs", "team_games", "playoff_gamelogs")
            and frame.height > 0 and "GAME_DATE" in frame.columns):



        for fmt_s in ("%b %d, %Y", "%Y-%m-%d"):
            try:
                frame = frame.with_columns(
                    pl.col("GAME_DATE").str.strptime(
                        pl.Date, fmt_s, strict=False).alias("_d"))
                if frame["_d"].null_count() < frame.height:
                    frame = frame.sort("_d", descending=True,
                                       nulls_last=True).drop("_d")
                else:
                    frame = frame.drop("_d")
                    continue
                break
            except Exception:
                if "_d" in frame.columns:
                    frame = frame.drop("_d")
                continue
    if name in ("player_gamelogs", "team_games", "playoff_gamelogs") and frame.height > 0:




        from shared.tools.gamelog import dedupe_game_log_frame

        frame = dedupe_game_log_frame(frame)
    if fmt == "csv":
        return Response(frame.write_csv(), media_type="text/csv")
    if fmt == "parquet":
        buf = io.BytesIO()
        frame.write_parquet(buf)
        return Response(buf.getvalue(), media_type="application/octet-stream")
    out = _envelope(table, season, frame, cached)
    out["ok"] = True
    return out
