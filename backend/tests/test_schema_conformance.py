import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from evals.schema_conformance import (
    SchemaConformanceError,
    ConformanceReport,
    EndpointConfig,
    ProbePlan,
    ProbeResult,
    accepted_constructs,
    _request_kwargs,
    attribute_constructs,
    classify_http_status,
    classify_response,
    collect_constructs,
    is_credential_failure,
    load_plan,
    render_matrix,
    requests_for_model,
    schema_sha256,
    stage_specs,
    unattributed,
)

CONFIG = {
    "budget_requests": 4,
    "endpoints": [{
        "name": "acme",
        "base_url": "https://acme.invalid/v1",
        "key_env": ["ACME_API_KEY"],
        "models": ["acme-small", "acme-large"],
        "strict": True,
        "timeout_s": 5.0,
    }],
}

def _write_config(tmp_path, payload):
    path = tmp_path / "endpoints.json"
    path.write_text(json.dumps(payload))
    return path

def test_load_plan_reads_every_configured_endpoint(tmp_path):
    path = _write_config(tmp_path, CONFIG)
    plan = load_plan(path)
    assert plan.budget == 4
    assert [e.name for e in plan.endpoints] == ["acme"]
    assert plan.endpoints[0].models == ("acme-small", "acme-large")
    assert plan.model_count == 2

def test_load_plan_rejects_missing_base_url(tmp_path):
    payload = {"budget_requests": 2, "endpoints": [
        {"name": "acme", "base_url": "", "models": ["m"]}]}
    try:
        load_plan(_write_config(tmp_path, payload))
    except SchemaConformanceError as exc:
        assert "base_url" in str(exc)
    else:
        raise AssertionError("empty base_url must fail closed")

def test_load_plan_rejects_endpoint_without_models(tmp_path):
    payload = {"budget_requests": 2, "endpoints": [
        {"name": "acme", "base_url": "https://a.invalid/v1", "models": []}]}
    try:
        load_plan(_write_config(tmp_path, payload))
    except SchemaConformanceError as exc:
        assert "model" in str(exc)
    else:
        raise AssertionError("an endpoint with no models must fail closed")

def test_load_plan_rejects_nonpositive_budget(tmp_path):
    payload = {"budget_requests": 0, "endpoints": [
        {"name": "acme", "base_url": "https://a.invalid/v1",
         "models": ["m"]}]}
    try:
        load_plan(_write_config(tmp_path, payload))
    except SchemaConformanceError as exc:
        assert "budget_requests" in str(exc)
    else:
        raise AssertionError("a zero budget must fail closed")

def test_missing_key_reports_absence_and_never_the_value():
    endpoint = EndpointConfig(
        name="acme", base_url="https://acme.invalid/v1",
        key_env=("ACME_API_KEY", "ACME_FALLBACK_API_KEY"),
        models=("m",), strict=True, timeout_s=1.0, thinking_off=False)
    assert endpoint.key_present({}) is False
    assert endpoint.resolve_key({}) is None

def test_environment_reads_a_dotenv_file_without_exporting_it(tmp_path):
    from evals.schema_conformance import environment

    env_file = tmp_path / ".env"
    env_file.write_text(
        "# comment\n"
        "PROBE_PRESENT_KEY=abc123\n"
        "PROBE_EMPTY_KEY=\n"
        'PROBE_QUOTED_KEY="xyz789"\n'
        "not a pair\n")
    env = environment(env_file)
    assert env["PROBE_PRESENT_KEY"] == "abc123"
    assert env["PROBE_EMPTY_KEY"] == ""
    assert env["PROBE_QUOTED_KEY"] == "xyz789"
    assert "not a pair" not in env
    assert "PROBE_PRESENT_KEY" not in __import__("os").environ

def test_environment_prefers_an_already_exported_variable(tmp_path,
                                                          monkeypatch):
    from evals.schema_conformance import environment

    monkeypatch.setenv("PROBE_OVERRIDE_KEY", "from-shell")
    env_file = tmp_path / ".env"
    env_file.write_text("PROBE_OVERRIDE_KEY=from-file\n")
    assert environment(env_file)["PROBE_OVERRIDE_KEY"] == "from-shell"

