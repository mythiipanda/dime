from datetime import UTC, datetime
from decimal import Decimal

import pytest

from shared import store
from shared.tools import team as team_tools
from v2.adapters.capabilities import CAPABILITIES, COUNT, PER_GAME
from v2.adapters.core import ToolCapability
from v2.contracts import (
    Claim,
    ClaimSource,
    DraftReport,
    EntityRef,
    EvidenceEnvelope,
    EvidenceOutputBinding,
    PeriodScope,
    PeriodScopeSource,
    Plan,
    PlanNode,
    PlanStatus,
    RunMode,
    SeasonRef,
    TaskSpec,
    VerifiedClaim,
)
from v2.runtime.models import ExecutionResult, admit_verified_claim_bindings

_TEAM_ID = 1610612738
_SEASON = "2024-25"
_OUTPUT_UNITS = {
    "GAMES": COUNT,
    "WINS": COUNT,
    "LOSSES": COUNT,
    "PTS": "points",
    "PPG": PER_GAME,
}


def _game_rows():
    rows = [
        {
            "team_id": _TEAM_ID,
            "game_id": f"regular-{index}",
            "season_type": "regular-season",
            "season": _SEASON,
            "wl": "W" if index % 3 else "L",
            "pts": 90 + index,
        }
        for index in range(37)
    ]
    rows.append({
        "team_id": _TEAM_ID,
        "game_id": "playoff-only",
        "season_type": "playoffs",
        "season": _SEASON,
        "wl": "W",
        "pts": 999,
    })
    return rows


class _Cursor:
    def __init__(self, rows, names=()):
        self._rows = rows
        self.description = [(name,) for name in names]

    def fetchall(self):
        return self._rows


class _WarehouseFixture:
    _columns = {
        "team_id", "team_abbreviation", "game_id", "game_date",
        "matchup", "wl", "pts", "fga", "fta", "season_type",
    }

    def __init__(self, rows):
        self.rows = rows
        self.read_query = None
        self.read_parameters = None

    def execute(self, sql, parameters=None):
        if sql == "SHOW TABLES":
            return _Cursor([("silver_hist_gamelogs",)])
        if sql.startswith("PRAGMA table_info"):
            return _Cursor([(index, name) for index, name
                            in enumerate(sorted(self._columns))])
        self.read_query = sql
        self.read_parameters = parameters
        assert "g.season_type = 'regular-season'" in sql
        assert "g._season = ?" in sql
        assert parameters[0] == _SEASON
        assert parameters[2] == _SEASON
        assert parameters[3] == _TEAM_ID
        selected = [row for row in self.rows
                    if row["season_type"] == "regular-season"]
        names = ("Team_ID", "Game_ID", "WL", "PTS", "_season")
        values = [(
            row["team_id"], row["game_id"], row["wl"], row["pts"],
            row["season"],
        ) for row in selected]
        return _Cursor(values, names)

    def close(self):
        return None


def _task(period_scope=PeriodScope.REGULAR_SEASON, outputs=None):
    outputs = outputs or list(_OUTPUT_UNITS)
    return TaskSpec(
        goal="Summarize this team's regular season.",
        mode=RunMode.QUICK,
        deliverable="Available team season summary",
        metric_ids=list(outputs),
        requested_outputs=list(outputs),
        entities=[EntityRef(
            id=str(_TEAM_ID), type="team", display_name="Boston Celtics")],
        season=SeasonRef(value=_SEASON, source="user", confidence=1.0),
        period_scope=period_scope,
        period_scope_source=PeriodScopeSource.EXPLICIT_REQUEST,
    )


def _resolved_team_evidence():
    entity = EntityRef(
        id=str(_TEAM_ID), type="team", display_name="Boston Celtics")
    return EvidenceEnvelope(
        evidence_id="resolved-team",
        capability="entity_resolution",
        source="fixture:entity-resolution",
        observed_at=datetime.now(UTC),
        rows={"team_id": str(_TEAM_ID)},
        entities=[entity],
    )


