import importlib.util
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from shared import store


def _load_seed_module():
    path = (Path(__file__).resolve().parent.parent / "scripts"
            / "build_team_four_factors.py")
    spec = importlib.util.spec_from_file_location(
        "build_team_four_factors_seed", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


COLUMNS = ["TEAM", "Team_ID", "_season", "GP", "W", "EFG_PCT", "TOV_PCT",
           "ORB_PCT", "FT_RATE", "OPP_EFG_PCT", "OPP_TOV_PCT", "DRB_PCT",
           "OPP_FT_RATE"]


def _rows():
    return [{**{c: 0 for c in COLUMNS},
             **{"TEAM": f"T{i:02d}", "Team_ID": i, "_season": "S"}}
            for i in range(30)]


@pytest.fixture()
def seed_module(tmp_path, monkeypatch):
    module = _load_seed_module()
    monkeypatch.setattr(module, "league_seasons", lambda: ("S",))
    monkeypatch.setattr(module, "build", lambda season: (_rows(), 30))
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "seed.duckdb")
    monkeypatch.setattr(store, "LOCK_PATH", tmp_path / ".write.lock")
    store.warehouse_tables_cache_clear()
    store.warehouse_pool_clear()
    return module


def test_seed_main_materializes_thirty_team_rows(seed_module, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["build_team_four_factors.py", "S"])
    seed_module.main()
    con = store.connect(read_only=True)
    try:
        names = [d[0] for d in con.execute(
            "SELECT * FROM silver_four_factors_team LIMIT 0").description]
        (n,) = con.execute(
            "SELECT COUNT(*) FROM silver_four_factors_team "
            "WHERE _season = 'S'").fetchone()
    finally:
        con.close()
    assert n == 30
    for column in COLUMNS:
        assert column in names
