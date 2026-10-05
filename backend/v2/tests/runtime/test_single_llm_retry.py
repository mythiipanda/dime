import pytest

from v2.adapters.models import ProviderStructuredModel

PER_MINUTE_429 = "429 RESOURCE_EXHAUSTED (GenerateRequestsPerMinutePerProjectPerModel, per-second limit)"
PER_DAY_429 = "429 RESOURCE_EXHAUSTED (GenerateRequestsPerDayPerProjectPerModel-FreeTier, 500/day)"


def test_per_minute_429_is_rate_limit():
    assert ProviderStructuredModel._failure_class(Exception(PER_MINUTE_429)) == "rate_limit"


def test_per_day_429_is_quota_exhausted_not_rate_limit():
    assert ProviderStructuredModel._failure_class(Exception(PER_DAY_429)) == "quota_exhausted"


def test_quota_exceeded_code_is_quota_exhausted():
    assert ProviderStructuredModel._failure_class(
        Exception("429 quota_exceeded: daily quota exhausted, resets midnight Pacific")
    ) == "quota_exhausted"


@pytest.mark.parametrize("message", [
    "500 Internal error",
    "502 Bad Gateway",
    "503 Service Unavailable",
    "504 deadline exceeded",
])
def test_server_errors_are_server_error(message):
    assert ProviderStructuredModel._failure_class(Exception(message)) == "server_error"


def test_timeout_name_is_timeout():
    assert ProviderStructuredModel._failure_class(TimeoutError("timed out")) == "timeout"


def test_408_message_is_timeout():
    assert ProviderStructuredModel._failure_class(Exception("408 Request Timeout")) == "timeout"


@pytest.mark.parametrize("message", [
    "401 authentication: invalid API key",
    "403 permission_denied: key lacks access",
])
def test_auth_failures_are_authentication(message):
    assert ProviderStructuredModel._failure_class(Exception(message)) == "authentication"


def test_bare_400_is_client_error():
    assert ProviderStructuredModel._failure_class(
        Exception("400 Bad Request: INVALID_ARGUMENT malformed body")
    ) == "client_error"


def test_404_is_client_error():
    assert ProviderStructuredModel._failure_class(
        Exception("404 model_not_found: unknown model")
    ) == "client_error"


def test_schema_validation_name_is_structured_output():
    class SchemaValidationError(Exception):
        pass

    assert ProviderStructuredModel._failure_class(
        SchemaValidationError("bad shape")) == "structured_output"


def test_content_filter_name_is_content_filter():
    class ContentFilterError(Exception):
        pass

    assert ProviderStructuredModel._failure_class(
        ContentFilterError("blocked")) == "content_filter"


def test_connect_name_is_network():
    class ConnectError(Exception):
        pass

    assert ProviderStructuredModel._failure_class(ConnectError("refused")) == "network"


def test_unknown_error_is_provider_error():
    assert ProviderStructuredModel._failure_class(RuntimeError("down")) == "provider_error"


class _StubResponse:
    def __init__(self, headers=None):
        self.headers = headers or {}


class _StubHttpError(Exception):
    def __init__(self, message="", *, status=None, headers=None, retry_after=None):
        super().__init__(message)
        self.status_code = status
        self.response = _StubResponse(headers)
        if retry_after is not None:
            self.retry_after = retry_after


def test_retry_after_uses_retry_after_attribute():
    exc = _StubHttpError("429", retry_after=12.5)
    assert ProviderStructuredModel._retry_after_s(exc) == 12.5


def test_retry_after_attribute_capped_at_max_delay():
    exc = _StubHttpError("429", retry_after=300.0)
    assert ProviderStructuredModel._retry_after_s(exc) == 60.0


def test_retry_after_reads_retry_after_header():
    exc = _StubHttpError("429", headers={"Retry-After": "7"})
    assert ProviderStructuredModel._retry_after_s(exc) == 7.0


def test_retry_after_reads_retry_after_ms_header():
    exc = _StubHttpError("429", headers={"retry-after-ms": "1500"})
    assert ProviderStructuredModel._retry_after_s(exc) == 1.5


