from app.config import settings
from app.providers import (
    NVIDIA_NIM_BASE_URL,
    NVIDIA_NIM_DEFAULT,
    NVIDIA_NIM_MODELS,
    fallback_order,
    get_llm,
    models_catalog,
    resolve_model_id,
)


def test_nvidia_is_priority_one_and_exact_models_are_exposed(monkeypatch):
    monkeypatch.setattr(settings, "nvidia_nim_api_key", "key")
    for primary in ("nvidia", "openrouter", "mistral", "inception", "groq"):
        assert fallback_order(primary)[0] == "nvidia"
    catalog = models_catalog()
    assert catalog["available"]["nvidia"] is True
    assert [item["id"] for item in catalog["models"] if item["engine"] == "nvidia"] == [
        f"nvidia:{model}" for model in NVIDIA_NIM_MODELS
    ]


def test_nvidia_model_boundary_clamps_to_allowlist(monkeypatch):
    monkeypatch.setattr(settings, "nvidia_nim_api_key", "key")
    for model in NVIDIA_NIM_MODELS:
        assert resolve_model_id(f"nvidia:{model}") == ("nvidia", model)
    assert resolve_model_id("nvidia:unapproved/model") == ("nvidia", NVIDIA_NIM_DEFAULT)


def test_nvidia_client_uses_nim_endpoint(monkeypatch):
    monkeypatch.setattr(settings, "nvidia_nim_api_key", "key")
    client = get_llm("nvidia", NVIDIA_NIM_DEFAULT)
    assert client is not None
    assert client.model_name == NVIDIA_NIM_DEFAULT
    assert str(client.openai_api_base).rstrip("/") == NVIDIA_NIM_BASE_URL
