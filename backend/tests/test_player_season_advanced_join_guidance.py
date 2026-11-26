from pathlib import Path


WAREHOUSE_GUIDE = Path("backend/analyst/skills/warehouse-guide/SKILL.md")
PLAYER_EVALUATION = Path("backend/analyst/skills/player-evaluation/SKILL.md")


def warehouse_guide_row(table: str) -> str:
    text = WAREHOUSE_GUIDE.read_text()
    return next(
        line for line in text.splitlines() if line.startswith(f"| `{table}`")
    )


def test_warehouse_guide_assigns_ts_pct_to_player_season():
    row = warehouse_guide_row("silver_player_season")
    assert "FG_PCT/FG3_PCT/FT_PCT/TS_PCT" in row
    assert "TS-only current scoring-efficiency screens" in row
    assert "one aggregate query over this table" in row


def test_warehouse_guide_keeps_advanced_only_metrics_in_advanced():
    player_row = warehouse_guide_row("silver_player_season")
    advanced_row = warehouse_guide_row("silver_advanced")
    assert "USG_PCT/ratings/other advanced-only columns are not here" in player_row
    assert "USG_PCT" in advanced_row
    assert "OFF/DEF/NET_RATING" in advanced_row
    assert "AST_PCT" in advanced_row
    assert "REB_PCT" in advanced_row
    assert "EFG_PCT" in advanced_row


def test_warehouse_guide_routes_mixed_efficiency_screens_to_join():
    player_row = warehouse_guide_row("silver_player_season")
    advanced_row = warehouse_guide_row("silver_advanced")
    assert "TS-only current scoring-efficiency screens" in player_row
    assert "Mixed efficiency+usage/ratings screens" in advanced_row
    assert "join to `silver_player_season`" in advanced_row
    assert "PLAYER_ID" in advanced_row and "_season" in advanced_row


def test_warehouse_guide_drops_stale_ts_pct_advanced_only_routing():
    text = WAREHOUSE_GUIDE.read_text()
    stale_join = (
        "Scoring-efficiency screens (PPG with TS_PCT/USG_PCT cutoffs) "
        "are ALWAYS this join"
    )
    assert "No efficiency or usage columns" not in text
    assert "TS_PCT/USG_PCT/ratings are NOT here" not in text
    assert stale_join not in text


def test_player_evaluation_prefers_single_table_ts_pct_screens():
    text = PLAYER_EVALUATION.read_text()
    assert "Efficiency screens are single-table first" in text
    assert "silver_player_season" in text
    assert "TS_PCT" in text


def test_player_evaluation_limits_advanced_join_to_advanced_only_columns():
    text = PLAYER_EVALUATION.read_text()
    assert "Join `silver_advanced`" in text
    assert "advanced-only column" in text
    assert "USG_PCT" in text
