from shared.config import settings
from shared.providers import (
    GEMINI_DEFAULT,
    GEMINI_MODELS,
    NVIDIA_NIM_ALLOWLIST,    NVIDIA_NIM_BASE_URL,
    NVIDIA_NIM_DEFAULT,
    NVIDIA_NIM_MODELS,
    fallback_order,
    get_llm,
    models_catalog,
    resolve_model_id,
)

def test_gemini_is_priority_one_and_exact_models_are_exposed(monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "key")
    for primary in ("gemini", "nvidia", "openrouter", "mistral", "inception", "groq"):
        assert fallback_order(primary)[0] == "gemini"
    catalog = models_catalog()
    assert catalog["available"]["gemini"] is True
    assert sorted(item["id"] for item in catalog["models"] if item["engine"] == "gemini") == [
        f"gemini:{model}" for model in sorted(GEMINI_MODELS)
    ]
    gemini_ids = [item["id"] for item in catalog["models"] if item["engine"] == "gemini"]
    assert gemini_ids.index(f"gemini:{GEMINI_DEFAULT}") == 0
    assert catalog["models"][0]["id"] == f"gemini:{GEMINI_DEFAULT}"
    assert catalog["models"][0]["default"] is True

def test_nvidia_models_are_exposed(monkeypatch):
    monkeypatch.setattr(settings, "nvidia_nim_api_key", "key")
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

def test_nvidia_llm_sends_thinking_off_on_every_nim_model(monkeypatch):
    monkeypatch.setattr(settings, "nvidia_nim_api_key", "fake-nim-key")
    from shared import providers

    class RecordingChatOpenAI:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    monkeypatch.setattr(providers, "ChatOpenAI", RecordingChatOpenAI)
    expected = {"chat_template_kwargs": {"enable_thinking": False}}
    for model in sorted(NVIDIA_NIM_ALLOWLIST):
        llm = get_llm("nvidia", model)
        assert llm is not None
        assert llm.kwargs.get("extra_body") == expected

def test_deepseek_flash_is_routable_on_nim(monkeypatch):
    monkeypatch.setattr(settings, "nvidia_nim_api_key", "key")
    from shared.providers import is_free_model
    assert resolve_model_id("nvidia:deepseek-ai/deepseek-v4.1-flash") == ("nvidia", "deepseek-ai/deepseek-v4.1-flash")
    assert is_free_model("nvidia", "deepseek-ai/deepseek-v4.1-flash") is True
