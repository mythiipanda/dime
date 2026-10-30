from __future__ import annotations

import inspect
import json
from typing import Any

import httpx
import pytest
from pydantic import BaseModel
from shared import providers
from shared.config import settings


@pytest.fixture
def reflection_enabled(monkeypatch: pytest.MonkeyPatch) -> Any:
    monkeypatch.setattr(settings, "reflection_api_key", "reflection-key")
    monkeypatch.setattr(settings, "dime_enable_reflection", True)
    monkeypatch.setattr(settings, "reflection_model", "")
    return settings

def test_the_route_resolves_the_pinned_model_and_its_alias(reflection_enabled: Any) -> None:
    assert providers.resolve_model_id("reflection:beam-1") == (
        "reflection", "Beam-1.0-501B-A23B")
    assert providers.resolve_model_id(
        "reflection:Beam-1.0-501B-A23B") == (
            "reflection", "Beam-1.0-501B-A23B")

def test_the_route_is_a_verified_https_endpoint() -> None:
    assert providers.REFLECTION_BASE_URL == "https://api.reflection.ai/openai/v1"

def test_an_unapproved_reflection_model_fails_closed(reflection_enabled: Any) -> None:
    for slug in ("beam-2", "", "Beam-1.0-501B-A23B ", "gpt-4o"):
        with pytest.raises(providers.ProviderPolicyError,
                           match="unapproved Reflection model"):
            providers.resolve_model_id("reflection:" + slug)

def test_the_route_needs_both_the_key_and_the_explicit_enable(
        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "reflection_api_key", "")
    monkeypatch.setattr(settings, "dime_enable_reflection", True)
    with pytest.raises(providers.ProviderPolicyError, match="not activated"):
        providers.resolve_model_id("reflection:beam-1")
    monkeypatch.setattr(settings, "reflection_api_key", "reflection-key")
    monkeypatch.setattr(settings, "dime_enable_reflection", False)
    with pytest.raises(providers.ProviderPolicyError, match="not activated"):
        providers.resolve_model_id("reflection:beam-1")

def test_reflection_never_enters_the_automatic_fallback_chain(
        reflection_enabled: Any) -> None:
    assert "reflection" not in providers.active_provider_order()
    for primary in ("gemini", "openrouter", "inception", "reflection"):
        assert "reflection" not in providers.fallback_order(primary)


def test_the_catalog_registers_the_route_when_enabled_and_keyed(
        reflection_enabled: Any) -> None:
    catalog = providers.models_catalog()
    assert catalog["available"]["reflection"] is True
    option = next(
        item for item in catalog["models"]
        if item["engine"] == "reflection")
    assert option["id"] == "reflection:Beam-1.0-501B-A23B"
    assert option["available"] is True


def test_the_catalog_omits_the_route_when_not_enabled_or_keyed(
        reflection_enabled: Any) -> None:
    settings.dime_enable_reflection = False
    catalog = providers.models_catalog()
    assert "reflection" not in catalog["available"]
    assert not [item for item in catalog["models"]
                if item["engine"] == "reflection"]
    settings.dime_enable_reflection = True
    settings.reflection_api_key = ""
    catalog = providers.models_catalog()
    assert "reflection" not in catalog["available"]
    assert not [item for item in catalog["models"]
                if item["engine"] == "reflection"]


def test_reflection_is_priced_as_an_allowlisted_free_beta(
        reflection_enabled: Any) -> None:
    assert providers.is_free_model(
        "reflection", providers.REFLECTION_DEFAULT) is True
    assert providers.is_free_model("reflection", "gpt-4o") is False


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"
