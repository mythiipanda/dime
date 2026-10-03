from typing import Any

from .. import store

END_MIN = 2015
END_MAX = 2026
CURRENT_SEASON = "2025-26"
CURRENT_END_YEAR = 2026


def to_label(end_year: int) -> str:
    y = int(end_year)
    return f"{y - 1}-{str(y)[-2:]}"


def to_end_year(season: object) -> int | None:
    s = str(season or "").strip()
    if len(s) == 4 and s.isdigit():
        return int(s)
    if len(s) == 7 and s[:4].isdigit() and s[4] == "-" and s[5:].isdigit():
        return 2000 + int(s[5:])
    return None


def _tables() -> set[str]:
    try:
        return set(store.tables())
    except Exception:
        return set()


def _num(value: object) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _rows(sql: str, params: list) -> list[dict[str, Any]]:
    try:
        con = store.connect(read_only=True)
    except Exception:
        return []
    try:
        try:
            return con.execute(sql, params).fetchdf().to_dict(orient="records")
        except Exception:
            return []
    finally:
        try:
            con.close()
        except Exception:
            pass


def raptor_end_year() -> int | None:
    if "silver_raptor_player" not in _tables():
        return None
    rows = _rows("SELECT MAX(SEASON) AS m FROM silver_raptor_player", [])
    if not rows:
        return None
    v = _num(rows[0].get("m"))
    return int(v) if v is not None else None


def _columns(table: str) -> set[str]:
    try:
        con = store.connect(read_only=True)
        try:
            return {r[1] for r in con.execute(
                f"PRAGMA table_info({table})").fetchall()}
        finally:
            try:
                con.close()
            except Exception:
                pass
    except Exception:
        return set()


def raptor_map(name: str = "", pid: int = 0) -> dict[int, float]:
    if "silver_raptor_player" not in _tables():
        return {}
    present = _columns("silver_raptor_player")
    clauses: list[str] = []
    params: list[object] = []
    if pid and "PLAYER_ID" in present:
        clauses.append("CAST(PLAYER_ID AS VARCHAR) = CAST(? AS VARCHAR)")
        params.append(str(pid))
    if name and "PLAYER_NAME" in present:
        clauses.append("LOWER(PLAYER_NAME) = LOWER(?)")
        params.append(name)
    if not clauses:
        return {}
    rows = _rows(
        "SELECT SEASON, RAPTOR_TOTAL FROM silver_raptor_player WHERE "
        + " OR ".join(clauses),
        params,
    )
    out: dict[int, float] = {}
    for r in rows:
        y = _num(r.get("SEASON"))
        v = _num(r.get("RAPTOR_TOTAL"))
        if y is not None and v is not None:
            out[int(y)] = float(v)
    return out


def _hist_rows(pid: int, name: str = "") -> list[dict[str, Any]]:
    if "silver_hist_player_seasons" not in _tables():
        return []
    if pid:
        rows = _rows(
            "SELECT player_id, player_name, team_abbreviation, season, "
            "gp, min, pts, reb, ast, stl, blk, tov, fg_pct, fg3_pct, "
            "ft_pct, ts_pct FROM silver_hist_player_seasons "
            "WHERE CAST(player_id AS VARCHAR) = CAST(? AS VARCHAR) "
            "ORDER BY season",
            [str(pid)],
        )
        if rows:
            return rows
    if name:
        return _rows(
            "SELECT player_id, player_name, team_abbreviation, season, "
            "gp, min, pts, reb, ast, stl, blk, tov, fg_pct, fg3_pct, "
            "ft_pct, ts_pct FROM silver_hist_player_seasons "
            "WHERE LOWER(player_name) = LOWER(?) ORDER BY season",
            [name],
        )
    return []


def _per_game(total: object, gp: object, nd: int = 1) -> float | None:
    t = _num(total)
    g = _num(gp)
    if t is None or g is None or g <= 0:
        return None
    return round(t / g, nd)


