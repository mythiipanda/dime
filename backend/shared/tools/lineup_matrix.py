
from typing import Any

from langchain_core.tools import tool

from .. import store as _store
from ..sources import nba_stats
from ._core import MAX_ROWS, TTL_PBPSTATS, _warehouse_or_live, clamp_season, coerce_team_id, last_completed_season, resolve_season
from .lineup import _dedupe_lineup_rows
from .team import _lineup_key

UnitKey = tuple[int, int, int, int, int]
PairKey = tuple[UnitKey, UnitKey]

SMALL_PAIR_POSS = 30
_BLOWOUT_MARGIN = 20
_BLOWOUT_SHARE_FLAG = 0.5

_NO_DATA_NOTE = (
    "no play-level possession data for this matchup in the warehouse;"
    " nothing estimated, nothing fabricated"
)


def _unit_key(players: list) -> UnitKey | None:
    try:
        if len(players) != 5:
            return None
        return tuple(sorted(int(p) for p in players))
    except (TypeError, ValueError):
        return None


def _unit_from_row(r: dict[str, Any], prefix: str) -> UnitKey | None:
    return _unit_key([r.get(f"{prefix}_player_{i}") for i in range(1, 6)])


def _season_lineup_minutes(
    poss_rows: list[dict], team_id: int,
) -> dict[UnitKey, int]:
    counts: dict[UnitKey, int] = {}
    for r in poss_rows or []:
        try:
            off_tid = int(r.get("offense_team_id"))
            def_tid = int(r.get("defense_team_id"))
        except (TypeError, ValueError):
            continue
        if off_tid == team_id:
            key = _unit_from_row(r, "off")
            if key is not None:
                counts[key] = counts.get(key, 0) + 1
        if def_tid == team_id:
            key = _unit_from_row(r, "def")
            if key is not None:
                counts[key] = counts.get(key, 0) + 1
    return counts


def _pair_flags(poss: int, blowout_share: float) -> list[str]:
    flags: list[str] = []
    if poss < SMALL_PAIR_POSS:
        flags.append(
            f"tiny-sample: {poss} shared possessions under the "
            f"{SMALL_PAIR_POSS}-possession floor, not signal")
    if blowout_share >= _BLOWOUT_SHARE_FLAG:
        flags.append(
            f"blowout-heavy: {round(blowout_share * 100)}% of shared "
            "possessions played with a 20+ point margin")
    flags.append(
        "estimated-minutes: shared court time estimated from possessions "
        "(~2 possessions per minute), not play-clock minutes")
    return flags


def _pair_row(
    key_a: UnitKey, key_b: UnitKey, agg: dict, name_a: str, name_b: str,
) -> dict[str, Any]:
    poss = agg.get("poss", 0)
    off_a = agg.get("off_poss_a", 0)
    off_b = agg.get("off_poss_b", 0)
    pts_a = agg.get("pts_a", 0)
    pts_b = agg.get("pts_b", 0)
    blowout = agg.get("blowout", 0)
    off_r = round(pts_a / off_a * 100, 1) if off_a else 0.0
    def_r = round(pts_b / off_b * 100, 1) if off_b else 0.0
    share = round(blowout / poss, 3) if poss else 0.0
    return {
        "team_a_lineup": name_a,
        "team_a_ids": list(key_a),
        "team_b_lineup": name_b,
        "team_b_ids": list(key_b),
        "poss": poss,
        "est_minutes": round(poss / 2, 1),
        "off_poss_a": off_a,
        "off_poss_b": off_b,
        "pts_a": pts_a,
        "pts_b": pts_b,
        "OFF_RATING_A": off_r,
        "DEF_RATING_A": def_r,
        "NET_RATING_A": round(off_r - def_r, 1),
        "blowout_share": share,
        "flags": _pair_flags(poss, share),
    }


def _truncate_note(total: int, shown: int) -> str:
    return (f"showing {shown} of {total} pairs "
            f"(top by estimated minutes)")


def _surname_map(season: str) -> dict[int, str]:
    season = resolve_season(season)
    try:
        rows = _store._read_df(
            "SELECT player_id, player_name FROM silver_hist_player_seasons"
            " WHERE _season = ?",
            [season],
        )
    except Exception:
        return {}
    out: dict[int, str] = {}
    try:
        for r in rows or []:
            try:
                pid = int(r.get("player_id"))  # type: ignore[arg-type]
            except (TypeError, ValueError):
                continue
            name = str(r.get("player_name") or "").strip()
            if not name:
                continue
            out[pid] = name.split()[-1]
    except Exception:
        return {}
    return out