def test_real_config_reaches_every_required_endpoint_with_a_key():
    from evals.schema_conformance import environment

    plan = load_plan()
    names = {endpoint.name for endpoint in plan.endpoints}
    assert {"gemini", "nvidia", "groq", "openrouter", "mistral"} <= names
    env = environment()
    for endpoint in plan.endpoints:
        assert endpoint.key_present(env), endpoint.name
        assert endpoint.base_url.startswith("https://")

def test_real_config_models_match_the_runtime_allowlists():
    import shared.providers as prov
    from evals.schema_conformance import environment

    plan = load_plan()
    env = environment()
    by_name = {endpoint.name: endpoint for endpoint in plan.endpoints}
    for model in by_name["gemini"].models:
        assert model in prov.GEMINI_ALLOWLIST, model
    for model in by_name["nvidia"].models:
        assert model in prov.NVIDIA_NIM_ALLOWLIST, model
    assert by_name["groq"].models == (prov.GROQ_DEFAULT,)
    for model in by_name["mistral"].models:
        assert prov.is_free_model("mistral", model), model
    for model in by_name["openrouter"].models:
        assert model in prov.OPENROUTER_ALLOWLIST or (
            model == prov.OPENROUTER_AUTO), model
    assert by_name["gemini"].base_url == prov.GEMINI_BASE_URL
    assert by_name["nvidia"].base_url == prov.NVIDIA_NIM_BASE_URL
    del env

def test_real_config_stays_inside_the_sixty_request_budget():
    plan = load_plan()
    assert plan.budget <= 60
    specs = stage_specs()
    total = sum(
        requests_for_model(specs, model, index == 0)
        for endpoint in plan.endpoints
        for index, model in enumerate(endpoint.models))
    assert total <= plan.budget, total

def test_control_probe_runs_once_per_endpoint_not_once_per_model():
    plan = load_plan()
    specs = stage_specs()
    multi = [e for e in plan.endpoints if len(e.models) > 1]
    assert multi, "expected at least one multi-model endpoint"
    for endpoint in multi:
        costs = [
            requests_for_model(specs, model, index == 0)
            for index, model in enumerate(endpoint.models)]
        base = min(costs)
        assert costs[0] == base + 1, endpoint.name
        assert all(cost == base for cost in costs[1:]), endpoint.name

def test_key_present_falls_back_to_the_second_env_name():
    endpoint = EndpointConfig(
        name="acme", base_url="https://acme.invalid/v1",
        key_env=("ACME_API_KEY", "ACME_FALLBACK_API_KEY"),
        models=("m",), strict=True, timeout_s=1.0, thinking_off=False)
    env = {"ACME_API_KEY": "   ", "ACME_FALLBACK_API_KEY": "real"}
    assert endpoint.key_present(env) is True
    assert endpoint.resolve_key(env) == "real"

def test_classify_http_status_separates_validation_from_http():
    accepted = json.dumps({"choices": [{"message": {"content": "{}"}}]})
    assert classify_http_status(200, accepted) == "accepted"
    assert classify_http_status(400, "invalid schema at root") == (
        "rejected_validation")
    assert classify_http_status(422, "response_format unsupported") == (
        "rejected_validation")
    assert classify_http_status(500, "server_error") == "rejected_http"
    assert classify_http_status(503, "upstream") == "rejected_http"
    assert classify_http_status(401, "bad key") == "rejected_http"
    assert classify_http_status(429, "slow down") == "rejected_http"

def test_a_quota_wall_on_a_400_is_not_a_schema_rejection():
    verdict = classify_response(400, json.dumps(
        {"error": {"code": 429, "message": "You exceeded your current quota"}}))
    assert verdict.outcome == "rejected_http"
    assert verdict.schema_attributable is False
    assert verdict.stated_construct is None

def test_a_missing_model_404_attributes_nothing():
    verdict = classify_response(404, "404 page not found")
    assert verdict.outcome == "rejected_http"
    assert verdict.schema_attributable is False
    assert verdict.stated_construct is None

def test_a_quota_wall_never_blames_a_construct_even_when_the_body_has_one():
    verdict = classify_response(429, json.dumps(
        {"error": {"code": 429, "message": "rate limit exceeded"}}))
    assert verdict.outcome == "rejected_http"
    assert verdict.stated_construct is None
    wrapped = classify_response(200, json.dumps(
        {"choices": None, "error": {"code": 429, "message": "quota"}}))
    assert wrapped.outcome == "rejected_http"
    assert wrapped.stated_construct is None

