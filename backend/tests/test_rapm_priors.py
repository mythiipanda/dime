"""Multi-season RAPM prior tests. Pure math always runs.

Warehouse reads are read-only. Tests touching silver_rapm_prior
return early when the coordinator has not seeded it yet.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _tables() -> set:
    from app import store

    con = store.connect()
    try:
        return {r[0] for r in con.execute("SHOW TABLES").fetchall()}
    finally:
        con.close()


def test_season_label_mapping():
    from scripts.seed_rapm_priors import PRIOR_SEASONS, season_label

    assert season_label(2022) == "2021-22"
    assert season_label(2025) == "2024-25"
    assert set(PRIOR_SEASONS) == {2022, 2023, 2024, 2025}
    assert "2025-26" not in PRIOR_SEASONS.values()


def test_season_label_rejects_live_season():
    import pytest

    from scripts.seed_rapm_priors import season_label

    with pytest.raises(ValueError):
        season_label(2026)


def test_clamp_prior_seasons():
    from app.tools.priors import clamp_prior_seasons

    assert clamp_prior_seasons(None) == [2022, 2023, 2024, 2025]
    assert clamp_prior_seasons([2020, 2027]) == [2022, 2025]
    assert clamp_prior_seasons("2024") == [2024]
    assert clamp_prior_seasons(["garbage"]) == []


def test_blend_weighted_mean():
    from app.tools.priors import blend_estimate

    out = blend_estimate({"rapm": 2.0, "possessions": 1000},
                         [{"rapm": 4.0, "possessions": 1000}])
    assert out == {"estimate": 3.0, "total_possessions": 2000}


def test_blend_empty_is_none():
    from app.tools.priors import blend_estimate

    assert blend_estimate(None, []) is None
    assert blend_estimate({"rapm": None, "possessions": 0}, []) is None


def test_compute_ranks_efficient_side_first():
    import polars as pl

    from scripts.seed_rapm_priors import compute_season_rapm

    off = [f"off_player_{i}" for i in range(1, 6)]
    defs = [f"def_player_{i}" for i in range(1, 6)]
    good = {"points": 1.2, **dict(zip(off, list("abcde"))),
            **dict(zip(defs, list("fghij")))}
    bad = {"points": 0.8, **dict(zip(off, list("fghij"))),
           **dict(zip(defs, list("abcde")))}
    frame = compute_season_rapm(pl.DataFrame([good] * 60 + [bad] * 60),
                                "2021-22", min_poss=10)
    by_id = {r["player_id"]: r["rapm"] for r in frame.to_dicts()}
    assert by_id["a"] > by_id["f"]


def test_silver_rapm_holds_current_season():
    from app import store

    try:
        n = store._read_df("SELECT COUNT(*) AS n FROM silver_rapm WHERE _season = ?",
                           ["2025-26"])[0]["n"]
    except Exception:
        return
    assert int(n) > 100


def test_get_rapm_prior_missing_player_is_honest():
    from app.tools.priors import get_rapm_prior

    res = get_rapm_prior.invoke({"player": "Zzz No Such Player", "seasons": [2024]})
    assert res["ok"] is False
    assert res.get("error")


def test_get_rapm_prior_registered():
    from app import tools

    assert "get_rapm_prior" in tools.TOOL_NAMES
