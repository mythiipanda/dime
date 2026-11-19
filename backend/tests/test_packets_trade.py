from pathlib import Path
import sys
from types import SimpleNamespace

import duckdb
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

from shared import store
from shared.tools import get_trade_check
from shared.tools.league import CAP
from v2.main import app
from v2.packets.models import Packet
from v2.packets import trade


client = TestClient(app)
WAREHOUSE = store.DB_PATH
BODY = {"team_a":"OKC","team_b":"LAL","a_sends":["Shai Gilgeous-Alexander"],"b_sends":["Luka Doncic"]}


def post(**kwargs):
    return client.post("/api/packets/trade_evaluation",json={**BODY,**kwargs})


def section(packet,id):
    return next(s for s in packet.sections if s.id==id)


@pytest.fixture
def real(monkeypatch):
    if not WAREHOUSE.exists():
        pytest.skip("warehouse not provisioned")
    monkeypatch.setattr(store,"connect",lambda **kwargs:duckdb.connect(str(WAREHOUSE),read_only=True))
    return WAREHOUSE


@pytest.fixture
def minimal(tmp_path,monkeypatch):
    path=tmp_path/"trade.duckdb"
    with duckdb.connect(str(path)) as con:
        con.execute('''CREATE TABLE silver_player_season (PLAYER_ID BIGINT, PLAYER VARCHAR, TEAM VARCHAR,
            AGE DOUBLE, GP DOUBLE, MPG DOUBLE, PPG DOUBLE, RPG DOUBLE, APG DOUBLE,
            _source VARCHAR, _season VARCHAR, _fetched_at VARCHAR, _entity VARCHAR)''')
        con.executemany("INSERT INTO silver_player_season VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",[
            [1,"Alpha Guard","OKC",27,50,30,25,5,8,"fixture","2025-26","2026-01-01","league"],
            [2,"Luka Dončić","LAL",26,60,35,30,8,9,"fixture","2025-26","2026-01-01","league"],
            [3,"Alpha Wing","OKC",25,40,20,10,6,2,"fixture","2025-26","2026-01-01","league"]])
        con.execute('''CREATE TABLE silver_cap_players (player VARCHAR, team VARCHAR, salary BIGINT,
            contract_type VARCHAR, player_option BOOLEAN, team_option BOOLEAN, guaranteed BOOLEAN,
            _source VARCHAR, _season VARCHAR, _fetched_at VARCHAR, _entity VARCHAR)''')
        con.executemany("INSERT INTO silver_cap_players VALUES (?,?,?,?,?,?,?,?,?,?,?)",[
            ["Alpha Guard","OKC",40_000_000,"Standard",False,False,True,"fixture","2026-27","2026-01-01","OKC"],
            ["Luka Doncic","LAL",50_000_000,"Standard",True,False,True,"fixture","2026-27","2026-01-01","LAL"],
            ["Alpha Wing","OKC",10_000_000,"Standard",None,False,True,"fixture","2026-27","2026-01-01","OKC"]])
    monkeypatch.setattr(store,"connect",lambda **kwargs:duckdb.connect(str(path),read_only=True))
    return path


def fixture_post(**kwargs):
    return post(a_sends=kwargs.pop("a_sends",[1]),b_sends=kwargs.pop("b_sends",[2]),**kwargs)


