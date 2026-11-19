import asyncio as _asyncio
import sys
from typing import Any

from langchain_core.tools import tool


def _pkg():
    return sys.modules[__package__]


_BUCKET_TO_ZONE = {
    "0-3ft": "Restricted Area",
    "3-10ft": "In The Paint (Non-RA)",
    "10-16ft": "Mid-Range",
    "16ft-3P": "Mid-Range",
    "3P": "Above the Break 3",
}

_HIST_THREE_ZONES = frozenset({"corner_3", "atb_3"})

_BUCKET_LEAGUE_FLOOR = 50


def _bucket_fga_fgm(rows: list[dict[str, Any]]) -> dict[str, list[float]]:
    import math as _math

    agg: dict[str, list[float]] = {}
    for row in rows:
        zone = _BUCKET_TO_ZONE.get(str(row.get("ZONE")))
        if zone is None:
            continue
        made = float(row.get("FGM") or 0)
        attempt = float(row.get("FGA") or 0)
        if not (_math.isfinite(made) and _math.isfinite(attempt)):
            continue
        slot = agg.setdefault(zone, [0.0, 0.0])
        slot[0] += made
        slot[1] += attempt
    return agg


def _bucket_league_fg(rows: list[dict[str, Any]]) -> dict[str, float]:
    return {
        zone: round(made / attempt, 3)
        for zone, (made, attempt) in _bucket_fga_fgm(rows).items()
        if attempt >= _BUCKET_LEAGUE_FLOOR
    }


def _zone_split_frame(season: str, player_id: object | None = None):
    store = _pkg().store
    if player_id is None:
        return store.read_frame("silver_zone_splits", "_season = ?", [season])
    return store.read_frame(
        "silver_zone_splits",
        "_season = ? AND CAST(PLAYER_ID AS VARCHAR) = CAST(? AS VARCHAR)",
        [season, str(player_id)],
    )


def _shot_zone_of(row: dict[str, Any]) -> str:
    import math as _math

    basic = str(row.get("SHOT_ZONE_BASIC") or "").strip()
    if basic:
        return basic
    try:
        distance = _math.hypot(float(row.get("LOC_X", 0)), float(row.get("LOC_Y", 0))) / 10
    except (TypeError, ValueError):
        return "Mid-Range"
    return "Restricted Area" if distance < 8 else ("Above the Break 3" if distance > 23.75 else "Mid-Range")


def _shot_is_made(row: dict[str, Any]) -> bool:
    return str(row.get("SHOT_MADE_FLAG", "") or "") == "1" or str(row.get("EVENT_TYPE", "")).lower().startswith("made")


def _shot_is_three(row: dict[str, Any]) -> bool:
    return "3pt" in str(row.get("SHOT_TYPE", "") or "").lower()


def _zone_shot_totals(shot_dicts: list[dict[str, Any]]) -> dict[str, list[int]]:
    totals: dict[str, list[int]] = {}
    for row in shot_dicts:
        slot = totals.setdefault(_shot_zone_of(row), [0, 0, 0])
        slot[1] += 1
        if _shot_is_made(row):
            slot[0] += 1
            if _shot_is_three(row):
                slot[2] += 1
    return totals


def _fold_agg_rows(rows: list[dict[str, Any]]) -> tuple[dict, int]:
    pkg = _pkg()
    folded = {key: [0, 0] for key in pkg._HIST_ZONE_KEYS}
    for r in rows:
        slot = folded.get(str(r.get("zone")))
        if slot is None:
            continue
        slot[1] += int(r.get("fga") or 0)
        slot[0] += int(r.get("fgm") or 0)
    return folded, sum(a for _, a in folded.values())


