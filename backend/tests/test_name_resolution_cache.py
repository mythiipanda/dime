import pytest

from app.tools import _core as core_mod
from app.tools._core import coerce_player_id, score_player_candidates

EXPECTED = {
    "LeBron James": 2544,
    "Stephen Curry": 201939,
    "Nikola Jokic": 203999,
    "Luka Doncic": 1629029,
    "SGA": 1628983,
}


def test_index_built_once():
    assert len(core_mod._PLAYER_ROWS) > 1000
    assert len(core_mod._PLAYER_ROWS) == len(core_mod._PLAYER_NORMS)


def test_resolution_stable_and_cached():
    coerce_player_id.cache_clear()
    first = {name: coerce_player_id(name) for name in EXPECTED}
    assert first == EXPECTED
    misses_after_first = coerce_player_id.cache_info().misses
    assert misses_after_first >= len(EXPECTED)
    second = {name: coerce_player_id(name) for name in EXPECTED}
    assert second == first
    info = coerce_player_id.cache_info()
    assert info.hits >= len(EXPECTED)


def test_cache_key_is_stripped_lowercase():
    coerce_player_id.cache_clear()
    base = coerce_player_id("LeBron James")
    assert coerce_player_id("lebron james") == base
    assert coerce_player_id("  LEBRON JAMES  ") == base
    assert coerce_player_id("sga") == coerce_player_id("SGA")
    assert coerce_player_id.cache_info().hits >= 3


def test_unknown_names_still_miss():
    coerce_player_id.cache_clear()
    before = coerce_player_id.cache_info()
    with pytest.raises(ValueError, match="unknown player"):
        coerce_player_id("Zzz Not A Player Xyz")
    with pytest.raises(ValueError, match="unknown player"):
        coerce_player_id("Zzz Not A Player Xyz")
    after = coerce_player_id.cache_info()
    assert after.currsize == before.currsize
    ranked = score_player_candidates("Zzz Not A Player Xyz")
    assert not ranked or ranked[0][0] < 0.8
