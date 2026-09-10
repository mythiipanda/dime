"""Lineup-vs-lineup matchup matrix for a team pairing.

For a playoff-series style question ("which five of ours beats which five of
theirs?"), cross every qualifying 5-man unit of team A against every
qualifying unit of team B head-to-head over shared possessions from
silver_hist_possessions: shared minutes, net rating in those minutes, and
sample-size flags.

The warehouse holds no true head-to-head clock-minutes table, so shared
minutes are estimated as poss/2 (~2 possessions per minute). That honesty is
carried in the flags, the meta notes, and the tool docstring: nothing here is
play-clock minutes. Lineup qualification uses season possession totals from
verified play-level data; silver_lineups MIN comes from a partial upstream
fetch and is used for unit names only.
"""

from typing import Any

from langchain_core.tools import tool

from .. import store as _store
from ..sources import nba_stats
from ._core import MAX_ROWS, SEASON, TTL_PBPSTATS, _warehouse_or_live, clamp_season, coerce_team_id
from .lineup import _dedupe_lineup_rows
from .team import _lineup_key

UnitKey = tuple[int, int, int, int, int]
PairKey = tuple[UnitKey, UnitKey]

SMALL_PAIR_POSS = 30
_BLOWOUT_MARGIN = 20
_BLOWOUT_SHARE_FLAG = 0.5

_POSS_COLS = (
    "game_id, possession_number, offense_team_id, defense_team_id, points,"
    " off_player_1, off_player_2, off_player_3, off_player_4, off_player_5,"
    " def_player_1, def_player_2, def_player_3, def_player_4, def_player_5"
)
_MATCHUP_SQL = (
    f"SELECT {_POSS_COLS} FROM silver_hist_possessions WHERE _season = ?"
    " AND ((offense_team_id = ? AND defense_team_id = ?)"
    " OR (offense_team_id = ? AND defense_team_id = ?))"
    " AND count_as_possession = 'true'"
)
_SEASON_SQL = (
    f"SELECT {_POSS_COLS} FROM silver_hist_possessions WHERE _season = ?"
    " AND (offense_team_id IN (?, ?) OR defense_team_id IN (?, ?))"
    " AND count_as_possession = 'true'"
)
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


def _qualifying_lineups(
    poss_rows: list[dict], team_a: int, team_b: int, min_minutes: float,
) -> tuple[dict[UnitKey, int], dict[UnitKey, int]]:
    counts_a = _season_lineup_minutes(poss_rows, team_a)
    counts_b = _season_lineup_minutes(poss_rows, team_b)
    qual_a = {k: v for k, v in counts_a.items() if v / 2 >= min_minutes}
    qual_b = {k: v for k, v in counts_b.items() if v / 2 >= min_minutes}
    return qual_a, qual_b


def _accumulate_pairs(
    poss_rows: list[dict], team_a: int, team_b: int,
    qual_a: set[UnitKey], qual_b: set[UnitKey],
) -> dict[PairKey, dict]:
    agg: dict[PairKey, dict] = {}
    runs: dict[str, dict[int, int]] = {}
    for r in poss_rows or []:
        try:
            off_tid = int(r.get("offense_team_id"))
            def_tid = int(r.get("defense_team_id"))
        except (TypeError, ValueError):
            continue
        try:
            pts = int(r.get("points"))
        except (TypeError, ValueError):
            pts = 0
        game = str(r.get("game_id"))
        run = runs.setdefault(game, {})
        margin = run.get(team_a, 0) - run.get(team_b, 0)
        run[off_tid] = run.get(off_tid, 0) + pts
        run.setdefault(def_tid, 0)
        if off_tid == def_tid:
            continue
        off_unit = _unit_from_row(r, "off")
        def_unit = _unit_from_row(r, "def")
        if off_unit is None or def_unit is None:
            continue
        if off_tid == team_a and def_tid == team_b:
            key_a, key_b = off_unit, def_unit
        elif off_tid == team_b and def_tid == team_a:
            key_a, key_b = def_unit, off_unit
        else:
            continue
        if key_a not in qual_a or key_b not in qual_b:
            continue
        a = agg.setdefault((key_a, key_b),
                           {"poss": 0, "off_poss_a": 0, "off_poss_b": 0,
                            "pts_a": 0, "pts_b": 0, "blowout": 0})
        a["poss"] += 1
        if off_tid == team_a:
            a["off_poss_a"] += 1
            a["pts_a"] += pts
        else:
            a["off_poss_b"] += 1
            a["pts_b"] += pts
        if abs(margin) >= _BLOWOUT_MARGIN:
            a["blowout"] += 1
    return agg


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