def test_retry_after_reads_retry_delay_from_body():
    exc = _StubHttpError('429 RESOURCE_EXHAUSTED {"retryDelay": "34.4s"}')
    assert ProviderStructuredModel._retry_after_s(exc) == 34.4


def test_retry_after_reads_please_retry_in_message():
    exc = _StubHttpError("429 RESOURCE_EXHAUSTED: Please retry in 45.06s")
    assert ProviderStructuredModel._retry_after_s(exc) == 45.06


def test_retry_after_missing_is_none():
    assert ProviderStructuredModel._retry_after_s(Exception("boom")) is None


def test_backoff_grows_exponentially_to_cap(monkeypatch):
    monkeypatch.setattr("v2.adapters.models.random.uniform", lambda a, b: b)
    delays = [ProviderStructuredModel._backoff_delay_s(index) for index in range(8)]
    assert delays == [1.0, 2.0, 4.0, 8.0, 16.0, 32.0, 60.0, 60.0]


def test_backoff_jitter_stays_inside_documented_band():
    delay = ProviderStructuredModel._backoff_delay_s(0)
    assert 0.5 <= delay <= 1.0
    delay = ProviderStructuredModel._backoff_delay_s(1)
    assert 1.0 <= delay <= 2.0


def test_backoff_honors_retry_after_floor(monkeypatch):
    monkeypatch.setattr("v2.adapters.models.random.uniform", lambda a, b: a)
    assert ProviderStructuredModel._backoff_delay_s(0, retry_after_s=5.0) >= 5.0


def test_route_policies_have_no_failover_or_masking_keys():
    from v2.adapters.models import ROUTE_POLICIES
    for route, policy in ROUTE_POLICIES.items():
        assert "secondary_limit" not in policy, route
        assert "deterministic_fallback" not in policy, route


def test_route_policy_attempt_budgets_and_timeouts():
    from v2.adapters.models import ROUTE_POLICIES
    assert ROUTE_POLICIES["planner"]["attempt_timeout_s"] == 30.0
    assert ROUTE_POLICIES["planner"]["max_attempts"] == 2
    assert ROUTE_POLICIES["planner"]["total_budget_s"] == 60.0
    assert ROUTE_POLICIES["intake"]["total_budget_s"] == 60.0
    assert ROUTE_POLICIES["requirement_review"]["total_budget_s"] == 60.0
    assert ROUTE_POLICIES["synthesizer"]["total_budget_s"] == 50.0
    assert ROUTE_POLICIES["semantic_verifier"]["total_budget_s"] == 60.0


def _envelope(route="intake"):
    from v2.runtime import RequestEnvelope
    return RequestEnvelope.freeze(
        provider="gemini", model="primary", route=route,
        prompt="p", context={}, tool_schemas={}, planner_version="v2")


class _Model:
    def __init__(self, name="primary"):
        from v2.adapters.structured import (EndpointCapabilities, resolve_strategy)
        self.model_name = name
        self.capabilities = EndpointCapabilities(
            endpoint="https://stub.invalid/v1",
            strict_json_schema=True, tool_calling=True,
            strict_tool_definitions=True)
        self.strategy = resolve_strategy(self.capabilities)


def _ok_result():
    from v2.contracts import TaskSpec
    return type("R", (), {
        "output": TaskSpec(goal="ok", mode="quick", deliverable="x")})()


@pytest.mark.anyio
async def test_transient_429_retries_same_model_then_succeeds(monkeypatch):
    from v2.contracts import TaskSpec
    calls = []
    sleeps = []

    class FlakyAgent:
        def __init__(self, model, *a, **k):
            self.name = model.model_name

        async def run(self, prompt):
            calls.append(self.name)
            if len(calls) == 1:
                raise Exception(PER_MINUTE_429)
            return _ok_result()

    async def capture_sleep(value):
        sleeps.append(value)

    monkeypatch.setattr("v2.adapters.models.Agent", FlakyAgent)
    monkeypatch.setattr("v2.adapters.models.anyio.sleep", capture_sleep)
    m = ProviderStructuredModel("gemini", "primary")
    monkeypatch.setattr(m, "_models", lambda: [("gemini", _Model("primary"))])
    out = await m.generate(schema=TaskSpec, prompt="p",
                           payload={"q": "x"}, envelope=_envelope())
    assert out.goal == "ok"
    assert calls == ["primary", "primary"]
    assert len(sleeps) == 1
    assert 0.5 <= sleeps[0] <= 1.0
    assert [f["message_class"] for f in m.last_failures] == ["rate_limit"]
    assert m.last_provider == "gemini"


