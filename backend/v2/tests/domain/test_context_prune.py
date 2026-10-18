from __future__ import annotations

from datetime import UTC, datetime

import pytest

from v2.contracts import ConversationTurn, EvidenceEnvelope

def _turns(count: int, *, width: int = 120) -> tuple[ConversationTurn, ...]:
    body = " ".join(f"segment-{index}" for index in range(width))
    return tuple(
        ConversationTurn(
            role="user" if index % 2 == 0 else "assistant",
            content=f"turn {index} {body}",
        )
        for index in range(count)
    )

def _envelope(rows) -> EvidenceEnvelope:
    return EvidenceEnvelope(
        evidence_id="evidence:board",
        capability="board",
        source="fixture",
        observed_at=datetime(2026, 9, 14, tzinfo=UTC),
        season="2024-25",
        rows=rows,
        units={"PTS": "count"},
        metric_definitions={"PTS": "points", "REB": "rebounds"},
    )

def _board_rows(count: int) -> list[dict]:
    return [
        {"ID": index, "PTS": 10 + index, "REB": 5}
        for index in range(count)
    ]

def _real_tokens(text: str) -> int:
    tiktoken = pytest.importorskip("tiktoken")
    return len(tiktoken.get_encoding("cl100k_base").encode(text))

def test_long_session_prunes_row_payloads_before_aggregates():
    from v2.domain.evidence import prune_session_context

    rows = _board_rows(60)
    envelope = _envelope(rows)
    cited = {"evidence:board": {"rows[0].PTS": 10}}
    turns = _turns(8)
    before = _real_tokens(envelope.model_dump_json())
    pruned_turns, pruned_map, report = prune_session_context(
        turns, {"evidence:board": envelope}, cited, token_budget=10**9)
    after = _real_tokens(pruned_map["evidence:board"].model_dump_json())
    assert after < before
    assert report.levels_applied[0] == "rows"
    assert report.dropped_rows == 59
    assert pruned_map["evidence:board"].rows[0] == {"ID": 0, "PTS": 10, "REB": 5}
    assert pruned_map["evidence:board"].units == {"PTS": "count"}
    assert pruned_map["evidence:board"].evidence_id == "evidence:board"

def test_citations_survive_every_prune_level():
    from v2.domain.evidence import (
        count_tokens, prune_session_context, resolve_selector)

    rows = _board_rows(40)
    envelope = _envelope(rows)
    cited = {
        "evidence:board": {
            "rows[0].PTS": 10,
            "rows[39].PTS": 49,
        }
    }
    turns = _turns(8)
    pruned_turns, pruned_map, report = prune_session_context(
        turns, {"evidence:board": envelope}, cited,
        token_budget=count_tokens(turns[-1].content) + 500)
    assert set(report.levels_applied) == {"rows", "tool_meta", "turn_prose"}
    for selector, value in cited["evidence:board"].items():
        assert resolve_selector(pruned_map["evidence:board"].rows, selector) == value
    assert len(pruned_turns) == 8
    assert pruned_turns[-1] == turns[-1]

def test_prune_refuses_when_citation_would_orphan():
    from v2.domain.evidence import CitationOrphanError, prune_session_context

    envelope = _envelope([{"ID": 0, "PTS": 10}])
    cited = {"evidence:board": {"rows[5].PTS": 99}}
    with pytest.raises(CitationOrphanError):
        prune_session_context(
            _turns(2), {"evidence:board": envelope}, cited, token_budget=10**9)

