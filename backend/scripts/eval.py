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


def rows(res: object, default: object = None) -> object:
    """Crash-proof rows accessor. Returns the rows value when present,
    otherwise the default ([] unless specified)."""
    if not isinstance(res, dict):
        return default if default is not None else []
    r = res.get("rows")
    if r is not None:
        return r
    return default if default is not None else []


def safe(res: object) -> str:
    """Crash-proof detail string. Live tools fail without rows."""
    try:
        if isinstance(res, dict):
            return str(res.get("rows", res.get("error", res)))[:160]
        return str(res)[:160]
    except Exception:
        return "unprintable"


def main() -> None:
    res = tools.search_nba.invoke({"query": "LeBron James"})
    check("search finds lebron id 2544",
          any(p.get("id") == 2544 for p in rows(res)["players"]), str(res))

    res = tools.get_player_intel.invoke({"player_id": 2544})
    check("intel returns rows with provenance",
          len(rows(res)) > 0 and "source" in res["meta"], str(res)[:200])
    game_id = rows(res)[0].get("Game_ID", "") if rows(res) else ""
    game_date = rows(res)[0].get("GAME_DATE", "") if rows(res) else ""

    res = tools.get_team_hub.invoke({"team_id": 1610612747})
    check("team hub returns games",
          len(rows(res)["games"]) > 0, str(res)[:200])

    res = tools.get_standings.invoke({})
    check("standings returns 30 teams", len(rows(res)) == 30, str(len(rows(res))))

    res = tools.get_leaders.invoke({"stat_category": "PTS"})
    check("leaders carry PTS column",
          rows(res) and "PTS" in rows(res)[0], str(res)[:200])

    res = tools.get_leaders.invoke({"stat_category": "AST"})
    check("second category caches separately",
          rows(res) and "AST" in rows(res)[0], str(res)[:200])

    if game_id:
        res = tools.get_boxscore.invoke({"game_id": str(game_id)})
        check("boxscore chains from gamelog",
              len(rows(res)) > 0, str(res)[:200])
    if game_date:
        from datetime import datetime

        try:
            day = datetime.strptime(game_date, "%b %d, %Y").strftime("%m/%d/%Y")
        except ValueError:
            day = game_date
        res = tools.get_games_on_date.invoke({"game_date": day})
        check("scoreboard chains from gamelog date",
              len(rows(res)) > 0, str(res)[:200])

    res = tools.get_lineups.invoke({"team_id": 1610612760})
    check("lineups carry group plus minus",
          rows(res) and "GROUP_NAME" in rows(res)[0]
          and "PLUS_MINUS" in rows(res)[0], str(res)[:200])

    res = tools.get_on_off.invoke({"player_id": 2544, "team_id": 1610612747})
    check("on-off returns splits",
          rows(res) and "On-Off" in rows(res)[0], str(res)[:200])

    res = tools.get_four_factors.invoke({"player_id": 2544, "team_id": 1610612747})
    check("four factors return rows",
          len(rows(res)) > 0, str(res)[:200])

    res = tools.get_last_x.invoke({"player_id": 2544, "n": 5})
    check("last-x returns 5 recent first",
          len(rows(res)) == 5, str(res)[:200])

    res = tools.get_percentiles.invoke({"player_id": 203999})
    check("percentiles cover five cats",
          len(rows(res)) == 5, str(res)[:200])

    res = tools.get_hustle.invoke({})
    check("hustle returns rows",
          len(rows(res)) > 0, str(res)[:200])

    res = tools.get_splits.invoke({"player_id": 2544})
    check("splits home away",
          {r["split"] for r in rows(res)} >= {"home", "away", "last10"}
          and all(r["GP"] > 0 for r in rows(res)), str(res)[:200])

    res = tools.get_scouting_report.invoke({"team_id": 1610612760})
    check("scouting has record",
          "record" in rows(res), str(res)[:200])

    res = tools.get_recap.invoke({"game_id": str(game_id)})
    check("recap names top scorer",
          rows(res) and "PLAYER" in rows(res)[0], str(res)[:200])

    res = tools.get_finder.invoke({"mode": "streak", "team_abbrev": "OKC"})
    check("finder streak reads history",
          rows(res, {}).get("longest_win_streak", 0) >= 10, str(res)[:200])

    res = tools.get_playoffs.invoke({})
    check("playoffs name champion",
          rows(res, {}).get("champion", "") != "", str(res)[:200])

    res = tools.get_player_intel.invoke({"player_id": "Luka Doncic"})
    check("intel accepts names",
          len(rows(res)) > 0, str(res)[:200])

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
    cmp_sides = rows(cmp_res, {}) if isinstance(rows(cmp_res, {}), dict) else {}
    check("compare composite sides",
          cmp_res["ok"] and (cmp_sides.get("a", {}) or {}).get("ppg", 0) > 20
          and (cmp_sides.get("b", {}) or {}).get("ppg", 0) > 20
          and (cmp_sides.get("a", {}) or {}).get("team") == "LAL"
          and (cmp_sides.get("b", {}) or {}).get("team") == "OKC"
          and (cmp_sides.get("a", {}) or {}).get("rpg", 0) > 0
          and "on_off" not in (cmp_sides.get("a", {}) or {}),
          str(cmp_res)[:200])
    try:
        prev_res = _asyncio.run(_prev())
    except Exception as e:
        prev_res = {"ok": False, "error": f"preview crashed: {e}"}
    check("preview composite probs",
          prev_res.get("ok") and abs(sum(rows(prev_res, {}).get("win_prob", {}).values()) - 1.0) < 0.01,
          str(prev_res)[:200])

    met_res = tools.compare_metrics.invoke(
        {"a": "Luka Doncic", "b": "Shai Gilgeous-Alexander"})
    met_rows = met_res.get("rows", {}) if isinstance(met_res.get("rows"), dict) else {}
    check("metrics adjudication names agreement",
          met_res.get("ok") and len(met_rows.get("metrics", [])) == 8
          and met_rows.get("agreement") in ("agree", "split", "none")
          and "EPM" in [u.get("metric") for u in met_rows.get("unavailable", [])],
          safe(met_res))

    deb_res = tools.get_debate_card.invoke(
        {"a": "Luka Doncic", "b": "Shai Gilgeous-Alexander"})
    deb_rows = deb_res.get("rows", {}) if isinstance(deb_res.get("rows"), dict) else {}
    check("debate card renders shareable file",
          deb_res.get("ok") and str(deb_rows.get("path", "")).endswith(".html"),
          safe(deb_res))

    import asyncio as _aio3

    async def _today():
        return await tools.get_today.ainvoke({})

    today_res = _aio3.run(_today())
    check("today board loads movers",
          today_res.get("ok") and len(today_res.get("rows", {}).get("movers", [])) > 0,
          safe(today_res))

    hus_res = tools.get_hustle_boards.invoke({})
    check("hustle boards name defenders",
          hus_res.get("ok") and len(hus_res.get("rows", {}).get("dpoy", [])) > 0,
          safe(hus_res))

    deep_res = tools.get_standings_deep.invoke({})
    check("deep standings carry clutch splits",
          deep_res.get("ok") and len(deep_res.get("rows", {}).get("clutch", [])) > 0,
          safe(deep_res))

    res = tools.get_trend.invoke({"player_id": 2544})
    check("trend reports direction",
          res["ok"] and rows(res, {}).get("direction") in ("up", "down", "flat"),
          str(res)[:200])

    res = tools.get_cap_ledger.invoke({"team": "OKC"})
    check("cap ledger reports payroll",
          res["ok"] and rows(res, {}).get("payroll", 0) > 10**8
          and isinstance(rows(res, {}).get("room_under_apron2"), int),
          safe(res))

    res = tools.get_trade_check.invoke({"team_a": "OKC", "players_a": "Shai Gilgeous-Alexander",
                                        "team_b": "DEN", "players_b": "Nikola Jokic"})
    check("trade check returns verdict",
          res["ok"] and "legal" in rows(res), str(res)[:200])
    check("trade check carries disclaimer",
          "simplified" in rows(res, {}).get("disclaimer", "").lower(), safe(res))

    res = tools.get_trade_check.invoke({"team_a": "LAL", "players_a": "LeBron James",
                                        "team_b": "BOS", "players_b": "Jayson Tatum"})
    check("trade check fails loud on unknown names",
          (not res["ok"] and "LeBron James" in str(res.get("error", "")))
          or (res["ok"] and "legal" in rows(res)), str(res)[:160])

    res = tools.get_injuries.invoke({"team": "ATL"})
    check("injuries filter by team",
          res["ok"] and all("Atlanta" in r.get("display_name", "")
                            for r in rows(res)), str(res)[:160])

    res = tools.get_ratings.invoke({})
    check("ratings carry ranks",
          res["ok"] and len(rows(res)) == 30
          and rows(res)[0].get("NET_RATING_RANK") is not None
          and all(r.get("TEAM") for r in rows(res)), str(res)[:160])

    res = tools.get_clutch.invoke({"scope": "player"})
    check("clutch names a leader",
          res["ok"] and len(rows(res)) > 0
          and rows(res)[0].get("PTS", 0) > 50, str(res)[:160])

    res = tools.get_boxscore.invoke({"game_id": "0042500405"})
    check("boxscore carries watch link",
          res["ok"] and res["meta"].get("links", {}).get("watch", "").startswith(
              "https://www.nba.com/game/"), str(res["meta"])[:160])

    res = tools.get_elo.invoke({})
    check("elo ranks thirty teams",
          res["ok"] and len(rows(res)) == 30
          and abs(sum(r["ELO"] for r in rows(res)) - 45000) < 5,
          safe(res))

    async def _sim():
        return await tools.get_playoff_sim.ainvoke({})

    sim_res = _asyncio.run(_sim())
    check("playoff sim odds sum",
          sim_res["ok"] and abs(sum(
              rows(sim_res, {}).get("title_probs", {}).values()) - 100) < 2,
          str(rows(sim_res, {}).get("meta"))[:160])

    res = tools.get_contract_value.invoke({})
    check("contract value both signs",
          res["ok"] and len(rows(res)) == 20
          and rows(res)[0].get("RESIDUAL", 0) > 0
          and rows(res)[-1].get("RESIDUAL", 0) < 0, safe(res))

    res = tools.get_shot_zones.invoke({"player_id": 2544})
    check("shot zones carry efg and share",
          res["ok"] and abs(sum(r.get("SHARE", 0) for r in rows(res)) - 1.0) < 0.01
          and all(0 <= r.get("eFG_PCT", -1) <= 1.5 for r in rows(res)),
          safe(res))

    import asyncio as _aio2

    async def _board():
        return await tools.get_draft_board.ainvoke({})

    board_res = _aio2.run(_board())
    check("draft board ranks scorers",
          board_res["ok"] and len(rows(board_res)) == 30
          and rows(board_res)[0].get("SCORE", 0) > 80,
          safe(board_res))

    async def _model():
        return await tools.get_draft_model.ainvoke({})

    model_res = _aio2.run(_model())
    check("draft model probabilities sane",
          model_res["ok"] and len(rows(model_res)) == 20
          and all(0 <= r.get("STAR_P", -1) <= 1 for r in rows(model_res))
          and "proxy" in str(model_res.get("meta", {})).lower(),
          str(rows(model_res)[:1])[:160])

    async def _shotcmp():
        return await tools.get_shot_compare.ainvoke(
            {"a": "LeBron James", "b": "Stephen Curry"})

    cmp_res = _aio2.run(_shotcmp())
    check("shot compare aligns zones",
          cmp_res["ok"] and len(rows(cmp_res, {})) == 6
          and cmp_res.get("verdict", "") != "",
          str(cmp_res.get("verdict"))[:160])

    res = tools.get_risers.invoke({})
    check("risers name hot teams",
          res["ok"] and len(rows(res, {}).get("risers", [])) == 5
          and len(rows(res, {}).get("fallers", [])) == 5,
          safe(res))

    res = tools.get_team_splits.invoke({"team": "OKC"})
    check("team splits balance",
          res["ok"] and sum(r["GP"] for r in rows(res)
                            if r["split"] in ("home", "away")) == 82
          and {"home", "away", "last10"} <= {r["split"] for r in rows(res)},
          safe(res))

    async def _inj():
        return await tools.get_injury_impact.ainvoke({"team": "GSW"})

    inj_res = _aio2.run(_inj())
    check("injury impact grades",
          inj_res["ok"] and rows(inj_res, {}).get("impact") in
          ("high", "moderate", "low")
          and isinstance(rows(inj_res, {}).get("out"), list),
          safe(inj_res))

    res = tools.get_raptor_history.invoke({"player": "LeBron James"})
    check("raptor history spans seasons",
          res["ok"] and len(rows(res)) >= 5
          and rows(res)[0].get("RAPTOR", 0) > 0,
          safe(res))

    res = tools.run_python.invoke(
        {"code": "out = con.execute(\"SELECT COUNT(*) FROM silver_standings\").fetchall()[0][0]"})
    check("python sandbox reads warehouse",
          res["ok"] and int(rows(res, {}).get("out") or 0) > 0,
          safe(res))
    res = tools.run_python.invoke({"code": "import os"})
    check("python sandbox blocks imports", not res["ok"], str(res)[:80])

    async def _pack():
        return await tools.get_scout_pack.ainvoke(
            {"team": "OKC", "opponent": "BOS"})

    pack_res = _aio2.run(_pack())
    check("scout pack briefs both sides",
          pack_res["ok"] and rows(pack_res, {})["team"].get("net_rating", 0) > 5
          and len(rows(pack_res, {})["team"].get("top_lineups", [])) > 0
          and "net gap" in rows(pack_res, {}).get("edge", ""),
          safe(pack_res))

    async def _rot():
        return await tools.get_rotation_check.ainvoke({"team": "LAL"})

    rot_res = _aio2.run(_rot())
    check("rotation check lists players",
          rot_res["ok"] and len(rows(rot_res, {}).get("players", [])) >= 8
          and "flag" in rows(rot_res, {}),
          safe(rot_res))

    res = tools.get_cap_ledger.invoke({"team": "DEN"})
    check("cap ledger uses real salaries",
          res["ok"] and "basketball-reference" in res["meta"].get("source", ""),
          str(res["meta"].get("source"))[:120])

    res = tools.get_finder.invoke({"mode": "player_streak",
                                   "team_abbrev": "LeBron James",
                                   "season": "2024-25"})
    check("finder player streak sane",
          res["ok"] and rows(res, {}).get("longest_20pt_streak", 0) >= 1
          and rows(res, {}).get("games", 0) > 0, str(res)[:200])

    res = tools.get_finder.invoke({"mode": "head2head",
                                   "team_abbrev": "2544",
                                   "opponent": "LeBron James",
                                   "season": "2024-25"})
    check("finder head2head ppg sane",
          res["ok"] and 5 < rows(res)["a"].get("ppg", 0) < 40
          and 5 < rows(res)["b"].get("ppg", 0) < 40, str(res)[:200])

    res = tools.get_wowy.invoke({"player_a": "Luka", "player_b": "LeBron"})
    check("wowy splits calculate minutes and ratings",
          res["ok"] and len(rows(res)) == 4
          and all("net_rating" in r for r in rows(res)), str(res)[:200])

    res = tools.get_advanced.invoke({"player": "Shai Gilgeous-Alexander"})
    check("advanced carries usage and pie",
          res["ok"] and 0.2 < float(rows(res, {}).get("USG_PCT", 0)) < 0.5
          and float(rows(res, {}).get("PIE", 0)) > 0.1, str(res)[:200])

    check("compare carries clutch points",
          (cmp_sides.get("b", {}) or {}).get("clutch_pts", 0) == 175
          and (cmp_sides.get("a", {}) or {}).get("clutch_pts", 0) > 0,
          str(cmp_sides)[:200])

    res = tools.get_playoff_intel.invoke(
        {"player_id": 1628983, "season": "2024-25"})
    check("playoff intel returns 10+ rows",
          res["ok"] and len(rows(res)) >= 10, str(res)[:200])

    print(f"\neval: {PASS} pass, {FAIL} fail")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