def test_an_expired_key_is_a_credential_failure_not_a_schema_problem():
    verdict = classify_response(
        401, json.dumps({"detail": "Your API key expired on 2026-10-01."}))
    assert verdict.outcome == "rejected_http"
    assert verdict.stated_construct is None
    assert verdict.schema_attributable is False
    assert is_credential_failure(verdict.detail)
    schema_noise = classify_response(
        400, "invalid api key and additionalProperties both mentioned")
    assert schema_noise.stated_construct is None

def test_a_502_provider_unavailable_blames_no_construct():
    verdict = classify_response(502, json.dumps({
        "message": "Upstream error from Nvidia: Internal server error",
        "code": 502, "metadata": {"error_type": "provider_unavailable"}}))
    assert verdict.outcome == "rejected_http"
    assert verdict.stated_construct is None

def test_http_200_with_a_null_choices_is_not_acceptance():
    verdict = classify_response(200, json.dumps(
        {"choices": None, "error": {"message": "Internal error",
                                     "code": 500}}))
    assert verdict.outcome == "rejected_http"
    assert "Internal error" in verdict.detail

def test_http_200_wrapping_an_upstream_schema_refusal_is_a_validation_rejection():
    body = json.dumps({
        "choices": None,
        "error": {
            "code": 400,
            "message": (
                "Upstream error from Nvidia: ValueError: Grammar error: "
                "regex parse error: ^(?!^[-+.]*$)[+-]?0*[0-9]*\\.?[0-9]*$ "
                "error: look-around, including look-ahead and look-behind, "
                "is not supported while processing "
                "json-schema:///#/$defs/DeclaredCalculation"),
        }})
    verdict = classify_response(200, body)
    assert verdict.outcome == "rejected_validation"
    assert verdict.stated_construct == "pattern"
    assert verdict.schema_attributable is True

def test_a_lookahead_in_pattern_is_attributed_to_pattern():
    verdict = classify_response(
        400, "grammar error: look-ahead is not supported in this regex")
    assert verdict.outcome == "rejected_validation"
    assert verdict.stated_construct == "pattern"

def test_an_additionalproperties_refusal_is_attributed_to_that_keyword():
    verdict = classify_response(
        400, "schema error: additionalProperties is not supported")
    assert verdict.stated_construct == "additionalProperties"

def test_a_timeout_attributes_no_construct():
    result = ProbeResult("p", "m", "intake", "timed_out", 60000,
                         "a" * 64, 1, "APITimeoutError")
    report = ConformanceReport(results=[result])
    specs = stage_specs()
    findings = attribute_constructs(report, specs)
    assert findings == []
    assert unattributed(report) == [result]

def test_probe_reads_a_wrapped_upstream_refusal_through_the_plain_client(
        monkeypatch):
    import asyncio

    from evals import schema_conformance as sc

    monkeypatch.setenv("DIME_CONFORMANCE_WRAP_KEY", "probe-key")
    endpoint = EndpointConfig("acme", "https://acme.invalid/v1",
                              ("DIME_CONFORMANCE_WRAP_KEY",), ("m",),
                              True, 1.0, False)
    specs = (sc.StageSpec("intake", "intake", sc.control_schema()),)

    class _Response:
        choices = None

        def model_dump(self, exclude_none=True):
            return {"choices": None, "error": {
                "code": 400,
                "message": (
                    "Upstream error: ValueError: Grammar error: "
                    "look-ahead is not supported while processing "
                    "json-schema:///#/$defs/DeclaredCalculation")}}

    class _Completions:
        async def create(self, **kwargs):
            return _Response()

    class _Chat:
        completions = _Completions()

    class _Client:
        chat = _Chat()

        async def close(self):
            return None

    monkeypatch.setattr(sc, "_build_client",
                        lambda endpoint, api_key, timeout_s: _Client())
    results, _spent = asyncio.run(
        sc.probe_model(endpoint, "m", specs, with_control=False))
    stage = next(r for r in results if r.stage == "intake")
    assert stage.outcome == "rejected_validation"
    assert stage.stated_construct == "pattern"
    assert stage.schema_attributable is True

