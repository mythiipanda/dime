from collections import Counter
from datetime import UTC, datetime
import json
from uuid import uuid4

import duckdb
from fastapi import HTTPException
from nba_api.stats.static import teams

from shared.sources.salaries import TEAM_ABBR
from shared.tools import get_trade_check
from shared.tools.league import CAP, _payroll, _payroll_source
from v2.boards.service import _name
from .deep_dive import ADV, BASE, Data, number, table, unique, unavailable
from .models import Callout, Citation, Kpi, Kpis, Packet, Section, Text, format_value


SALARY_SEASON = "2026-27"
TEAM_ALIASES = TEAM_ABBR
BASE_COLUMNS = ["PLAYER_ID","PLAYER","TEAM","AGE","GP","MPG","PPG","RPG","APG"]
ADV_COLUMNS = ["PLAYER_ID","TS_PCT","USG_PCT","NET_RATING","PIE"]
PRODUCTION = [("age","Age","years"),("gp","Games","count"),("mpg","Minutes / game","per_game"),
              ("ppg","Points / game","per_game"),("rpg","Rebounds / game","per_game"),("apg","Assists / game","per_game"),
              ("ts_pct","True shooting","pct"),("usg_pct","Usage","pct"),("net_rating","Net rating","rating"),
              ("pie","PIE","pct"),("rapm","RAPM","points_per_100_possessions")]


def canonical_team(value):
    code = str(value or "").upper()
    return TEAM_ALIASES.get(code, code)


def resolve_team(value):
    code = canonical_team(value.strip())
    matches = [t["abbreviation"] for t in teams.get_teams()
               if code == t["abbreviation"] or _name(value) in {_name(t["full_name"]),_name(t["nickname"]),str(t["id"])}]
    if len(matches) != 1:
        raise HTTPException(422,detail={"reason":"unknown_or_ambiguous_team","team":value,"candidates":matches})
    return matches[0]


def resolve_player(rows, ref, expected_team):
    matches = [r for r in rows if str(r["PLAYER_ID"]) == str(ref).strip() or _name(r["PLAYER"]) == _name(str(ref))]
    if len(matches) != 1:
        raise HTTPException(422,detail={"reason":"ambiguous_player" if matches else "unknown_player",
                            "player":ref,"candidates":[{"id":r["PLAYER_ID"],"name":r["PLAYER"]} for r in matches][:20]})
    row = matches[0]
    found = canonical_team(row["TEAM"])
    if found != expected_team:
        raise HTTPException(422,detail={"reason":"wrong_team","player":row["PLAYER"],"expected_team":expected_team,"team_found":found})
    return row


def complete_sum(values):
    return sum(values) if all(v is not None for v in values) else None


def kpi(label, value, unit, cite=None, reason="missing_or_ambiguous_salary", context=None):
    return Kpi(label=label,value=value,unit=unit,display=format_value(value,unit),cite=cite,
               null_reason=reason if value is None else None,context=context)


def salary_snapshot(data):
    """Run legacy payroll helpers on bounded, selected-vintage warehouse copies."""
    snapshot = duckdb.connect(":memory:")
    cites = {}
    contracts = []
    sources = [
        ("silver_salaries", ["PLAYER_NAME","TEAM","SALARY_2025_26"],
         'PLAYER_NAME VARCHAR, TEAM VARCHAR, SALARY_2025_26 DOUBLE'),
        ("silver_cap_players", ["player","team","salary","contract_type","player_option","team_option","guaranteed"],
         'player VARCHAR, team VARCHAR, salary DOUBLE, contract_type VARCHAR, player_option BOOLEAN, team_option BOOLEAN, guaranteed BOOLEAN'),
    ]
    try:
        for source, columns, schema in sources:
            rows, cid = data.read(source,columns,'"_season" = ?',[SALARY_SEASON])
            if cid:
                data.citations[cid].season = SALARY_SEASON
                data.citations[cid].salary_vintage = {"season":SALARY_SEASON,"fetched_at":data.citations[cid].fetched_at}
                cites[source] = cid
                snapshot.execute(f'CREATE TABLE "{source}" ({schema}, _season VARCHAR, _fetched_at VARCHAR)')
                if rows:
                    values = [[r[c] for c in columns]+[SALARY_SEASON,str(r["_fetched_at"]) if r["_fetched_at"] else None] for r in rows]
                    snapshot.executemany(f'INSERT INTO "{source}" VALUES ({",".join("?" for _ in values[0])})',values)
            if source == "silver_cap_players":
                contracts = rows
        return snapshot, cites, contracts
    except Exception:
        snapshot.close()
        raise


