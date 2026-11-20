import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.seed_salary_teams import _fold, apply_team_patch
from shared.sources.salaries import TEAM_ABBR
from shared.tools._core import _STATIC_TEAMS

_CANONICAL_ABBRS = {abbr for abbr, _full, _tid in _STATIC_TEAMS}


def test_csv_codes_normalize_to_canonical_abbrs():
    assert TEAM_ABBR["BRK"] == "BKN"
    assert TEAM_ABBR["CHO"] == "CHA"
    assert TEAM_ABBR["PHO"] == "PHX"
    assert TEAM_ABBR["WSH"] == "WAS"
    for canonical in TEAM_ABBR.values():
        assert canonical in _CANONICAL_ABBRS


def test_team_patch_writes_only_canonical_abbrs(tmp_path):
    import duckdb

    path = tmp_path / "salaries.duckdb"
    con = duckdb.connect(str(path))
    try:
        con.execute(
            "CREATE TABLE silver_salaries (PLAYER_NAME VARCHAR, TEAM VARCHAR)")
        con.execute("INSERT INTO silver_salaries VALUES "
                    "('Mikal Bridges', 'BRK'), "
                    "('LaMelo Ball', 'CHO'), "
                    "('Devin Booker', 'PHO'), "
                    "('Jordan Poole', 'WSH'), "
                    "('Stephen Curry', 'GSW'), "
                    "('Unknown Prospect', NULL)")
    finally:
        con.close()
    mapping = {
        _fold("Mikal Bridges"): "BKN",
        _fold("LaMelo Ball"): "CHA",
        _fold("Devin Booker"): "PHX",
        _fold("Jordan Poole"): "WAS",
        _fold("Stephen Curry"): "GSW",
    }
    con = duckdb.connect(str(path))
    try:
        matched, overridden = apply_team_patch(con, mapping)
        teams = {r[0] for r in con.execute(
            "SELECT TEAM FROM silver_salaries WHERE TEAM IS NOT NULL").fetchall()}
    finally:
        con.close()
    assert matched == 5
    assert overridden == 4
    assert teams <= _CANONICAL_ABBRS
    assert teams == {"BKN", "CHA", "PHX", "WAS", "GSW"}
