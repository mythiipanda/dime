"""Held-out eval. Novel questions never used in development. No LLM cost.

Usage: python -m scripts.holdout_eval
Each case calls the same tool the chat path would use and grades
ok-with-rows, clean errors, and correct team mapping.
"""

import asyncio as _aio2
import sys
import unicodedata as _ud
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import tools

PASS = 0
FAIL = 0

BANNED = ("get_", "silver_", "select", "traceback", "duckdb", ".sql")


def check(name: str, cond: bool, detail: str = "") -> None:
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"PASS {name}")
    else:
        FAIL += 1
        print(f"FAIL {name} :: {detail[:200]}")


def clean(err: object) -> bool:
    text = str(err or "").lower()
    return not any(b in text for b in BANNED)


def norm(s: object) -> str:
    return "".join(
        c for c in _ud.normalize("NFKD", str(s or ""))
        if not _ud.combining(c)).lower().strip()


def ledger_has(team: str, player_sub: str) -> bool:
    try:
        res = tools.get_cap_ledger.invoke({"team": team})
    except Exception:
        return False
    if not res.get("ok"):
        return False
    want = norm(player_sub)
    return any(want in norm(p.get("player")) for p in res["rows"].get("players", []))


def main() -> None:
    cmp_res = _aio2.run(tools.get_compare.ainvoke(
        {"a": "Alperen Sengun", "b": "LeBron James"}))
    sides = cmp_res.get("rows", {}) if isinstance(cmp_res.get("rows"), dict) else {}
    side_a = sides.get("a", {}) or {}
    check("sengun-vs-lebron compare",
          cmp_res.get("ok") and (side_a.get("gp", 0) or 0) > 0
          and (side_a.get("ppg", 0) or 0) > 10
          and side_a.get("team") == "HOU"
          and clean(cmp_res.get("error")),
          str({k: side_a.get(k) for k in ("team", "ppg", "gp")}) + str(cmp_res.get("error", "")))

    trade_res = tools.get_trade_check.invoke(
        {"team_a": "SAC", "players_a": "Zach LaVine",
         "team_b": "DEN", "players_b": ""})
    rows = trade_res.get("rows", {}) if isinstance(trade_res.get("rows"), dict) else {}
    check("lavine-for-picks trade",
          trade_res.get("ok") and "legal" in rows
          and (rows.get("team_a", {}) or {}).get("team") == "SAC"
          and ledger_has("SAC", "Zach LaVine")
          and clean(trade_res.get("error")),
          str(rows.get("team_a", {}))[:120] + str(trade_res.get("error", "")))

    shot_res = _aio2.run(tools.get_shot_compare.ainvoke(
        {"a": "Luka Doncic", "b": "Stephen Curry"}))
    check("luka-curry shot diet",
          shot_res.get("ok") and len(shot_res.get("rows", []) or []) == 6
          and shot_res.get("verdict", "") != ""
          and ledger_has("GSW", "Stephen Curry")
          and clean(shot_res.get("error")),
          str(shot_res.get("verdict", "")) + str(shot_res.get("error", "")))

    inj_res = _aio2.run(tools.get_injury_impact.ainvoke({"team": "GSW"}))
    inj_rows = inj_res.get("rows", {}) if isinstance(inj_res.get("rows"), dict) else {}
    check("warriors injury impact",
          inj_res.get("ok") and inj_rows.get("impact") in ("high", "moderate", "low")
          and isinstance(inj_rows.get("out"), list)
          and clean(inj_res.get("error")),
          str(inj_rows)[:160] + str(inj_res.get("error", "")))

    intel_res = tools.get_player_intel.invoke({"player_id": "Nikola Jokic"})
    intel_rows = intel_res.get("rows", []) or []
    asts = [float(r.get("AST") or 0) for r in intel_rows if isinstance(r, dict) and r.get("AST") is not None]
    apg = round(sum(asts) / max(len(asts), 1), 1) if asts else 0
    check("jokic assists per game",
          intel_res.get("ok") and len(intel_rows) > 0 and len(asts) > 0 and apg > 5
          and ledger_has("DEN", "Nikola Jokic")
          and clean(intel_res.get("error")),
          f"apg={apg} n={len(asts)}" + str(intel_res.get("error", "")))

    lead_res = tools.get_leaders.invoke({"stat_category": "PTS"})
    lead_rows = lead_res.get("rows", []) or []
    check("league scoring leader",
          lead_res.get("ok") and len(lead_rows) > 0 and "PTS" in (lead_rows[0] or {})
          and clean(lead_res.get("error")),
          str(lead_rows[0])[:160] + str(lead_res.get("error", "")))

    rot_res = _aio2.run(tools.get_rotation_check.ainvoke({"team": "LAL"}))
    rot_rows = rot_res.get("rows", {}) if isinstance(rot_res.get("rows"), dict) else {}
    check("lakers rotation health",
          rot_res.get("ok") and len(rot_rows.get("players", []) or []) >= 8
          and "flag" in rot_rows
          and clean(rot_res.get("error")),
          str(rot_rows.get("flag", "")) + str(rot_res.get("error", "")))

    cap_res = tools.get_cap_ledger.invoke({"team": "DEN"})
    cap_rows = cap_res.get("rows", {}) if isinstance(cap_res.get("rows"), dict) else {}
    check("nuggets payroll over tax",
          cap_res.get("ok") and (cap_rows.get("payroll", 0) or 0) > 10**8
          and isinstance(cap_rows.get("over_tax"), bool)
          and cap_rows.get("team") == "DEN"
          and clean(cap_res.get("error")),
          str(cap_rows.get("payroll")) + str(cap_res.get("error", "")))

    print(f"\nholdout: {PASS} pass, {FAIL} fail")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
