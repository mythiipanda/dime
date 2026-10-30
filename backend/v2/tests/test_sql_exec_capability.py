import json
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND))

WAREHOUSE = BACKEND / "data" / "warehouse.duckdb"

pytestmark = pytest.mark.skipif(
    not WAREHOUSE.exists(),
    reason=f"the warehouse is absent at {WAREHOUSE}")

YOUNG_SCORERS = (
    "SELECT COUNT(*) AS n FROM silver_hist_player_seasons "
    "WHERE _season = '{season}' AND age <= 23 AND pts >= 20"
)
MOST_WINS = (
    "SELECT team_city, team_name, wins AS n FROM silver_hist_standings "
    "WHERE _season = '{season}' ORDER BY wins DESC LIMIT 1"
)
FIFTY_WIN_COUNT = (
    "SELECT COUNT(*) AS n FROM silver_hist_standings "
    "WHERE _season = '{season}' AND wins >= 50"
)

EXPECTED = {
    ("2023-24", "young"): 9,
    ("2024-25", "young"): 9,
    ("2024-25", "fifty"): 9,
    ("2023-24", "fifty"): 7,
}

@pytest.fixture
def real_warehouse(monkeypatch):
    from shared import store
    from shared.tools import _core
    from v2.adapters import coverage

    connect = store.connect
    monkeypatch.setattr(store, "DB_PATH", WAREHOUSE)
    monkeypatch.setattr(store, "CANONICAL_DB_PATH", WAREHOUSE)
    monkeypatch.setattr(
        store, "connect", lambda read_only=True: connect(read_only=True))
    store.warehouse_tables_cache_clear()
    store.warehouse_pool_clear()
    store.warehouse_identity_cache_clear()
    _core.last_completed_season_cache_clear()
    coverage.coverage_cache_clear()
    yield WAREHOUSE
    store.warehouse_tables_cache_clear()
    store.warehouse_pool_clear()
    store.warehouse_identity_cache_clear()
    _core.last_completed_season_cache_clear()
    coverage.coverage_cache_clear()

@pytest.fixture(autouse=True)
def _open_chat_budget():
    from v2.api import routes

    routes._CHAT_HITS.clear()
    yield
    routes._CHAT_HITS.clear()


def test_the_capability_declares_units_for_every_numeric_output(
        real_warehouse):
    from v2.adapters import call_capability
    from v2.adapters.capabilities import CAPABILITIES

    units = CAPABILITIES["sql_exec"].units
    assert units["n"] == "count"
    assert "count" in CAPABILITIES["sql_exec"].metric_definitions["n"]
    for season in ("2023-24", "2024-25"):
        envelope = call_capability("sql_exec", {
            "sql": YOUNG_SCORERS.format(season=season), "season": season})
        numeric = {
            key for row in envelope.rows for key, value in row.items()
            if isinstance(value, (int, float)) and not isinstance(value, bool)
        }
        assert numeric and numeric <= set(units)
        assert set(envelope.units) <= set(units)

def test_the_names_a_planner_asks_for_resolve_to_a_returned_column():
    from v2.adapters.capabilities import CAPABILITIES, resolve_metric_column

    spec = CAPABILITIES["sql_exec"]
    assert resolve_metric_column(spec, "n") == "n"
    assert resolve_metric_column(spec, "TOTAL_COUNT") == "n"
    assert resolve_metric_column(spec, "WINS") == "wins"
    assert resolve_metric_column(spec, "HOME_RUNS") == "HOME_RUNS"

def test_the_capability_description_separates_a_query_from_a_curated_table():
    from v2.adapters.capabilities import CAPABILITY_DESCRIPTIONS

    description = CAPABILITY_DESCRIPTIONS["sql_exec"]
    assert "Agent-written" in description
    assert "no prebuilt tool" in description
    assert "never" in description and "curated" in description

@pytest.mark.parametrize("season,kind,expected", [
    ("2023-24", "young", 9),
    ("2024-25", "young", 9),
    ("2024-25", "fifty", 9),
    ("2023-24", "fifty", 7),
])
def test_a_question_no_prebuilt_tool_answers_returns_real_cited_rows(
        real_warehouse, season, kind, expected):
    from v2.adapters import call_capability

    template = YOUNG_SCORERS if kind == "young" else FIFTY_WIN_COUNT
    assert EXPECTED[(season, kind)] == expected
    envelope = call_capability("sql_exec", {
        "sql": template.format(season=season), "season": season})
    assert envelope.capability == "sql_exec"
    assert envelope.season == season
    assert envelope.rows == [{"n": expected}]
    assert envelope.units == {"n": "count"}
    assert envelope.source == "v1:sql_exec:warehouse"
    assert "Agent-written SQL" in envelope.coverage
    assert "silver_hist_" in envelope.coverage
    assert envelope.source_identity.kind == "warehouse"

