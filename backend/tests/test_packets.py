from datetime import UTC, datetime
from pathlib import Path
import sys
from uuid import uuid4

import duckdb
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from shared import store
from v2.main import app
from v2.packets import deep_dive
from v2.packets.models import Citation, Claim, Kpi, Kpis, Narrative, Packet, Section, Table
from v2.packets.narrative import narrative_prompt, validate_narrative
from v2.packets.models import format_value


WAREHOUSE = store.DB_PATH
client = TestClient(app)


@pytest.fixture
def real(monkeypatch):
    if not WAREHOUSE.exists():
        pytest.skip("warehouse not provisioned")
    monkeypatch.setattr(store, "connect", lambda **kwargs: duckdb.connect(str(WAREHOUSE), read_only=True))
    return WAREHOUSE


@pytest.fixture
def minimal(tmp_path, monkeypatch):
    path = tmp_path / "packets.duckdb"
    with duckdb.connect(str(path)) as con:
        con.execute('''CREATE TABLE silver_player_season (
            PLAYER_ID BIGINT, PLAYER VARCHAR, TEAM VARCHAR, AGE DOUBLE, GP DOUBLE, MPG DOUBLE,
            PPG DOUBLE, RPG DOUBLE, APG DOUBLE, SPG DOUBLE, BPG DOUBLE,
            _source VARCHAR, _season VARCHAR, _fetched_at VARCHAR, _entity VARCHAR)''')
        con.executemany("INSERT INTO silver_player_season VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", [
            [1,"Luka Dončić","AAA",26,50,30,30,8,9,1,1,"fixture","2025-26","2026-01-01","league"],
            [2,"Alpha Guard","BBB",25,40,25,20,5,6,2,2,"fixture","2025-26","2026-01-01","league"],
            [3,"Bench Guard","CCC",20,5,10,100,20,20,5,5,"fixture","2025-26","2026-01-01","league"],
        ])
    monkeypatch.setattr(store,"connect",lambda **kwargs: duckdb.connect(str(path),read_only=True))
    return path


def request(player="Shai Gilgeous-Alexander", **kwargs):
    return client.post("/api/packets/player_deep_dive",json={"player":player,**kwargs})


def section(packet, id):
    return next(s for s in packet.sections if s.id == id)


def test_real_packet_kpis_schema_citations_and_query_replay(real):
    response=request()
    assert response.status_code == 200, response.text
    packet=Packet.model_validate(response.json())
    assert packet.narrative is None
    assert Packet.model_validate_json(packet.model_dump_json()) == packet
    assert len(packet.sections)==6
    items={item.label:item for item in section(packet,"profile").blocks[0].items}
    with duckdb.connect(str(real),read_only=True) as con:
        ppg,rpg,apg,age=con.execute("SELECT PPG,RPG,APG,AGE FROM silver_player_season WHERE PLAYER_ID=? AND _season=?",[1628983,"2025-26"]).fetchone()
        ts=con.execute("SELECT TS_PCT FROM silver_advanced WHERE PLAYER_ID=? AND _season=?",[1628983,"2025-26"]).fetchone()[0]
        for label,expected in [("PPG",ppg),("RPG",rpg),("APG",apg),("Age",age),("TS%",ts*100)]:
            assert items[label].value == pytest.approx(expected)
            assert packet.citations[items[label].cite].row_key == {"PLAYER_ID":1628983,"_season":"2025-26"}
        for cite in packet.citations.values():
            assert "LIMIT ?" in cite.sql
            assert con.execute(cite.sql,cite.params).description
            assert all(cid in packet.citations for cid in cite.supporting_cites)
    for s in packet.sections:
        for block in s.blocks:
            ids=[]
            if block.type=="kpis": ids=[i.cite for i in block.items if i.cite]
            elif block.type=="table": ids=list(block.cites.values())
            elif block.type=="chart": ids=[block.cite] if block.cite else []
            elif block.type=="text": ids=block.cites
            assert all(cid in packet.citations for cid in ids)
    assert items["2026-27 salary"].context.startswith("2026-27 salary; vintage:")
    assert any("not a projection" in s for s in packet.limitations)