def payroll(data, snapshot, cites, team):
    # The helper falls back to cap players when the salary sheet lacks this team.
    sources = [s for s in ("silver_salaries","silver_cap_players") if s in cites]
    for source in sources:
        count = snapshot.execute(f'SELECT COUNT(*) FROM "{source}" WHERE upper(team) = ?', [team]).fetchone()[0]
        if not count:
            continue
        total, roster = _payroll(team,snapshot)
        salaries = [number(r["salary"]) for r in roster]
        names = [_name(r["player"]) for r in roster]
        valid = all(v is not None and v >= 0 for v in salaries) and len(names) == len(set(names))
        if not valid:
            data.gaps.append(f"{team}: payroll roster has missing, invalid or duplicate salaries; cap math is null.")
            return None, roster, cites[source]
        return number(total), roster, cites[source]
    data.gaps.append(f"{team}: no {SALARY_SEASON} payroll roster.")
    return None, [], None


def checker_blocks(data, ta, tb, sides, ledgers, outgoing, source_cites):
    arguments = {"team_a":ta,"team_b":tb,"season":SALARY_SEASON}
    for team,key in ((ta,"players_a"),(tb,"players_b")):
        roster = ledgers[team][1]
        arguments[key] = ", ".join(next((r["player"] for r in roster if _name(r["player"]) == _name(p["PLAYER"])),p["PLAYER"]) for p in sides[team])
    if any(ledgers[t][0] is None or outgoing[t] is None for t in (ta,tb)):
        result = {"ok":False,"error":"Missing or ambiguous payroll/player salaries; checker verdict unavailable."}
    else:
        try:
            result = get_trade_check.invoke(arguments)
        except duckdb.Error:
            result = {"ok":False,"error":"Trade checker could not read its required warehouse inputs."}
    cid = f"c{len(data.citations)+1}"
    data.citations[cid] = Citation(source_table="shared.tools.get_trade_check",table="shared.tools.get_trade_check",
        columns=["rows","meta"],season=SALARY_SEASON,sql="SELECT CAST(? AS JSON) AS checker_result LIMIT ?",
        params=[json.dumps(result,default=str),1],row_key={"checker":"shared.tools.get_trade_check","arguments":arguments},
        source=result.get("meta",{}).get("source"),salary_vintage={"season":SALARY_SEASON,"fetched_at":result.get("rows",{}).get("salary_date")},
        supporting_cites=list(dict.fromkeys(c for c in source_cites if c)),
        transformation="Recorded direct get_trade_check result, not recomputed matching math; SQL replays this recorded result; supporting citations describe warehouse inputs.")
    payload = result.get("rows",{}) if result.get("ok") else {}
    issues = payload.get("issues",[])
    rows = []
    for key,team,other_key in (("team_a",ta,"team_b"),("team_b",tb,"team_a")):
        side = payload.get(key,{})
        reasons = [reason for reason in issues if str(reason).startswith(team+" ") or not any(str(reason).startswith(t+" ") for t in (ta,tb))]
        valid = bool(payload) and side.get("team") == team
        rows.append({"team":team,"verdict":side.get("legal",not reasons) if valid else None,
            "deal_legal":payload.get("legal") if valid else None,
            "rule":side.get("match_rule"),"allowed_incoming":side.get("allowed_in"),
            "incoming":payload.get(other_key,{}).get("out"),"outgoing_needed":side.get("outgoing_needed"),
            "over_apron1":side.get("over_apron1"),"over_apron2":side.get("over_apron2"),
            "reasons":"; ".join(reasons) if valid else result.get("error","Checker returned different team attribution."),
            "null_reason":None if valid else "checker_verdict_unavailable"})
    specs = [("team","Team",None),("verdict","Passes reported checks",None),("deal_legal","Checker deal verdict",None),
        ("rule","Rule applied",None),("allowed_incoming","Allowed incoming","usd"),("incoming","Actual incoming","usd"),
        ("outgoing_needed","Outgoing needed","usd"),("over_apron1","Above first apron",None),("over_apron2","Above second apron",None),("reasons","Checker reasons",None)]
    blocks = [table(rows,specs,{"*":cid},"Direct get_trade_check result for the 2026-27 salary vintage; team outcomes are attributed from the checker's reported issues.","Trade checker verdict")]
    checks = payload.get("checks",[])
    if checks:
        blocks.append(table(checks,[("rule","Check",None),("checked","Evaluated",None),("note","Checker note",None)],{"*":cid},title="Checker rule coverage"))
        not_modeled = [str(c["rule"]) for c in checks if c.get("checked") is False]
        if not_modeled:
            blocks.append(Callout(tone="warn",md="Not modeled by the checker: "+"; ".join(not_modeled)+f". [^{cid}]"))
    if not payload or any(r["null_reason"] for r in rows):
        blocks.append(unavailable(data,result.get("error","Checker attribution differs from the validated trade; no verdict is asserted.")))
    return blocks