def test_thinking_off_reaches_the_request_for_a_nim_endpoint():
    from v2.adapters.models import NIM_THINKING_OFF_EXTRA_BODY

    endpoint = EndpointConfig("nvidia", "https://nim.invalid/v1", ("K",),
                              ("m",), True, 1.0, True)
    assert _request_kwargs(endpoint)["extra_body"] == (
        NIM_THINKING_OFF_EXTRA_BODY)
    plain = EndpointConfig("openrouter", "https://or.invalid/v1", ("K",),
                          ("m",), True, 1.0, False)
    assert _request_kwargs(plain) == {}

def test_no_artifact_writes_a_credential_value(tmp_path):
    from evals.schema_conformance import build_artifacts

    secret = "sk-live-never-print-this-value"
    endpoint = EndpointConfig("acme", "https://acme.invalid/v1", ("K",),
                              ("m",), True, 1.0, False)
    plan = ProbePlan((endpoint,), 5)
    results = [
        ProbeResult("acme", "m", "intake", "rejected_http", 12, "a" * 64, 1,
                    f"upstream echoed {secret} back at us"),
        ProbeResult("acme", "m", "plan", "accepted", 9, "b" * 64, 1, ""),
    ]
    paths = build_artifacts(
        ConformanceReport(results=results, requests_spent=2), plan, tmp_path,
        env={"ACME_API_KEY": secret})
    for path in paths.values():
        assert secret not in path.read_text(), path
        assert "<redacted>" in path.read_text(), path

def test_merge_keeps_the_accepted_outcome_across_sweeps(tmp_path):
    from evals.schema_conformance import build_artifacts, merge_report

    prior = ConformanceReport(results=[
        ProbeResult("p", "m", "intake", "accepted", 1200, "a" * 64, 1),
        ProbeResult("p", "m", "plan", "rejected_validation", 300, "b" * 64, 1,
                    "look-ahead unsupported", "pattern", True),
    ], requests_spent=2)
    path = build_artifacts(
        prior, ProbePlan(endpoints=(), budget=10), tmp_path)["json"]
    fresh = ConformanceReport(results=[
        ProbeResult("p", "m", "intake", "rejected_http", 200, "a" * 64, 1,
                    "Rate limit exceeded: free-models-per-day"),
        ProbeResult("p", "m", "plan", "rejected_http", 210, "b" * 64, 1,
                    "Rate limit exceeded: free-models-per-day"),
    ], requests_spent=2)
    merged = merge_report(fresh, path)
    assert merged.requests_spent == 2
    intake = next(r for r in merged.results if r.stage == "intake")
    assert intake.accepted, "a rate limit must not overwrite a real accept"
    plan_cell = next(r for r in merged.results if r.stage == "plan")
    assert plan_cell.outcome == "rejected_validation"
    assert plan_cell.stated_construct == "pattern"

def test_merge_adds_cells_a_fresh_sweep_never_reached(tmp_path):
    from evals.schema_conformance import build_artifacts, merge_report

    prior = ConformanceReport(results=[
        ProbeResult("p", "m1", "intake", "accepted", 5, "a" * 64, 1)],
        requests_spent=1)
    path = build_artifacts(
        prior, ProbePlan(endpoints=(), budget=10), tmp_path)["json"]
    fresh = ConformanceReport(results=[
        ProbeResult("p", "m2", "intake", "accepted", 6, "b" * 64, 1)],
        requests_spent=1)
    merged = merge_report(fresh, path)
    assert {(r.model) for r in merged.results} == {"m1", "m2"}

def test_merge_without_a_prior_file_returns_the_fresh_report(tmp_path):
    from evals.schema_conformance import merge_report

    fresh = ConformanceReport(
        results=[ProbeResult("p", "m", "intake", "accepted", 1, "a" * 64, 1)],
        requests_spent=1)
    assert merge_report(fresh, tmp_path / "absent.json") is fresh

