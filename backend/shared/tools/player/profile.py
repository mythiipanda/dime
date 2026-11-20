import datetime as _dt
import sys
from typing import Any

from langchain_core.tools import tool


def _pkg():
    return sys.modules[__package__]


_CAREER_STAT_KEYS = ("GP", "MIN", "PTS", "REB", "AST", "STL", "BLK", "FG3M")


@tool(
    description='Full NBA regular-season career totals for one player.\n\nLive primary source first (true full career); when the live source\nis unreachable, sums the warehouse season lines (2014-15 onward,\nper-game rates x games) and marks the coverage partial instead of\ninventing a full-career figure (F77: text_to_sql used to sum a\nwrong slice and ship fabricated totals like "291.5 career points").'
)
def get_career_totals(player: str) -> dict[str, Any]:
    pkg = _pkg()
    try:
        pid = pkg.coerce_player_id(player)
    except Exception:
        pid = 0
    if not pid:
        return {"tool": "get_career_totals", "ok": False, "error": f"I don't recognize the player '{player}'."}
    name = pkg._display_name(player)
    res = pkg.nba_stats.career_totals(int(pid))
    if res.ok and res.frame is not None and res.frame.height > 0:
        row = {str(k).lower(): v for k, v in res.frame.to_dicts()[0].items()}
        out = {"player": name}
        for key in _CAREER_STAT_KEYS:
            out[key] = pkg._num(row.get(key.lower()))
        return {
            "tool": "get_career_totals",
            "ok": True,
            "rows": [out],
            "meta": {"source": "nba_api", "coverage": "full_career"},
        }

    store = pkg.store
    hist = store.read_frame("silver_hist_player_seasons", "player_id = ?", [int(pid)])
    sums: dict[str, float] = {}
    seasons = hist.height
    for r in hist.to_dicts():
        gp = pkg._num(r.get("gp")) or 0.0
        sums["GP"] = sums.get("GP", 0.0) + gp
        for key, col in (
            ("MIN", "min"),
            ("PTS", "pts"),
            ("REB", "reb"),
            ("AST", "ast"),
            ("STL", "stl"),
            ("BLK", "blk"),
            ("FG3M", "fg3m"),
        ):
            rate = pkg._num(r.get(col))
            if rate is not None:
                sums[key] = sums.get(key, 0.0) + rate * gp
    through = "2024-25"
    cur = store.read_frame("silver_player_season", "PLAYER_ID = ?", [int(pid)])
    if cur.height > 0:
        r = cur.to_dicts()[0]
        gp = pkg._num(r.get("GP")) or 0.0
        if gp:
            through = str(r.get("_season") or "") or pkg.resolve_season(None) or through
            seasons += 1
            sums["GP"] = sums.get("GP", 0.0) + gp
            for key, col in (
                ("MIN", "MPG"),
                ("PTS", "PPG"),
                ("REB", "RPG"),
                ("AST", "APG"),
                ("STL", "SPG"),
                ("BLK", "BPG"),
            ):
                rate = pkg._num(r.get(col))
                if rate is not None:
                    sums[key] = sums.get(key, 0.0) + rate * gp
    if not sums:
        return {
            "tool": "get_career_totals",
            "ok": False,
            "error": (
                f"Career totals for {name} aren't available "
                "right now; the live stats source didn't "
                "respond and no season lines are on file."
            ),
        }
    out = {"player": name}
    out.update({k: round(v) for k, v in sums.items()})
    return {
        "tool": "get_career_totals",
        "ok": True,
        "rows": [out],
        "meta": {
            "source": "warehouse",
            "coverage": "partial_from_2014-15",
            "through": through,
            "seasons_on_file": seasons,
        },
    }