def _hist_zone_rows(player: dict, league: dict, total: int, floor: int) -> tuple[list, list]:
    pkg = _pkg()
    rows: list[dict[str, Any]] = []
    excluded: list[str] = []
    for key in pkg._HIST_ZONE_KEYS:
        m, a = player[key]
        if not a or a < floor:
            excluded.append(key)
            continue
        lm, la = league[key]
        threes = m if key in _HIST_THREE_ZONES else 0
        league_threes = lm if key in _HIST_THREE_ZONES else 0
        fgp = round(m / a, 3)
        efg = round((m + 0.5 * threes) / a, 3)
        league_efg = round((lm + 0.5 * league_threes) / la, 3) if la else 0.0
        share = round(a / total, 3) if total else 0.0
        rows.append(
            {
                "zone": key,
                "FGM": m,
                "FGA": a,
                "FG_PCT": fgp,
                "share": share,
                "eFG_PCT": efg,
                "SHARE": share,
                "fgm": m,
                "fga": a,
                "fg_pct": fgp,
                "freq_pct": share,
                "LEAGUE_DELTA": round(efg - league_efg, 3),
            }
        )
    return rows, excluded


def _hist_shot_zone_result(player_id: str | int, season: str, floor: int, hist_year: int) -> dict[str, Any] | None:
    pkg = _pkg()
    if not hist_year:
        return None
    try:
        league_rows = pkg._fetch_hist_aggs("silver_hist_shots", hist_year)
        player_rows = pkg._fetch_hist_aggs("silver_hist_shots", hist_year, where="person_id = ?", params=[player_id])
    except Exception:
        return None
    if not league_rows:
        return None
    folded_league, _ = _fold_agg_rows(league_rows)
    folded_player, hist_total = _fold_agg_rows(player_rows)
    if hist_total <= 0:
        return None
    hist_rows, hist_excluded = _hist_zone_rows(folded_player, folded_league, hist_total, floor)
    meta: dict[str, Any] = {
        "source": "warehouse:silver_hist_shots",
        "fetched_at": pkg._hist_fetched_at("silver_hist_shots", hist_year),
        "rows": len(hist_rows),
        "season": season,
        "cached": True,
        "baseline": "silver_hist_shots league zone eFG",
        "player_shots": hist_total,
        "min_attempts": floor,
        "excluded_zones": hist_excluded,
        "zones": dict(pkg._HIST_ZONE_LEGEND),
    }
    if not hist_rows:
        meta["note"] = (
            f"player {player_id} has {hist_total} tracked shots "
            f"but no zone reaches the {floor}-attempt floor"
        )
    return {"tool": "get_shot_zones", "ok": True, "rows": hist_rows, "meta": meta}


def _zone_split_shot_result(player_id: str | int, season: str) -> dict[str, Any] | None:
    pkg = _pkg()
    player_frame = _zone_split_frame(season, player_id)
    if player_frame.height <= 0:
        return None
    league_frame = _zone_split_frame(season)
    league_fg = _bucket_league_fg(league_frame.to_dicts()) if league_frame.height > 0 else {}
    merged = _bucket_fga_fgm(player_frame.to_dicts())
    out_rows = []
    for zone, (made, attempt) in merged.items():
        fg_pct = round(made / attempt, 3) if attempt else 0.0
        row: dict[str, Any] = {
            "zone": zone,
            "FGM": int(made),
            "FGA": int(attempt),
            "FG_PCT": fg_pct,
            "eFG_PCT": round(fg_pct * 1.5, 3) if pkg._is_three_zone(zone) else fg_pct,
            "share": 0.0,
            "fgm": int(made),
            "fga": int(attempt),
            "fg_pct": fg_pct,
            "freq_pct": 0.0,
        }
        if zone in league_fg:
            row["LEAGUE_DELTA"] = round(fg_pct - league_fg[zone], 3)
        out_rows.append(row)
    total = sum(row["FGA"] for row in out_rows) or 1
    for row in out_rows:
        row["share"] = round(row["FGA"] / total, 3)
        row["freq_pct"] = row["share"]
    meta: dict[str, Any] = {
        "source": "basketball-reference",
        "season": season,
        "rows": len(out_rows),
        "cached": True,
        "note": (
            "distance buckets mapped onto court zones "
            "(3-10ft counts as paint, both mid buckets "
            "merge, corner threes included in "
            "above-the-break), not exact NBA zones"
        ),
    }
    if league_fg:
        meta["baseline"] = "silver_zone_splits league bucket FG%"
    return {"tool": "get_shot_zones", "ok": True, "rows": out_rows, "meta": meta}