def test_a_shared_wire_schema_is_probed_once_and_fanned_out():
    import asyncio

    from evals import schema_conformance as sc

    specs = stage_specs()
    assert specs[2].schema is specs[4].schema, "repair reuses the draft schema"
    sends = []

    class _Response:
        choices = [{"message": {"content": "{}"}}]

        def model_dump(self, exclude_none=True):
            return {"choices": [{"message": {"content": "{}"}}]}

    class _Completions:
        async def create(self, **kwargs):
            sends.append(kwargs["response_format"]["json_schema"]["schema"])
            return _Response()

    class _Chat:
        completions = _Completions()

    class _Client:
        chat = _Chat()

        async def close(self):
            return None

    endpoint = EndpointConfig("acme", "https://acme.invalid/v1",
                              ("DIME_CONFORMANCE_FANOUT_KEY",), ("m",),
                              True, 1.0, False)
    original = sc._build_client
    sc._build_client = lambda endpoint, api_key, timeout_s: _Client()
    try:
        results, spent = asyncio.run(
            sc.probe_model(endpoint, "m", specs, with_control=False,
                            env={"DIME_CONFORMANCE_FANOUT_KEY": "k"}))
    finally:
        sc._build_client = original
    assert spent == len(sends)
    assert spent == 4
    assert len(results) == 5
    synth = next(r for r in results if r.stage == "synthesizer")
    repair = next(r for r in results if r.stage == "repair")
    assert synth.outcome == repair.outcome == "accepted"
    assert synth.schema_sha256 == repair.schema_sha256

def test_a_stated_construct_wins_over_the_differential_set():
    specs = stage_specs()
    verifier = next(s for s in specs if s.stage == "verifier")
    intake = next(s for s in specs if s.stage == "intake")
    accepted = ProbeResult("gemini", "m", verifier.stage, "accepted", 9,
                           "a" * 64, 10)
    rejected = ProbeResult("gemini", "m", intake.stage, "rejected_validation",
                           40, "b" * 64, 20, "look-ahead is not supported",
                           stated_construct="pattern",
                           schema_attributable=True)
    report = ConformanceReport(results=[accepted, rejected])
    findings = attribute_constructs(report, specs)
    assert [f.construct for f in findings] == ["pattern"]

def test_unattributed_lists_a_rejection_no_construct_explains():
    specs = stage_specs()
    intake = next(s for s in specs if s.stage == "intake")
    result = ProbeResult("gemini", "m", intake.stage, "rejected_http", 90,
                         "a" * 64, 1, "model is currently experiencing high "
                         "demand")
    report = ConformanceReport(results=[result])
    assert attribute_constructs(report, specs) == []
    assert unattributed(report) == [result]

def test_an_unnamed_http_rejection_never_attributes_by_difference():
    specs = stage_specs()
    verifier = next(s for s in specs if s.stage == "verifier")
    intake = next(s for s in specs if s.stage == "intake")
    report = ConformanceReport(results=[
        ProbeResult("gemini", "m", verifier.stage, "accepted", 9, "a" * 64, 1),
        ProbeResult("gemini", "m", intake.stage, "rejected_http", 40,
                    "b" * 64, 1, "Internal error encountered."),
    ])
    assert attribute_constructs(report, specs) == []

def test_a_gemini_internal_error_is_not_a_schema_rejection():
    verdict = classify_response(500, json.dumps(
        [{"error": {"code": 500, "message": "Internal error encountered.",
                    "status": "INTERNAL"}}]))
    assert verdict.outcome == "rejected_http"
    assert verdict.stated_construct is None
    assert verdict.schema_attributable is False

def test_a_gemini_demand_spike_is_not_a_schema_rejection():
    verdict = classify_response(503, json.dumps(
        {"error": {"code": 503, "message": "This model is currently "
                                           "experiencing high demand."}}))
    assert verdict.outcome == "rejected_http"
    assert verdict.stated_construct is None

def test_collect_constructs_finds_nested_keywords():
    schema = {
        "type": "object",
        "$defs": {"Inner": {"type": "object", "properties": {
            "x": {"anyOf": [{"type": "string", "pattern": "^a"},
                            {"type": "null"}]}}}},
        "properties": {"inner": {"$ref": "#/$defs/Inner"}},
        "additionalProperties": False,
    }
    found = collect_constructs(schema)
    assert {"type", "$defs", "properties", "additionalProperties",
            "anyOf", "pattern", "$ref"} <= found
    assert "enum" not in found

