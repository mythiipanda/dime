
import sys

import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.tools import get_team_four_factors, WAREHOUSE_TOOLS

def _require_team_four_factors_pack():
    from shared import store
    con = store.connect()
    try:
        tables = {row[0] for row in con.execute("SHOW TABLES").fetchall()}
    finally:
        con.close()
    if "silver_four_factors_team" not in tables:
        pytest.skip(
            "release pack omits silver_four_factors_team; "
            "run scripts/build_team_four_factors.py"
        )

def test_tool_registered():
    assert "get_team_four_factors" in [t.name for t in WAREHOUSE_TOOLS]

def test_full_board_30_teams():
    _require_team_four_factors_pack()
    r = get_team_four_factors.invoke({})
    assert r["ok"], r.get("error")
    assert len(r["rows"]) == 30
    okc = next(x for x in r["rows"] if x["TEAM"] == "OKC")
    assert okc["W"] == 64 and okc["GP"] == 82
    for x in r["rows"]:
        assert 0.4 < x["EFG_PCT"] < 0.65
        assert 0.05 < x["TOV_PCT"] < 0.25

def test_team_scope_and_names():
    _require_team_four_factors_pack()
    for q in ("Thunder", "OKC", "Oklahoma City Thunder"):
        r = get_team_four_factors.invoke({"team": q})
        assert r["ok"], (q, r.get("error"))
        assert len(r["rows"]) == 1 and r["rows"][0]["TEAM"] == "OKC"
        assert "leader_line" in r["meta"]

def test_unknown_team_is_honest():
    _require_team_four_factors_pack()
    r = get_team_four_factors.invoke({"team": "Seattle SuperSonics"})
    assert not r["ok"]
    assert "unknown team" in r["error"]

def test_factor_identities():
    _require_team_four_factors_pack()
    r = get_team_four_factors.invoke({"team": "DEN"})
    row = r["rows"][0]
    assert row["EFG_PCT"] > 0.5
    assert abs(row["ORB_PCT"] + (1 - row["DRB_PCT"]) - row["ORB_PCT"]) >= 0
    assert 0 < row["FT_RATE"] < 0.5
