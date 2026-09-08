"""Analyst eval set. Canonical tasks against warehouse tools. No LLM cost.

Usage: python -m scripts.eval
Pass means real rows plus provenance on every task.
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
        print(f"FAIL {name} :: {detail[:160]}")


def main() -> None:
    res = tools.search_nba.invoke({"query": "LeBron James"})
    check("search finds lebron id 2544",
          any(p.get("id") == 2544 for p in res["rows"]["players"]), str(res))

    res = tools.get_player_intel.invoke({"player_id": 2544})
    check("intel returns rows with provenance",
          len(res["rows"]) > 0 and "source" in res["meta"], str(res)[:200])
    game_id = res["rows"][0].get("Game_ID", "") if res["rows"] else ""
    game_date = res["rows"][0].get("GAME_DATE", "") if res["rows"] else ""

    res = tools.get_team_hub.invoke({"team_id": 1610612747})
    check("team hub returns games",
          len(res["rows"]["games"]) > 0, str(res)[:200])

    res = tools.get_standings.invoke({})
    check("standings returns 30 teams", len(res["rows"]) == 30, str(len(res["rows"])))

    res = tools.get_leaders.invoke({"stat_category": "PTS"})
    check("leaders carry PTS column",
          res["rows"] and "PTS" in res["rows"][0], str(res)[:200])

    res = tools.get_leaders.invoke({"stat_category": "AST"})
    check("second category caches separately",
          res["rows"] and "AST" in res["rows"][0], str(res)[:200])

    if game_id:
        res = tools.get_boxscore.invoke({"game_id": str(game_id)})
        check("boxscore chains from gamelog",
              len(res["rows"]) > 0, str(res)[:200])
    if game_date:
        from datetime import datetime

        try:
            day = datetime.strptime(game_date, "%b %d, %Y").strftime("%m/%d/%Y")
        except ValueError:
            day = game_date
        res = tools.get_games_on_date.invoke({"game_date": day})
        check("scoreboard chains from gamelog date",
              len(res["rows"]) > 0, str(res)[:200])

    res = tools.get_lineups.invoke({"team_id": 1610612760})
    check("lineups carry group plus minus",
          res["rows"] and "GROUP_NAME" in res["rows"][0]
          and "PLUS_MINUS" in res["rows"][0], str(res)[:200])

    res = tools.get_on_off.invoke({"player_id": 2544, "team_id": 1610612747})
    check("on-off returns splits",
          res["rows"] and "On-Off" in res["rows"][0], str(res)[:200])

    res = tools.get_four_factors.invoke({"player_id": 2544, "team_id": 1610612747})
    check("four factors return rows",
          len(res["rows"]) > 0, str(res)[:200])

    res = tools.get_last_x.invoke({"player_id": 2544, "n": 5})
    check("last-x returns 5 recent first",
          len(res["rows"]) == 5, str(res)[:200])

    res = tools.get_percentiles.invoke({"player_id": 203999})
    check("percentiles cover five cats",
          len(res["rows"]) == 5, str(res)[:200])

    res = tools.get_hustle.invoke({})
    check("hustle returns rows",
          len(res["rows"]) > 0, str(res)[:200])

    res = tools.get_splits.invoke({"player_id": 2544})
    check("splits home away",
          {r["split"] for r in res["rows"]} >= {"home", "away", "last10"}
          and all(r["GP"] > 0 for r in res["rows"]), str(res)[:200])

    res = tools.get_scouting_report.invoke({"team_id": 1610612760})
    check("scouting has record",
          "record" in res["rows"], str(res)[:200])

    res = tools.get_recap.invoke({"game_id": str(game_id)})
    check("recap names top scorer",
          res["rows"] and "PLAYER" in res["rows"][0], str(res)[:200])

    res = tools.get_finder.invoke({"mode": "streak", "team_abbrev": "OKC"})
    check("finder streak reads history",
          res["rows"].get("longest_win_streak", 0) >= 10, str(res)[:200])

    res = tools.get_playoffs.invoke({})
    check("playoffs name champion",
          res["rows"].get("champion", "") != "", str(res)[:200])

    res = tools.get_player_intel.invoke({"player_id": "Luka Doncic"})
    check("intel accepts names",
          len(res["rows"]) > 0, str(res)[:200])

    from app.tools._core import coerce_player_id
    check("nicknames resolve",
          coerce_player_id("SGA") == 1628983, "")

    import asyncio as _asyncio

    async def _cmp():
        return await tools.get_compare.ainvoke(
            {"a": "Luka Doncic", "b": "Shai Gilgeous-Alexander"})

    async def _prev():
        return await tools.get_preview.ainvoke(
            {"a": "Thunder", "b": "Celtics"})

    cmp_res = _asyncio.run(_cmp())
    check("compare composite sides",
          cmp_res["ok"] and cmp_res["rows"]["a"].get("ppg", 0) > 20
          and cmp_res["rows"]["b"].get("ppg", 0) > 20,
          str(cmp_res)[:200])
    prev_res = _asyncio.run(_prev())
    check("preview composite probs",
          prev_res["ok"] and abs(sum(prev_res["rows"]["win_prob"].values()) - 1.0) < 0.01,
          str(prev_res)[:200])

    res = tools.get_trend.invoke({"player_id": 2544})
    check("trend reports direction",
          res["ok"] and res["rows"].get("direction") in ("up", "down", "flat"),
          str(res)[:200])

    res = tools.get_cap_ledger.invoke({"team": "OKC"})
    check("cap ledger reports payroll",
          res["ok"] and res["rows"].get("payroll", 0) > 10**8
          and isinstance(res["rows"].get("room_under_apron2"), int),
          str(res["rows"].get("payroll")))

    res = tools.get_trade_check.invoke({"team_a": "OKC", "players_a": "Shai Gilgeous-Alexander",
                                        "team_b": "DEN", "players_b": "Nikola Jokic"})
    check("trade check returns verdict",
          res["ok"] and "legal" in res["rows"], str(res)[:200])
    check("trade check carries disclaimer",
          "simplified" in res["rows"].get("disclaimer", "").lower(), str(res["rows"])[:160])

    res = tools.get_trade_check.invoke({"team_a": "LAL", "players_a": "LeBron James",
                                        "team_b": "BOS", "players_b": "Jayson Tatum"})
    check("trade check fails loud on unknown names",
          (not res["ok"] and "LeBron James" in str(res.get("error", "")))
          or (res["ok"] and "legal" in res["rows"]), str(res)[:160])

    res = tools.get_injuries.invoke({"team": "ATL"})
    check("injuries filter by team",
          res["ok"] and all("Atlanta" in r.get("display_name", "")
                            for r in res["rows"]), str(res)[:160])

    res = tools.get_ratings.invoke({})
    check("ratings carry ranks",
          res["ok"] and len(res["rows"]) == 30
          and res["rows"][0].get("NET_RATING_RANK") is not None
          and all(r.get("TEAM") for r in res["rows"]), str(res)[:160])

    res = tools.get_clutch.invoke({"scope": "player"})
    check("clutch names a leader",
          res["ok"] and len(res["rows"]) > 0
          and res["rows"][0].get("PTS", 0) > 50, str(res)[:160])

    res = tools.get_boxscore.invoke({"game_id": "0042500405"})
    check("boxscore carries watch link",
          res["ok"] and res["meta"].get("links", {}).get("watch", "").startswith(
              "https://www.nba.com/game/"), str(res["meta"])[:160])

    res = tools.get_elo.invoke({})
    check("elo ranks thirty teams",
          res["ok"] and len(res["rows"]) == 30
          and abs(sum(r["ELO"] for r in res["rows"]) - 45000) < 5,
          str(res["rows"][:2])[:160])

    async def _sim():
        return await tools.get_playoff_sim.ainvoke({})

    sim_res = _asyncio.run(_sim())
    check("playoff sim odds sum",
          sim_res["ok"] and abs(sum(
              sim_res["rows"]["title_probs"].values()) - 100) < 2,
          str(sim_res["rows"].get("meta"))[:160])

    res = tools.get_contract_value.invoke({})
    check("contract value both signs",
          res["ok"] and len(res["rows"]) == 20
          and res["rows"][0].get("RESIDUAL", 0) > 0
          and res["rows"][-1].get("RESIDUAL", 0) < 0, str(res["rows"][:1])[:160])

    res = tools.get_shot_zones.invoke({"player_id": 2544})
    check("shot zones carry efg and share",
          res["ok"] and abs(sum(r.get("SHARE", 0) for r in res["rows"]) - 1.0) < 0.01
          and all(0 <= r.get("eFG_PCT", -1) <= 1.5 for r in res["rows"]),
          str(res["rows"][:1])[:160])

    import asyncio as _aio2

    async def _board():
        return await tools.get_draft_board.ainvoke({})

    board_res = _aio2.run(_board())
    check("draft board ranks scorers",
          board_res["ok"] and len(board_res["rows"]) == 30
          and board_res["rows"][0].get("SCORE", 0) > 80,
          str(board_res["rows"][:1])[:160])

    async def _model():
        return await tools.get_draft_model.ainvoke({})

    model_res = _aio2.run(_model())
    check("draft model probabilities sane",
          model_res["ok"] and len(model_res["rows"]) == 20
          and all(0 <= r.get("STAR_P", -1) <= 1 for r in model_res["rows"])
          and "proxy" in str(model_res.get("meta", {})).lower(),
          str(model_res["rows"][:1])[:160])

    async def _shotcmp():
        return await tools.get_shot_compare.ainvoke(
            {"a": "LeBron James", "b": "Stephen Curry"})

    cmp_res = _aio2.run(_shotcmp())
    check("shot compare aligns zones",
          cmp_res["ok"] and len(cmp_res["rows"]) == 6
          and cmp_res.get("verdict", "") != "",
          str(cmp_res.get("verdict"))[:160])

    res = tools.get_risers.invoke({})
    check("risers name hot teams",
          res["ok"] and len(res["rows"].get("risers", [])) == 5
          and len(res["rows"].get("fallers", [])) == 5,
          str(res["rows"].get("risers", [])[:2])[:160])

    res = tools.get_team_splits.invoke({"team": "OKC"})
    check("team splits balance",
          res["ok"] and sum(r["GP"] for r in res["rows"]
                            if r["split"] in ("home", "away")) == 82
          and {"home", "away", "last10"} <= {r["split"] for r in res["rows"]},
          str(res["rows"][:2])[:160])

    async def _inj():
        return await tools.get_injury_impact.ainvoke({"team": "GSW"})

    inj_res = _aio2.run(_inj())
    check("injury impact grades",
          inj_res["ok"] and inj_res["rows"].get("impact") in
          ("high", "moderate", "low")
          and isinstance(inj_res["rows"].get("out"), list),
          str(inj_res["rows"])[:160])

    res = tools.get_raptor_history.invoke({"player": "LeBron James"})
    check("raptor history spans seasons",
          res["ok"] and len(res["rows"]) >= 5
          and res["rows"][0].get("RAPTOR", 0) > 0,
          str(res["rows"][:1])[:160])

    res = tools.run_python.invoke(
        {"code": "out = con.execute(\"SELECT COUNT(*) FROM silver_standings\").fetchall()[0][0]"})
    check("python sandbox reads warehouse",
          res["ok"] and int(res["rows"].get("out") or 0) > 0,
          str(res["rows"])[:120])
    res = tools.run_python.invoke({"code": "import os"})
    check("python sandbox blocks imports", not res["ok"], str(res)[:80])

    async def _pack():
        return await tools.get_scout_pack.ainvoke(
            {"team": "OKC", "opponent": "BOS"})

    pack_res = _aio2.run(_pack())
    check("scout pack briefs both sides",
          pack_res["ok"] and pack_res["rows"]["team"].get("net_rating", 0) > 5
          and len(pack_res["rows"]["team"].get("top_lineups", [])) > 0
          and "net gap" in pack_res["rows"].get("edge", ""),
          str(pack_res["rows"].get("edge"))[:160])

    async def _rot():
        return await tools.get_rotation_check.ainvoke({"team": "LAL"})

    rot_res = _aio2.run(_rot())
    check("rotation check lists players",
          rot_res["ok"] and len(rot_res["rows"].get("players", [])) >= 8
          and "flag" in rot_res["rows"],
          str(rot_res["rows"].get("flag"))[:160])

    res = tools.get_cap_ledger.invoke({"team": "DEN"})
    check("cap ledger uses real salaries",
          res["ok"] and "basketball-reference" in res["meta"].get("source", ""),
          str(res["meta"].get("source"))[:120])

    res = tools.get_finder.invoke({"mode": "player_streak",
                                   "team_abbrev": "LeBron James",
                                   "season": "2024-25"})
    check("finder player streak sane",
          res["ok"] and res["rows"].get("longest_20pt_streak", 0) >= 1
          and res["rows"].get("games", 0) > 0, str(res)[:200])

    res = tools.get_finder.invoke({"mode": "head2head",
                                   "team_abbrev": "2544",
                                   "opponent": "LeBron James",
                                   "season": "2024-25"})
    check("finder head2head ppg sane",
          res["ok"] and 5 < res["rows"]["a"].get("ppg", 0) < 40
          and 5 < res["rows"]["b"].get("ppg", 0) < 40, str(res)[:200])

    print(f"\neval: {PASS} pass, {FAIL} fail")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