@tool(description="Game log plus shot sample for one player id. Warehouse first.")
def get_player_intel(player_id: str | int, season: str | None = None) -> dict[str, Any]:
    pkg = _pkg()
    season = pkg.resolve_season(season)
    player_id = pkg.coerce_player_id(player_id)

    rows, meta = pkg._warehouse_or_live(
        "silver_player_gamelogs",
        "_season = ? AND _entity = ?",
        [season, f"player:{player_id}"],
        lambda: pkg.nba_stats.player_gamelog(player_id, season),
        season,
        entity=f"player:{player_id}",
        ttl_s=pkg.TTL_GAMELOG,
        limit=500,
    )
    if not rows:
        line = pkg._season_line(player_id, season)
        if line:
            std = pkg._std_context(player_id, season, line)
            return {
                "tool": "get_player_intel",
                "ok": True,
                "rows": [line],
                "meta": {
                    "source": "basketball-reference",
                    "season": season,
                    "coverage": "season_line",
                    "note": "game-by-game log not seeded for this player; showing season line",
                    **({"season_to_date": std} if std else {}),
                },
            }
        from ..splits import _resolve_name as _rname3

        _d = _rname3(int(player_id), str(player_id))
        return {
            "tool": "get_player_intel",
            "ok": False,
            "error": (
                f"No {season} game log rows for {_d}; "
                f"{pkg._gamelog_coverage()}, and season "
                "lines cover 2014-15 onward."
            ),
        }
    std = pkg._std_context(player_id, season, None)
    if std:
        meta = {**meta, "season_to_date": std}
    out: dict[str, Any] = {"tool": "get_player_intel", "ok": True, "rows": rows, "meta": meta}
    try:
        from ..gamelog import playoff_inactive_note as _pin
        from ..splits import _resolve_name as _rname4

        _note = _pin(int(player_id), season, _rname4(int(player_id), str(player_id)))
        if _note:
            out["inactive_note"] = _note
    except Exception:
        pass
    return out


@tool(
    description="Per-game season averages (PPG, RPG, APG, SPG, BPG, percentages,\ngames played) for one player. Names or ids. Warehouse only, seeded\nfrom basketball-reference; no game-by-game detail."
)
def get_season_averages(player_id: str | int, season: str | None = None) -> dict[str, Any]:
    pkg = _pkg()
    season = pkg.resolve_season(season)
    try:
        pid = pkg.coerce_player_id(player_id)
    except ValueError:
        return {"tool": "get_season_averages", "ok": False, "error": f"unknown player: {player_id}"}
    line = pkg._season_line(pid, season)
    if not line:
        _covered = pkg._season_line_seasons()
        if _covered is not None and season not in _covered:
            return {
                "tool": "get_season_averages",
                "ok": False,
                "error": f"No season line on file for {season}; " + pkg._season_line_coverage() + ".",
                "season_error": True,
            }
        return {
            "tool": "get_season_averages",
            "ok": False,
            "error": f"No season line on file for {season}; " + pkg._season_line_coverage() + ".",
        }
    name = str(line.get("PLAYER") or player_id)
    answer = (
        f"{name} averaged {float(line['PPG']):g} points, "
        f"{float(line['RPG']):g} rebounds, and {float(line['APG']):g} assists "
        f"in {int(line['GP'])} games during the {season} season. "
        f"He shot {float(line['FG_PCT']) * 100:.1f}% from the field, "
        f"{float(line['FG3_PCT']) * 100:.1f}% from three, and "
        f"{float(line['FT_PCT']) * 100:.1f}% at the line."
    )
    std = pkg._std_context(pid, season, line)
    return {
        "tool": "get_season_averages",
        "ok": True,
        "rows": [line],
        "meta": {
            "source": "basketball-reference",
            "season": season,
            "coverage": "season_line",
            "deterministic_answer": answer,
            **({"season_to_date": std} if std else {}),
        },
    }