def _patch_fixture_warehouse(monkeypatch, warehouse):
    monkeypatch.setattr(store, "connect", lambda *, read_only=False: warehouse)
    monkeypatch.setattr(store, "warehouse_identity", lambda: {
        "warehouse_id": "configured-runtime",
        "warehouse_sha256": "0" * 64,
    })


def _admit_summary_bindings(task, envelope, outputs=None):
    from v2.adapters.capabilities import resolve_metric_column

    outputs = outputs or list(_OUTPUT_UNITS)
    capability = CAPABILITIES["team_season_summary"]
    owner = "team-summary"
    resolver = "team-resolution"
    resolved = _resolved_team_evidence()
    resolver_node = PlanNode(
        id=resolver,
        description="Resolve selected team",
        capability_hints=["entity_resolution"],
        status=PlanStatus.COMPLETE,
    )
    node = PlanNode(
        id=owner,
        description="Available team season summary",
        capability_hints=["team_season_summary"],
        depends_on=[resolver],
        status=PlanStatus.COMPLETE,
    )
    execution = ExecutionResult(
        plan=Plan(nodes=[resolver_node, node]),
        evidence_by_node={resolver: resolved, owner: envelope},
        attempts={resolver: 1, owner: 1},
    )
    row = envelope.rows[0]
    columns = {
        output_id: resolve_metric_column(capability, output_id)
        for output_id in outputs
    }
    values = {output_id: row[columns[output_id]]
              for output_id in outputs}
    bindings = [
        EvidenceOutputBinding(
            requirement_kind="task",
            output_id=output_id,
            node_id=owner,
            evidence_id=envelope.evidence_id,
            selector=f"rows[0].{columns[output_id]}",
            row_selector="rows[0]",
            value={
                "kind": "float" if columns[output_id] == "PPG" else "integer",
                "value": values[output_id],
            },
            subject_entity_type="team",
            subject_entity_id=str(_TEAM_ID),
            subject_selector="rows[0].TEAM_ID",
            unit={"kind": "declared", "value": capability.units[
                columns[output_id]]},
            domain="team_season_summary",
        )
        for output_id in outputs
    ]
    claim = Claim(
        text="The evidence contains the requested team summary.",
        kind="observed",
        evidence_ids=[envelope.evidence_id],
        output_bindings=bindings,
    )
    draft = DraftReport(sections=["Summary"], claims=[claim])
    verified = VerifiedClaim(
        claim_index=0,
        claim=claim,
        evidence_ids=[envelope.evidence_id],
        sources=[ClaimSource(
            evidence_id=envelope.evidence_id,
            source=envelope.source,
            capability=envelope.capability,
            observed_at=envelope.observed_at,
        )],
        output_bindings=bindings,
    )
    return admit_verified_claim_bindings(task, execution, draft, verified)


@pytest.mark.anyio
async def test_full_regular_rows_flow_through_tool_envelope_and_typed_bindings(
    monkeypatch,
):
    warehouse = _WarehouseFixture(_game_rows())
    _patch_fixture_warehouse(monkeypatch, warehouse)
    monkeypatch.setattr(team_tools, "_abbrev", lambda _team: "BOS")
    evidence = _resolved_team_evidence()
    task = _task()
    node = PlanNode(
        id="summary",
        description="Team summary",
        capability_hints=["team_season_summary"],
        arguments={
            "team_id": "WRONG_TEAM",
            "season": "2099-00",
            "period_scope": "all",
        },
    )
    tool = ToolCapability(
        "team_season_summary",
        tools={"get_team_season_summary": team_tools.get_team_season_summary},
    )

    envelope = await tool.execute(node, task, [evidence])

    assert len(_game_rows()) == 38
    assert len(warehouse.read_query) > 0
    assert envelope.season == _SEASON
    assert envelope.source.endswith("warehouse:silver_hist_gamelogs")
    assert envelope.rows == [{
        "TEAM_ID": _TEAM_ID,
        "SEASON": _SEASON,
        "PERIOD_SCOPE": "regular_season",
        "GAMES": 37,
        "WINS": sum(1 for index in range(37) if index % 3),
        "LOSSES": sum(1 for index in range(37) if not index % 3),
        "PTS": sum(90 + index for index in range(37)),
        "PPG": sum(90 + index for index in range(37)) / 37,
    }]
    assert envelope.units == _OUTPUT_UNITS
    assert set(envelope.metric_definitions) >= set(_OUTPUT_UNITS)
    assert envelope.entities[0].id == str(_TEAM_ID)
    assert "completeness is unverified" in envelope.coverage
    assert "available warehouse rows only" in envelope.warnings[0]

    admitted = _admit_summary_bindings(task, envelope)
    assert {item.output_id for item in admitted.output_bindings} == set(_OUTPUT_UNITS)
    assert CAPABILITIES["team_season_summary"].units == _OUTPUT_UNITS