def test_token_counts_drop_while_answer_completeness_unchanged():
    from v2.domain.evidence import prune_session_context
    from v2.runtime.verifier import verify_mechanical
    from v2.contracts import (
        Claim, ClaimKind, DraftReport, EvidenceOutputBinding, TaskSpec,
    )

    rows = _board_rows(60)
    envelope = _envelope(rows)
    cited = {"evidence:board": {"rows[0].PTS": 10}}
    task = TaskSpec(goal="goal", mode="quick", deliverable="pts")
    claim = Claim(
        text="Board shows 10 points.",
        kind=ClaimKind.OBSERVED,
        evidence_ids=["evidence:board"],
        output_bindings=[EvidenceOutputBinding(
            requirement_kind="task",
            requirement_id=None,
            output_id="PTS",
            node_id="board",
            evidence_id="evidence:board",
            selector="rows[0].PTS",
            row_selector="rows[0]",
            value={"kind": "integer", "value": 10},
            subject_entity_type="player",
            subject_entity_id="0",
            subject_selector="rows[0].ID",
            unit={"kind": "declared", "value": "count"},
            domain="board",
        )],
    )
    draft = DraftReport(sections=["Board"], claims=[claim])
    before_report = verify_mechanical(task, draft, [envelope])
    before_supported = [r.supported for r in before_report.claim_results]
    before_tokens = _real_tokens(envelope.model_dump_json())

    turns = _turns(8)
    pruned_turns, pruned_map, report = prune_session_context(
        turns, {"evidence:board": envelope}, cited, token_budget=1200)

    after_report = verify_mechanical(
        task, draft, [pruned_map["evidence:board"]])
    after_supported = [r.supported for r in after_report.claim_results]
    after_tokens = _real_tokens(pruned_map["evidence:board"].model_dump_json())
    assert after_tokens < before_tokens
    assert report.tokens_before > report.tokens_after
    assert after_supported == before_supported == [True]

def _named_envelope(name: str, rows) -> EvidenceEnvelope:
    return _envelope(rows).model_copy(update={"evidence_id": name})

def test_evict_old_evidence_keeps_newest_three_and_protects_citations():
    from v2.domain.evidence import envelope_tokens, evict_old_evidence

    names = [f"evidence:e{index}" for index in range(5)]
    evidence = {name: _named_envelope(name, _board_rows(10)) for name in names}
    cited = {names[0]: {"rows[0].PTS": 10}}
    narrowed, evicted = evict_old_evidence(evidence, cited)

    assert evicted == (names[1],)
    assert narrowed[names[0]] == evidence[names[0]]
    assert narrowed[names[1]].rows == {}
    assert narrowed[names[1]].warnings
    assert envelope_tokens(narrowed[names[1]]) < envelope_tokens(evidence[names[1]])
    for name in names[2:]:
        assert narrowed[name] == evidence[name]

def test_prune_session_evicts_stale_evidence_before_turn_prose():
    from v2.domain.evidence import (
        count_tokens, envelope_tokens, prune_session_context)

    names = [f"evidence:e{index}" for index in range(5)]
    evidence = {name: _named_envelope(name, _board_rows(20)) for name in names}
    turns = _turns(2)
    _, compacted, _ = prune_session_context(
        turns, evidence, {}, token_budget=10**9)
    budget = (sum(count_tokens(turn.content) for turn in turns)
              + sum(envelope_tokens(item) for item in compacted.values()) - 1)

    pruned_turns, pruned_map, report = prune_session_context(
        turns, evidence, {}, token_budget=budget)

    assert "evidence_eviction" in report.levels_applied
    assert "turn_prose" not in report.levels_applied
    assert pruned_turns == turns
    assert pruned_map[names[0]].rows == {}
    assert pruned_map[names[1]].rows == {}
    assert pruned_map[names[0]].warnings
    assert pruned_map[names[4]] == compacted[names[4]]

def test_loop_prunes_context_prose_to_budget_without_network():
    import asyncio

    from v2.contracts import VerificationStatus
    from v2.runtime import PlanExecutor, Runtime
    from v2.runtime.tests.test_loop import (
        Planner, SequenceVerifier, Synthesizer,
    )
    from v2.contracts import RunMode, TaskSpec

    class ContextIntake:
        async def understand(self, request: str, context=()) -> TaskSpec:
            return TaskSpec(goal=request, mode=RunMode.QUICK, deliverable="text")

    instance = Runtime(
        intake=ContextIntake(),
        planner=Planner(),
        executor=PlanExecutor({"fake": __import__(
            "v2.runtime", fromlist=["FakeCapability"]).FakeCapability(
                "fake", {"value": 42})}),
        synthesizer=Synthesizer(),
        mechanical_verifier=SequenceVerifier(VerificationStatus.PASS),
        semantic_verifier=SequenceVerifier(VerificationStatus.PASS),
        context_token_budget=400,
    )
    from v2.domain.evidence import count_tokens

    turns = _turns(8)
    before = sum(count_tokens(turn.content) for turn in turns)
    assert before > 400
    result = asyncio.run(instance.run("answer", context=turns))
    assert result.verification.status == VerificationStatus.PASS