def test_collect_constructs_sees_through_lists_of_schemas():
    assert collect_constructs([{"type": "string"}, {"const": 3}]) == {
        "type", "const"}

def test_constructs_absent_from_accepted_schema_are_not_attributed():
    specs = stage_specs()
    accepted_specs = specs[:1]
    result = ProbeResult("gemini", "m", specs[0].stage, "accepted", 12,
                         "a" * 64, 10)
    report = ConformanceReport(results=[result])
    attributed = attribute_constructs(report, accepted_specs)
    assert attributed == []

def test_construct_present_only_in_rejected_schema_is_attributed():
    specs = stage_specs()
    verifier = next(s for s in specs if s.stage == "verifier")
    intake = next(s for s in specs if s.stage == "intake")
    accepted = ProbeResult("gemini", "m", verifier.stage, "accepted", 9,
                           "a" * 64, 10)
    rejected = ProbeResult("gemini", "m", intake.stage, "rejected_validation",
                           40, "b" * 64, 20, "schema rejected",
                           schema_attributable=True)
    report = ConformanceReport(results=[accepted, rejected])
    verifier_constructs = collect_constructs(
        verifier.wire_response_format("m")["json_schema"]["schema"])
    intake_constructs = collect_constructs(
        intake.wire_response_format("m")["json_schema"]["schema"])
    unique = intake_constructs - verifier_constructs
    findings = attribute_constructs(report, specs)
    attributed = {f.construct for f in findings}
    assert unique
    assert unique <= attributed
    assert findings
    assert findings[0].broken_models == ("gemini/m",)
    assert findings[0].broken_cells == (f"gemini/m/{intake.stage}",)

def test_accepted_constructs_union_covers_every_accepted_schema():
    specs = stage_specs()
    results = [ProbeResult("gemini", "m", s.stage, "accepted", 5, "c" * 64, 1)
               for s in specs]
    report = ConformanceReport(results=results)
    got = accepted_constructs(report, "gemini", "m", specs)
    assert "type" in got and "properties" in got

def test_requests_remaining_never_goes_negative():
    report = ConformanceReport(requests_spent=9)
    assert report.requests_remaining(4) == 0

def test_render_matrix_marks_every_outcome_kind():
    results = [
        ProbeResult("p", "m1", "intake", "accepted", 1500, "a" * 64, 1),
        ProbeResult("p", "m1", "plan", "rejected_validation", 2000,
                    "b" * 64, 2),
        ProbeResult("p", "m2", "intake", "rejected_http", 3000, "c" * 64, 3),
        ProbeResult("p", "m2", "plan", "timed_out", 60000, "d" * 64, 4),
        ProbeResult("p", "m3", "intake", "unreachable", 0, "", 0),
    ]
    report = ConformanceReport(results=results)
    text = render_matrix(report)
    assert "ok 1.5s" in text
    assert "VAL 2.0s" in text
    assert "HTTP 3.0s" in text
    assert "TIME 60.0s" in text
    assert "UNREACH 0.0s" in text

def test_schema_sha256_is_canonical_and_order_independent():
    left = {"type": "object", "properties": {"a": {"type": "string"}}}
    right = {"properties": {"a": {"type": "string"}}, "type": "object"}
    assert schema_sha256(left) == schema_sha256(right)

def test_stage_specs_cover_every_harness_stage_from_running_code():
    specs = stage_specs()
    assert [s.stage for s in specs] == [
        "intake", "plan", "synthesizer", "verifier", "repair"]
    assert len({s.schema.__name__ for s in specs}) == 4

def test_wire_schema_is_what_the_adapter_sends_not_the_pydantic_dump():
    from v2.arguments import PlannerOutputWire

    specs = stage_specs()
    plan_spec = next(s for s in specs if s.stage == "plan")
    raw = PlannerOutputWire.model_json_schema()
    wire = plan_spec.wire_response_format("gemini-3.8-flash")
    body = wire["json_schema"]["schema"]
    assert wire["json_schema"]["strict"] is True
    assert schema_sha256(raw) != schema_sha256(body)