@tool(description="Playoff game log for one player. Names or ids. Warehouse first.")
def get_playoff_intel(player_id: str | int, season: str | None = None) -> dict[str, Any]:
    pkg = _pkg()
    season = pkg.resolve_season(season)
    try:
        pid = pkg.coerce_player_id(player_id)
    except ValueError:
        return {"tool": "get_playoff_intel", "ok": False, "error": f"unknown player: {player_id}"}
    rows, meta = pkg._warehouse_or_live(
        "silver_playoff_gamelogs",
        "_season = ? AND _entity = ?",
        [season, f"player:{pid}"],
        lambda: pkg.nba_stats.player_playoff_gamelog(pid, season),
        season,
        entity=f"player:{pid}",
        ttl_s=pkg.TTL_GAMELOG,
        limit=100,
    )
    if not rows:
        try:
            con = pkg.store.connect()
            try:
                tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
                if "silver_playoff_gamelogs" in tables:
                    seasons = sorted(
                        r[0]
                        for r in con.execute("SELECT DISTINCT _season FROM silver_playoff_gamelogs").fetchall()
                        if r[0]
                    )
                else:
                    seasons = []
            finally:
                con.close()
        except Exception:
            seasons = []
        from ..gamelog import playoff_inactive_note as _pin
        from ..splits import _resolve_name as _rname

        _disp = _rname(pid, str(player_id))
        note = _pin(pid, season, _disp)
        if note:
            err = f"No playoff games found for {_disp} in {season}: {note}."
        elif seasons:
            coverage = ", ".join(seasons)
            err = f"No playoff games found for {_disp} in {season} (playoff coverage: {coverage})."
        else:
            err = f"No playoff games found for {_disp} in {season} and no playoff seasons are stored yet."
        return {"tool": "get_playoff_intel", "ok": False, "error": err}
    cols = ["GAME_DATE", "MATCHUP", "PTS", "REB", "AST", "MIN"]
    slim = [{k: r.get(k) for k in cols if k in r} for r in rows]

    from ..splits import _resolve_name as _pnm

    _disp = _pnm(pid, str(player_id))
    for r in slim:
        r["PLAYER"] = _disp

    def _sum(col: str) -> int:
        return int(sum(float(r.get(col) or 0) for r in slim))

    meta = dict(meta or {})
    meta["player"] = _disp
    meta["totals"] = {
        "GP": len(slim),
        "PTS": _sum("PTS"),
        "REB": _sum("REB"),
        "AST": _sum("AST"),
        "MIN": _sum("MIN"),
    }
    meta["totals_note"] = (
        "Canonical series totals - quote these verbatim for any "
        "aggregate ask instead of summing the rows yourself."
    )
    gp = len(slim)
    if gp:
        meta["deterministic_answer"] = (
            f"{_disp} averaged {meta['totals']['PTS'] / gp:.1f} points, "
            f"{meta['totals']['REB'] / gp:.1f} rebounds, and "
            f"{meta['totals']['AST'] / gp:.1f} assists over {gp} playoff "
            f"games in the {season} season."
        )
    return {"tool": "get_playoff_intel", "ok": True, "rows": slim, "meta": meta}


@tool(description="Last n games for one player id, most recent first.")
def get_last_x(player_id: str | int, n: int = 10, season: str | None = None) -> dict[str, Any]:
    pkg = _pkg()
    season = pkg.resolve_season(season)
    player_id = pkg.coerce_player_id(player_id)

    rows, meta = pkg._warehouse_or_live(
        "silver_player_gamelogs",
        "_season = ? AND _entity = ?",
        [season, f"player:{player_id}"],
        lambda: pkg.nba_stats.player_gamelog(player_id, season),
        season,
        entity=f"player:{player_id}",
        ttl_s=pkg.TTL_GAMELOG,
        limit=500,
    )
    if not rows:
        line = pkg._season_line(player_id, season)
        if line:
            return {
                "tool": "get_last_x",
                "ok": True,
                "rows": [line],
                "meta": {
                    "source": "basketball-reference",
                    "season": season,
                    "coverage": "season_line",
                    "note": "game-by-game log not seeded for this player; showing season line",
                },
            }
        return {"tool": "get_last_x", "ok": False, "error": meta.get("error") or "empty upstream response"}
    import polars as _pl

    frame = _pl.DataFrame(rows)
    try:
        frame = frame.with_columns(
            _pl.col("GAME_DATE")
            .str.strptime(_pl.Date, "%b %d, %Y", strict=False)
            .fill_null(_pl.col("GAME_DATE").str.strptime(_pl.Date, "%Y-%m-%d", strict=False))
            .alias("_d")
        )
        if frame.filter(_pl.col("_d").is_null() & _pl.col("GAME_DATE").is_not_null()).height:
            frame = frame.drop("_d")
            raise ValueError("unparseable GAME_DATE")
        frame = frame.sort("_d", descending=True).drop("_d")
    except Exception:
        frame = frame.reverse()
    out = frame.head(min(max(n, 1), 25)).to_dicts()
    return {"tool": "get_last_x", "ok": True, "rows": out, "meta": meta}