def test_real_trade_kpis_payroll_production_rotation_and_citations(real):
    response=post(notes="Offer includes a user-provided 2030 first-round pick; unvalued.")
    assert response.status_code==200,response.text
    packet=Packet.model_validate(response.json())
    checker=get_trade_check.invoke({"team_a":"OKC","team_b":"LAL","players_a":"Shai Gilgeous-Alexander","players_b":"Luka Doncic","season":"2026-27"})
    assert checker["ok"],checker
    assert packet.kind=="trade_evaluation" and len(packet.sections)==5
    assert Packet.model_validate_json(packet.model_dump_json())==packet
    values={i.label:i.value for b in section(packet,"deal_summary").blocks if b.type=="kpis" for i in b.items}
    with duckdb.connect(str(real),read_only=True) as con:
        wages={name:salary for name,salary in con.execute("SELECT PLAYER_NAME,SALARY_2025_26 FROM silver_salaries WHERE PLAYER_NAME IN (?,?) AND _season=?",["Shai Gilgeous-Alexander","Luka Doncic","2026-27"]).fetchall()}
        sga,luka=wages["Shai Gilgeous-Alexander"],wages["Luka Doncic"]
        assert values["OKC outgoing salary"]==sga
        assert values["OKC incoming salary"]==luka
        assert values["OKC net salary change"]==luka-sga
        assert values["LAL net salary change"]==sga-luka
        caps=section(packet,"cap_position").blocks[0].rows
        for team,outgoing,incoming in (("OKC",sga,luka),("LAL",luka,sga)):
            before=con.execute("SELECT SUM(SALARY_2025_26) FROM silver_salaries WHERE TEAM=? AND _season=?",[team,"2026-27"]).fetchone()[0]
            pre=next(r for r in caps if r["team"]==team and r["position"]=="Before")
            after=next(r for r in caps if r["team"]==team and r["position"]=="After")
            assert pre["payroll"]==before
            assert after["payroll"]==before-outgoing+incoming
            for key,threshold in CAP.items():
                assert after[key]==threshold and after[f"room_{key}"]==threshold-after["payroll"]
            matching=next(r for r in section(packet,"cap_position").blocks[1].rows if r["team"]==team)
            side=checker["rows"]["team_a" if team=="OKC" else "team_b"]
            assert matching["allowed_incoming"]==side["allowed_in"]
            assert matching["rule"]==side["match_rule"]
            assert matching["deal_legal"]==checker["rows"]["legal"]
        sga_row=section(packet,"production_exchanged").blocks[0].rows[0]
        ppg,gp,mpg=con.execute("SELECT PPG,GP,MPG FROM silver_player_season WHERE PLAYER_ID=? AND _season=?",[1628983,"2025-26"]).fetchone()
        ts=con.execute("SELECT TS_PCT FROM silver_advanced WHERE PLAYER_ID=? AND _season=?",[1628983,"2025-26"]).fetchone()[0]
        assert sga_row["ppg"]==ppg and sga_row["gp"]==gp and sga_row["ts_pct"]==pytest.approx(ts*100)
        weighted=section(packet,"production_exchanged").blocks[1].rows[0]
        assert weighted["ppg"]==pytest.approx(ppg) and weighted["minutes"]==pytest.approx(gp*mpg)
        rotation=section(packet,"rotation_impact").blocks[0].rows[0]
        total=con.execute("SELECT SUM(MIN) FROM silver_player_gamelogs WHERE _season=? AND MATCHUP LIKE ?",["2025-26","OKC %"]).fetchone()[0]
        sent=con.execute("SELECT SUM(MIN) FROM silver_player_gamelogs WHERE _season=? AND MATCHUP LIKE ? AND Player_ID=?",["2025-26","OKC %",1628983]).fetchone()[0]
        assert rotation["season_minutes"]==total and rotation["outgoing_minutes"]==sent
        assert rotation["outgoing_share"]==pytest.approx(100*sent/total)
        observed={stat:(float(on),float(off)) for stat,on,off in con.execute('SELECT Stat,"On","Off" FROM silver_on_off WHERE _season=? AND _entity=? AND Stat IN (?,?)',
            ["2025-26","player:1628983","Pts per 100 Possessions","Pts per 100 Possessions - Defense"]).fetchall()}
        impact=section(packet,"rotation_impact").blocks[1].rows[0]
        assert impact["on_net"]==pytest.approx(observed["Pts per 100 Possessions"][0]-observed["Pts per 100 Possessions - Defense"][0])
        for citation in packet.citations.values():
            assert con.execute(citation.sql,citation.params).description
            assert all(cid in packet.citations for cid in citation.supporting_cites)
    assert "user-provided" in section(packet,"deal_summary").blocks[-1].md
    for s in packet.sections:
        for b in s.blocks:
            ids=[i.cite for i in b.items if i.cite] if b.type=="kpis" else list(b.cites.values()) if b.type=="table" else b.cites if b.type=="text" else []
            assert all(cid in packet.citations for cid in ids)


def test_fixture_salary_fallback_and_minutes_weighted_rates(minimal,monkeypatch):
    called=[]
    original=trade._payroll
    def payroll(team,con):
        called.append(team)
        return original(team,con)
    monkeypatch.setattr(trade,"_payroll",payroll)
    response=fixture_post(a_sends=[1,3],team_a="Oklahoma City Thunder",team_b="Lakers")
    assert response.status_code==200,response.text
    packet=Packet.model_validate(response.json())
    assert called==["OKC","LAL"]
    weighted=section(packet,"production_exchanged").blocks[1].rows[0]
    assert weighted["ppg"]==pytest.approx((25*1500+10*800)/2300)
    assert weighted["gp"]==90
    assert weighted["minutes"]==2300
    assert any(b.type=="callout" for b in section(packet,"rotation_impact").blocks)
    contracts=section(packet,"contracts").blocks[0]
    assert contracts.rows[1]["player_option"] is None and contracts.rows[1]["null_reason"]


