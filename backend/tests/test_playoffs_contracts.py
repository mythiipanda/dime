import asyncio

from shared.tools.league import get_playoffs

def _finals():
    r = asyncio.run(get_playoffs.ainvoke({"season": "2025-26"}))
    assert r["ok"]
    return r["rows"]["finals"]

def test_finals_games_have_home_and_scores():
    games = {g["date"]: g for g in _finals()["games"]}
    assert len(games) == 5
    g1 = games["2026-06-03"]
    assert g1["home"] == "SAS" and g1["winner"] == "NYK"
    assert g1["score"] == {"NYK": 105, "SAS": 95}
    assert g1["scoreline"] == "NYK 105, SAS 95"

def test_finals_game3_home_is_explicit():

    games = {g["date"]: g for g in _finals()["games"]}
    g3 = games["2026-06-08"]
    assert g3["home"] == "NYK" and g3["winner"] == "SAS"
    assert g3["score"] == {"NYK": 111, "SAS": 115}

def test_contract_value_team_scope():
    from shared.tools.league import get_contract_value
    r = asyncio.run(get_contract_value.ainvoke(
        {"season": "2025-26", "team": "Spurs"}))
    assert r["ok"] and r["meta"]["team_scope"] == "SAS"
    assert all(f["TEAM"] == "SAS" for f in r["rows"])
    r2 = asyncio.run(get_contract_value.ainvoke({"season": "2025-26"}))
    assert r2["ok"] and len(r2["rows"]) == 20
    assert r2["meta"]["team_scope"] is None

def test_playoffs_reuses_pooled_warehouse_connection():
    import duckdb

    real_connect = duckdb.connect
    opens = []

    def counting_connect(*args, **kwargs):
        opens.append(1)
        return real_connect(*args, **kwargs)

    async def run_twice():
        duckdb.connect = counting_connect
        try:
            first = await get_playoffs.ainvoke({"season": "2025-26"})
            assert first["ok"]
            steady_opens = len(opens)
            second = await get_playoffs.ainvoke({"season": "2025-26"})
            assert second["ok"]
            assert second["rows"] == first["rows"]
            return len(opens) - steady_opens
        finally:
            duckdb.connect = real_connect

    assert asyncio.run(run_twice()) <= 1
