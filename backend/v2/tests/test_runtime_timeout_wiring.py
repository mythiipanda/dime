from v2.runtime.assembly import build_runtime

def test_assembled_runtime_carries_configured_timeouts():
    runtime, _ledger = build_runtime(
        provider="openrouter",
        model_name="fixture-probe",
        run_id="timeout-probe",
        run_timeout_s=111.0,
        node_timeout_s=22.0,
    )
    assert runtime._run_timeout_s == 111.0
    assert runtime._executor._node_timeout_s == 22.0

def test_assembled_runtime_defaults_leave_timeouts_off():
    runtime, _ledger = build_runtime(
        provider="openrouter",
        model_name="fixture-probe",
        run_id="timeout-default-probe",
    )
    assert runtime._run_timeout_s is None
    assert runtime._executor._node_timeout_s is None
