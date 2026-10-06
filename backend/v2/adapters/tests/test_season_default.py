import pytest

def _seed_warehouse_seasons(tmp_path, monkeypatch, seasons):
    import duckdb

    from shared import store
    from shared.tools import _core as core_mod
    from v2.adapters import coverage as coverage_mod

    db = tmp_path / "warehouse.duckdb"
    connection = duckdb.connect(str(db))
    connection.execute(
        "CREATE TABLE silver_boxscores (_season VARCHAR, GAME_ID VARCHAR)")
    for table in (
        "silver_leaders_pts",
        "silver_leaders_reb",
        "silver_leaders_ast",
        "silver_leaders_stl",
        "silver_leaders_blk",
        "silver_leaders_dreb",
        "silver_leaders_fg_pct",
    ):
        connection.execute(
            f"CREATE TABLE {table} (_season VARCHAR, PLAYER VARCHAR)")
    for season in seasons:
        connection.execute(
            "INSERT INTO silver_boxscores VALUES (?, ?)",
            [season, "00200001"])
        for table in (
            "silver_leaders_pts",
            "silver_leaders_reb",
            "silver_leaders_ast",
            "silver_leaders_stl",
            "silver_leaders_blk",
            "silver_leaders_dreb",
            "silver_leaders_fg_pct",
        ):
            connection.execute(
                f"INSERT INTO {table} VALUES (?, ?)", [season, "Sample Player"])
    connection.close()
    monkeypatch.setattr(store, "DB_PATH", db)
    core_mod.last_completed_season_cache_clear()
    coverage_mod.coverage_cache_clear()
    return db

class StubModel:
    def __init__(self, values):
        self.values = iter(values)

    async def generate(self, **call):
        return call["schema"].model_validate(next(self.values))

def _intake(stub):
    from v2.adapters.models import ModelIntake

    return ModelIntake(
        stub, provider="stub", model_name="stub",
        capability_catalog={"qualified_leaders": {}})

@pytest.mark.anyio
async def test_unseasoned_stat_question_pins_warehouse_current(
    tmp_path, monkeypatch,
):
    _seed_warehouse_seasons(tmp_path, monkeypatch, ["2024-25", "2025-26"])
    stub = StubModel([{
        "goal": "season scoring average",
        "mode": "quick",
        "deliverable": "points per game",
        "required_evidence": ["qualified_leaders"],
    }])
    task = await _intake(stub).understand(
        "Who scores the most points per game?")
    assert task.season is not None
    assert task.season.value == "2025-26"
    assert task.season.source == "default"
    assert task.open_questions == []

@pytest.mark.anyio
async def test_this_season_lands_on_current(tmp_path, monkeypatch):
    _seed_warehouse_seasons(tmp_path, monkeypatch, ["2024-25", "2025-26"])
    stub = StubModel([{
        "goal": "season scoring average",
        "mode": "quick",
        "deliverable": "points per game",
        "season": {
            "value": "2025-26", "source": "resolved", "confidence": 0.9,
        },
        "required_evidence": ["qualified_leaders"],
    }])
    task = await _intake(stub).understand(
        "Who scores the most points per game this season?")
    assert task.season.value == "2025-26"
    assert task.open_questions == []

@pytest.mark.anyio
async def test_named_prior_season_is_preserved(tmp_path, monkeypatch):
    _seed_warehouse_seasons(tmp_path, monkeypatch, ["2024-25", "2025-26"])
    stub = StubModel([{
        "goal": "prior season scoring average",
        "mode": "quick",
        "deliverable": "points per game",
        "season": {
            "value": "2024-25", "source": "user", "confidence": 1.0,
        },
        "required_evidence": ["qualified_leaders"],
    }])
    task = await _intake(stub).understand(
        "Who scored the most points per game in 2024-25?")
    assert task.season.value == "2024-25"
    assert task.season.source == "user"
    assert task.open_questions == []

def test_wrong_season_evidence_is_rejected():
    from datetime import UTC, date, datetime

    from v2.contracts import (
        Claim,
        ClaimKind,
        DraftReport,
        EntityRef,
        EvidenceEnvelope,
        RunMode,
        SeasonRef,
        TaskSpec,
    )
    from v2.runtime.verifier import verify_mechanical

    task = TaskSpec(
        goal="Rank Boston", mode=RunMode.QUICK, deliverable="answer",
        entities=[EntityRef(
            id="BOS", type="team", display_name="Capital City Stars")],
        season=SeasonRef(value="2025-26", source="user", confidence=1),
        as_of=date(2026, 4, 15))
    envelope = EvidenceEnvelope(
        evidence_id="standings", capability="standings",
        source="warehouse:standings",
        observed_at=datetime(2026, 4, 15, 12, tzinfo=UTC),
        season="2024-25", as_of=date(2026, 4, 15),
        entities=[EntityRef(
            id="BOS", type="team", display_name="Capital City Stars")],
        rows=[{"TEAM": "Capital City Stars", "W": 61}],
        units={"W": "count"})
    claim = Claim(
        text="The Capital City Stars had 61 wins in 2025-26.",
        kind=ClaimKind.OBSERVED, evidence_ids=["standings"])
    reasons = verify_mechanical(
        task, DraftReport(sections=[claim.text], claims=[claim]),
        [envelope]).claim_results[0].reasons
    assert any("does not match task season" in reason for reason in reasons)

def test_publication_refuses_wrong_season_evidence():
    from datetime import UTC, datetime

    import pytest

    from v2.contracts import (
        DraftReport,
        EntityRef,
        EvidenceEnvelope,
        Plan,
        PlanNode,
        RunMode,
        SeasonRef,
        TaskSpec,
        VerificationReport,
        VerificationStatus,
    )
    from v2.runtime.models import ExecutionResult, RuntimeResult

    task = TaskSpec(
        goal="Rank Boston", mode=RunMode.QUICK, deliverable="answer",
        entities=[EntityRef(
            id="BOS", type="team", display_name="Capital City Stars")],
        season=SeasonRef(value="2025-26", source="user", confidence=1))
    plan = Plan(nodes=[PlanNode(
        id="board", description="standings board",
        capability_hints=["standings"], status="complete")])
    envelope = EvidenceEnvelope(
        evidence_id="evidence:board", capability="standings",
        source="warehouse:standings",
        observed_at=datetime(2026, 4, 15, 12, tzinfo=UTC),
        season="2024-25",
        entities=[EntityRef(
            id="BOS", type="team", display_name="Capital City Stars")],
        rows=[{"TEAM": "Capital City Stars", "W": 61}],
        units={"W": "count"})
    execution = ExecutionResult(
        plan=plan,
        evidence_by_node={"board": envelope},
        attempts={"board": 1})
    draft = DraftReport(sections=[], claims=[])
    verification = VerificationReport(
        status=VerificationStatus.PASS, claim_results=[])
    with pytest.raises(ValueError, match="does not match task season"):
        RuntimeResult(
            task=task, execution=execution, draft=draft,
            verification=verification, verified_claims=[], gaps=[])