def current_row(pid: int) -> dict[str, Any] | None:
    if "silver_leaders_pts" not in _tables():
        return None
    rows = _rows(
        "SELECT PLAYER_ID, PLAYER, TEAM, GP, MIN, PTS, REB, AST, STL, BLK, "
        "FG_PCT, FG3_PCT, FT_PCT FROM silver_leaders_pts "
        "WHERE _season = ? AND CAST(PLAYER_ID AS VARCHAR) = "
        "CAST(? AS VARCHAR) LIMIT 1",
        [CURRENT_SEASON, str(pid)],
    )
    if not rows:
        return None
    r = rows[0]
    gp = _num(r.get("GP"))
    if gp is None or gp <= 0:
        return None
    ts = None
    if "silver_advanced" in _tables():
        a = _rows(
            "SELECT TS_PCT FROM silver_advanced WHERE _season = ? AND "
            "CAST(PLAYER_ID AS VARCHAR) = CAST(? AS VARCHAR) LIMIT 1",
            [CURRENT_SEASON, str(pid)],
        )
        if a:
            v = _num(a[0].get("TS_PCT"))
            if v is not None:
                ts = round(v / 100, 3) if v > 1.0 else round(v, 3)
    return {
        "player_id": r.get("PLAYER_ID"),
        "player_name": r.get("PLAYER"),
        "team_abbreviation": r.get("TEAM"),
        "season": CURRENT_END_YEAR,
        "gp": int(gp),
        "min": _per_game(r.get("MIN"), gp),
        "pts": _per_game(r.get("PTS"), gp),
        "reb": _per_game(r.get("REB"), gp),
        "ast": _per_game(r.get("AST"), gp),
        "stl": _per_game(r.get("STL"), gp),
        "blk": _per_game(r.get("BLK"), gp),
        "fg_pct": _num(r.get("FG_PCT")),
        "fg3_pct": _num(r.get("FG3_PCT")),
        "ft_pct": _num(r.get("FT_PCT")),
        "ts_pct": ts,
    }


def arc_for_id(pid: int) -> list[dict[str, Any]]:
    try:
        ident = int(pid)
    except (TypeError, ValueError):
        return []
    hist = _hist_rows(ident)
    name = str(hist[0].get("player_name") or "") if hist else ""
    if not name and "silver_leaders_pts" in _tables():
        lead = _rows(
            "SELECT PLAYER FROM silver_leaders_pts WHERE "
            "CAST(PLAYER_ID AS VARCHAR) = CAST(? AS VARCHAR) LIMIT 1",
            [str(ident)],
        )
        if lead:
            name = str(lead[0].get("PLAYER") or "")
    rap = raptor_map(name, ident)
    rend = raptor_end_year()
    out: list[dict[str, Any]] = []
    for h in hist:
        y = _num(h.get("season"))
        if y is None:
            continue
        year = int(y)
        rv = rap.get(year)
        out.append({
            "end_year": year,
            "season": to_label(year),
            "source": "hist",
            "player_name": h.get("player_name"),
            "team_abbreviation": h.get("team_abbreviation"),
            "gp": h.get("gp"),
            "pts": _num(h.get("pts")),
            "reb": _num(h.get("reb")),
            "ast": _num(h.get("ast")),
            "stl": _num(h.get("stl")),
            "blk": _num(h.get("blk")),
            "min": _num(h.get("min")),
            "fg_pct": _num(h.get("fg_pct")),
            "fg3_pct": _num(h.get("fg3_pct")),
            "ft_pct": _num(h.get("ft_pct")),
            "ts_pct": _num(h.get("ts_pct")),
            "raptor": rv,
            "raptor_gap": rv is None and rend is not None and year > int(rend),
        })
    cur = current_row(ident)
    if cur is not None:
        rv = rap.get(CURRENT_END_YEAR)
        cur_out: dict[str, Any] = {
            "end_year": CURRENT_END_YEAR,
            "season": CURRENT_SEASON,
            "source": "current",
            "player_name": cur.get("player_name"),
            "team_abbreviation": cur.get("team_abbreviation"),
        }
        for key in ("gp", "pts", "reb", "ast", "stl", "blk", "min",
                    "fg_pct", "fg3_pct", "ft_pct", "ts_pct"):
            cur_out[key] = cur.get(key)
        cur_out["raptor"] = rv
        cur_out["raptor_gap"] = rv is None
        out.append(cur_out)
    out.sort(key=lambda r: int(r["end_year"]))
    return out


def arc_for_name(name: str) -> list[dict[str, Any]]:
    label = str(name or "").strip()
    if not label:
        return []
    hist = _hist_rows(0, label)
    if hist:
        try:
            return arc_for_id(int(hist[0].get("player_id")))
        except (TypeError, ValueError):
            pass
    if "silver_leaders_pts" in _tables():
        lead = _rows(
            "SELECT PLAYER_ID FROM silver_leaders_pts WHERE "
            "LOWER(PLAYER) = LOWER(?) LIMIT 1",
            [label],
        )
        if lead:
            try:
                return arc_for_id(int(lead[0].get("PLAYER_ID")))
            except (TypeError, ValueError):
                return []
    return []


def line_for_season(pid: int, season: object) -> dict[str, Any] | None:
    year = to_end_year(season)
    if year is None:
        return None
    for row in arc_for_id(pid):
        if int(row["end_year"]) == year:
            return row
    return None
