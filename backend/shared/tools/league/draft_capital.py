import re
from typing import Any

from langchain_core.tools import tool

from ._helpers import _owned_connection, _pkg, _warehouse_tables

PICK_ONE_VALUE_M = 45.0

_PICKS_SEASON = "2026-27"


def _pick_tables(con) -> set[str]:
    return _warehouse_tables(con)


def _team_abbr_map(con) -> dict[int, str]:
    try:
        return {int(tid): abbr for tid, abbr in con.execute(
            "select distinct TEAM_ID, TEAM from silver_leaders_pts "
            "where _season = '2025-26'").fetchall()}
    except Exception:
        return {}


def _net_ranks(con) -> dict[str, int]:
    try:
        tid_to_abbr = _team_abbr_map(con)
        return {tid_to_abbr[tid]: int(rank) for tid, rank in con.execute(
            "select TEAM_ID, NET_RATING_RANK from silver_team_ratings "
            "where _season = '2025-26'").fetchall() if tid in tid_to_abbr}
    except Exception:
        return {}


def _curve(con) -> dict[int, float]:
    try:
        return {int(slot): float(idx) for slot, idx in con.execute(
            "select SLOT, VALUE_INDEX from silver_draft_value_curve "
            "where _season = ?", [_PICKS_SEASON]).fetchall()}
    except Exception:
        return {}


def _est_slot(orig: str, rnd: int, net_ranks: dict[str, int]) -> int | None:
    rank = net_ranks.get(orig.upper())
    if not isinstance(rank, int):
        return None
    first = max(1, min(round(31 - rank * 0.85), 30))
    return first if rnd == 1 else 30 + first


def _held_list(held_by: str) -> list[str]:
    return [h for h in str(held_by or "").split(";") if h]


def _pick_rows(con, team: str, years: list[int] | None) -> list[dict[str, Any]]:
    tables = _pick_tables(con)
    curve = _curve(con) if "silver_draft_value_curve" in tables else {}
    net_ranks = _net_ranks(con) if "silver_team_ratings" in tables else {}
    sql = ("select DRAFT_YEAR, ROUND, ORIG_TEAM, STATUS, HELD_BY, "
           "PROTECTION, POOLED, CONDITIONAL, SUMMARY, LAST_EDITED "
           "from silver_future_picks where _season = ?")
    params: list[Any] = [_PICKS_SEASON]
    if years:
        sql += " and DRAFT_YEAR in (" + ",".join("?" * len(years)) + ")"
        params += years
    sql += " order by DRAFT_YEAR, ROUND, ORIG_TEAM"
    raw = con.execute(sql, params).fetchall()
    t = team.upper()
    rows: list[dict[str, Any]] = []
    for (year, rnd, orig, status, held_by, prot, pooled, cond, summary,
         edited) in raw:
        holders = _held_list(held_by)
        if team:
            if orig == t:
                direction = {"own": "kept", "swap": "swap risk",
                             "traded": "outgoing",
                             "forfeited": "forfeited"}.get(status, status)
            elif t in holders:
                direction = "incoming"
            else:
                continue
        else:
            direction = ""
        slot = _est_slot(orig, int(rnd), net_ranks)
        idx = curve.get(slot) if slot else None
        value_m = round(idx * PICK_ONE_VALUE_M, 1) if idx is not None else None
        rows.append({
            "draft_year": int(year), "round": int(rnd),
            "orig_team": orig, "status": status,
            "held_by": holders, "direction": direction,
            "protection": prot, "pooled": bool(pooled),
            "conditional": bool(cond), "summary": summary,
            "est_slot": slot,
            "curve_index": round(idx, 4) if idx is not None else None,
            "est_value_m": value_m,
            "last_edited": edited,
        })
    return rows


def _league_summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    teams = sorted({r["orig_team"] for r in rows}
                   | {h for r in rows for h in r["held_by"]})
    out = []
    for t in teams:
        kept = sum(1 for r in rows if r["orig_team"] == t
                   and r["status"] == "own")
        outgoing = sum(1 for r in rows if r["orig_team"] == t
                       and r["status"] in {"traded", "forfeited"})
        swaps = sum(1 for r in rows if r["orig_team"] == t
                    and r["status"] == "swap")
        incoming = sum(1 for r in rows if t in r["held_by"])
        value = round(sum(r["est_value_m"] or 0.0 for r in rows
                          if t in r["held_by"] or
                          (r["orig_team"] == t and r["status"] in
                           {"own", "swap"})), 1)
        out.append({"team": t, "own_kept": kept, "own_lost": outgoing,
                    "swaps_pending": swaps, "incoming": incoming,
                    "net_picks": kept + incoming - outgoing,
                    "est_capital_value_m": value})
    out.sort(key=lambda r: r["est_capital_value_m"], reverse=True)
    return out


@tool(description='Future draft pick ownership: who holds each team\'s 2027+ '
                  'picks, protections, swap rights and forfeits, valued on an '
                  'empirical draft-value curve. Optional enrichment for trade '
                  'analysis; warehouse-backed only, requires seeded '
                  'silver_future_picks.')
def get_draft_capital(team: str = "", draft_year: str = "") -> dict[str, Any]:
    years = None
    if str(draft_year).strip():
        found = re.findall(r"20\d\d", str(draft_year))
        years = [int(y) for y in found] or None
    with _owned_connection(None, read_only=True) as con:
        if "silver_future_picks" not in _pick_tables(con):
            return {"tool": "get_draft_capital", "ok": False,
                    "error": ("silver_future_picks is not seeded in this "
                              "warehouse; run "
                              "backend/scripts/seed_draft_capital.py on a "
                              "scratch copy first")}
        rows = _pick_rows(con, team, years)
        meta_rows = con.execute(
            "select max(LAST_EDITED), max(_fetched_at) "
            "from silver_future_picks where _season = ?",
            [_PICKS_SEASON]).fetchone()
    if team and not rows:
        return {"tool": "get_draft_capital", "ok": False,
                "error": f"no future pick rows for {team.upper()}"}
    out_rows = _league_summary(rows) if not team else rows
    return {"tool": "get_draft_capital", "ok": True, "rows": out_rows,
            "meta": {
                "season": _PICKS_SEASON,
                "sources": [
                    "https://thedraftday.com/api/picks (hand-maintained "
                    "from RealGM's future draft pick listing)",
                    "silver_draft_value_curve derived from "
                    "silver_hist_draft + silver_raptor_player "
                    "(1997-2015 drafts, sportsdataverse + 538 RAPTOR)",
                    "slot estimate from silver_team_ratings 2025-26 "
                    "NET_RATING_RANK",
                ],
                "value_basis": ("est_value_m = curve_index (mean career WAR "
                                "of that slot, pick 1 = 1.0) x "
                                f"{PICK_ONE_VALUE_M:g}M anchor"),
                "as_of": meta_rows[0],
                "fetched_at": meta_rows[1],
                "caveats": [
                    "protections and swap conditions are stated but not "
                    "resolved into conveyance probabilities",
                    "ownership status can change with new trades; check "
                    "last_edited",
                ]}}
