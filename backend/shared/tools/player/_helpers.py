import logging as _logging
import sys
from typing import Any


def _pkg():
    return sys.modules[__package__]


_logger = _logging.getLogger(__name__)


def _num(value: object) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _is_three_zone(name: object) -> bool:
    z = str(name or "").lower()
    return "3" in z or "corner" in z or "break" in z


def _display_name(raw: object) -> str:
    txt = str(raw or "").strip()
    if not txt.isdigit():
        return txt
    try:
        from nba_api.stats.static import players as _pl_static

        hit = _pl_static.find_player_by_id(int(txt))
        if hit and hit.get("full_name"):
            return str(hit["full_name"])
    except Exception:
        pass
    return txt


def _read_df(sql: str, params: list, tries: int = 5) -> list[dict[str, Any]]:
    import time as _time

    import duckdb as _duckdb

    pkg = _pkg()
    last: Exception | None = None
    for _ in range(tries):
        try:
            con = pkg.store.connect(read_only=True)
            try:
                return con.execute(sql, params).fetchdf().to_dict(orient="records")
            finally:
                con.close()
        except _duckdb.CatalogException:
            raise
        except Exception as exc:
            last = exc
            _time.sleep(0.3)
    raise last or RuntimeError("warehouse read failed")


def _season_line_seasons() -> set[str] | None:
    try:
        from shared.coverage import table_seasons as _seasons
    except Exception:
        return None
    try:
        return set(_seasons("silver_player_season")) | set(_seasons("silver_hist_player_seasons"))
    except Exception:
        return None


def _season_line_coverage() -> str:
    _covered = _pkg()._season_line_seasons()
    if not _covered:
        return "season lines cover 2014-15 through the current season"
    _lo, _hi = min(_covered), max(_covered)
    if _lo == _hi:
        return f"season lines cover {_lo}"
    return f"season lines cover {_lo} through {_hi}"


def _gamelog_coverage() -> str:
    pkg = _pkg()
    try:
        con = pkg.store.connect(read_only=True)
        try:
            seasons = sorted(
                {
                    row[0]
                    for row in con.execute("SELECT DISTINCT _season FROM silver_player_gamelogs").fetchall()
                    if row[0]
                },
                key=lambda s: s[:4],
            )
        finally:
            con.close()
    except Exception:
        return "game logs cover the seasons stored in the warehouse"
    if not seasons:
        return "game logs cover the seasons stored in the warehouse"
    if len(seasons) == 1:
        return f"game logs cover {seasons[0]}"
    return f"game logs cover {seasons[0]}\u2013{seasons[-1]}"


def _season_line(player_id: object, season: str) -> dict[str, Any] | None:
    pkg = _pkg()
    store = pkg.store
    season = pkg.resolve_season(season)
    frame = store.read_frame(
        "silver_player_season",
        "_season = ? AND CAST(PLAYER_ID AS VARCHAR) = CAST(? AS VARCHAR)",
        [season, str(player_id)],
    )
    if frame.height > 0:
        row = frame.to_dicts()[0]
        if str(row.get("TEAM") or "").endswith("TM"):
            n = str(row["TEAM"])[:-2]
            row["TEAM"] = f"traded mid-season ({n} teams)"
        return {k: v for k, v in row.items() if not k.startswith("_")}

    frame = store.read_frame(
        "silver_hist_player_seasons",
        "_season = ? AND CAST(player_id AS VARCHAR) = CAST(? AS VARCHAR)",
        [season, str(player_id)],
    )
    if frame.height > 0:
        h = frame.to_dicts()[0]
        row = {
            "PLAYER_ID": h.get("player_id"),
            "PLAYER": h.get("player_name"),
            "TEAM": h.get("team_abbreviation"),
            "AGE": h.get("age"),
            "GP": h.get("gp"),
            "MPG": h.get("min"),
            "PPG": h.get("pts"),
            "RPG": h.get("reb"),
            "APG": h.get("ast"),
            "SPG": h.get("stl"),
            "BPG": h.get("blk"),
            "FG_PCT": h.get("fg_pct"),
            "FG3_PCT": h.get("fg3_pct"),
            "FT_PCT": h.get("ft_pct"),
            "TS_PCT": h.get("ts_pct"),
        }
        return {k: v for k, v in row.items() if v is not None}
    try:
        from ..career_arc import line_for_season as _arc_line

        arc = _arc_line(int(str(player_id)) if str(player_id).isdigit() else 0, season)
        if arc:
            row = {
                "PLAYER_ID": player_id,
                "PLAYER": arc.get("player_name"),
                "TEAM": arc.get("team_abbreviation"),
                "GP": arc.get("gp"),
                "MPG": arc.get("min"),
                "PPG": arc.get("pts"),
                "RPG": arc.get("reb"),
                "APG": arc.get("ast"),
                "SPG": arc.get("stl"),
                "BPG": arc.get("blk"),
                "FG_PCT": arc.get("fg_pct"),
                "FG3_PCT": arc.get("fg3_pct"),
                "FT_PCT": arc.get("ft_pct"),
                "TS_PCT": arc.get("ts_pct"),
            }
            slim = {k: v for k, v in row.items() if v is not None}
            if slim.get("PPG") is not None and slim.get("GP") is not None:
                return slim
    except Exception:
        pass
    return None
