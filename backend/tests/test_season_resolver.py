from __future__ import annotations

from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent.parent
WAREHOUSE = BACKEND / "data" / "warehouse.duckdb"

pytestmark = pytest.mark.skipif(
    not WAREHOUSE.exists(),
    reason=f"the warehouse is absent at {WAREHOUSE}")


def test_the_current_season_is_the_newest_several_tables_can_answer_for() -> None:
    from shared import store
    from shared.tools._core import (
        last_completed_season,
        last_completed_season_cache_clear,
    )

    last_completed_season_cache_clear()
    newest = max(
        store.seasons_with_data(table)[-1]
        for table in store._SEASON_TABLES
        if store.seasons_with_data(table))

    assert last_completed_season() == newest


def test_the_current_season_is_not_the_one_table_that_lags_the_rest() -> None:
    from shared import store

    lagging = store.seasons_with_data("silver_boxscores")[-1]
    current = store.completed_seasons_across_tables()[-1]

    assert current > lagging


def test_one_absent_season_table_does_not_empty_the_current_season() -> None:
    from shared import store

    union = store.completed_seasons_across_tables()

    assert union
    assert union == sorted(set(union))


def test_an_absent_season_is_unspecified_but_an_empty_string_is_garbage() -> None:
    from shared.tools._core import InvalidSeasonError, clamp_season

    assert clamp_season(None)
    with pytest.raises(InvalidSeasonError):
        clamp_season("")