def test_missing_salary_is_null_not_zero(minimal):
    with duckdb.connect(str(minimal)) as con:
        con.execute("DELETE FROM silver_cap_players WHERE player=?",["Luka Doncic"])
    response=fixture_post()
    assert response.status_code==200,response.text
    packet=Packet.model_validate(response.json())
    items={i.label:i for b in section(packet,"deal_summary").blocks if b.type=="kpis" for i in b.items}
    assert items["OKC incoming salary"].value is None and items["OKC incoming salary"].null_reason
    assert items["OKC net salary change"].value is None
    cap=section(packet,"cap_position").blocks[0].rows
    assert all(r["payroll"] is None and r["null_reason"] for r in cap if r["position"]=="After")
    assert any(b.type=="callout" for b in section(packet,"contracts").blocks)


def test_wrong_team_unknown_ambiguous_and_duplicate(minimal):
    response=fixture_post(a_sends=[2],b_sends=[1])
    assert response.status_code==422
    assert response.json()["detail"]["team_found"]=="LAL"
    assert fixture_post(a_sends=["Unknown"]).status_code==422
    assert fixture_post(a_sends=[1,1]).json()["detail"]["reason"]=="duplicate_player"
    with duckdb.connect(str(minimal)) as con:
        con.execute("UPDATE silver_player_season SET PLAYER=? WHERE PLAYER_ID=?",["Alpha Guard",3])
    assert fixture_post(a_sends=["Alpha Guard"]).json()["detail"]["reason"]=="ambiguous_player"


def test_absent_salary_tables_and_empty_side(minimal):
    with duckdb.connect(str(minimal)) as con:
        con.execute("DROP TABLE silver_cap_players")
    response=fixture_post(a_sends=[])
    assert response.status_code==200,response.text
    packet=Packet.model_validate(response.json())
    items={i.label:i for b in section(packet,"deal_summary").blocks if b.type=="kpis" for i in b.items}
    assert items["OKC outgoing salary"].value==0
    assert items["OKC incoming salary"].value is None
    assert any("table unavailable" in s for s in packet.limitations)


def test_only_requested_salary_vintage_is_used(minimal):
    with duckdb.connect(str(minimal)) as con:
        con.execute("INSERT INTO silver_cap_players SELECT player,team,1,contract_type,player_option,team_option,guaranteed,_source,'2025-26',_fetched_at,_entity FROM silver_cap_players")
    response=fixture_post()
    assert response.status_code==200,response.text
    packet=Packet.model_validate(response.json())
    items={i.label:i for b in section(packet,"deal_summary").blocks if b.type=="kpis" for i in b.items}
    assert items["OKC outgoing salary"].value==40_000_000
    assert items["OKC incoming salary"].value==50_000_000


@pytest.mark.parametrize("invalid",["negative","duplicate"])
def test_invalid_salary_roster_fails_closed(minimal,invalid):
    with duckdb.connect(str(minimal)) as con:
        if invalid=="negative":
            con.execute("UPDATE silver_cap_players SET salary=-1 WHERE player='Alpha Guard'")
        else:
            con.execute("INSERT INTO silver_cap_players SELECT * FROM silver_cap_players WHERE player='Alpha Guard'")
    response=fixture_post()
    assert response.status_code==200,response.text
    packet=Packet.model_validate(response.json())
    cap=section(packet,"cap_position").blocks[0].rows
    assert all(r["payroll"] is None and r["null_reason"] for r in cap if r["team"]=="OKC")


def test_trade_warehouse_unavailable_returns_503(monkeypatch):
    def offline(**kwargs):
        raise duckdb.IOException("offline")
    monkeypatch.setattr(store,"connect",offline)
    assert post().status_code==503


@pytest.mark.parametrize("changes",[{"team_a":"nonsense"},{"team_a":"LAL"},{"a_sends":[],"b_sends":[]},{"a_sends":[True]},{"a_sends":[-1]},{"season":"invalid"}])
def test_invalid_trade_requests(minimal,changes):
    assert fixture_post(**changes).status_code==422