def _fallback_name(key: UnitKey, surnames: dict[int, str] | None = None) -> str:
    if surnames:
        try:
            if all(i in surnames for i in key):
                return ", ".join(surnames[i] for i in key)
        except (TypeError, KeyError):
            pass
    return "unit " + str(key[0])[:6] + "…"


_SEASON_UNITS_SQL = (
    "SELECT team, p1, p2, p3, p4, p5, COUNT(*) AS n FROM ("
    " SELECT offense_team_id AS team,"
    " off_player_1 AS p1, off_player_2 AS p2, off_player_3 AS p3,"
    " off_player_4 AS p4, off_player_5 AS p5"
    " FROM silver_hist_possessions"
    " WHERE _season = ? AND offense_team_id IN (?, ?)"
    " AND count_as_possession = 'true'"
    " AND off_player_1 IS NOT NULL AND off_player_2 IS NOT NULL"
    " AND off_player_3 IS NOT NULL AND off_player_4 IS NOT NULL"
    " AND off_player_5 IS NOT NULL"
    " UNION ALL"
    " SELECT defense_team_id AS team,"
    " def_player_1 AS p1, def_player_2 AS p2, def_player_3 AS p3,"
    " def_player_4 AS p4, def_player_5 AS p5"
    " FROM silver_hist_possessions"
    " WHERE _season = ? AND defense_team_id IN (?, ?)"
    " AND count_as_possession = 'true'"
    " AND def_player_1 IS NOT NULL AND def_player_2 IS NOT NULL"
    " AND def_player_3 IS NOT NULL AND def_player_4 IS NOT NULL"
    " AND def_player_5 IS NOT NULL"
    " ) GROUP BY team, p1, p2, p3, p4, p5"
)


_PAIR_AGGS_SQL = (
    "SELECT ua1, ua2, ua3, ua4, ua5, ub1, ub2, ub3, ub4, ub5,"
    " COUNT(*) AS poss,"
    " COUNT(*) FILTER (offense_team_id = ?) AS off_poss_a,"
    " COUNT(*) FILTER (offense_team_id = ?) AS off_poss_b,"
    " COALESCE(SUM(points) FILTER (offense_team_id = ?), 0) AS pts_a,"
    " COALESCE(SUM(points) FILTER (offense_team_id = ?), 0) AS pts_b,"
    " COUNT(*) FILTER (ABS(margin) >= ?) AS blowout,"
    " MIN(game_id || LPAD(CAST(possession_number AS VARCHAR), 20, '0'))"
    " AS first_seen"
    " FROM ("
    " SELECT game_id, possession_number, offense_team_id,"
    " COALESCE(points, 0) AS points,"
    " CASE WHEN offense_team_id = ?"
    " THEN off_player_1 ELSE def_player_1 END AS ua1,"
    " CASE WHEN offense_team_id = ?"
    " THEN off_player_2 ELSE def_player_2 END AS ua2,"
    " CASE WHEN offense_team_id = ?"
    " THEN off_player_3 ELSE def_player_3 END AS ua3,"
    " CASE WHEN offense_team_id = ?"
    " THEN off_player_4 ELSE def_player_4 END AS ua4,"
    " CASE WHEN offense_team_id = ?"
    " THEN off_player_5 ELSE def_player_5 END AS ua5,"
    " CASE WHEN offense_team_id = ?"
    " THEN off_player_1 ELSE def_player_1 END AS ub1,"
    " CASE WHEN offense_team_id = ?"
    " THEN off_player_2 ELSE def_player_2 END AS ub2,"
    " CASE WHEN offense_team_id = ?"
    " THEN off_player_3 ELSE def_player_3 END AS ub3,"
    " CASE WHEN offense_team_id = ?"
    " THEN off_player_4 ELSE def_player_4 END AS ub4,"
    " CASE WHEN offense_team_id = ?"
    " THEN off_player_5 ELSE def_player_5 END AS ub5,"
    " COALESCE(SUM(CASE WHEN offense_team_id = ?"
    " THEN COALESCE(points, 0) ELSE 0 END) OVER w"
    " - SUM(CASE WHEN offense_team_id = ?"
    " THEN COALESCE(points, 0) ELSE 0 END) OVER w, 0) AS margin"
    " FROM silver_hist_possessions"
    " WHERE _season = ?"
    " AND ((offense_team_id = ? AND defense_team_id = ?)"
    " OR (offense_team_id = ? AND defense_team_id = ?))"
    " AND count_as_possession = 'true'"
    " AND offense_team_id <> defense_team_id"
    " AND off_player_1 IS NOT NULL AND off_player_2 IS NOT NULL"
    " AND off_player_3 IS NOT NULL AND off_player_4 IS NOT NULL"
    " AND off_player_5 IS NOT NULL"
    " AND def_player_1 IS NOT NULL AND def_player_2 IS NOT NULL"
    " AND def_player_3 IS NOT NULL AND def_player_4 IS NOT NULL"
    " AND def_player_5 IS NOT NULL"
    " WINDOW w AS (PARTITION BY game_id ORDER BY possession_number"
    " ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING)"
    " ) GROUP BY ua1, ua2, ua3, ua4, ua5, ub1, ub2, ub3, ub4, ub5"
)


