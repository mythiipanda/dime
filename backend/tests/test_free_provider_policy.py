from app.providers import (
    OPENROUTER_AUTO, fallback_order, is_free_model, models_catalog,
    resolve_model_id,
)
from app.config import settings


def test_every_runtime_fallback_chain_is_free_only():
    for primary in ("openrouter", "mistral", "inception", "groq"):
        assert fallback_order(primary) in (["openrouter", "mistral"],
                                            ["mistral", "openrouter"])
        assert not ({"inception", "groq"} & set(fallback_order(primary)))


def test_openrouter_paid_and_stale_slugs_clamp(monkeypatch):
    monkeypatch.setattr(settings, "openrouter_model", "openai/gpt-4o")
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
    assert set(catalog["available"]) == {"openrouter", "mistral"}
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
    monkeypatch.setattr(settings,"openrouter_api_key","")
    monkeypatch.setattr(settings,"mistral_api_key","free-limit")
    model=adapter.ProviderStructuredModel("mistral","arbitrary-input")
    env=RequestEnvelope.freeze(provider="mistral",model="arbitrary-input",
        route="intake",prompt="p",context={},tool_schemas={},planner_version="v2")
    got=asyncio.run(model.generate(schema=Out,prompt="p",payload={},envelope=env))
    assert got.value=="ok"
    assert model.last_model==f"mistral_free_limit:{settings.mistral_model}"


def test_groq_free_tier_activation_is_exact_and_ordered(monkeypatch):
    import app.providers as providers
    monkeypatch.setattr(settings, "openrouter_api_key", "free")
    monkeypatch.setattr(settings, "mistral_api_key", "free")
    monkeypatch.setattr(settings, "inception_api_key", "inception")
    monkeypatch.setattr(settings, "groq_api_key", "free-tier-key")
    monkeypatch.setattr(settings, "dime_enable_inception", True)
    monkeypatch.setattr(settings, "dime_enable_groq", True)
    monkeypatch.setattr(settings, "groq_model", providers.GROQ_DEFAULT)
    assert providers.resolve_model_id("inception:any") == (
        "inception", providers.INCEPTION_DEFAULT)
    assert providers.fallback_order("inception") == [
        "inception", "groq", "openrouter", "mistral"]
    assert providers.is_free_model("groq", "openai/gpt-oss-20b")
    assert not providers.is_free_model("groq", "openai/gpt-oss-120b")
    with __import__("pytest").raises(providers.ProviderPolicyError):
        providers.resolve_model_id("groq:openai/gpt-oss-120b")


def test_groq_key_is_inert_without_explicit_activation(monkeypatch):
    import app.providers as providers
    monkeypatch.setattr(settings, "dime_enable_groq", False)
    monkeypatch.setattr(settings, "groq_api_key", "retained")
    assert "groq" not in providers.active_provider_order()
    assert providers.get_llm("groq") is None


@__import__("pytest").mark.parametrize("slug", [
    "openai/gpt-oss-120b", "groq/compound", "", "openai/gpt-oss-20B",
    "openai/gpt-oss-20b ", "openai/gpt-oss-20b-extra"])
def test_explicit_unlisted_groq_slugs_fail_closed_before_client(monkeypatch, slug):
    import app.providers as providers
    monkeypatch.setattr(settings, "dime_enable_groq", True)
    monkeypatch.setattr(settings, "groq_api_key", "free")
    with __import__("pytest").raises(providers.ProviderPolicyError):
        providers.resolve_model_id("groq:" + slug)