def test_percentiles_use_only_qualified_players_and_midrank(minimal):
    packet=Packet.model_validate(request("Luka Doncic").json())
    blocks=section(packet,"league_context").blocks
    assert "GP ≥20 and MPG ≥15" in blocks[0].md
    points=next(r for b in blocks if b.type=="table" for r in b.rows if r["metric"]=="Points")
    assert points["n"]==2
    assert points["percentile"]==75
    bench=Packet.model_validate(request(3).json())
    rows=next(b.rows for b in section(bench,"league_context").blocks if b.type=="table")
    assert all(r["percentile"] is None and r["null_reason"] for r in rows)


def test_accent_exact_identity_and_unknown_ambiguous(minimal):
    for name in ("Luka Doncic","Luka Dončić","  LUKA  DONCIC ",1,"1"):
        result=request(name)
        assert result.status_code==200, result.text
        assert result.json()["inputs"]["player_id"]==1
    unknown=request("Luka")
    assert unknown.status_code==422
    assert unknown.json()["detail"]["reason"]=="unknown_player"
    assert unknown.json()["detail"]["candidates"][0]["id"]==1
    with duckdb.connect(str(minimal)) as con:
        con.execute("INSERT INTO silver_player_season SELECT 4,'Luka Doncic',TEAM,AGE,GP,MPG,PPG,RPG,APG,SPG,BPG,_source,_season,_fetched_at,_entity FROM silver_player_season WHERE PLAYER_ID=1")
    ambiguous=request("Luka Dončić")
    assert ambiguous.status_code==422
    assert {r["id"] for r in ambiguous.json()["detail"]["candidates"]}=={1,4}


def test_missing_tables_columns_and_empty_sections_are_callouts(minimal,monkeypatch):
    original=deep_dive.Data.read
    def missing(self,table,*args,**kwargs):
        if table != deep_dive.BASE:
            self.available.discard(table)
        return original(self,table,*args,**kwargs)
    monkeypatch.setattr(deep_dive.Data,"read",missing)
    response=request(1)
    assert response.status_code==200,response.text
    packet=Packet.model_validate(response.json())
    for id in ("shot_profile","form_splits","impact","career"):
        assert any(b.type=="callout" for b in section(packet,id).blocks)
    kpis=section(packet,"profile").blocks[0].items
    assert all(i.null_reason for i in kpis if i.value is None)
    assert any("table unavailable" in gap for gap in packet.limitations)


def test_form_shots_and_career_match_direct_sql(real):
    packet=Packet.model_validate(request(1628983).json())
    with duckdb.connect(str(real),read_only=True) as con:
        pts,reb,ast,fga,fta=con.execute("SELECT avg(PTS),avg(REB),avg(AST),avg(FGA),avg(FTA) FROM silver_player_gamelogs WHERE _season=? AND Player_ID=?",["2025-26",1628983]).fetchone()
        splits=next(b for b in section(packet,"form_splits").blocks if b.type=="table")
        row=splits.rows[0]
        assert row["pts"]==pytest.approx(pts)
        assert row["ts_pct"]==pytest.approx(100*pts/(2*(fga+.44*fta)))
        line=next(b for b in section(packet,"form_splits").blocks if b.type=="chart")
        assert all(r["rolling_5"] is None for r in line.data[:4])
        assert line.data[4]["rolling_5"]==pytest.approx(sum(r["pts"] for r in line.data[:5])/5)
        rows=next(b.rows for b in section(packet,"shot_profile").blocks if b.type=="table")
        assert sum(r["share"] for r in rows)==pytest.approx(100)
        for row in rows:
            expected=con.execute('''WITH q AS (SELECT PLAYER_ID FROM silver_player_season WHERE _season=? AND GP>=20 AND MPG>=15 GROUP BY PLAYER_ID HAVING count(*)=1),
                bad AS (SELECT PLAYER_ID FROM silver_zone_splits WHERE _season=? GROUP BY PLAYER_ID,ZONE HAVING count(*)>1)
                SELECT 100*sum(FGM)/sum(FGA) FROM silver_zone_splits WHERE _season=? AND ZONE=? AND FGA>0 AND isfinite(FGM) AND PLAYER_ID IN (SELECT PLAYER_ID FROM q) AND PLAYER_ID NOT IN (SELECT PLAYER_ID FROM bad)''',["2025-26","2025-26","2025-26",row["zone"]]).fetchone()[0]
            assert row["league_fg_pct"]==pytest.approx(expected)
        career=next(b.rows for b in section(packet,"career").blocks if b.type=="table")
        assert career[-1]["season"]=="2025-26"
        assert all(r["season"]<="2024-25" for r in career[:-1])


