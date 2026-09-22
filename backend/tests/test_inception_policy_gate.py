from app.config import settings
from app import providers


def _keys(monkeypatch):
    monkeypatch.setattr(settings,"openrouter_api_key","free")
    monkeypatch.setattr(settings,"mistral_api_key","free")
    monkeypatch.setattr(settings,"inception_api_key","retained")


def test_retained_key_is_inert_by_default(monkeypatch):
    _keys(monkeypatch); monkeypatch.setattr(settings,"dime_enable_inception",False)
    assert "inception" not in providers.fallback_order("openrouter")
    assert providers.get_llm("inception") is None
    assert "inception" not in providers.models_catalog()["available"]


def test_explicit_policy_reactivates_inception(monkeypatch):
    _keys(monkeypatch); monkeypatch.setattr(settings,"dime_enable_inception",True)
    seen=[]
    monkeypatch.setattr(providers,"ChatOpenAI",lambda **kw: seen.append(kw) or object())
    assert providers.fallback_order("inception")[0] == "nvidia"
    assert providers.resolve_model_id("inception:any") == (
        "inception", settings.inception_model)
    assert providers.get_llm("inception") is not None
    assert seen[0]["model"] == settings.inception_model
    catalog=providers.models_catalog()
    assert catalog["available"]["inception"] is True
    assert any(m["engine"]=="inception" for m in catalog["models"])


def test_flag_without_key_cannot_activate(monkeypatch):
    monkeypatch.setattr(settings,"dime_enable_inception",True)
    monkeypatch.setattr(settings,"inception_api_key","")
    assert "inception" not in providers.active_provider_order()
    assert providers.get_llm("inception") is None
