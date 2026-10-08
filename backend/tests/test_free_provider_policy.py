from shared.providers import (
    GEMINI_ALLOWLIST, GEMINI_BASE_URL, GEMINI_DEFAULT, GEMINI_MODELS,
    OPENROUTER_AUTO, ProviderPolicyError, fallback_order, is_free_model,
    models_catalog, resolve_model_id,
)
from shared.config import settings

def test_every_runtime_fallback_chain_is_free_only():
    for primary in ("openrouter", "mistral", "inception", "groq", "gemini",
                    "cerebras"):
        assert set(fallback_order(primary)) <= {
            "gemini", "nvidia", "openrouter", "mistral", "cerebras", "groq"}
        assert fallback_order(primary)[0] in {"gemini", "cerebras"}
        assert "inception" not in fallback_order(primary)

def test_openrouter_paid_and_stale_slugs_clamp(monkeypatch):
    monkeypatch.setattr(settings, "openrouter_model", "openai/gpt-4o")
    monkeypatch.setattr(settings, "nvidia_nim_api_key", "")
    monkeypatch.setattr(settings, "openrouter_api_key", "key")
    monkeypatch.setattr(settings, "gemini_api_key", "")
    monkeypatch.setattr(settings, "cerebras_api_key", "")
    monkeypatch.setattr(settings, "dime_enable_groq", False)
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
    assert set(catalog["available"]) >= {
        "gemini", "nvidia", "openrouter", "mistral"}
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
    import shared.providers as providers
    constructed = []
    monkeypatch.setattr(settings, "inception_api_key", "retained-key")
    monkeypatch.setattr(settings, "groq_api_key", "retained-key")
    monkeypatch.setattr(providers, "ChatOpenAI",
                        lambda **kwargs: constructed.append(kwargs) or object())
    monkeypatch.setattr(settings, "dime_enable_groq", False)
    assert providers.get_llm("inception", "mercury-2.5") is None
    assert providers.get_llm("groq", "openai/gpt-oss-120b") is None
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

def test_groq_free_tier_activation_is_exact_and_ordered(monkeypatch):
    import shared.providers as providers
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
        "cerebras", "gemini", "nvidia", "groq", "openrouter", "mistral",
        "inception"]
    assert providers.is_free_model("groq", "openai/gpt-oss-20b")
    assert providers.is_free_model("groq", "openai/gpt-oss-120b")
    assert providers.resolve_model_id("groq:openai/gpt-oss-120b") == (
        "groq", "openai/gpt-oss-120b")
    with __import__("pytest").raises(providers.ProviderPolicyError):
        providers.resolve_model_id("groq:qwen/qwen3.8-27b")

def test_groq_key_is_inert_without_explicit_activation(monkeypatch):
    import shared.providers as providers
    monkeypatch.setattr(settings, "dime_enable_groq", False)
    monkeypatch.setattr(settings, "groq_api_key", "retained")
    assert "groq" not in providers.active_provider_order()
    assert providers.get_llm("groq") is None

@__import__("pytest").mark.parametrize("slug", [
    "qwen/qwen3.8-27b", "groq/compound", "", "openai/gpt-oss-20B",
    "openai/gpt-oss-20b ", "openai/gpt-oss-120b-extra"])
def test_explicit_unlisted_groq_slugs_fail_closed_before_client(monkeypatch, slug):
    import shared.providers as providers
    monkeypatch.setattr(settings, "dime_enable_groq", True)
    monkeypatch.setattr(settings, "groq_api_key", "free")
    with __import__("pytest").raises(providers.ProviderPolicyError):
        providers.resolve_model_id("groq:" + slug)

def test_gemini_allowlist_is_workhorse_and_quality_only(monkeypatch):
    assert GEMINI_DEFAULT == "gemini-3.5-flash"
    assert set(GEMINI_MODELS) == {
        "gemini-3.5-flash-lite", "gemini-3.5-flash", "gemini-3.8-flash",
        "gemma-4-31b-it"}
    assert GEMINI_ALLOWLIST == set(GEMINI_MODELS)