def test_the_wire_schema_no_longer_depends_on_the_model_name():
    specs = stage_specs()
    intake = next(s for s in specs if s.stage == "intake")
    assert intake.wire_response_format("gemini-3.5-flash") == (
        intake.wire_response_format("gemma-4-31b-it"))

def test_probe_budget_is_enforced_across_endpoints(monkeypatch):
    import asyncio

    from evals import schema_conformance as sc

    plan = ProbePlan(endpoints=(
        EndpointConfig("a", "https://a.invalid/v1", ("A_KEY",), ("m1",),
                       True, 0.01, False),
        EndpointConfig("b", "https://b.invalid/v1", ("B_KEY",), ("m2",),
                       True, 0.01, False),
    ), budget=2)

    calls = []

    async def fake_probe(endpoint, model, specs, with_control,
                         concurrency=4):
        calls.append((endpoint.name, model, with_control))
        return [
            ProbeResult(endpoint.name, model, spec.stage, "accepted", 1,
                        "e" * 64, 1)
            for spec in specs
        ], len(specs)

    one_spec = (sc.StageSpec("intake", "intake", sc.control_schema()),)
    monkeypatch.setattr(sc, "probe_model", fake_probe)
    monkeypatch.setattr(sc, "stage_specs", lambda: one_spec)
    monkeypatch.setattr(sc, "group_specs_by_wire_schema",
                        lambda specs, model: {"d": (list(specs), {})})
    monkeypatch.setattr(sc, "requests_for_model",
                        lambda specs, model, with_control: 1)
    report = asyncio.run(sc.run_probe(plan))
    assert report.requests_spent == 2
    assert calls == [("a", "m1", True), ("b", "m2", True)]

def test_probe_model_marks_every_stage_unreachable_without_a_credential(
        monkeypatch):
    import asyncio

    from evals import schema_conformance as sc

    monkeypatch.delenv("DIME_CONFORMANCE_FAKE_KEY", raising=False)
    endpoint = EndpointConfig("acme", "https://acme.invalid/v1",
                              ("DIME_CONFORMANCE_FAKE_KEY",), ("m",),
                              True, 0.01, False)
    specs = stage_specs()
    results, spent = asyncio.run(
        sc.probe_model(endpoint, "m", specs, with_control=True))
    assert spent == 0
    assert [r.outcome for r in results] == ["unreachable"] * len(specs)
    assert all("credential" in r.detail for r in results)
    assert all("DIME_CONFORMANCE_FAKE_KEY" not in r.detail for r in results)

def test_probe_model_never_writes_a_credential_into_a_detail(monkeypatch):
    import asyncio

    from evals import schema_conformance as sc

    monkeypatch.setenv("DIME_CONFORMANCE_FAKE_KEY", "sk-secret-value")
    endpoint = EndpointConfig("acme", "https://acme.invalid/v1",
                              ("DIME_CONFORMANCE_FAKE_KEY",), ("m",),
                              True, 0.01, False)
    specs = (sc.StageSpec("intake", "intake", sc.control_schema()),)

    class _Completions:
        async def create(self, **kwargs):
            raise RuntimeError("upstream said sk-secret-value was missing")

    class _Chat:
        completions = _Completions()

    class _Client:
        chat = _Chat()

        async def close(self):
            return None

    monkeypatch.setattr(sc, "_build_client",
                        lambda endpoint, api_key, timeout_s: _Client())
    results, spent = asyncio.run(
        sc.probe_model(endpoint, "m", specs, with_control=True))
    assert spent == 2
    control, stage = results
    assert control.stage == "control"
    assert stage.stage == "intake"
    assert stage.outcome == "rejected_http"
    assert "sk-secret-value" not in stage.detail

def test_artifacts_land_in_the_requested_directory(tmp_path):
    from evals.schema_conformance import build_artifacts

    plan = ProbePlan(endpoints=(), budget=3)
    report = ConformanceReport(
        results=[ProbeResult("p", "m", "intake", "accepted", 10, "f" * 64, 1)],
        requests_spent=1)
    paths = build_artifacts(report, plan, tmp_path)
    matrix = paths["matrix"].read_text()
    payload = json.loads(paths["json"].read_text())
    assert "Structured-output conformance matrix" in matrix
    assert payload["requests_spent"] == 1
    assert payload["results"][0]["stage"] == "intake"