from __future__ import annotations

from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent.parent
WAREHOUSE = BACKEND / "data" / "warehouse.duckdb"

pytestmark = pytest.mark.skipif(
    not WAREHOUSE.exists(),
    reason=f"the warehouse is absent at {WAREHOUSE}")


def test_last_completed_season_is_calendar_bounded() -> None:
    from shared import store
    from shared.tools._core import (
        calendar_last_completed_season,
        last_completed_season,
        last_completed_season_cache_clear,
    )

    last_completed_season_cache_clear()
    cal = calendar_last_completed_season()
    covered = sorted(
        {season for table in store._SEASON_TABLES
         for season in store.seasons_with_data(table)})
    finished = [season for season in covered if cal is None or season <= cal]

    assert last_completed_season() == (finished[-1] if finished else covered[-1])


def test_an_in_progress_season_is_not_reported_as_completed() -> None:
    from shared import store
    from shared.tools._core import (
        calendar_last_completed_season,
        last_completed_season,
        last_completed_season_cache_clear,
    )

    cal = calendar_last_completed_season()
    covered = {
        season for table in store._SEASON_TABLES
        for season in store.seasons_with_data(table)}
    if cal is None or not any(season > cal for season in covered):
        pytest.skip("warehouse holds no in-progress season to bound against")

    last_completed_season_cache_clear()
    assert last_completed_season() == cal


def test_completed_season_union_never_outpaces_registry_tables() -> None:
    from shared import store
    from shared.tools._core import last_completed_season, last_completed_season_cache_clear

    last_completed_season_cache_clear()
    newest_by_table = [
        seasons[-1]
        for table in store._SEASON_TABLES
        if (seasons := store.seasons_with_data(table))
    ]
    union = store.completed_seasons_across_tables()

    assert union
    assert union[-1] <= max(newest_by_table)
    assert last_completed_season() in union


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


def test_clamp_accepts_the_in_progress_season_when_data_exists() -> None:
    from shared import store
    from shared.tools._core import (
        calendar_last_completed_season, clamp_season, warehouse_max_season)

    data_max = warehouse_max_season()
    if data_max is None:
        pytest.skip("no warehouse seasons")
    cal = calendar_last_completed_season()
    assert clamp_season(data_max) == data_max
    if cal is not None and data_max > cal:
        assert clamp_season(data_max) == data_max


def test_clamp_rejects_seasons_beyond_the_warehouse() -> None:
    from shared.tools._core import InvalidSeasonError, clamp_season, warehouse_max_season

    data_max = warehouse_max_season()
    if data_max is None:
        pytest.skip("no warehouse seasons")
    start = int(data_max[:4]) + 1
    future = f"{start}-{(start + 1) % 100:02d}"
    with pytest.raises(InvalidSeasonError):
        clamp_season(future)


def test_default_resolution_never_errors() -> None:
    from shared.tools._core import clamp_season, resolve_season

    resolved = resolve_season(None, "silver_scoreboard")
    assert clamp_season(resolved) == resolved


def test_coverage_error_message_matches_data_presence() -> None:
    from shared import store
    from shared.tools._core import season_error_message, warehouse_max_season

    data_max = warehouse_max_season()
    if data_max is None:
        pytest.skip("no warehouse seasons")
    start = int(data_max[:4]) + 1
    future = f"{start}-{(start + 1) % 100:02d}"
    message = season_error_message(future, nearest=data_max)
    assert data_max in message
    assert "through" in message
