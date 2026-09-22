from app.providers import (
    OPENROUTER_AUTO, fallback_order, is_free_model, models_catalog,
    resolve_model_id,
)
from app.config import settings


def test_every_runtime_fallback_chain_is_free_only():
    for primary in ("openrouter", "mistral", "inception", "groq"):
        assert fallback_order(primary)[0] == "nvidia"
        assert set(fallback_order(primary)) == {"nvidia", "openrouter", "mistral"}
        assert not ({"inception", "groq"} & set(fallback_order(primary)))


def test_openrouter_paid_and_stale_slugs_clamp(monkeypatch):
    monkeypatch.setattr(settings, "openrouter_model", "openai/gpt-4o")
    monkeypatch.setattr(settings, "nvidia_nim_api_key", "")
    monkeypatch.setattr(settings, "openrouter_api_key", "key")
    for raw in (None, "openrouter:openai/gpt-4o", "openai/gpt-4o"):
        provider, slug = resolve_model_id(raw)
        assert provider == "openrouter"
        assert is_free_model(provider, slug)
    assert resolve_model_id("openrouter:" + OPENROUTER_AUTO) == (
        "openrouter", OPENROUTER_AUTO)


def test_mistral_explicit_slug_clamps_to_configured_free_limit(monkeypatch):
    monkeypatch.setattr(settings, "mistral_model", "owner-free-limit")
    assert resolve_model_id("mistral:paid-looking-other") == (
        "mistral", "owner-free-limit")
    assert is_free_model("mistral", "owner-free-limit")


def test_catalog_exposes_only_free_models(monkeypatch):
    monkeypatch.setattr(settings, "openrouter_model", "openai/gpt-4o")
    catalog = models_catalog()
    assert set(catalog["available"]) == {"nvidia", "openrouter", "mistral"}
    for item in catalog["models"]:
        provider, slug = item["id"].split(":", 1)
        assert is_free_model(provider, slug)


def test_structured_models_clamp_configured_paid_openrouter(monkeypatch):
    from v2.adapters.models import ProviderStructuredModel
    monkeypatch.setattr(settings, "openrouter_model", "openai/gpt-4o")
    monkeypatch.setattr(settings, "openrouter_api_key", "key")
    monkeypatch.setattr(settings, "mistral_api_key", "free-limit")
    monkeypatch.setattr(settings, "inception_api_key", "configured-paused")
    monkeypatch.setattr(settings, "groq_api_key", "configured-paused")
    models = ProviderStructuredModel("openrouter", "openai/gpt-4o")._models()
    assert models
    for provider, model in models:
        assert is_free_model(provider, model.model_name)


def test_direct_get_llm_never_constructs_paused_providers(monkeypatch):
    import app.providers as providers
    constructed = []
    monkeypatch.setattr(settings, "inception_api_key", "retained-key")
    monkeypatch.setattr(settings, "groq_api_key", "retained-key")
    monkeypatch.setattr(providers, "ChatOpenAI",
                        lambda **kwargs: constructed.append(kwargs) or object())
    assert providers.get_llm("inception", "mercury-2.5") is None
    assert providers.get_llm("groq", "anything") is None
    assert constructed == []


def test_structured_mistral_success_ledger_identity_is_free_limit(monkeypatch):
    import asyncio
    from pydantic import BaseModel
    from v2.adapters import models as adapter
    from v2.runtime import RequestEnvelope
    class Out(BaseModel): value: str
    class Run: output=Out(value="ok")
    class Agent:
        def __init__(self,*args,**kwargs): pass
        async def run(self,prompt): return Run()
    monkeypatch.setattr(adapter,"Agent",Agent)
    monkeypatch.setattr(settings,"nvidia_nim_api_key","")
    monkeypatch.setattr(settings,"openrouter_api_key","")
    monkeypatch.setattr(settings,"mistral_api_key","free-limit")
    model=adapter.ProviderStructuredModel("mistral","arbitrary-input")
    env=RequestEnvelope.freeze(provider="mistral",model="arbitrary-input",
        route="intake",prompt="p",context={},tool_schemas={},planner_version="v2")
    got=asyncio.run(model.generate(schema=Out,prompt="p",payload={},envelope=env))
    assert got.value=="ok"
    assert model.last_model==f"mistral_free_limit:{settings.mistral_model}"