def test_empty_identity_and_warehouse_unavailable(minimal,monkeypatch):
    assert request("Not A Player").status_code==422
    def unavailable(**kwargs):
        assert kwargs=={"read_only":True}
        raise duckdb.IOException("offline")
    monkeypatch.setattr(store,"connect",unavailable)
    assert request(1).status_code==503


def test_missing_columns_and_duplicate_profile_rows(minimal):
    with duckdb.connect(str(minimal)) as con:
        con.execute("CREATE TABLE silver_advanced (PLAYER_ID BIGINT)")
        con.execute("INSERT INTO silver_player_season SELECT * FROM silver_player_season WHERE PLAYER_ID=1")
    response=request(1)
    assert response.status_code==200,response.text
    packet=Packet.model_validate(response.json())
    assert all(item.value is None and item.null_reason for item in section(packet,"profile").blocks[0].items)
    assert any("required columns unavailable" in gap for gap in packet.limitations)


def test_read_bound_omits_population_instead_of_ranking_truncated_data(minimal):
    with duckdb.connect(str(minimal),read_only=True) as con:
        data=deep_dive.Data(con,"2025-26")
        rows,cid=data.read("silver_player_season",["PLAYER_ID"], '"_season" = ?', ["2025-26"],limit=1)
        assert rows==[] and cid is None
        assert "exceeds safe row bound" in data.gaps[0]


@pytest.mark.parametrize("body",[{"player":True},{"player":-1},{"player":""},{"player":"x","season":"bad"}])
def test_request_validation(body):
    assert client.post("/api/packets/player_deep_dive",json=body).status_code==422


def example_packet():
    return Packet(id=uuid4(),kind="player_deep_dive",title="Fixture",subtitle="Fixture",season="2025-26",generated_at=datetime.now(UTC),inputs={},
        citations={"c1":Citation(source_table="fixture",table="fixture",columns=["PPG"],season="2025-26",sql="SELECT 33.456 AS PPG LIMIT ?",params=[1],row_key={})},
        sections=[Section(id="profile",title="Profile",blocks=[Kpis(items=[Kpi(label="PPG",value=33.456,unit="per_game",display="33.46",cite="c1")])])],limitations=[])


def test_optional_narrative_roundtrip_and_prompt():
    packet=example_packet()
    assert Packet.model_validate_json(packet.model_dump_json()).narrative is None
    prompt=narrative_prompt(packet)
    assert '33.456' in prompt and 'c1' in prompt and '"$defs"' in prompt


