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


def _audit(rows: list[dict[str, Any]], horizon: list[int] | None) -> dict[str, Any]:
    span = horizon if horizon else sorted({r["draft_year"] for r in rows})
    scoped = [r for r in rows if not span or r["draft_year"] in span]
    inventory = []
    for y in span:
        yr = [r for r in scoped if r["draft_year"] == y]
        firsts = [r for r in yr if r["round"] == 1]
        has_first = any(r["direction"] in {"kept", "incoming", "swap risk"}
                        for r in firsts)
        inventory.append({
            "draft_year": y,
            "kept": sum(1 for r in yr if r["direction"] == "kept"),
            "incoming": sum(1 for r in yr if r["direction"] == "incoming"),
            "outgoing": sum(1 for r in yr if r["direction"] == "outgoing"),
            "swap_risk": sum(1 for r in yr if r["direction"] == "swap risk"),
            "forfeited": sum(1 for r in yr if r["direction"] == "forfeited"),
            "protected": sum(1 for r in yr if r["protection"]),
            "first_available": has_first,
        })
    bare_years = [i["draft_year"] for i in inventory
                  if not i["first_available"]]
    consecutive_bare = any(
        b - a == 1 for a, b in zip(bare_years, bare_years[1:]))
    held_value = round(sum(
        r["est_value_m"] or 0.0 for r in scoped
        if r["direction"] in {"kept", "incoming"}), 1)
    outgoing_value = round(sum(
        r["est_value_m"] or 0.0 for r in scoped
        if r["direction"] in {"outgoing", "forfeited"}), 1)
    swap_value = round(sum(
        r["est_value_m"] or 0.0 for r in scoped
        if r["direction"] == "swap risk"), 1)
    net_picks = sum(i["kept"] + i["incoming"]
                    - i["outgoing"] - i["forfeited"] for i in inventory)
    net_capital_m = round(held_value - outgoing_value, 1)
    return {
        "inventory": inventory,
        "stepien": {
            "years_lacking_first": bare_years,
            "consecutive_bare_years": consecutive_bare,
            "tradeable_firsts": [i["draft_year"] for i in inventory
                                 if i["first_available"]],
        },
        "held_value_m": held_value,
        "outgoing_value_m": outgoing_value,
        "swap_exposure_m": swap_value,
        "net_picks": net_picks,
        "net_capital_m": net_capital_m,
        "net_first_equivalents": round(net_capital_m / PICK_ONE_VALUE_M, 2),
        "unvalued_picks": sum(1 for r in scoped
                              if r["est_value_m"] is None),
    }


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


@tool(description='Future draft pick ownership and capital audit: who holds '
                  'each team\'s 2027+ picks, protections, swap rights and '
                  'forfeits, valued on an empirical draft-value curve. With '
                  'team + optional years_ahead horizon: per-year '
                  'kept/incoming/outgoing inventory, Stepien-rule first-round '
                  'coverage, and net draft-capital liquidity. Requires seeded '
                  'silver_future_picks.')
def get_draft_capital(team: str = "", draft_year: str = "",
                      years_ahead: int | None = None) -> dict[str, Any]:
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
            team_rows = _pick_rows(con, team, None)
            team_years = sorted({r["draft_year"] for r in team_rows})
            all_years = [r[0] for r in con.execute(
                "select distinct DRAFT_YEAR from silver_future_picks "
                "where _season = ? order by 1", [_PICKS_SEASON]).fetchall()]
            if team_years:
                detail = (f"no pick rows for {team.upper()} in "
                          f"{years}; {team.upper()} rows exist for "
                          f"draft_years {team_years}")
            else:
                detail = (f"no pick rows at all for {team.upper()}; "
                          f"silver_future_picks covers draft_years "
                          f"{all_years[0]}-{all_years[-1]}"
                          if all_years else
                          f"no pick rows at all for {team.upper()}")
            return {"tool": "get_draft_capital", "ok": False,
                    "error": detail}
    horizon = None
    if years_ahead is not None and str(years_ahead).strip():
        base = min(r["draft_year"] for r in rows) if rows else None
        horizon = list(range(base, base + int(years_ahead))) if base else None
    checks = [
        {"rule": "protections", "checked": False,
         "note": "protections and swap conditions are stated but not "
                 "resolved into conveyance probabilities"},
        {"rule": "conditional conveyance", "checked": False,
         "note": "conditional/pooled picks counted at face value; "
                 "conveyance timing unmodeled"},
        {"rule": "stepien margin", "checked": True,
         "note": "own-first bookkeeping only - treats incoming firsts and "
                 "swap risk as first-round assets; does not model pick "
                 "obligations in trades not yet logged"},
        {"rule": "valuation", "checked": True,
         "note": "est_value_m = draft-value-curve index x "
                 f"{PICK_ONE_VALUE_M:g}M anchor; slot estimated from "
                 "NET_RATING_RANK - unvalued picks counted separately"},
    ]
    out_rows = _league_summary(rows) if not team else rows
    out = {"tool": "get_draft_capital", "ok": True, "rows": out_rows,
           "checks": checks}
    if team:
        out["audit"] = _audit(rows, horizon)
    out.update({
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
                ]}})
    return out