def _player_shot_dicts(player_id: str | int, season: str) -> tuple[list[dict[str, Any]], str, str, dict[str, Any] | None]:
    pkg = _pkg()
    store = pkg.store
    frame = store.read_frame(
        "silver_shots",
        "_season = ? AND CAST(PLAYER_ID AS VARCHAR) = CAST(? AS VARCHAR)",
        [season, str(player_id)],
    )
    if frame.height > 0:
        fetched = str(frame["_fetched_at"][0]) if "_fetched_at" in frame.columns else ""
        return frame.to_dicts(), "warehouse:silver_shots", fetched, None
    live = pkg.nba_stats.shot_chart(player_id, season)
    if not live.ok or live.frame.height == 0:
        return (
            [],
            "",
            "",
            {
                "tool": "get_shot_zones",
                "ok": False,
                "error": live.error or "empty upstream response",
                "meta": {
                    "coverage": "none",
                    "note": "no seeded shot data for this player and live source unreachable",
                },
            },
        )
    return live.frame.to_dicts(), live.meta.source, live.meta.fetched_at, None


def _shot_level_league_efg(season: str) -> tuple[dict[str, float], bool, str]:
    store = _pkg().store
    try:
        frame = store.read_frame("silver_shots", "_season = ?", [season])
        columns = set(frame.columns)
        if not (frame.height > 0 and {"PLAYER_ID", "SHOT_ZONE_BASIC", "SHOT_MADE_FLAG"} <= columns):
            return {}, True, "silver_shots empty or missing zone/made columns"
        players = frame.select("PLAYER_ID").n_unique()
        if players < 10:
            return {}, True, f"silver_shots has {players} player(s), need 10+"
        totals: dict[str, list[int]] = {}
        for row in frame.to_dicts():
            zone = str(row.get("SHOT_ZONE_BASIC") or "").strip() or "Mid-Range"
            slot = totals.setdefault(zone, [0, 0, 0])
            slot[1] += 1
            if _shot_is_made(row):
                slot[0] += 1
                if _shot_is_three(row):
                    slot[2] += 1
        league_efg = {
            zone: round((made + 0.5 * threes) / attempt, 3)
            for zone, (made, attempt, threes) in totals.items()
            if attempt
        }
        return league_efg, False, ""
    except Exception as exc:
        return {}, True, str(exc)[:120]


def _bucket_fallback_fg(season: str) -> dict[str, float]:
    frame = _zone_split_frame(season)
    if frame.height <= 0:
        return {}
    bucket_fg = _bucket_league_fg(frame.to_dicts())
    atb = bucket_fg.get("Above the Break 3")
    if atb is not None:
        bucket_fg.setdefault("Left Corner 3", atb)
        bucket_fg.setdefault("Right Corner 3", atb)
    return bucket_fg