@pytest.mark.parametrize("season", ["2023-24", "2024-25"])
def test_the_most_wins_question_names_the_real_team_and_total(
        real_warehouse, season):
    from v2.adapters import call_capability

    envelope = call_capability("sql_exec", {
        "sql": MOST_WINS.format(season=season), "season": season})
    assert envelope.rows[0]["n"] == (
        64 if season == "2023-24" else 68)
    assert envelope.rows[0]["team_name"] == (
        "Celtics" if season == "2023-24" else "Thunder")

def test_the_query_is_part_of_the_evidence_identity(real_warehouse):
    from v2.adapters import call_capability

    first = call_capability("sql_exec", {
        "sql": YOUNG_SCORERS.format(season="2023-24"), "season": "2023-24"})
    rerun = call_capability("sql_exec", {
        "sql": YOUNG_SCORERS.format(season="2023-24"), "season": "2023-24"})
    other = call_capability("sql_exec", {
        "sql": FIFTY_WIN_COUNT.format(season="2023-24"), "season": "2023-24"})
    assert first.evidence_id == rerun.evidence_id
    assert first.evidence_id != other.evidence_id

@pytest.mark.parametrize("bad,violation", [
    ("DROP TABLE silver_standings", "only SELECT/WITH queries are allowed"),
    ("INSERT INTO silver_standings VALUES ('X', 1, '2025-26')",
     "only SELECT/WITH queries are allowed"),
    ("UPDATE silver_standings SET wins = 99",
     "only SELECT/WITH queries are allowed"),
    ("DELETE FROM silver_standings",
     "only SELECT/WITH queries are allowed"),
    ("SELECT * FROM silver_standings; DELETE FROM silver_standings",
     "stacked statements are not allowed"),
])
def test_a_write_attempt_is_refused_before_execution_naming_the_violation(
        real_warehouse, bad, violation):
    import duckdb

    from v2.adapters import call_capability
    from v2.adapters.core import AdapterError

    before = duckdb.connect(str(WAREHOUSE), read_only=True).execute(
        "SELECT COUNT(*) FROM silver_hist_standings").fetchone()[0]
    with pytest.raises(AdapterError) as excinfo:
        call_capability("sql_exec", {"sql": bad, "season": "2024-25"})
    assert violation in str(excinfo.value)
    assert bad[:60] in str(excinfo.value)
    after = duckdb.connect(str(WAREHOUSE), read_only=True).execute(
        "SELECT COUNT(*) FROM silver_hist_standings").fetchone()[0]
    assert before == after

def test_a_query_outside_the_declared_set_is_refused(real_warehouse):
    from shared.tools.league import _SQL_TABLES
    from v2.adapters import call_capability
    from v2.adapters.core import AdapterError

    bad = "SELECT * FROM silver_award_winners WHERE _season = '2024-25'"
    assert "silver_award_winners" not in set(_SQL_TABLES)
    with pytest.raises(AdapterError) as excinfo:
        call_capability("sql_exec", {"sql": bad, "season": "2024-25"})
    assert "unknown or unavailable tables" in str(excinfo.value)
    assert bad[:60] in str(excinfo.value)

def test_a_query_returning_nothing_fails_loudly_with_the_query_attached(
        real_warehouse):
    from v2.adapters import call_capability
    from v2.adapters.core import AdapterError

    sql = ("SELECT player_name, pts FROM silver_hist_player_seasons "
           "WHERE _season = '2024-25' AND age <= 10 AND pts >= 50")
    with pytest.raises(AdapterError) as excinfo:
        call_capability("sql_exec", {"sql": sql, "season": "2024-25"})
    assert "0 rows" in str(excinfo.value)
    assert sql[:60] in str(excinfo.value)

def test_a_wrong_subject_negative_fails_loudly_end_to_end(real_warehouse):
    from v2.adapters import call_capability
    from v2.adapters.core import AdapterError

    sql = ("SELECT player_name, pts FROM silver_hist_player_seasons "
           "WHERE _season = '2024-25' AND player_name = 'Nobody McNobody'")
    with pytest.raises(AdapterError) as excinfo:
        call_capability("sql_exec", {"sql": sql, "season": "2024-25"})
    assert "0 rows" in str(excinfo.value)
    assert "Nobody McNobody" in str(excinfo.value)


GOLDEN_CALLS = {
    "sql-young-scorers-2324": (
        YOUNG_SCORERS.format(season="2023-24"), "answer"),
    "sql-most-wins-2425": (
        MOST_WINS.format(season="2024-25"), "answer"),
}
