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


@pytest.fixture
def anyio_backend():
    return "asyncio"


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
async def test_runtime_request_reaches_public_answer_with_typed_summary_and_calculation(
    monkeypatch, tmp_path,
):
    import json

    import httpx
    from fastapi import FastAPI

    from v2.adapters import coverage
    from v2.api import routes
    from v2.projects.service import ProjectStore
    from v2.runtime import Runtime
    from v2.runtime import assembly

    request = (
        "For the Boston Celtics, summarize the 2024-25 regular season: "
        "games, wins, losses, total points, and points per game."
    )
    outputs = [
        "GAMES", "WINS", "LOSSES", "TOTAL_POINTS", "POINTS_PER_GAME",
    ]
    warehouse = _WarehouseFixture(_game_rows())
    _patch_fixture_warehouse(monkeypatch, warehouse)
    monkeypatch.setattr(team_tools, "_abbrev", lambda _team: "BOS")
    monkeypatch.setattr(coverage, "table_seasons", lambda _table: frozenset({_SEASON}))
    monkeypatch.setattr(assembly, "declared_schema_for", lambda _capability: None)
    monkeypatch.setattr(
        "shared.providers.resolve_model_id",
        lambda _model: ("openrouter", "fixture-model"),
    )
    monkeypatch.setenv("DIME_RUNTIME_V2", "on")
    monkeypatch.setenv("DIME_V2_LEDGER_DIR", str(tmp_path / "ledger"))
    monkeypatch.setenv("DIME_V2_ACTIVITY_DIR", str(tmp_path / "activity"))
    monkeypatch.setenv("DIME_V2_CHECKPOINT_DIR", str(tmp_path / "checkpoints"))
    monkeypatch.setenv("DIME_REVISION", "fixture-runtime")
    monkeypatch.setattr(routes, "_PROJECTS", ProjectStore(tmp_path / "projects.sqlite"))

    class DeterministicStructuredModel:
        instances = []

        def __init__(self, _provider, _model_name, **_kwargs):
            self.calls = []
            self.instances.append(self)

        async def generate(self, *, schema, prompt, payload, envelope, **_kwargs):
            self.calls.append({
                "route": envelope.route,
                "payload": payload,
                "prompt": prompt,
            })
            if envelope.route == "intake":
                return schema.model_validate({
                    "goal": request,
                    "mode": "quick",
                    "deliverable": "Available regular-season team summary",
                    "metric_ids": outputs,
                    "requested_outputs": outputs,
                    "entities": [{
                        "id": str(_TEAM_ID),
                        "type": "team",
                        "display_name": "Boston Celtics",
                    }],
                    "season": {
                        "value": _SEASON, "source": "user", "confidence": 1.0,
                    },
                    "period_scope": "playoffs",
                    "period_scope_source": "explicit_request",
                    "required_evidence": ["team_season_summary"],
                    "calculation_requirements": [{
                        "id": "ppg_arithmetic",
                        "description": "Calculate points per game as total points divided by games",
                        "requested_outputs": ["POINTS_PER_GAME"],
                    }],
                })
            if envelope.route == "planner":
                return schema.model_validate({"nodes": [{
                    "id": "team_summary",
                    "description": "Summarize the selected team and season",
                    "depends_on": [],
                    "capability": "team_season_summary",
                    "covers_requirement_ids": [],
                    "arguments": {"entries": [
                        {"key": "team_id", "kind": "string",
                         "string_value": "Boston Celtics"},
                        {"key": "season", "kind": "string",
                         "string_value": _SEASON},
                        {"key": "period_scope", "kind": "string",
                         "string_value": "regular_season"},
                    ]},
                    "max_attempts": 1,
                    "status": "pending",
                }]})
            if envelope.route == "synthesizer":
                summaries = [
                    item for item in payload["evidence"]
                    if item.get("capability") == "team_season_summary"
                ]
                assert summaries, payload["evidence"]
                summary = summaries[0]
                assert summary["season"] == _SEASON
                assert summary["source_identity"]["kind"] == "warehouse"
                assert summary["source_identity"]["warehouse_id"] == (
                    "configured-runtime")
                assert "completeness is unverified" in summary["coverage"]
                assert any(
                    entity["type"] == "team"
                    and entity["id"] == str(_TEAM_ID)
                    for entity in summary["entities"]
                )
                evidence_id = summary["evidence_id"]
                row = summary["rows"][0]
                columns = {
                    "GAMES": "GAMES", "WINS": "WINS", "LOSSES": "LOSSES",
                    "TOTAL_POINTS": "PTS", "POINTS_PER_GAME": "PPG",
                }
                units = {
                    "GAMES": "count", "WINS": "count", "LOSSES": "count",
                    "TOTAL_POINTS": "points", "POINTS_PER_GAME": "per_game",
                }
                bindings = []
                for output_id, column in columns.items():
                    value = row[column]
                    bindings.append({
                        "requirement_kind": "task",
                        "output_id": output_id,
                        "node_id": "team_summary",
                        "evidence_id": evidence_id,
                        "selector": f"rows[0].{column}",
                        "row_selector": "rows[0]",
                        "value": {
                            "kind": "float" if output_id == "POINTS_PER_GAME" else "integer",
                            "value": value,
                        },
                        "subject_entity_type": "team",
                        "subject_entity_id": str(_TEAM_ID),
                        "subject_selector": "rows[0].TEAM_ID",
                        "unit": {"kind": "declared", "value": units[output_id]},
                        "domain": "team_season_summary",
                    })
                bindings.append({
                    "requirement_kind": "calculation",
                    "requirement_id": "ppg_arithmetic",
                    "output_id": "POINTS_PER_GAME",
                    "calculation_id": "ppg_from_points_and_games",
                })
                ppg = Decimal(str(row["PTS"])) / Decimal(str(row["GAMES"]))
                text = (
                    "Boston Celtics had "
                    f"{row['GAMES']} available 2024-25 regular-season games, "
                    f"with {row['WINS']} wins and {row['LOSSES']} losses and "
                    f"{row['PTS']:,} total points. Points per game is total "
                    f"points divided by games: {row['PTS']:,} / "
                    f"{row['GAMES']} = {row['PPG']:g}. "
                    "Season completeness is unverified."
                )
                return schema.model_validate({
                    "sections": ["Available team summary"],
                    "claims": [{
                        "text": text,
                        "kind": "derived",
                        "evidence_ids": [evidence_id],
                        "calculation_id": "ppg_from_points_and_games",
                        "output_bindings": bindings,
                    }],
                    "calculations": [{
                        "calculation_id": "ppg_from_points_and_games",
                        "requirement_id": "ppg_arithmetic",
                        "operation": "divide",
                        "inputs": [
                            {"evidence_id": evidence_id, "path": "rows[0].PTS"},
                            {"evidence_id": evidence_id, "path": "rows[0].GAMES"},
                        ],
                        "result": str(ppg),
                        "unit": "per_game",
                    }],
                })
            if envelope.route == "semantic_verifier":
                draft = payload["draft"]
                return schema.model_validate({
                    "status": "pass",
                    "claim_results": [
                        {"claim_index": index, "supported": True}
                        for index, _claim in enumerate(draft["claims"])
                    ],
                })
            raise AssertionError(f"unexpected model route: {envelope.route}")

    monkeypatch.setattr(
        assembly, "ProviderStructuredModel", DeterministicStructuredModel)
    original_build_runtime = assembly.build_runtime
    built = {}

    def capture_runtime(**kwargs):
        runtime, ledger = original_build_runtime(**kwargs)
        built["runtime"] = runtime
        built["ledger"] = ledger
        return runtime, ledger

    monkeypatch.setattr(assembly, "build_runtime", capture_runtime)
    app = FastAPI()
    app.include_router(routes.router, prefix="/api")
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver",
    ) as client:
        response = await client.post("/api/v2/chat/stream", json={"q": request})

    assert response.status_code == 200
    assert isinstance(built["runtime"], Runtime)
    model = DeterministicStructuredModel.instances[-1]
    assert [call["route"] for call in model.calls] == [
        "intake", "planner", "synthesizer", "semantic_verifier",
    ]
    assert model.calls[0]["payload"]["period_scope_hint"] == "regular_season"
    assert model.calls[1]["payload"]["task"]["period_scope"] == "regular_season"
    assert model.calls[1]["payload"]["task"]["season"]["value"] == _SEASON
    assert warehouse.read_query is not None
    assert "g.season_type = 'regular-season'" in warehouse.read_query
    assert warehouse.read_parameters[0] == _SEASON
    assert warehouse.read_parameters[3] == _TEAM_ID
    assert warehouse.read_parameters[4] == "BOS"

    def event_data(name):
        payloads = [
            chunk.split("data: ", 1)[1]
            for chunk in response.text.split("\n\n")
            if chunk.startswith(f"event: {name}\n")
        ]
        assert payloads, f"missing {name} event"
        return json.loads(payloads[-1])

    custom = event_data("custom_data")
    final = event_data("final_answer")
    expected_values = {
        "GAMES": 37,
        "WINS": 24,
        "LOSSES": 13,
        "TOTAL_POINTS": 3996,
        "POINTS_PER_GAME": 108.0,
    }
    evidence_rows = [row for row in custom["tables"] if "value" in row]
    assert {row["output_id"] for row in evidence_rows} == set(outputs)
    assert {row["output_id"]: row["value"] for row in evidence_rows} == {
        "GAMES": "37", "WINS": "24", "LOSSES": "13",
        "TOTAL_POINTS": "3996", "POINTS_PER_GAME": "108.0",
    }
    assert {row["output_id"]: row["unit"] for row in evidence_rows} == {
        "GAMES": "count", "WINS": "count", "LOSSES": "count",
        "TOTAL_POINTS": "points", "POINTS_PER_GAME": "per_game",
    }
    assert all(row["subject_id"] == str(_TEAM_ID)
               for row in evidence_rows)
    assert all(row["provenance"] == {
        "capability": "team_season_summary",
        "origin": "warehouse",
        "warehouse_id": "configured-runtime",
        "season": _SEASON,
        "as_of": None,
        "live_sources": [],
    } for row in evidence_rows)
    calculation_rows = [
        row for row in custom["tables"] if "input_value" in row]
    assert [(row["input_value"], row["output_id"])
            for row in calculation_rows] == [
        ("3996", "POINTS_PER_GAME"), ("37", "POINTS_PER_GAME"),
    ]
    assert custom["unverified_numbers"] == []
    task_statuses = {
        row["output_id"]: row["status"]
        for row in final["carry"]["output_statuses"]
        if row["requirement_kind"] == "task"
    }
    assert task_statuses == {output_id: "complete" for output_id in outputs}
    calculation_statuses = [
        row for row in final["carry"]["output_statuses"]
        if row["requirement_kind"] == "calculation"
    ]
    assert any(
        row["requirement_kind"] == "calculation"
        and row["requirement_id"] == "ppg_arithmetic"
        and row["output_id"] == "POINTS_PER_GAME"
        and row["status"] == "complete"
        and row["value"] == "108"
        for row in calculation_statuses
    ), [(row.get("requirement_id"), row.get("status"), row.get("value"),
         row.get("unit")) for row in calculation_statuses]
    assert final["carry"]["verification"] == "pass", {
        "verified_claims": final["carry"]["verified_claims"],
        "gaps": final["carry"]["gaps"],
        "statuses": final["carry"]["output_statuses"],
    }
    assert "3,996 / 37 = 108" in final["text"]
    assert "completeness is unverified" in final["text"]


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
