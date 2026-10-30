from __future__ import annotations

import json

import httpx
import pytest

from shared import providers
from shared.config import settings


def test_agnes_is_opt_in_and_ordered_after_groq_before_gemini(monkeypatch):
    for name in (
        "cerebras_api_key", "nvidia_nim_api_key", "openrouter_api_key",
        "mistral_api_key",
    ):
        monkeypatch.setattr(settings, name, "")
    monkeypatch.setattr(settings, "dime_enable_inception", False)
    monkeypatch.setattr(settings, "dime_enable_groq", True)
    monkeypatch.setattr(settings, "groq_api_key", "fake-groq")
    monkeypatch.setattr(settings, "dime_enable_agnes", True)
    monkeypatch.setattr(settings, "agnes_api_key", "fake-agnes")
    monkeypatch.setattr(settings, "gemini_api_key", "fake-gemini")
    order = providers.active_provider_order()
    assert order[:3] == ("groq", "agnes", "gemini")
    assert providers._default_provider() == ("groq", providers.GROQ_DEFAULT)


def test_agnes_missing_key_or_enable_flag_is_inactive(monkeypatch):
    monkeypatch.setattr(settings, "dime_enable_agnes", True)
    monkeypatch.setattr(settings, "agnes_api_key", "")
    assert "agnes" not in providers.active_provider_order()
    assert providers.get_llm("agnes") is None
    with pytest.raises(providers.ProviderPolicyError, match="not activated"):
        providers.resolve_model_id("agnes:agnes-3.0-flash")

    monkeypatch.setattr(settings, "agnes_api_key", "fake-agnes")
    monkeypatch.setattr(settings, "dime_enable_agnes", False)
    assert "agnes" not in providers.active_provider_order()
    assert providers.get_llm("agnes") is None


@pytest.mark.parametrize("model", ["agnes-3.0-pro", "agnes-2.5-pro", "gpt-4o", ""])
def test_agnes_paid_or_unlisted_models_fail_closed(monkeypatch, model):
    monkeypatch.setattr(settings, "dime_enable_agnes", True)
    monkeypatch.setattr(settings, "agnes_api_key", "fake-agnes")
    with pytest.raises(providers.ProviderPolicyError, match="unapproved Agnes model"):
        providers.resolve_model_id("agnes:" + model)
    with pytest.raises(providers.ProviderPolicyError, match="unapproved Agnes model"):
        providers.get_llm("agnes", model)


def test_agnes_client_uses_allowlisted_https_openai_compatible_endpoint(monkeypatch):
    monkeypatch.setattr(settings, "dime_enable_agnes", True)
    monkeypatch.setattr(settings, "agnes_api_key", "fake-agnes")
    client = providers.get_llm("agnes")
    assert client is not None
    assert client.model_name == "agnes-3.0-flash"
    assert str(client.openai_api_base).rstrip("/") == providers.AGNES_BASE_URL
    assert client.openai_api_key.get_secret_value() == "fake-agnes"
    assert client.max_retries == 0


def test_catalog_registers_only_enabled_agnes_models(monkeypatch):
    monkeypatch.setattr(settings, "dime_enable_agnes", True)
    monkeypatch.setattr(settings, "agnes_api_key", "fake-agnes")
    catalog = providers.models_catalog()
    choices = [item for item in catalog["models"] if item["engine"] == "agnes"]
    assert {item["id"] for item in choices} == {
        "agnes:agnes-3.0-flash", "agnes:agnes-2.5-flash"}
    assert all(item["available"] for item in choices)


@pytest.fixture
def anyio_backend():
    return "asyncio"