@pytest.mark.anyio
async def test_retry_after_delay_is_honored(monkeypatch):
    from v2.contracts import TaskSpec
    calls = []
    sleeps = []

    class FlakyAgent:
        def __init__(self, model, *a, **k):
            pass

        async def run(self, prompt):
            calls.append(1)
            if len(calls) == 1:
                raise Exception("429 RESOURCE_EXHAUSTED: Please retry in 3s")
            return _ok_result()

    async def capture_sleep(value):
        sleeps.append(value)

    monkeypatch.setattr("v2.adapters.models.Agent", FlakyAgent)
    monkeypatch.setattr("v2.adapters.models.anyio.sleep", capture_sleep)
    m = ProviderStructuredModel("gemini", "primary")
    monkeypatch.setattr(m, "_models", lambda: [("gemini", _Model("primary"))])
    out = await m.generate(schema=TaskSpec, prompt="p",
                           payload={"q": "x"}, envelope=_envelope())
    assert out.goal == "ok"
    assert sleeps and sleeps[0] >= 3.0


@pytest.mark.anyio
async def test_daily_quota_fails_fast_without_retry(monkeypatch):
    from v2.contracts import TaskSpec
    calls = []

    class QuotaAgent:
        def __init__(self, *a, **k):
            pass

        async def run(self, prompt):
            calls.append(1)
            raise Exception(PER_DAY_429)

    monkeypatch.setattr("v2.adapters.models.Agent", QuotaAgent)
    m = ProviderStructuredModel("gemini", "primary")
    monkeypatch.setattr(m, "_models", lambda: [("gemini", _Model("primary"))])
    with pytest.raises(RuntimeError, match="all structured-output providers failed"):
        await m.generate(schema=TaskSpec, prompt="p",
                         payload={"q": "x"}, envelope=_envelope())
    assert len(calls) == 1
    assert [f["message_class"] for f in m.last_failures] == ["quota_exhausted"]


@pytest.mark.anyio
async def test_auth_error_fails_fast_without_retry(monkeypatch):
    from v2.contracts import TaskSpec
    calls = []

    class AuthAgent:
        def __init__(self, *a, **k):
            pass

        async def run(self, prompt):
            calls.append(1)
            raise Exception("401 authentication: invalid API key")

    monkeypatch.setattr("v2.adapters.models.Agent", AuthAgent)
    m = ProviderStructuredModel("gemini", "primary")
    monkeypatch.setattr(m, "_models", lambda: [("gemini", _Model("primary"))])
    with pytest.raises(RuntimeError, match="authentication"):
        await m.generate(schema=TaskSpec, prompt="p",
                         payload={"q": "x"}, envelope=_envelope())
    assert len(calls) == 1


@pytest.mark.anyio
async def test_second_model_is_never_consulted(monkeypatch):
    from v2.contracts import TaskSpec
    calls = []

    class AlwaysDownAgent:
        def __init__(self, model, *a, **k):
            self.name = model.model_name

        async def run(self, prompt):
            calls.append(self.name)
            raise TimeoutError("temporary")

    async def no_sleep(value):
        return None

    monkeypatch.setattr("v2.adapters.models.Agent", AlwaysDownAgent)
    monkeypatch.setattr("v2.adapters.models.anyio.sleep", no_sleep)
    monkeypatch.setattr("v2.adapters.models.random.uniform", lambda a, b: 0)
    m = ProviderStructuredModel("gemini", "primary")
    monkeypatch.setattr(m, "_models", lambda: [("gemini", _Model("primary")),
                                              ("mistral", _Model("secondary"))])
    with pytest.raises(RuntimeError, match="all structured-output providers failed"):
        await m.generate(schema=TaskSpec, prompt="p",
                         payload={"q": "x"}, envelope=_envelope())
    assert calls == ["primary", "primary"]
    assert {f["provider"] for f in m.last_failures} == {"gemini"}


