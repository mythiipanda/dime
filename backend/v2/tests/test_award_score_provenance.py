
def test_existing_award_output_declares_score_provenance(monkeypatch):
    from app.tools import awards

    monkeypatch.setattr(awards, "_missing_table", lambda: None)
    monkeypatch.setattr(awards, "_pool", lambda season: [
        {"player": "A", "team": "AAA", "gp": 50, "mins": 1500,
         "ppg": 20, "eff_pg": 20, "apg": 5, "rpg": 7, "age": 20},
        {"player": "B", "team": "BBB", "gp": 50, "mins": 1500,
         "ppg": 10, "eff_pg": 10, "apg": 2, "rpg": 3, "age": 20},
    ])
    monkeypatch.setattr("app.tools._core.season_static", lambda season: True)

    result = awards.get_award_race.invoke({"award": "ROY", "season": "2025-26"})
    meta = result["meta"]
    assert meta["source"] == "warehouse (nba_api)"
    assert meta["score_unit"] == "weighted_z_score"
    assert "within-qualified-pool" in meta["method"]
    assert "not points" in meta["score_definition"]
    assert "an official award result" in meta["score_definition"]


def test_rookie_leader_surface_declares_source_method_and_stat_unit(monkeypatch):
    import sys
    from unittest.mock import MagicMock
    from app.tools import league

    connection = MagicMock()
    connection.execute.side_effect = [
        MagicMock(fetchdf=lambda: MagicMock(to_dict=lambda _: [{
            "PLAYER_ID": 1, "PLAYER": "Rookie", "TEAM": "AAA", "AGE": 20,
            "GP": 50, "MPG": 30, "PPG": 20, "RPG": 5, "APG": 4,
            "SPG": 1, "BPG": 1, "FG_PCT": .5, "FG3_PCT": .4,
            "FT_PCT": .8,
        }])),
        MagicMock(fetchall=lambda: []),
        MagicMock(fetchall=lambda: []),
    ]
    fake_duckdb = MagicMock(connect=lambda *args, **kwargs: connection)
    monkeypatch.setitem(sys.modules, "duckdb", fake_duckdb)

    result = league.get_rookie_leaders.invoke({
        "stat": "fg3_pct", "season": "2025-26",
    })
    meta = result["meta"]
    assert "silver_player_season" in meta["source"]
    assert "excluding every player" in meta["method"]
    assert meta["stat"] == "FG3_PCT"
    assert meta["stat_unit"] == "fraction_0_1"