@pytest.mark.anyio
async def test_authored_output_aliases_bind_to_typed_summary_fields(monkeypatch):
    warehouse = _WarehouseFixture(_game_rows())
    _patch_fixture_warehouse(monkeypatch, warehouse)
    monkeypatch.setattr(team_tools, "_abbrev", lambda _team: "BOS")
    evidence = _resolved_team_evidence()
    task = _task()
    node = PlanNode(
        id="summary",
        description="Team summary",
        capability_hints=["team_season_summary"],
        arguments={},
    )
    tool = ToolCapability(
        "team_season_summary",
        tools={"get_team_season_summary": team_tools.get_team_season_summary},
    )
    envelope = await tool.execute(node, task, [evidence])

    for ppg_alias in ("MEAN_PPG", "POINTS_PER_GAME"):
        outputs = ["GAMES", "WINS", "LOSSES", "TOTAL_POINTS", ppg_alias]
        alias_task = _task(outputs=outputs)
        admitted = _admit_summary_bindings(alias_task, envelope, outputs)
        assert {item.output_id for item in admitted.output_bindings} == set(outputs)
        assert CAPABILITIES["team_season_summary"].output_aliases[
            "TOTAL_POINTS"] == "PTS"
        assert CAPABILITIES["team_season_summary"].output_aliases[
            ppg_alias] == "PPG"


@pytest.mark.anyio
@pytest.mark.parametrize("period_scope", ["playoffs", "all", "unspecified"])
async def test_unsupported_period_returns_unavailable_without_source_read(
    monkeypatch, period_scope,
):
    calls = []
    monkeypatch.setattr(
        team_tools, "_hist_team_games",
        lambda *_args: calls.append("read") or _game_rows(),
    )

    result = await team_tools.get_team_season_summary.ainvoke({
        "team_id": _TEAM_ID,
        "season": _SEASON,
        "period_scope": period_scope,
    })

    assert result["ok"] is False
    assert calls == []


@pytest.mark.anyio
@pytest.mark.parametrize("rows", [
    [],
    [{"Game_ID": "missing-team", "_season": _SEASON,
      "WL": "W", "PTS": 100}],
    [{"Team_ID": _TEAM_ID, "Game_ID": "missing-season",
      "WL": "W", "PTS": 100}],
    [{"Team_ID": _TEAM_ID, "_season": _SEASON,
      "WL": "W", "PTS": 100}],
    [{"Team_ID": _TEAM_ID, "Game_ID": "bad-result",
      "_season": _SEASON, "WL": "?", "PTS": 100}],
    [{"Team_ID": _TEAM_ID, "Game_ID": "bad-points",
      "_season": _SEASON, "WL": "W", "PTS": None}],
    [{"Team_ID": _TEAM_ID, "Game_ID": "duplicate",
      "_season": _SEASON, "WL": "W", "PTS": 100},
     {"Team_ID": _TEAM_ID, "Game_ID": "duplicate",
      "_season": _SEASON, "WL": "L", "PTS": 90}],
])
async def test_missing_or_ambiguous_rows_return_unavailable(monkeypatch, rows):
    monkeypatch.setattr(team_tools, "_hist_team_games", lambda *_args: rows)

    result = await team_tools.get_team_season_summary.ainvoke({
        "team_id": _TEAM_ID,
        "season": _SEASON,
        "period_scope": "regular_season",
    })

    assert result["ok"] is False


@pytest.fixture
def anyio_backend():
    return "asyncio"