_MATCHUP_GAMES_SQL = (
    "SELECT COUNT(DISTINCT game_id) AS games"
    " FROM silver_hist_possessions"
    " WHERE _season = ?"
    " AND ((offense_team_id = ? AND defense_team_id = ?)"
    " OR (offense_team_id = ? AND defense_team_id = ?))"
    " AND count_as_possession = 'true'"
)


def _qualifying_lineups_sql(
    season: str, team_a: int, team_b: int, min_minutes: float,
) -> tuple[dict[UnitKey, int], dict[UnitKey, int]]:
    rows = _store._read_df(
        _SEASON_UNITS_SQL,
        [season, team_a, team_b, season, team_a, team_b],
    )
    counts_a: dict[UnitKey, int] = {}
    counts_b: dict[UnitKey, int] = {}
    for r in rows or []:
        try:
            unit = tuple(sorted(int(r[f"p{i}"]) for i in range(1, 6)))
            n = int(r["n"] or 0)
        except (TypeError, ValueError, KeyError):
            continue
        try:
            tid = int(r["team"])
        except (TypeError, ValueError, KeyError):
            continue
        if tid == team_a:
            counts_a[unit] = counts_a.get(unit, 0) + n
        if tid == team_b:
            counts_b[unit] = counts_b.get(unit, 0) + n
    qual_a = {k: v for k, v in counts_a.items() if v / 2 >= min_minutes}
    qual_b = {k: v for k, v in counts_b.items() if v / 2 >= min_minutes}
    return qual_a, qual_b


def _pair_aggs_sql(
    season: str, team_a: int, team_b: int,
) -> dict[PairKey, dict]:
    rows = _store._read_df(
        _PAIR_AGGS_SQL,
        [team_a, team_b, team_a, team_b, _BLOWOUT_MARGIN,
         team_a, team_a, team_a, team_a, team_a,
         team_b, team_b, team_b, team_b, team_b,
         team_a, team_b,
         season, team_a, team_b, team_b, team_a],
    )
    agg: dict[PairKey, dict] = {}
    for r in rows or []:
        try:
            key_a = tuple(sorted(int(r[f"ua{i}"]) for i in range(1, 6)))
            key_b = tuple(sorted(int(r[f"ub{i}"]) for i in range(1, 6)))
            agg[(key_a, key_b)] = {
                "poss": int(r["poss"] or 0),
                "off_poss_a": int(r["off_poss_a"] or 0),
                "off_poss_b": int(r["off_poss_b"] or 0),
                "pts_a": int(r["pts_a"] or 0),
                "pts_b": int(r["pts_b"] or 0),
                "blowout": int(r["blowout"] or 0),
                "first_seen": str(r.get("first_seen") or "")}
        except (TypeError, ValueError, KeyError):
            continue
    return agg


def _matchup_games_sql(season: str, team_a: int, team_b: int) -> int:
    rows = _store._read_df(
        _MATCHUP_GAMES_SQL, [season, team_a, team_b, team_b, team_a],
    )
    try:
        return int((rows or [{}])[0].get("games") or 0)
    except (TypeError, ValueError):
        return 0


def _team_abbr(tid: int, raw: object) -> str:
    try:
        from nba_api.stats.static import teams as _static_teams

        for t in _static_teams.get_teams():
            if t.get("id") == tid:
                return str(t.get("abbreviation") or raw)
    except Exception:
        pass
    return str(raw)


