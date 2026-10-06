from __future__ import annotations

import json

def _parse_status_texts(text: str) -> list[str]:
    out: list[str] = []
    for chunk in text.split("\n\n"):
        if not chunk.startswith("event: status\n"):
            continue
        payload = chunk.split("data: ", 1)[1]
        out.append(json.loads(payload)["text"])
    return out

def test_leaders_status_stream_narrates_subject_without_plumbing(monkeypatch, tmp_path) -> None:
    from types import SimpleNamespace
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from v2 import contracts
    from v2.api import routes
    from v2.projects.service import ProjectStore
    from v2.runtime.ledger import RunLedger

    task = contracts.TaskSpec(
        goal="Who led the league in assists",
        mode="quick",
        deliverable="answer",
        season=contracts.SeasonRef(value="2024-25", source="user", confidence=1.0),
        requirements=[
            contracts.EvidenceRequirement(
                id="leaders",
                description="Assists leader",
                capability_options=["qualified_leaders"],
                capability_arguments={"stat_category": "AST", "season": "2024-25"},
            )
        ],
    )
    result = SimpleNamespace(
        task=task,
        output_statuses=[],
        draft=SimpleNamespace(calculations=[]),
        execution=SimpleNamespace(evidence=[]),
        verification=SimpleNamespace(status=SimpleNamespace(value="pass")),
        verified_claims=[],
        gaps=[],
        structural_flags=[],
    )

    class Runtime:
        async def run(self, *a, **k):
            return result

    def build(**kwargs):
        return Runtime(), RunLedger(kwargs["run_id"])

    monkeypatch.setenv("DIME_RUNTIME_V2", "on")
    monkeypatch.setenv("DIME_PROJECT_STORE", str(tmp_path / "p.sqlite"))
    monkeypatch.setattr("shared.providers.resolve_model_id", lambda value: ("openrouter", "fixture"))
    monkeypatch.setattr("v2.runtime.assembly.build_runtime", build)
    monkeypatch.setattr(routes, "_PROJECTS", ProjectStore(tmp_path / "p.sqlite"))
    app = FastAPI()
    app.include_router(routes.router, prefix="/api")
    text = TestClient(app).post("/api/v2/chat/stream", json={"q": "Who led the league in assists"}).text
    statuses = _parse_status_texts(text)
    assert 1 <= len(statuses) <= 4
    joined = " ".join(statuses).lower()
    assert "assist" in joined
    forbidden = [
        "qualified_leaders",
        "get_leaders",
        "internal-node",
        "internal-evidence",
        "evidence_id",
        "node_id",
        "capability",
        "tool_call",
        "tool_result",
        "synthesizing",
        "admission",
        "binding",
        "gaps",
        "partial",
        "{",
        "}",
    ]
    for marker in forbidden:
        assert marker not in joined

def test_status_lines_for_phrase_keeps_base_without_doubling() -> None:
    from v2 import contracts
    from v2.api import routes

    task = contracts.TaskSpec(
        goal="Q6 check",
        mode="quick",
        deliverable="answer",
        season=contracts.SeasonRef(value="2024-25", source="user", confidence=1.0),
        requirements=[
            contracts.EvidenceRequirement(
                id="r1",
                description="Points for the starters last season",
                capability_options=["qualified_leaders"],
                capability_arguments={},
            )
        ],
    )
    lines = routes._status_lines(task)
    assert lines == [
        "Checking Points for the starters last for 2024-25…",
        "Comparing Points for the starters last across 2024-25…",
        "Verifying every number…",
    ]
    assert "for for" not in " ".join(lines).lower()