def test_gemini_boundary_fails_closed_on_unapproved_slugs(monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "key")
    assert resolve_model_id("gemini:gemini-3.5-flash-lite") == (
        "gemini", "gemini-3.5-flash-lite")
    assert resolve_model_id("gemini:gemini-3.5-flash") == (
        "gemini", "gemini-3.5-flash")
    assert resolve_model_id("gemini-3.5-flash-lite") == (
        "gemini", "gemini-3.5-flash-lite")
    for unapproved in ("gemini-2.5-pro", "gemini-2.0-flash", ""):
        with __import__("pytest").raises(ProviderPolicyError):
            resolve_model_id("gemini:" + unapproved)

def test_gemini_is_free_and_default_when_keyed(monkeypatch):
    import shared.providers as providers
    monkeypatch.setattr(settings, "gemini_api_key", "key")
    monkeypatch.setattr(settings, "nvidia_nim_api_key", "")
    assert is_free_model("gemini", GEMINI_DEFAULT)
    assert not is_free_model("gemini", "gemini-2.5-pro")
    monkeypatch.setattr(settings, "cerebras_api_key", "")
    assert providers._default_provider() == ("gemini", GEMINI_DEFAULT)
    assert providers._gemini_model("gemini-3.5-flash") == "gemini-3.5-flash"
    assert providers._gemini_model("gemini-3.5-flash-lite") == "gemini-3.5-flash-lite"
    assert providers._gemini_model("gemini-2.5-pro") == GEMINI_DEFAULT
    catalog = models_catalog()
    assert catalog["available"]["gemini"] is True
    gemini_ids = [item["id"] for item in catalog["models"]
                  if item["engine"] == "gemini"]
    assert gemini_ids == [f"gemini:{m}" for m in GEMINI_MODELS]
    assert providers.fallback_order("nvidia")[0] == "gemini"
    defaults = [item["id"] for item in catalog["models"] if item["default"]]
    assert defaults == [f"gemini:{GEMINI_DEFAULT}"]

def test_gemini_inert_without_key(monkeypatch):
    import shared.providers as providers
    monkeypatch.setattr(settings, "gemini_api_key", "")
    monkeypatch.setattr(settings, "nvidia_nim_api_key", "key")
    assert providers.get_llm("gemini") is None
    assert providers._default_provider() == (
        "nvidia", providers.NVIDIA_NIM_DEFAULT)
    catalog = models_catalog()
    assert catalog["available"]["gemini"] is False

def test_no_keys_falls_back_to_mistral_default_without_crashing(monkeypatch):
    import shared.providers as providers
    monkeypatch.setattr(settings, "gemini_api_key", "")
    monkeypatch.setattr(settings, "nvidia_nim_api_key", "")
    monkeypatch.setattr(settings, "openrouter_api_key", "")
    monkeypatch.setattr(settings, "mistral_api_key", "")
    monkeypatch.setattr(settings, "dime_enable_groq", False)
    monkeypatch.setattr(settings, "dime_enable_inception", False)
    monkeypatch.setattr(settings, "cerebras_api_key", "")
    assert providers._default_provider() == (
        "mistral", providers.MISTRAL_DEFAULT)
    assert providers.resolve_model_id(None) == providers._default_provider()
    assert providers.fallback_order("gemini")[0] == "gemini"
    assert providers.get_llm("gemini") is None
    assert providers.get_llm("mistral") is None

def test_gemini_client_uses_openai_compatible_endpoint(monkeypatch):
    import shared.providers as providers
    monkeypatch.setattr(settings, "gemini_api_key", "key")
    client = providers.get_llm("gemini", GEMINI_DEFAULT)
    assert client is not None
    assert client.model_name == GEMINI_DEFAULT
    assert str(client.openai_api_base).rstrip("/") == GEMINI_BASE_URL.rstrip("/")
