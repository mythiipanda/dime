from v2.tests.compatibility.harness import ShadowRunner, TurnTrace


def test_shadow_failure_does_not_change_primary_result():
    scenario = {"id": "x", "chain": ["q"], "budget": {"max_tool_calls": 1}}
    runner = ShadowRunner(
        lambda _: [TurnTrace(0.1, 1, (), ())],
        lambda _: [TurnTrace(0.1, 2, (), ())],
    )
    result = runner.run(scenario)
    assert result["primary"].passed
    assert not result["shadow"].passed


def test_eval_trace_projects_from_the_same_runtime_ledger():
    from datetime import UTC, datetime
    from v2.contracts import EvidenceEnvelope
    from v2.runtime.ledger import LedgerKind, RunLedger

    ledger = RunLedger("run")
    ledger.append(LedgerKind.TOOL_CALL, turn_id="turn", step_id="facts",
                  call_id="call", data={"name": "standings", "args": {}})
    evidence = EvidenceEnvelope(
        evidence_id="ev", capability="standings", source="warehouse",
        observed_at=datetime.now(UTC), rows={"wins": 61})
    ledger.append(LedgerKind.TOOL_RESULT, turn_id="turn", step_id="facts",
                  call_id="call", data={"status": "ok",
                                         "evidence": evidence.model_dump(mode="json")})
    trace = TurnTrace.from_ledger(ledger.entries, seconds=.2, text="Boston won 61.")
    assert trace.tool_calls == 1
    assert trace.evidence == (evidence,)
    assert trace.tools[0]["name"] == "standings"