@tool(description="Decay-weighted recent form versus season baseline. DARKO-lite.")
def get_trend(player_id: str | int, season: str | None = None) -> dict[str, Any]:
    pkg = _pkg()
    season = pkg.resolve_season(season)
    player_id = pkg.coerce_player_id(player_id)

    rows, meta = pkg._warehouse_or_live(
        "silver_player_gamelogs",
        "_season = ? AND _entity = ?",
        [season, f"player:{player_id}"],
        lambda: pkg.nba_stats.player_gamelog(player_id, season),
        season,
        entity=f"player:{player_id}",
        ttl_s=pkg.TTL_GAMELOG,
        limit=500,
    )
    if not rows:
        return {"tool": "get_trend", "ok": False, "error": meta.get("error") or "empty upstream response"}

    from ..splits import parse_game_date as _pgd

    rows = sorted(rows, key=lambda r: _pgd(r.get("GAME_DATE")) or _dt.datetime.min)
    try:
        pts = [float(r.get("PTS") or 0) for r in rows]
    except (TypeError, ValueError):
        return {"tool": "get_trend", "ok": False, "error": "bad points"}
    if len(pts) < 5:
        return {"tool": "get_trend", "ok": False, "error": "too few games"}
    decay = 0.94
    weights = [decay ** (len(pts) - 1 - i) for i in range(len(pts))]
    recent = pts[-20:]
    rw = weights[-len(recent) :]
    form = sum(p * w for p, w in zip(recent, rw)) / sum(rw)
    base = sum(pts) / len(pts)
    return {
        "tool": "get_trend",
        "ok": True,
        "rows": {
            "games": len(pts),
            "season_ppg": round(base, 1),
            "form_ppg": round(form, 1),
            "delta": round(form - base, 1),
            "direction": "up" if form > base + 1 else ("down" if form < base - 1 else "flat"),
            "log_from": rows[0].get("GAME_DATE"),
            "log_to": rows[-1].get("GAME_DATE"),
            "form_from": rows[-len(recent)].get("GAME_DATE"),
            "form_games": len(recent),
        },
        "meta": meta,
    }


@tool(description="Percentile ranks for one player id across PTS REB AST STL BLK.")
def get_percentiles(player_id: str | int, season: str | None = None) -> dict[str, Any]:
    pkg = _pkg()
    season = pkg.resolve_season(season)
    player_id = pkg.coerce_player_id(player_id)
    cats = ["PTS", "REB", "AST", "STL", "BLK"]
    out: dict[str, Any] = {}
    for cat in cats:
        table = f"silver_leaders_{cat.lower()}"
        rows, _ = pkg._warehouse_or_live(
            table,
            "_season = ?",
            [season],
            lambda c=cat: pkg.nba_stats.leaders(c, season),
            season,
            limit=600,
            ttl_s=pkg.TTL_LEADERS,
        )
        hit = next((r for r in rows if r.get("PLAYER_ID") == player_id), None)
        if hit and hit.get("RANK"):
            store = pkg.store
            total = len(store.read_frame(table, "_season = ?", [season]))
            out[cat] = {
                "rank": hit["RANK"],
                "percentile": round(100 * (1 - (hit["RANK"] - 1) / max(total, 1)), 1),
            }
    return {"tool": "get_percentiles", "ok": True, "rows": out, "meta": {"source": "nba_api", "season": season}}


ADVANCED_COLS = [
    "PLAYER_NAME",
    "TEAM_ABBREVIATION",
    "GP",
    "MIN",
    "USG_PCT",
    "TS_PCT",
    "EFG_PCT",
    "AST_PCT",
    "TM_TOV_PCT",
    "PIE",
    "OFF_RATING",
    "DEF_RATING",
    "NET_RATING",
    "USG_PCT_RANK",
    "TS_PCT_RANK",
    "PIE_RANK",
    "NET_RATING_RANK",
]


@tool(description="Advanced box metrics for one player: usage, efficiency, PIE, ratings.")
def get_advanced(player: str | int, season: str | None = None) -> dict[str, Any]:
    pkg = _pkg()
    season = pkg.resolve_season(season)
    player_id = pkg.coerce_player_id(player)
    rows: list[dict[str, Any]] = []
    try:
        rows = pkg._read_df(
            "SELECT * FROM silver_advanced WHERE _season = ? AND CAST(PLAYER_ID AS VARCHAR) = CAST(? AS VARCHAR)",
            [season, str(player_id)],
        )
    except Exception:
        rows = []
    if not rows:
        res = pkg.nba_stats.player_advanced(season)
        if res.ok and res.frame.height:
            try:
                pkg.store.save_frame("silver_advanced", res, "player-advanced")
            except Exception:
                pass
            rows = [r for r in res.frame.to_dicts() if str(r.get("PLAYER_ID")) == str(player_id)][:1]
    else:
        rows = rows[:1]
    if not rows:
        return {"tool": "get_advanced", "ok": False, "error": f"no advanced row for player {player_id}"}
    slim = {k: rows[0].get(k) for k in ADVANCED_COLS if k in rows[0]}

    for k in ("USG_PCT", "TS_PCT", "EFG_PCT", "AST_PCT", "PIE"):
        v = slim.get(k)
        if isinstance(v, (int, float)) and v <= 1.0:
            slim[k] = round(v * 100, 1)
    return {
        "tool": "get_advanced",
        "ok": True,
        "rows": slim,
        "meta": {"source": "nba_api", "season": season, "units": "percentages on 0-100 scale"},
    }