def test_models_returns_only_the_configured_provider(monkeypatch):
    monkeypatch.setattr("v2.adapters.models.settings.gemini_api_key", "key")
    monkeypatch.setattr("v2.adapters.models.settings.mistral_api_key", "key")
    monkeypatch.setattr("v2.adapters.models.settings.gemini_model", "gemini-3.5-flash-lite")
    models = ProviderStructuredModel("gemini", "gemini-3.5-flash-lite")._models()
    assert [provider for provider, _ in models] == ["gemini"]


@pytest.mark.anyio
async def test_synthesizer_exhaustion_raises_without_empty_draft():
    from v2.adapters.models import ModelSynthesizer
    from v2.contracts import TaskSpec

    class Down:
        async def generate(self, **call):
            raise RuntimeError("all structured-output providers failed [x]")

    with pytest.raises(RuntimeError, match="all structured-output providers failed"):
        await ModelSynthesizer(Down(), provider="s", model_name="s").synthesize(
            TaskSpec(goal="record", mode="quick", deliverable="answer"), [])


@pytest.mark.anyio
async def test_fused_intake_returns_unreviewed_task_without_fabricated_nodes():
    from v2.adapters.models import ModelIntake

    class ReviewDown:
        async def generate(self, **call):
            return call["schema"].model_validate({
                "goal": "pair", "mode": "quick", "deliverable": "answer",
                "entities": [
                    {"id": "myles-turner", "type": "player", "display_name": "Myles Turner"},
                    {"id": "luka-doncic", "type": "player", "display_name": "Luka Doncic"}],
                "season": {"value": "2025-26", "source": "user", "confidence": 1.0},
                "required_evidence": ["player_comparison"]})

    class FailingReview(ReviewDown):
        calls = 0

        async def generate(self, **call):
            type(self).calls += 1
            if type(self).calls == 1:
                return await super().generate(**call)
            raise RuntimeError("all structured-output providers failed [x]")

    model = FailingReview()
    task = await ModelIntake(model, provider="stub", model_name="stub",
                             capability_catalog={"player_comparison": {}},
                             requirement_review=True).understand("pair")
    assert task.requirements == []
    assert FailingReview.calls == 1


def test_chained_validation_cause_is_structured_output():
    class SchemaValidationError(Exception):
        pass

    outer = Exception("Exceeded maximum output retries (1)")
    outer.__cause__ = SchemaValidationError("bad shape")
    assert ProviderStructuredModel._failure_class(outer) == "structured_output"


def test_chained_timeout_cause_is_timeout():
    outer = RuntimeError("wrapper")
    outer.__cause__ = TimeoutError("timed out")
    assert ProviderStructuredModel._failure_class(outer) == "timeout"


@pytest.mark.anyio
async def test_decode_error_retries_same_model_then_succeeds(monkeypatch):
    from v2.contracts import TaskSpec
    calls = []
    decodes = []

    class OkAgent:
        def __init__(self, model, *a, **k):
            self.name = model.model_name

        async def run(self, prompt):
            calls.append(self.name)
            return _ok_result()

    def flaky_decode(output):
        decodes.append(output)
        if len(decodes) == 1:
            raise ValueError("kind payload mismatch")
        return {"drops": []}

    async def capture_sleep(value):
        pass

    monkeypatch.setattr("v2.adapters.models.Agent", OkAgent)
    monkeypatch.setattr("v2.adapters.models.anyio.sleep", capture_sleep)
    m = ProviderStructuredModel("gemini", "primary")
    monkeypatch.setattr(m, "_models", lambda: [("gemini", _Model("primary"))])
    out = await m.generate(schema=TaskSpec, prompt="p",
                           payload={"q": "x"}, envelope=_envelope(),
                           decode=flaky_decode)
    assert out.goal == "ok"
    assert calls == ["primary", "primary"]
    assert len(decodes) == 2
    assert [f["message_class"] for f in m.last_failures] == ["provider_error"]
    assert m.last_decode_extra == {"drops": []}