def test_team_code_aliases():
    assert trade.resolve_team("BRK")=="BKN"
    assert trade.resolve_team("CHO")=="CHA"
    assert trade.resolve_team("PHO")=="PHX"


def test_real_rotation_accepts_bref_pho_game_logs(real):
    response=post(team_a="PHX",team_b="OKC",a_sends=["Devin Booker"],b_sends=["Shai Gilgeous-Alexander"])
    assert response.status_code==200,response.text
    packet=Packet.model_validate(response.json())
    rotation=section(packet,"rotation_impact").blocks[0].rows[0]
    with duckdb.connect(str(real),read_only=True) as con:
        total=con.execute("SELECT SUM(MIN) FROM silver_player_gamelogs WHERE _season=? AND SUBSTR(MATCHUP,1,3) IN (?,?)",["2025-26","PHX","PHO"]).fetchone()[0]
        outgoing=con.execute("SELECT SUM(MIN) FROM silver_player_gamelogs WHERE _season=? AND Player_ID=? AND SUBSTR(MATCHUP,1,3) IN (?,?)",["2025-26",1626164,"PHX","PHO"]).fetchone()[0]
    assert total and outgoing
    assert rotation["season_minutes"]==total
    assert rotation["outgoing_minutes"]==outgoing
    assert rotation["outgoing_share"]==pytest.approx(100*outgoing/total)


@pytest.mark.parametrize("apron",[False,True])
def test_packet_verdict_equals_public_checker(minimal,apron):
    with duckdb.connect(str(minimal)) as con:
        if apron:
            con.execute("UPDATE silver_cap_players SET salary=200000000 WHERE player='Alpha Wing'")
        con.execute('''CREATE TABLE silver_salaries AS SELECT player AS PLAYER_NAME, team AS TEAM,
            salary AS SALARY_2025_26, _source, _season, _fetched_at, _entity FROM silver_cap_players''')
    sends=[1,3] if apron else [1]
    players="Alpha Guard, Alpha Wing" if apron else "Alpha Guard"
    expected=get_trade_check.invoke({"team_a":"OKC","team_b":"LAL","players_a":players,"players_b":"Luka Doncic","season":"2026-27"})
    assert expected["ok"],expected
    response=fixture_post(a_sends=sends)
    assert response.status_code==200,response.text
    packet=Packet.model_validate(response.json())
    cap=section(packet,"cap_position")
    rows=cap.blocks[1].rows
    for row,key,other in zip(rows,("team_a","team_b"),("team_b","team_a")):
        side=expected["rows"][key]
        assert row["deal_legal"]==expected["rows"]["legal"]
        assert row["allowed_incoming"]==side["allowed_in"]
        assert row["incoming"]==expected["rows"][other]["out"]
        assert row["rule"]==side["match_rule"]
        for issue in expected["rows"]["issues"]:
            if issue.startswith(row["team"]+" "):
                assert issue in row["reasons"] and row["verdict"] is False
    assert rows[0]["over_apron2"] is apron
    if apron:
        assert "cannot aggregate" in rows[0]["reasons"]
    unchecked=[c["rule"] for c in expected["rows"]["checks"] if not c["checked"]]
    warning=next(b.md for b in cap.blocks if b.type=="callout" and b.md.startswith("Not modeled"))
    assert all(rule in warning for rule in unchecked)


def test_checker_absorption_response_is_not_recomputed(minimal,monkeypatch):
    calls=[]
    def invoke(arguments):
        calls.append(arguments)
        return {"ok":True,"rows":{"team_a":{"team":"OKC","out":40000000,"allowed_in":115250000,"match_rule":"cap room plus outgoing salary plus $250k (under the cap)"},
            "team_b":{"team":"LAL","out":50000000,"allowed_in":125250000,"match_rule":"cap room plus outgoing salary plus $250k (under the cap)"},
            "legal":True,"issues":[],"checks":[]},"meta":{"source":"injected checker response"}}
    monkeypatch.setattr(trade,"get_trade_check",SimpleNamespace(invoke=invoke))
    response=fixture_post()
    assert response.status_code==200,response.text
    rows=section(Packet.model_validate(response.json()),"cap_position").blocks[1].rows
    assert calls==[{"team_a":"OKC","team_b":"LAL","season":"2026-27","players_a":"Alpha Guard","players_b":"Luka Doncic"}]
    assert rows[0]["allowed_incoming"]==115250000
    assert rows[0]["verdict"] and "under the cap" in rows[0]["rule"]