def build_trade(con, team_a, team_b, a_sends, b_sends, season, notes=None):
    ta, tb = resolve_team(team_a), resolve_team(team_b)
    if ta == tb:
        raise HTTPException(422,detail={"reason":"same_team"})
    if not a_sends and not b_sends:
        raise HTTPException(422,detail={"reason":"no_players"})
    d = Data(con,season)
    base, bc = d.read(BASE,BASE_COLUMNS,'"_season" = ?',[season])
    adv, ac = d.read(ADV,ADV_COLUMNS,'"_season" = ?',[season])
    sides = {ta:[resolve_player(base,p,ta) for p in a_sends],tb:[resolve_player(base,p,tb) for p in b_sends]}
    selected = sides[ta]+sides[tb]
    ids = [r["PLAYER_ID"] for r in selected]
    if len(ids) != len(set(ids)):
        raise HTTPException(422,detail={"reason":"duplicate_player"})
    snapshot, salary_cites, contracts = salary_snapshot(d)
    try:
        ledgers = {t:payroll(d,snapshot,salary_cites,t) for t in (ta,tb)}
        source = _payroll_source(snapshot)
    finally:
        snapshot.close()

    wages, wage_cites = {}, {}
    for team, rows in sides.items():
        _, roster, cid = ledgers[team]
        for row in rows:
            matched = [r for r in roster if _name(r["player"]) == _name(row["PLAYER"])]
            raw = unique(matched).get("salary")
            salary = number(raw)
            wages[row["PLAYER_ID"]] = salary if salary is not None and salary >= 0 else None
            wage_cites[row["PLAYER_ID"]] = cid
    outgoing = {t:complete_sum([wages[r["PLAYER_ID"]] for r in rows]) for t,rows in sides.items()}
    deal_blocks = []
    cap_rows, cap_cites = [], {}
    threshold_cite = f"c{len(d.citations)+1}"
    d.citations[threshold_cite] = Citation(source_table="backend/shared/tools/league.py::CAP",table="backend/shared/tools/league.py::CAP",
        columns=list(CAP),season=SALARY_SEASON,sql='SELECT ? AS cap, ? AS tax, ? AS apron1, ? AS apron2 LIMIT ?',
        params=[*CAP.values(),1],row_key={"helper":"shared.tools.league.CAP"},source="Repository CAP constants used by get_cap_ledger; not a live CBA lookup",
        salary_vintage={"season":SALARY_SEASON})
    for team, other in ((ta,tb),(tb,ta)):
        out, incoming = outgoing[team], outgoing[other]
        before, _, pc = ledgers[team]
        inputs = [pc,ledgers[other][2]]
        cid = d.derived(pc or ledgers[other][2],inputs+[threshold_cite],
                        "2026-27 recorded payroll via shared.tools.league._payroll; after=before-outgoing+incoming; thresholds use CAP. Legality is delegated separately to get_trade_check.")
        change = incoming-out if incoming is not None and out is not None else None
        after = before+change if before is not None and change is not None else None
        deal_blocks.append(Kpis(items=[kpi(f"{team} outgoing salary",out,"usd",cid,context=SALARY_SEASON),
            kpi(f"{team} incoming salary",incoming,"usd",cid,context=SALARY_SEASON),
            kpi(f"{team} net salary change",change,"usd",cid,context=SALARY_SEASON),
            kpi(f"{team} players sent",len(sides[team]),"count",bc),kpi(f"{team} players received",len(sides[other]),"count",bc)]))
        for label, value in (("Before",before),("After",after)):
            cap_cites[str(len(cap_rows))] = cid or threshold_cite
            cap_rows.append({"team":team,"position":label,"payroll":value,**CAP,
                **{f"room_{key}":threshold-value if value is not None else None for key,threshold in CAP.items()},
                "null_reason":None if value is not None else "incomplete_payroll_or_trade_salaries"})
    deal = Section(id="deal_summary",title="Deal summary",blocks=deal_blocks)
    movements = [f"{r['PLAYER']} to {dest}" for origin,dest in ((ta,tb),(tb,ta)) for r in sides[origin]]
    if bc:
        deal.summary = "; ".join(movements)+f" [^{bc}]."
    if notes:
        deal.blocks.append(Text(md="User-provided notes / picks — unvalued and unverified:\n\n"+notes,cites=[]))
    else:
        deal.blocks.append(Text(md="No user-provided notes or picks; picks are not valued.",cites=[]))
    cap_specs = [("team","Team",None),("position","Position",None),("payroll","Recorded payroll","usd")]
    for key,label in (("cap","Cap"),("tax","Tax"),("apron1","First apron"),("apron2","Second apron")):
        cap_specs += [(key,label,"usd"),(f"room_{key}",f"Room below {label.lower()}","usd")]
    cap = Section(id="cap_position",title="Cap position and legality",summary=f"Cap comparisons and the trade checker use the {SALARY_SEASON} salary vintage, separate from {season} production [^{threshold_cite}].",blocks=[
        table(cap_rows,cap_specs,cap_cites,f"{SALARY_SEASON}; {source}; payroll is a recorded roster sum, not a certified cap ledger.","Payroll and thresholds"),
        *checker_blocks(d,ta,tb,sides,ledgers,outgoing,[*salary_cites.values(),bc,threshold_cite])])
    if any(r["payroll"] is None for r in cap_rows):
        cap.blocks.append(unavailable(d,"Incomplete payroll or player salaries; affected cap math is null, never zero-filled."))

    production_rows, prod_cites, contract_rows, contract_cites = [], {}, [], {}
    placeholders = ",".join("?" for _ in ids)
    rapm, rc = d.read("silver_rapm",["player_id","rapm"],f'"_season" = ? AND "player_id" IN ({placeholders})',[season,*[str(p) for p in ids]],100)
    for origin,dest in ((ta,tb),(tb,ta)):
        for row in sides[origin]:
            pid = row["PLAYER_ID"]
            advanced = unique([r for r in adv if r["PLAYER_ID"] == pid])
            rp = unique([r for r in rapm if str(r["player_id"]) == str(pid)])
            entry = {"player":row["PLAYER"],"from_team":origin,"to_team":dest,
                     **{k.lower():number(row.get(k)) for k in ("AGE","GP","MPG","PPG","RPG","APG")},
                     **{k.lower():number(advanced.get(k))*100 if number(advanced.get(k)) is not None and k != "NET_RATING" else number(advanced.get(k)) for k in ("TS_PCT","USG_PCT","NET_RATING","PIE")},
                     "rapm":number(rp.get("rapm"))}
            entry["minutes"] = entry["gp"]*entry["mpg"] if entry["gp"] is not None and entry["mpg"] is not None else None
            if any(v is None for v in entry.values()):
                entry["null_reason"] = "missing_or_ambiguous_production_source"
                d.gaps.append("Some player production metrics are missing or ambiguous.")
            cid = d.derived(bc,[ac,rc],f"Player {pid}; percentages multiplied by 100; estimated season minutes=GP*MPG.")
            prod_cites[str(len(production_rows))] = cid
            production_rows.append(entry)
            matched = [r for r in contracts if _name(r["player"]) == _name(row["PLAYER"]) and canonical_team(r["team"]) == origin]
            contract = unique(matched)
            contract_cid = d.for_row(salary_cites.get("silver_cap_players"),contract,{"player":row["PLAYER"],"team":origin,"_season":SALARY_SEASON})
            if contract_cid:
                contract_cites[str(len(contract_rows))] = contract_cid
            contract_rows.append({"player":row["PLAYER"],"team":origin,
                **{k:contract.get(k) for k in ("contract_type","player_option","team_option","guaranteed")},
                "null_reason":None if contract and all(contract.get(k) is not None for k in ("contract_type","player_option","team_option","guaranteed")) else "missing_or_ambiguous_contract_fields"})

    totals = []
    for team in (ta,tb):
        rows = [r for r in production_rows if r["from_team"] == team]
        minutes = complete_sum([r["minutes"] for r in rows])
        weighted = {}
        for key,_,_ in PRODUCTION:
            values = [r[key] for r in rows]
            weighted[key] = sum(r[key]*r["minutes"] for r in rows)/minutes if minutes and None not in values else None
        weighted["gp"] = complete_sum([r["gp"] for r in rows])
        totals.append({"team":team,"minutes":minutes,**weighted,"null_reason":"no_players_or_missing_metric_or_minutes" if any(v is None for v in weighted.values()) else None})
    production_cite = d.derived(bc,[ac,rc],"Side rates weighted by GP*MPG; GP is summed, not averaged. These are descriptive weighted rates, not additive projected lineup production.")
    production = Section(id="production_exchanged",title="Production exchanged",blocks=[
        table(production_rows,[("player","Player",None),("from_team","From",None),("to_team","To",None),*PRODUCTION],prod_cites,title="Players exchanged"),
        table(totals,[("team","Sending team",None),("minutes","Estimated season minutes","count"),*PRODUCTION],{"*":production_cite},"Weighted by estimated season minutes (GP × MPG); games are summed; rates are not team totals.","Minutes-weighted side totals")])
    if all(t["ppg"] is not None for t in totals):
        a,b = totals
        comparison = f"{a['team']} and {b['team']} send equal minutes-weighted scoring" if a["ppg"] == b["ppg"] else f"{max(totals,key=lambda r:r['ppg'])['team']} sends more minutes-weighted scoring"
        production.summary = comparison+f" ({ta}: {format_value(a['ppg'])}, {tb}: {format_value(b['ppg'])} points per game), not a projected wins comparison [^{production_cite}]."
        production.blocks.append(Text(md=production.summary,cites=[production_cite]))
    if any(r.get("null_reason") for r in production_rows):
        production.blocks.append(unavailable(d,"Some production sources are missing or ambiguous; affected metrics remain null."))

    rotation = rotation_section(d,sides,ta,tb,season)
    contracts_section = Section(id="contracts",title="Contracts",blocks=[table(contract_rows,
        [("player","Player",None),("team","Salary-sheet team",None),("contract_type","Contract type",None),("player_option","Player option",None),("team_option","Team option",None),("guaranteed","Guaranteed",None)],contract_cites,
        "2026-27 cap-player snapshot; no multi-year contract schedule. Deal salaries follow the payroll helper's preferred source, which can differ from this contract source.","Contract terms")])
    if contract_cites:
        contracts_section.summary = f"Available contract terms are from the separate {SALARY_SEASON} snapshot, not a multi-year commitment schedule [^{next(iter(contract_cites.values()))}]."
    if any(r["null_reason"] for r in contract_rows):
        contracts_section.blocks.append(unavailable(d,"Some contract fields are missing or ambiguous; unknown options are not assumed false."))
    if any(v is None for v in wages.values()):
        deal.blocks.append(unavailable(d,"A player is unmatched or ambiguous on the stated team's salary roster; affected salary totals are null."))
    return Packet(id=uuid4(),kind="trade_evaluation",title=f"{ta} ↔ {tb} · Trade evaluation",subtitle=f"{season} production · {SALARY_SEASON} salary snapshot",season=season,
        generated_at=datetime.now(UTC),inputs={"team_a":ta,"team_b":tb,"a_sends":a_sends,"b_sends":b_sends,"notes":notes},
        sections=[deal,cap,production,rotation,contracts_section],citations=d.citations,
        limitations=list(dict.fromkeys(["Descriptive scenario, not a projection or a trade-legality certification.",
            "2026-27 salary vintage and cap constants are separate from selected-season production; no multi-year contract schedule.",
            "Payroll uses _payroll source precedence (silver_salaries then silver_cap_players); sources can disagree. Recorded rosters may be incomplete or estimated.",
            "Production weights use GP × MPG because season minutes are rounded per-game rates; no projected lineup production or pick valuation.",
            "Notes and picks are user-provided, unverified and unvalued.",*d.gaps])))