def _shot_level_rows(
    totals: dict[str, list[int]],
    total: int,
    league_efg: dict[str, float],
    bucket_fg: dict[str, float],
    baseline_missing: bool,
) -> list[dict[str, Any]]:
    rows = []
    for zone, (made, attempt, threes) in sorted(totals.items()):
        fg_pct = round(made / attempt, 3) if attempt else 0.0
        efg = round((made + 0.5 * threes) / attempt, 3) if attempt else 0.0
        share = round(attempt / total, 3)
        row: dict[str, Any] = {
            "zone": zone,
            "FGM": made,
            "FGA": attempt,
            "FG_PCT": fg_pct,
            "share": share,
            "eFG_PCT": efg,
            "SHARE": share,
            "fgm": made,
            "fga": attempt,
            "fg_pct": fg_pct,
            "freq_pct": share,
        }
        if not baseline_missing and zone in league_efg:
            row["LEAGUE_DELTA"] = round(efg - league_efg[zone], 3)
        elif zone in bucket_fg:
            row["LEAGUE_DELTA"] = round(fg_pct - bucket_fg[zone], 3)
        rows.append(row)
    return rows


def _shot_level_meta(
    shot_source: str,
    shot_fetched: str,
    rows: list[dict[str, Any]],
    season: str,
    bucket_fg: dict[str, float],
    baseline_missing: bool,
    baseline_detail: str,
) -> dict[str, Any]:
    meta: dict[str, Any] = {
        "source": shot_source,
        "fetched_at": shot_fetched,
        "rows": len(rows),
        "season": season,
        "cached": shot_source.startswith("warehouse"),
    }
    if baseline_missing and bucket_fg:
        meta["baseline"] = "silver_zone_splits league bucket FG% (mapped)"
    elif baseline_missing:
        meta["baseline_missing"] = True
        if baseline_detail:
            meta["baseline_detail"] = baseline_detail
    else:
        meta["baseline"] = "silver_shots league zone eFG"
    return meta


@tool(
    description="Zone splits for one player id: rim, midrange, three with shares.\n\nWarehouse-first: historical silver_hist_shots geometric zones, then\nseeded silver_shots, then seeded silver_zone_splits\n(basketball-reference distance buckets, league-wide), then live\nshot_chart (fail-fast; endpoint-blocked from datacenter IPs).\nZones below min_attempts (default 50, clamped 10..200) are excluded."
)
def get_shot_zones(player_id: str | int, season: str | None = None, min_attempts: int = 50) -> dict[str, Any]:
    pkg = _pkg()
    season = pkg.resolve_season(season)
    player_id = pkg.coerce_player_id(player_id)
    floor = 0 if min_attempts == 0 else pkg._clamp_hist_floor(min_attempts)
    try:
        hist_year = pkg._hist_season_year(season)
    except Exception:
        hist_year = 0
    hist_result = _hist_shot_zone_result(player_id, season, floor, hist_year)
    if hist_result is not None:
        return hist_result
    split_result = _zone_split_shot_result(player_id, season)
    if split_result is not None:
        return split_result
    shot_dicts, shot_source, shot_fetched, failure = _player_shot_dicts(player_id, season)
    if failure is not None:
        return failure
    totals = _zone_shot_totals(shot_dicts)
    total = sum(attempt for _, attempt, _ in totals.values()) or 1
    league_efg, baseline_missing, baseline_detail = _shot_level_league_efg(season)
    bucket_fg: dict[str, float] = {}
    if baseline_missing:
        bucket_fg = _bucket_fallback_fg(season)
        if not bucket_fg:
            baseline_detail = (
                "league baseline unavailable: shot-level data "
                "seeded for few players and bucket table "
                "missing for this season"
            )
    rows = _shot_level_rows(totals, total, league_efg, bucket_fg, baseline_missing)
    meta = _shot_level_meta(shot_source, shot_fetched, rows, season, bucket_fg, baseline_missing, baseline_detail)
    return {"tool": "get_shot_zones", "ok": True, "rows": rows, "meta": meta}


def _zone_float(row: dict, *keys: str) -> float | None:
    for k in keys:
        v = row.get(k)
        if v is None:
            continue
        try:
            return float(v)
        except (TypeError, ValueError):
            continue
    return None