def _fallback_name(key: UnitKey) -> str:
    return "unit " + "-".join(str(i) for i in key)


def _build_matrix(
    poss_rows: list[dict], team_a: int, team_b: int,
    qual_a: set[UnitKey] | dict[UnitKey, int],
    qual_b: set[UnitKey] | dict[UnitKey, int],
    names_a: dict[UnitKey, str], names_b: dict[UnitKey, str],
) -> list[dict[str, Any]]:
    ordered = sorted(poss_rows or [],
                     key=lambda r: (str(r.get("game_id")), _poss_num(r)))
    acc = _accumulate_pairs(ordered, team_a, team_b, set(qual_a), set(qual_b))
    rows = [
        _pair_row(key_a, key_b, a,
                  (names_a or {}).get(key_a) or _fallback_name(key_a),
                  (names_b or {}).get(key_b) or _fallback_name(key_b))
        for (key_a, key_b), a in acc.items()
    ]
    rows.sort(key=lambda r: r["est_minutes"], reverse=True)
    return rows


def _poss_num(r: dict[str, Any]) -> int:
    try:
        return int(r.get("possession_number") or 0)
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
    rows, meta = _warehouse_or_live(
        "silver_lineups", "_season = ? AND _entity = ?",
        [season, f"team:{team_id}"],
        lambda tid=team_id: nba_stats.lineups(tid, season), season,
        entity=f"team:{team_id}", ttl_s=TTL_PBPSTATS, limit=100_000,
    )
    names: dict[UnitKey, str] = {}
    for r in _dedupe_lineup_rows(rows):
        key = _lineup_key(r)
        if key is None:
            continue
        names[key] = r.get("GROUP_NAME") or _fallback_name(key)
    return names, meta


@tool
def get_lineup_matchup_matrix(
    team_a: str, team_b: str, min_minutes: float = 10,
    season: str = SEASON,
) -> dict[str, Any]:
    """Lineup-vs-lineup matrix for a team matchup. Names, abbrevs, or ids.

    Crosses every qualifying 5-man unit of team A against every qualifying
    unit of team B over their shared play-level possessions: shared minutes,
    net rating in those minutes, sample-size flags. Lineups qualify at
    min_minutes season minutes (poss/2); shared minutes are estimated from
    possessions (~2 per minute), never play-clock minutes.
    """
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
        matchup_rows = _store._read_df(_MATCHUP_SQL, [season, aid, bid, bid, aid])
        season_rows = _store._read_df(_SEASON_SQL, [season, aid, bid, aid, bid])
    except Exception:
        return {"tool": "get_lineup_matchup_matrix", "ok": True, "rows": [],
                "meta": {**base_meta, "data_note": _NO_DATA_NOTE}}
    if not matchup_rows:
        return {"tool": "get_lineup_matchup_matrix", "ok": True, "rows": [],
                "meta": {**base_meta, "data_note": _NO_DATA_NOTE}}
    matchup_rows.sort(key=lambda r: (str(r.get("game_id")), _poss_num(r)))
    qual_a, qual_b = _qualifying_lineups(season_rows, aid, bid, min_minutes)
    pairs = _build_matrix(matchup_rows, aid, bid, qual_a, qual_b,
                          names_a, names_b)
    meta = {
        **base_meta,
        "team_a_lineups": len(qual_a),
        "team_b_lineups": len(qual_b),
        "pairs": len(pairs),
        "matchup_games": len({str(r.get("game_id")) for r in matchup_rows}),
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
            "rows": pairs[:MAX_ROWS], "meta": meta}