def rotation_section(data, sides, ta, tb, season):
    codes = sorted({ta,tb} | {alias for alias, canonical in TEAM_ALIASES.items() if canonical in (ta,tb)})
    matches = " OR ".join('"MATCHUP" LIKE ?' for _ in codes)
    logs, lc = data.read("silver_player_gamelogs",["Player_ID","Game_ID","MATCHUP","MIN"],
        f'"_season" = ? AND ({matches})',[season,*[code+" %" for code in codes]],5000)
    counts = Counter((r["Player_ID"],r["Game_ID"]) for r in logs)
    usable = bool(logs) and all(v == 1 for v in counts.values()) and all(number(r["MIN"]) is not None for r in logs)
    rows, impact_rows, impact_cites = [], [], {}
    for team,other in ((ta,tb),(tb,ta)):
        team_logs = [r for r in logs if canonical_team(str(r["MATCHUP"]).split()[0]) == team]
        total = sum(number(r["MIN"]) for r in team_logs) if usable and team_logs else None
        def minutes(players, origin):
            values = []
            for player in players:
                found = [r for r in logs if r["Player_ID"] == player["PLAYER_ID"] and canonical_team(str(r["MATCHUP"]).split()[0]) == origin]
                values.append(sum(number(r["MIN"]) for r in found) if usable and found else None)
            return complete_sum(values)
        outgoing, incoming = minutes(sides[team],team), minutes(sides[other],other)
        rows.append({"team":team,"season_minutes":total,"outgoing_minutes":outgoing,"incoming_minutes":incoming,
            "outgoing_share":100*outgoing/total if total and outgoing is not None else None,
            "incoming_share":100*incoming/total if total and incoming is not None else None,
            "null_reason":None if total and outgoing is not None and incoming is not None else "missing_or_ambiguous_game_minutes"})
        for player in sides[team]:
            onoff,cid = data.read("silver_on_off",["Stat","On","Off","On-Off"],'"_season" = ? AND "_entity" = ?',[season,f"player:{player['PLAYER_ID']}"],200)
            net = unique([r for r in onoff if r["Stat"] in ("Net Rating","Net rating")])
            offense = unique([r for r in onoff if r["Stat"] == "Pts per 100 Possessions"])
            defense = unique([r for r in onoff if r["Stat"] == "Pts per 100 Possessions - Defense"])
            values = {}
            for key in ("On","Off","On-Off"):
                value = number(net.get(key))
                ov,dv = number(offense.get(key)),number(defense.get(key))
                values[key] = value if value is not None else ov-dv if ov is not None and dv is not None else None
            derived = data.derived(cid,[],"Net rating is provider net rating or points per 100 possessions minus defensive points per 100 possessions; On-Off is the net-rating difference.")
            if derived:
                impact_cites[str(len(impact_rows))] = derived
            impact_rows.append({"player":player["PLAYER"],"team":team,"on_net":values["On"],"off_net":values["Off"],"net_delta":values["On-Off"],
                                "null_reason":"missing_or_ambiguous_on_off" if any(v is None for v in values.values()) else None})
    cite = data.derived(lc,[],"Season minutes summed from player-game logs by MATCHUP team; incoming minutes are observed at the origin team divided by destination season minutes, not a projection.")
    blocks = [table(rows,[("team","Team",None),("season_minutes","Team season minutes","count"),("outgoing_minutes","Outgoing minutes","count"),("incoming_minutes","Incoming minutes","count"),("outgoing_share","Outgoing share","pct"),("incoming_share","Incoming share","pct")],{"*":cite} if cite else {},
                    "Available game-log minutes; incoming minutes reflect origin-team usage, not a projected destination rotation.","Rotation minutes"),
              table(impact_rows,[("player","Player",None),("team","Observed team",None),("on_net","On-court net rating","rating"),("off_net","Off-court net rating","rating"),("net_delta","On minus off","rating")],impact_cites,title="Observed on/off net rating")]
    if any(r["null_reason"] for r in rows+impact_rows):
        blocks.append(unavailable(data,"Some rotation minutes or on/off net ratings are missing or ambiguous; affected values remain null."))
    return Section(id="rotation_impact",title="Rotation impact",summary=f"Rotation shares use available {season} player-game minutes, not projected playing time [^{cite}]." if cite and usable else None,blocks=blocks)
