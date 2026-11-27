import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "analyst"))

WAREHOUSE = os.path.join(os.path.dirname(__file__), "..", "data", "warehouse.duckdb")
pytestmark = pytest.mark.skipif(
    not os.path.exists(WAREHOUSE) or os.path.getsize(WAREHOUSE) > 200 * 1024 * 1024,
    reason="warehouse fixture unavailable",
)


@pytest.fixture(scope="module")
def dossier():
    from analyst.direct_data import product_scout_dossier

    return product_scout_dossier.invoke({"team": "BOS", "opponent": "NYK", "season": ""})


def test_scout_dossier_shape(dossier):
    assert dossier["ok"] is True
    assert dossier["opponent"]["abbrev"] == "NYK"
    sections = dossier["sections"]
    for key in ("recent_form", "four_factors", "shot_profile", "top_lineups", "injuries", "head_to_head", "rotation"):
        assert key in sections, key


def test_scout_dossier_form_and_factors_populated(dossier):
    sections = dossier["sections"]
    form = sections["recent_form"]["rows"]
    assert form["last10_record"]
    assert form["games"]
    factors = sections["four_factors"]["rows"]
    assert "offense" in factors and "defense" in factors
    assert factors["offense"]["efg_pct"] > 0


def test_scout_dossier_form_rows_are_deduped_real_games(dossier):
    games = dossier["sections"]["recent_form"]["rows"]["games"]
    keys = [(g["date"], g["matchup"]) for g in games]
    assert len(keys) == len(set(keys)), f"duplicate game rows: {keys}"
    for g in games:
        if g["pts"] is not None and g["opp_pts"] is not None:
            assert g["pts"] != g["opp_pts"], f"tie score is impossible: {g}"
            if g["wl"] == "W":
                assert g["pts"] > g["opp_pts"], g
            elif g["wl"] == "L":
                assert g["pts"] < g["opp_pts"], g


def test_scout_dossier_factor_units_are_fractions(dossier):
    factors = dossier["sections"]["four_factors"]["rows"]
    for side in ("offense", "defense"):
        row = factors[side]
        for key in ("efg_pct", "tov_pct", "oreb_pct"):
            value = row.get(key)
            if value is not None:
                assert 0 < value < 1, f"{side}.{key}={value} is not a fraction-scale ratio"


def test_scout_dossier_sections_carry_provenance(dossier):
    for key in ("recent_form", "four_factors", "shot_profile", "top_lineups", "head_to_head"):
        assert dossier["sections"][key].get("source"), key


def test_scout_dossier_registered():
    from analyst.direct_data import internal_catalogue

    assert "product_scout_dossier" in internal_catalogue()


def test_scout_dossier_rejects_missing_args():
    from analyst.direct_data import product_scout_dossier

    out = product_scout_dossier.invoke({"team": "", "opponent": "NYK", "season": ""})
    assert out["ok"] is False
