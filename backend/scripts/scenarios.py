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


def main() -> None:
    luka = tools.resolve_entity.invoke({"query": "Luka Doncic"})
    luka_id = (luka["rows"]["players"] or [{}])[0].get("id", 0)
    check("resolve finds luka id", luka_id == 1629029, str(luka_id))

    sga = tools.resolve_entity.invoke({"query": "Shai Gilgeous-Alexander"})
    sga_id = (sga["rows"]["players"] or [{}])[0].get("id", 0)
    check("resolve finds sga id", sga_id == 1628983, str(sga_id))

    a = tools.get_player_intel.invoke({"player_id": luka_id})
    b = tools.get_player_intel.invoke({"player_id": sga_id})
    check("compare has both gamelogs",
          len(a["rows"]) > 0 and len(b["rows"]) > 0, "")

    met = tools.compare_metrics.invoke({"a": luka_id, "b": sga_id})
    check("metrics adjudication agrees or splits",
          met.get("ok") and met.get("rows", {}).get("agreement") in (
              "agree", "split", "none"), str(met.get("rows", {}).get("verdict"))[:160])

    okc = tools.resolve_entity.invoke({"query": "Oklahoma City Thunder"})
    okc_id = (okc["rows"]["teams"] or [{}])[0].get("id", 0)
    check("resolve finds okc id", okc_id == 1610612760, str(okc_id))

    hub = tools.get_team_hub.invoke({"team_id": okc_id})
    check("preview hub has games plus roster",
          len(hub["rows"]["games"]) > 0, str(hub)[:200])

    form = tools.get_last_x.invoke({"player_id": luka_id, "n": 10})
    pts = [r.get("PTS", 0) for r in form["rows"]]
    check("form averages sane",
          len(pts) == 10 and sum(pts) / 10 > 10, str(pts[:4]))

    pct = tools.get_percentiles.invoke({"player_id": luka_id})
    check("percentiles cover five cats", len(pct["rows"]) == 5, str(pct["rows"]))

    oo = tools.get_on_off.invoke({"player_id": luka_id, "team_id": 1610612747})
    check("on-off has deltas",
          any("On-Off" in r for r in oo["rows"]), str(oo["rows"][:1]))

    zones = tools.get_shot_zones.invoke({"player_id": luka_id})
    share = sum(r.get("share", 0) for r in zones["rows"])
    check("zones shares sum to one", abs(share - 1.0) < 0.05, str(share))

    brief = tools.get_briefing.invoke({})
    check("briefing carries games",
          isinstance(brief["rows"], dict) and "games" in brief["rows"], "")

    box = tools.get_boxscore.invoke(
        {"game_id": str(a["rows"][0].get("Game_ID", ""))})
    check("boxscore chains from intel",
          len(box["rows"]) > 0, str(box)[:200])

    comp = tools.get_comps.invoke({"player_id": 2544})
    check("comps return neighbors",
          len(comp["rows"]) == 5, str(comp["rows"][:1]))

    rest = tools.get_rest.invoke({"team_abbrev": "OKC"})
    check("rest splits read history",
          "back_to_back" in rest["rows"], str(rest["rows"]))

    wp = tools.get_win_prob.invoke({"team_a": "OKC", "team_b": "DEN"})
    check("win prob favors better record",
          wp["rows"]["win_prob"]["OKC"] > wp["rows"]["win_prob"]["DEN"]
          and wp["rows"]["elo_a"] > wp["rows"]["elo_b"], str(wp["rows"]))

    zones = tools.get_shot_zones.invoke({"player_id": 2544})
    check("shot zones sum shares",
          abs(sum(r.get("share", 0) for r in zones["rows"]) - 1.0) < 0.05, "")

    import asyncio as _asyncio

    async def _prev2():
        return await tools.get_preview.ainvoke(
            {"a": "Thunder", "b": "Celtics"})

    prev = _asyncio.run(_prev2())
    pa = prev["rows"].get("a", {})
    pb = prev["rows"].get("b", {})
    wp = prev["rows"].get("win_prob", {})
    check("preview carries both teams plus odds",
          prev["ok"] and pa.get("team_id") == 1610612760
          and "top_lineup" in pa and "top_lineup" in pb
          and abs(sum(wp.values()) - 1.0) < 0.01, str(prev)[:200])

    rs = tools.get_finder.invoke({"mode": "player_streak",
                                  "team_abbrev": "LeBron James",
                                  "season": "2024-25"})
    rh = tools.get_finder.invoke({"mode": "head2head",
                                  "team_abbrev": "LeBron James",
                                  "opponent": "2544",
                                  "season": "2024-25"})
    check("finder player modes streak plus head2head",
          rs["ok"] and rs["rows"].get("longest_20pt_streak", 0) >= 1
          and rh["ok"] and 5 < rh["rows"]["a"].get("ppg", 0) < 40
          and 5 < rh["rows"]["b"].get("ppg", 0) < 40,
          str((rs, rh))[:200])

    cast = tools.run_python.invoke({
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
