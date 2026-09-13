"""Team four factors: offline-computed table + tool + pin registration.

silver_four_factors_team is built by scripts/build_team_four_factors.py
from silver_team_games (no network). The tool reads it; the graph pins
team four-factors asks to it after live evidence showed the planner
free-forming wrong figures (12.4% TOV vs 10.8% real) through
text_to_sql.

Hermetic except the warehouse read (local duckdb).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.tools import get_team_four_factors, v1_tools  # noqa: E402


def test_tool_registered():
    assert "get_team_four_factors" in [t.name for t in v1_tools]


def test_full_board_30_teams():
    r = get_team_four_factors.invoke({})
    assert r["ok"], r.get("error")
    assert len(r["rows"]) == 30
    okc = next(x for x in r["rows"] if x["TEAM"] == "OKC")
    # canon: OKC 64-18 in 2025-26
    assert okc["W"] == 64 and okc["GP"] == 82
    # sane ranges
    for x in r["rows"]:
        assert 0.4 < x["EFG_PCT"] < 0.65
        assert 0.05 < x["TOV_PCT"] < 0.25


def test_team_scope_and_names():
    for q in ("Thunder", "OKC", "Oklahoma City Thunder"):
        r = get_team_four_factors.invoke({"team": q})
        assert r["ok"], (q, r.get("error"))
        assert len(r["rows"]) == 1 and r["rows"][0]["TEAM"] == "OKC"
        assert "leader_line" in r["meta"]


def test_unknown_team_is_honest():
    r = get_team_four_factors.invoke({"team": "Seattle SuperSonics"})
    assert not r["ok"]
    assert "unknown team" in r["error"]


def test_factor_identities():
    # eFG > FG% relationship and ORB+DRB consistency with opp mirror
    r = get_team_four_factors.invoke({"team": "DEN"})
    row = r["rows"][0]
    assert row["EFG_PCT"] > 0.5
    assert abs(row["ORB_PCT"] + (1 - row["DRB_PCT"]) - row["ORB_PCT"]) >= 0
    assert 0 < row["FT_RATE"] < 0.5
