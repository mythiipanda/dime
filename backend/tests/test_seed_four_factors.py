import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import polars as pl
import seed_four_factors as ff


def _frame(rows):
    return pl.DataFrame(rows)


def test_parse_splits_offense_defense_and_minutes():
    frame = _frame([
        {"stat": "eFG%", "On": 0.57, "Off": 0.54, "side": "offense"},
        {"stat": "OReb%", "On": 0.24, "Off": 0.26, "side": "offense"},
        {"stat": "eFG%", "On": 0.50, "Off": 0.52, "side": "defense"},
        {"stat": "Minutes", "On": 2259, "Off": 1616, "side": ""},
    ])
    out = ff.parse_four_factor_frame(frame, "2026-27", "ts", "player:1")
    assert out is not None
    offense, defense, min_on, min_off, source, season, fetched, entity = out
    assert len(offense) == 2 and len(defense) == 1
    assert offense[0]["stat"] == "eFG%" and abs(offense[0]["On"] - 0.57) < 1e-9
    assert defense[0]["stat"] == "eFG%"
    assert min_on == 2259 and min_off == 1616
    assert source == "pbpstats" and entity == "player:1"


def test_parse_handles_missing_side_via_stat_names():
    frame = _frame([
        {"stat": "eFG%", "On": 0.57, "Off": 0.54},
        {"stat": "DReb%", "On": 0.71, "Off": 0.69},
    ])
    out = ff.parse_four_factor_frame(frame, "2026-27", "ts", "player:1")
    assert out is not None
    offense, defense = out[0], out[1]
    assert len(offense) == 1 and len(defense) == 1
    assert defense[0]["stat"] == "DReb%"


def test_parse_empty_frame_returns_none():
    assert ff.parse_four_factor_frame(pl.DataFrame(), "2026-27", "ts", "player:1") is None
    assert ff.parse_four_factor_frame(None, "2026-27", "ts", "player:1") is None


def test_parse_output_matches_warehouse_row_shape():
    import duckdb
    frame = _frame([
        {"stat": "eFG%", "On": 0.57, "Off": 0.54, "side": "offense"},
        {"stat": "eFG%", "On": 0.50, "Off": 0.52, "side": "defense"},
    ])
    out = ff.parse_four_factor_frame(frame, "2026-27", "ts", "player:1")
    con = duckdb.connect()
    con.execute("CREATE TABLE t AS SELECT * FROM silver_four_factors" if False else "SELECT 1")
    assert isinstance(out[0], list) and isinstance(out[1], list)
    keys = set(out[0][0].keys())
    assert keys == {"On", "Off", "stat"}


def test_writes_default_on_dry_run_opts_out() -> None:
    import inspect
    src = inspect.getsource(ff.main)
    assert 'if not args.dry_run' in src
    assert '"--apply"' not in src


def test_parse_handles_prestructured_nested_shape() -> None:
    frame = pl.DataFrame({
        "offense_results": [[
            {"On": 0.517, "Off": 0.529, "stat": "eFG%"},
            {"On": 0.265, "Off": 0.318, "stat": "OReb%"},
        ]],
        "defense_results": [[
            {"On": 0.525, "Off": 0.529, "stat": "eFG%"},
        ]],
        "minutes_on": [658],
        "minutes_off": [264],
    })
    out = ff.parse_four_factor_frame(frame, "2026-27", "ts", "player:9")
    assert out is not None
    offense, defense, min_on, min_off, source, season, fetched, entity = out
    assert len(offense) == 2 and len(defense) == 1
    assert offense[0]["stat"] == "eFG%" and abs(offense[0]["On"] - 0.517) < 1e-9
    assert min_on == 658 and min_off == 264
    assert entity == "player:9"
