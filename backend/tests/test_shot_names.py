import sys
from pathlib import Path

import polars as pl
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.seed_history import full_name_map, normalize_shot_names


def test_full_name_map_has_full_names():
    names = full_name_map()
    assert names[1628369] == "Jayson Tatum"
    assert " " in names[2544]


def test_normalize_shot_names_rewrites_surnames():
    frame = pl.DataFrame({
        "person_id": [1628369, 999999999],
        "player_name": ["Tatum", "Nobody"],
        "team_tricode": ["BOS", "BOS"],
    })
    out = normalize_shot_names(frame)
    assert out["player_name"].to_list() == ["Jayson Tatum", "Nobody"]


def test_normalize_shot_names_missing_cols_passthrough():
    frame = pl.DataFrame({"x": [1]})
    assert normalize_shot_names(frame).equals(frame)


def test_repair_updates_scratch_warehouse(tmp_path):
    import duckdb

    from scripts.repair_shot_names import repair

    db = tmp_path / "wh.duckdb"
    con = duckdb.connect(str(db))
    con.execute("create table silver_hist_shots "
                "(person_id BIGINT, player_name VARCHAR, _season VARCHAR)")
    con.execute("insert into silver_hist_shots values "
                "(1628369, 'Tatum', '2024-25'),"
                "(2544, 'James', '2024-25'),"
                "(999999999, 'Ghost', '2024-25')")
    n = repair(con)
    rows = con.execute(
        "select player_name from silver_hist_shots order by person_id").fetchall()
    con.close()
    assert n == 2
    assert [r[0] for r in rows] == ["LeBron James", "Jayson Tatum", "Ghost"]
