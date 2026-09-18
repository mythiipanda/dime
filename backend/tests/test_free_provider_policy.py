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
