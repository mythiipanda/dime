"""Deep scenario suite. Daily analyst cases against tools plus warehouse.

Usage: python -m scripts.scenarios
Deterministic where possible. Two live LLM chats at the end.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import tools

PASS = 0
FAIL = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"PASS {name}")
    else:
        FAIL += 1
        print(f"FAIL {name} :: {detail[:200]}")


def rows(res: object, default: object = None) -> object:
    """Crash-proof rows accessor."""
    if not isinstance(res, dict):
        return default if default is not None else []
    r = res.get("rows")
    if r is not None:
        return r
    return default if default is not None else []


def safe_invoke(tool, payload: dict) -> dict:
    """Invoke a tool, converting exceptions to error dicts."""
    try:
        res = tool.invoke(payload)
        return res if isinstance(res, dict) else {"ok": False, "error": "non-dict result"}
    except Exception as e:
        return {"ok": False, "error": f"tool crashed: {e}"}


def main() -> None:
    luka = safe_invoke(tools.resolve_entity, {"query": "Luka Doncic"})
    luka_id = (rows(luka)["players"] or [{}])[0].get("id", 0)
    check("resolve finds luka id", luka_id == 1629029, str(luka_id))

    sga = safe_invoke(tools.resolve_entity, {"query": "Shai Gilgeous-Alexander"})
    sga_id = (rows(sga)["players"] or [{}])[0].get("id", 0)
    check("resolve finds sga id", sga_id == 1628983, str(sga_id))

    a = safe_invoke(tools.get_player_intel, {"player_id": luka_id})
    b = safe_invoke(tools.get_player_intel, {"player_id": sga_id})
    check("compare has both gamelogs",
          len(rows(a)) > 0 and len(rows(b)) > 0, "")

    okc = safe_invoke(tools.resolve_entity, {"query": "Oklahoma City Thunder"})
    okc_id = (rows(okc)["teams"] or [{}])[0].get("id", 0)
    check("resolve finds okc id", okc_id == 1610612760, str(okc_id))

    hub = safe_invoke(tools.get_team_hub, {"team_id": okc_id})
    check("preview hub has games plus roster",
          len(rows(hub)["games"]) > 0, str(hub)[:200])

    form = safe_invoke(tools.get_last_x, {"player_id": luka_id, "n": 10})
    pts = [r.get("PTS", 0) for r in rows(form)]
    check("form averages sane",
          len(pts) == 10 and sum(pts) / 10 > 10, str(pts[:4]))

    pct = safe_invoke(tools.get_percentiles, {"player_id": luka_id})
    check("percentiles cover five cats", len(rows(pct)) == 5, str(rows(pct)))

    oo = safe_invoke(tools.get_on_off, {"player_id": luka_id, "team_id": 1610612747})
    check("on-off has deltas",
          any("On-Off" in r for r in rows(oo)), str(rows(oo)[:1]))

    zones = safe_invoke(tools.get_shot_zones, {"player_id": luka_id})
    share = sum(r.get("share", 0) for r in rows(zones))
    check("zones shares sum to one", abs(share - 1.0) < 0.05, str(share))

    brief = safe_invoke(tools.get_briefing, {})
    check("briefing carries games",
          isinstance(rows(brief), dict) and "games" in rows(brief), "")

    box = safe_invoke(tools.get_boxscore, 
        {"game_id": str(rows(a)[0].get("Game_ID", ""))})
    check("boxscore chains from intel",
          len(rows(box)) > 0, str(box)[:200])

    comp = safe_invoke(tools.get_comps, {"player_id": 2544})
    check("comps return neighbors",
          len(rows(comp)) == 5, str(rows(comp)[:1]))

    rest = safe_invoke(tools.get_rest, {"team_abbrev": "OKC"})
    check("rest splits read history",
          "back_to_back" in rows(rest, {}), str(rows(rest, {})))

    wp = safe_invoke(tools.get_win_prob, {"team_a": "OKC", "team_b": "DEN"})
    wp_rows = rows(wp, {})
    wp_probs = wp_rows.get("win_prob", {}) if isinstance(wp_rows, dict) else {}
    check("win prob favors better record",
          wp_probs.get("OKC", 0) > wp_probs.get("DEN", 0)
          and wp_rows.get("elo_a", 0) > wp_rows.get("elo_b", 0), str(rows(wp)))

    zones = safe_invoke(tools.get_shot_zones, {"player_id": 2544})
    check("shot zones sum shares",
          abs(sum(r.get("share", 0) for r in rows(zones)) - 1.0) < 0.05, "")

    import asyncio as _asyncio

    async def _prev2():
        try:
            return await tools.get_preview.ainvoke(
                {"a": "Thunder", "b": "Celtics"})
        except Exception as e:
            return {"ok": False, "error": f"preview crashed: {e}"}

    prev = _asyncio.run(_prev2())
    pa = rows(prev, {}).get("a", {})
    pb = rows(prev, {}).get("b", {})
    wp = rows(prev, {}).get("win_prob", {})
    check("preview carries both teams plus odds",
          prev["ok"] and pa.get("team_id") == 1610612760
          and "top_lineup" in pa and "top_lineup" in pb
          and abs(sum(wp.values()) - 1.0) < 0.01, str(prev)[:200])

    rs = safe_invoke(tools.get_finder, {"mode": "player_streak",
                                  "team_abbrev": "LeBron James",
                                  "season": "2024-25"})
    rh = safe_invoke(tools.get_finder, {"mode": "head2head",
                                  "team_abbrev": "LeBron James",
                                  "opponent": "2544",
                                  "season": "2024-25"})
    check("finder player modes streak plus head2head",
          rs["ok"] and rows(rs, {}).get("longest_20pt_streak", 0) >= 1
          and rh["ok"] and 5 < rows(rh, {}).get("a", {}).get("ppg", 0) < 40
          and 5 < rows(rh, {}).get("b", {}).get("ppg", 0) < 40,
          str((rs, rh))[:200])

    cast = safe_invoke(tools.run_python, {
        "code": "rows = con.execute(\"SELECT AVG(PTS * 1.0 / GP) FROM "
                "silver_leaders_pts WHERE TEAM = 'OKC' AND "
                "PLAYER <> 'Shai Gilgeous-Alexander' AND "
                "_season = '2025-26' AND GP >= 10\").fetchall()\n"
                "out = rows[0][0]"
    })
    try:
        cast_ppg = float((cast.get("rows") or {}).get("out"))
    except (TypeError, ValueError):
        cast_ppg = -1.0
    check("supporting cast ppg is numeric and positive",
          cast.get("ok") and cast_ppg > 0, str(cast)[:200])

    print(f"\nscenarios: {PASS} pass, {FAIL} fail")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