def test_narrative_keeps_rounded_claims_and_rejects_uncited_unknown_wrong_numbers():
    packet=example_packet()
    narrative=Narrative(status="draft",generated_by="future-model",summary=[
        Claim(md="Scores 33.46 points [^c1].",cites=["c1"]),
        Claim(md="Uncited statement.",cites=[]),
        Claim(md="Unknown source.",cites=["missing"]),
        Claim(md="Scores 99.9 points.",cites=["c1"]),
        Claim(md="Another unknown [^missing].",cites=["c1"]),
    ],recommendation=[Claim(md="Review the scoring profile.",cites=["c1"])])
    before=packet.model_dump_json()
    accepted,rejected=validate_narrative(packet,narrative)
    assert len(accepted.summary)==1 and len(accepted.recommendation)==1
    assert len(rejected)==4 and all(r["reason"] for r in rejected)
    assert packet.model_dump_json()==before
    response=client.post("/api/packets/narrative",json={"packet":packet.model_dump(mode="json"),"narrative":narrative.model_dump(mode="json")})
    assert response.status_code==200,response.text
    assert len(response.json()["rejected"])==4
    assert response.json()["packet_with_narrative"]["narrative"]["summary"]==[accepted.summary[0].model_dump()]


def test_narrative_table_row_scoping_and_no_numeric_evidence():
    packet=example_packet()
    packet.citations["c2"]=packet.citations["c1"].model_copy()
    packet.sections.append(Section(id="rows",title="Rows",blocks=[Table(columns=[],rows=[{"score":12.25},{"score":99}],cites={"0":"c1","1":"c2"})]))
    result,rejected=validate_narrative(packet,Narrative(summary=[Claim(md="Value 12.3.",cites=["c1"]),Claim(md="Value 99.",cites=["c1"])]))
    assert len(result.summary)==1 and len(rejected)==1


def test_narrative_leading_decimal_and_signed_numbers():
    packet=example_packet()
    packet.sections[0].blocks[0].items[0].value=-0.51
    claims=[Claim(md="Value −.5.",cites=["c1"]),Claim(md="Value 0.5.",cites=["c1"])]
    accepted,rejected=validate_narrative(packet,Narrative(summary=claims))
    assert accepted.summary==claims[:1]
    assert len(rejected)==1 and rejected[0]["reason"].startswith("unsupported_number")
    packet.sections[0].blocks[0].items[0].value=9
    accepted,rejected=validate_narrative(packet,Narrative(summary=[Claim(md="Value .9.",cites=["c1"])]))
    assert not accepted.summary and len(rejected)==1
    accepted,rejected=validate_narrative(packet,Narrative(summary=[Claim(md="Value 1e1000000.",cites=["c1"])]))
    assert not accepted.summary and rejected[0]["reason"]=="invalid_number"


@pytest.mark.parametrize("value,unit,expected",[(27,"years","27"),(65,"count","65"),(40_800_000,"usd","$40.8M"),(66.5,"pct","66.5%"),(16.3,"rating","+16.3"),(None,"usd","—")])
def test_display_formatter(value,unit,expected):
    assert format_value(value,unit)==expected


def test_polished_deep_dive_display_summaries_and_impact(real):
    packet=Packet.model_validate(request().json())
    for s in packet.sections:
        assert s.summary and "[^" in s.summary
        for block in s.blocks:
            if block.type=="table":
                assert not any(c.key.lower().endswith("_id") for c in block.columns)
                assert len(block.rows)==len(block.display_rows)
            elif block.type=="chart":
                assert len(block.data)==len(block.display_data)
    impact=section(packet,"impact")
    curated=next(b for b in impact.blocks if b.type=="table" and b.title=="On/off highlights")
    assert 1<=len(curated.rows)<=8 and not curated.collapsed
    assert impact.blocks[-1].title=="On/off appendix" and impact.blocks[-1].collapsed
    assert len(impact.blocks[-1].rows)>len(curated.rows)
    assert not any(b.type=="callout" and b.md in ("Clutch totals","Hustle totals") for b in impact.blocks)
    age=next(i for i in section(packet,"profile").blocks[0].items if i.label=="Age")
    assert age.display==str(int(age.value))
