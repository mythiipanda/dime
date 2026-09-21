from app.config import settings
from app import providers
from v2.adapters.models import ProviderStructuredModel


def test_structured_chain_clamps_groq_and_keeps_inception_first(monkeypatch):
    monkeypatch.setattr(settings, "dime_enable_inception", True)
    monkeypatch.setattr(settings, "dime_enable_groq", True)
    monkeypatch.setattr(settings, "inception_api_key", "inception")
    monkeypatch.setattr(settings, "groq_api_key", "groq-free")
    monkeypatch.setattr(settings, "openrouter_api_key", "openrouter-free")
    monkeypatch.setattr(settings, "mistral_api_key", "mistral-free")
    monkeypatch.setattr(settings, "groq_model", "paid-or-unlisted")
    models = ProviderStructuredModel("inception", "mercury-2.5")._models()
    assert [provider for provider, _ in models] == [
        "inception", "groq", "openrouter", "mistral"]
    assert models[1][1].model_name == providers.GROQ_DEFAULT
    assert providers.is_free_model("groq", models[1][1].model_name)


def test_one_logical_boundary_has_one_request_and_transparent_groq_fallback(monkeypatch):
    import asyncio
    from pydantic import BaseModel
    from v2.adapters import RecordedStructuredModel
    from v2.runtime import RequestEnvelope, RunLedger
    class Out(BaseModel):
        value: str
    class Inner:
        last_provider = "groq"
        last_model = "openai/gpt-oss-20b"
        last_failures = [{"route":"intake","provider":"inception","model":"mercury-2.5","attempt_number":1,"exception_type":"TimeoutError","message_class":"timeout","latency_ms":1}]
        async def generate(self, **call): return Out(value="ok")
    env = RequestEnvelope.freeze(provider="inception", model="mercury-2.5",
        route="intake", prompt="p", context={}, tool_schemas={}, planner_version="v2")
    ledger = RunLedger("run")
    got = asyncio.run(RecordedStructuredModel(Inner(), ledger, turn_id="run").generate(
        schema=Out, prompt="p", payload={}, envelope=env))
    assert got.value == "ok"
    assert [entry.kind for entry in ledger.entries].count("model/request") == 1
    attempt = [entry for entry in ledger.entries if entry.kind == "assistant/attempt"][0]
    assert attempt.data["provider"] == "groq"
    assert attempt.data["model"] == "openai/gpt-oss-20b"
    assert attempt.data["provider_attempts"][0]["provider"] == "inception"


def test_ordinary_groq_client_requires_activation_and_has_fixed_config(monkeypatch):
    captured=[]
    monkeypatch.setattr(settings,"groq_api_key","key")
    monkeypatch.setattr(settings,"dime_enable_groq",False)
    monkeypatch.setattr(providers,"ChatOpenAI",lambda **kw: captured.append(kw) or object())
    assert providers.get_llm("groq") is None
    monkeypatch.setattr(settings,"dime_enable_groq",True)
    with __import__("pytest").raises(providers.ProviderPolicyError):
        providers.get_llm("groq","openai/gpt-oss-120b")
    assert providers.get_llm("groq",providers.GROQ_DEFAULT) is not None
    assert captured == [{"model":"openai/gpt-oss-20b","base_url":"https://api.groq.com/openai/v1","api_key":"key","timeout":settings.llm_timeout_s,"max_retries":0}]


def test_streaming_groq_uses_same_gated_fixed_client(monkeypatch):
    import asyncio
    class Chunk: content="ok"
    class Client:
        async def astream(self,*a,**k):
            yield Chunk()
    monkeypatch.setattr(settings,"dime_enable_groq",True)
    monkeypatch.setattr(settings,"groq_api_key","key")
    monkeypatch.setattr(providers,"get_llm",lambda name,model=None: Client() if name=="groq" else None)
    monkeypatch.setattr(providers,"fallback_order",lambda primary:["groq"])
    async def collect():
        return [x async for x in providers.astream_with_fallback("groq","openai/gpt-oss-20b",[])]
    assert asyncio.run(collect()) == [{"provider":"groq","text":"ok"}]



def test_structured_groq_client_is_fixed_one_attempt_and_activation_gated(monkeypatch):
    monkeypatch.setattr(settings,"dime_enable_inception",False)
    monkeypatch.setattr(settings,"dime_enable_groq",False)
    monkeypatch.setattr(settings,"groq_api_key","key")
    assert "groq" not in providers.fallback_order("openrouter")
    monkeypatch.setattr(settings,"dime_enable_groq",True)
    got=ProviderStructuredModel("groq","openai/gpt-oss-20b")._models()
    assert got[0][0] == "groq" and got[0][1].model_name == "openai/gpt-oss-20b"
    client=got[0][1]._provider.client
    assert str(client.base_url).rstrip("/") == "https://api.groq.com/openai/v1"
    assert client.max_retries == 0


@__import__("pytest").mark.parametrize("failure", [
    TimeoutError("timed out"), RuntimeError("429 rate limit"),
    RuntimeError("503 provider failure"), RuntimeError("malformed JSON schema"),
])
def test_groq_faults_attempt_once_then_continue_with_transparent_evidence(monkeypatch, failure):
    import asyncio
    from pydantic import BaseModel
    from types import SimpleNamespace
    from v2.runtime import RequestEnvelope
    class Out(BaseModel): value: str
    calls=[]
    class FakeAgent:
        def __init__(self, model, **kwargs):
            self.model=model; calls.append((model.model_name, kwargs["retries"]))
        async def run(self, payload):
            if self.model.model_name == providers.GROQ_DEFAULT: raise failure
            return SimpleNamespace(output=Out(value="ok"))
    model=ProviderStructuredModel("groq",providers.GROQ_DEFAULT)
    model._models=lambda: [
        ("groq",SimpleNamespace(model_name=providers.GROQ_DEFAULT)),
        ("openrouter",SimpleNamespace(model_name=providers.OPENROUTER_DEFAULT))]
    monkeypatch.setattr("v2.adapters.models.Agent",FakeAgent)
    env=RequestEnvelope.freeze(provider="groq",model=providers.GROQ_DEFAULT,
        route="intake",prompt="p",context={},tool_schemas={},planner_version="v2")
    out=asyncio.run(model.generate(schema=Out,prompt="p",payload={},envelope=env))
    assert out.value == "ok"
    assert calls == [(providers.GROQ_DEFAULT,0),(providers.OPENROUTER_DEFAULT,settings.llm_max_retries)]
    assert len(model.last_failures)==1
    assert model.last_failures[0]["provider"]=="groq"
    assert model.last_failures[0]["attempt_number"]==1