def _lineup_names(team_id: int, season: str) -> tuple[dict[UnitKey, str], dict[str, Any]]:
    season = resolve_season(season)
    rows, meta = _warehouse_or_live(
        "silver_lineups", "_season = ? AND TEAM_ID = ? AND (_entity LIKE 'lineups:%' OR _entity = ?)",
        [season, team_id, f"team:{team_id}"],
        lambda tid=team_id: nba_stats.lineups(tid, season), season,
        entity=f"team:{team_id}", ttl_s=TTL_PBPSTATS, limit=100_000,
    )
    names: dict[UnitKey, str] = {}
    for r in _dedupe_lineup_rows(rows):
        key = _lineup_key(r)
        if key is None:
            continue
        gn = r.get("GROUP_NAME")
        if gn:
            names[key] = gn
    return names, meta


@tool
def get_lineup_matchup_matrix(
    team_a: str, team_b: str, min_minutes: float = 10,
    season: str | None = None,
) -> dict[str, Any]:
    """Lineup-vs-lineup matrix for a team matchup. Names, abbrevs, or ids.

    Crosses every qualifying 5-man unit of team A against every qualifying
    unit of team B over their shared play-level possessions: shared minutes,
    net rating in those minutes, sample-size flags. Lineups qualify at
    min_minutes season minutes (poss/2); shared minutes are estimated from
    possessions (~2 per minute), never play-clock minutes.
    """
    season = resolve_season(season)
    season = clamp_season(season)
    try:
        aid = coerce_team_id(team_a)
        bid = coerce_team_id(team_b)
    except ValueError as exc:
        return {"tool": "get_lineup_matchup_matrix", "ok": False,
                "error": str(exc)[:160]}
    if aid == bid:
        return {"tool": "get_lineup_matchup_matrix", "ok": False,
                "error": "team_a and team_b must be different teams "
                         "for a matchup matrix"}
    names_a, meta_a = _lineup_names(aid, season)
    names_b, meta_b = _lineup_names(bid, season)
    base_meta: dict[str, Any] = {
        "source": "warehouse",
        "lineups_meta": {"team_a": meta_a, "team_b": meta_b},
        "season": season,
        "team_a": {"id": aid, "abbr": _team_abbr(aid, team_a)},
        "team_b": {"id": bid, "abbr": _team_abbr(bid, team_b)},
    }
    try:
        qual_a, qual_b = _qualifying_lineups_sql(season, aid, bid,
                                                 min_minutes)
        pair_agg = _pair_aggs_sql(season, aid, bid)
        matchup_games = _matchup_games_sql(season, aid, bid)
    except Exception:
        return {"tool": "get_lineup_matchup_matrix", "ok": True, "rows": [],
                "meta": {**base_meta, "data_note": _NO_DATA_NOTE}}
    if not pair_agg:
        return {"tool": "get_lineup_matchup_matrix", "ok": True, "rows": [],
                "meta": {**base_meta, "data_note": _NO_DATA_NOTE}}
    surnames = _surname_map(season)
    in_a, in_b = set(qual_a), set(qual_b)
    scored = []
    for (key_a, key_b), a in pair_agg.items():
        if key_a not in in_a or key_b not in in_b:
            continue
        scored.append((str(a.get("first_seen") or ""), _pair_row(
            key_a, key_b, a,
            names_a.get(key_a) or _fallback_name(key_a, surnames),
            names_b.get(key_b) or _fallback_name(key_b, surnames))))
    scored.sort(key=lambda t: (-t[1]["est_minutes"], t[0]))
    pairs = [row for _, row in scored]
    shown_rows = pairs[:MAX_ROWS]
    meta = {
        **base_meta,
        "team_a_lineups": len(qual_a),
        "team_b_lineups": len(qual_b),
        "pairs": len(pairs),
        "rows_returned": len(shown_rows),
        "truncation_note": _truncate_note(len(pairs), len(shown_rows)),
        "matchup_games": matchup_games,
        "minutes_note": (
            "shared minutes estimated from possessions (~2 per minute);"
            " the warehouse holds no true head-to-head clock minutes"),
        "qualification_note": (
            f"lineups qualify at {min_minutes} season minutes (poss/2 from"
            " verified play-level data; silver_lineups MIN comes from a"
            " partial upstream fetch and is used for names only)"),
        "blowout_rule": ("flagged at 50% of shared possessions with a "
                         "20+ point margin"),
        "small_sample_floor": f"{SMALL_PAIR_POSS} shared possessions",
    }
    return {"tool": "get_lineup_matchup_matrix", "ok": True,
            "rows": shown_rows, "meta": meta}