def _compare_zone_row(zone: str, ra: dict, rb: dict, a: str, b: str) -> dict[str, Any]:
    ae, be = _zone_float(ra, "eFG_PCT"), _zone_float(rb, "eFG_PCT")
    afg, bfg = _zone_float(ra, "FG_PCT", "fg_pct"), _zone_float(rb, "FG_PCT", "fg_pct")
    ash, bsh = _zone_float(ra, "SHARE", "share"), _zone_float(rb, "SHARE", "share")
    if ae is None or be is None or ash is None or bsh is None:
        edge = None
    elif max(ash, bsh) < 0.05 or ae == be:
        edge = "wash"
    else:
        edge = a if ae > be else b
    return {
        "zone": zone,
        "a_eFG": ae,
        "b_eFG": be,
        "a_fg": afg,
        "b_fg": bfg,
        "a_share": ash,
        "b_share": bsh,
        "edge": edge,
    }


def _zone_owner(row: dict[str, Any] | None, a: str, b: str, check_share: bool) -> str | None:
    if not row or row["a_eFG"] is None or row["b_eFG"] is None:
        return None
    if check_share and (row["a_share"] is None or row["b_share"] is None or max(row["a_share"], row["b_share"]) < 0.05):
        return None if row["a_share"] is None or row["b_share"] is None else "wash"
    if row["a_eFG"] == row["b_eFG"]:
        return "wash"
    return a if row["a_eFG"] > row["b_eFG"] else b


@tool(
    description="Shot-diet showdown: zone eFG and share for two players.\n\nMissing zone data stays null, never 0.0: a player without a seeded\nzone row has NO data there, not a 0% shooter. Edges and the verdict\nare computed only where BOTH players have data; takeaways must never\nbe built on a missing cell."
)
async def get_shot_compare(a: str, b: str, season: str | None = None) -> dict[str, Any]:
    pkg = _pkg()
    season = pkg.resolve_season(season)

    async def _zones(who: str) -> dict[str, dict]:
        try:
            pid = pkg.coerce_player_id(who)
            res = await pkg.get_shot_zones.ainvoke({"player_id": pid, "season": season})
            return {r.get("zone", "?"): r for r in res.get("rows", [])}
        except Exception:
            return {}

    ma, mb = await _asyncio.gather(_zones(a), _zones(b))
    a, b = pkg._display_name(a), pkg._display_name(b)
    missing = [n for n, m in ((a, ma), (b, mb)) if not m]
    rows = [_compare_zone_row(z, ma.get(z, {}), mb.get(z, {}), a, b) for z in sorted(set(ma) | set(mb))]
    rim = next((r for r in rows if r["zone"] in ("Restricted Area", "rim")), None)
    rim_owner = _zone_owner(rim, a, b, check_share=True)
    threes = [r for r in rows if pkg._is_three_zone(r["zone"]) and r["a_share"] is not None and r["b_share"] is not None]
    arc = max(threes, key=lambda r: max(r["a_share"], r["b_share"]), default=None)
    arc_owner = _zone_owner(arc, a, b, check_share=False)
    arc_zone = arc["zone"] if arc_owner is not None and arc else None
    if missing:
        verdict = (
            f"Shot diet unavailable for {', '.join(missing)} in {season}; "
            "comparison shown only where both players have seeded zone data."
        )
    else:
        rim_txt = {"wash": "neither owns the rim", None: "rim data missing"}.get(rim_owner, f"{rim_owner} owns the rim")
        arc_txt = {"wash": "neither owns the arc", None: "arc data missing"}.get(
            arc_owner, f"{arc_owner} owns the arc ({arc_zone})"
        )
        verdict = f"{rim_txt}; {arc_txt}."
    meta: dict[str, Any] = {
        "source": "warehouse",
        "season": season,
        "a": a,
        "b": b,
        "arc_zone": arc_zone,
        "arc_edge": arc_owner,
    }
    if missing:
        meta["missing_zone_data"] = missing
    return {"tool": "get_shot_compare", "ok": True, "rows": rows, "verdict": verdict, "meta": meta}
