from test_award_results_runtime_warehouse import _results, runtime_awards


def test_mvp_winner_history_matches_every_recorded_season(runtime_awards):
    result = _results(view="winner_history", award="MVP")
    assert result["ok"] is True, result
    rows = result["rows"]
    seasons = [row["season"] for row in rows]
    assert len(rows) == 47
    assert len(set(seasons)) == 47
    assert seasons == sorted(seasons)
    assert seasons[0] == "1976-77"
    assert seasons[-1] == "2025-26"
    assert all(row["rank"] == 1 for row in rows)
    assert result["meta"]["count"] == 47
    assert result["meta"]["seasons_covered"] == seasons
    assert result["meta"]["history_through"] == "2025-26"
    assert "1981-82" not in seasons
    assert "1982-83" not in seasons
    assert "1983-84" in seasons
    assert [row["season"] for row in rows if row["winner"] == "Larry Bird"] == [
        "1983-84", "1985-86"]
    assert not any(left == "1981-82" and right == "1982-83"
                   for left, right in zip(seasons, seasons[1:]))


def test_winner_history_preserves_all_tied_leaders(runtime_awards):
    result = _results(view="winner_history", award="ALL_NBA", season="2024-25")
    assert result["ok"] is True, result
    leaders = [row for row in result["rows"] if row["season"] == "2024-25"]
    assert {row["player"] for row in leaders} == {
        "Giannis Antetokounmpo", "Shai Gilgeous-Alexander", "Nikola Jokić",
        "Jayson Tatum", "Donovan Mitchell"}
    assert {row["rank"] for row in leaders} == {1}
    assert {row["rank_label"] for row in leaders} == {"1T"}
    assert {row["tied"] for row in leaders} == {True}


def test_winner_history_honors_upper_bound_and_validates_inputs(runtime_awards):
    limited = _results(view="winner_history", award="MVP", season="2023-24")
    assert limited["ok"] is True, limited
    assert limited["meta"]["count"] == 45
    assert limited["meta"]["history_through"] == "2023-24"
    assert limited["meta"]["seasons_covered"][-1] == "2023-24"
    unknown = _results(view="winner_history", award="NOT_AN_AWARD")
    assert unknown["ok"] is False
    assert unknown["reason"] == "unknown_award"
    named = _results(view="winner_history", award="MVP", player="Larry Bird")
    assert named["ok"] is False
    assert named["reason"] == "player_unsupported"


def test_tool_schema_advertises_winner_history(runtime_awards):
    from shared.tools.award_results import get_award_results

    schema = get_award_results.args_schema.model_json_schema()
    assert "winner_history" in schema["properties"]["view"]["enum"]
