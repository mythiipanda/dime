from app.providers import fallback_order, models_catalog, resolve_model_id


def test_every_runtime_fallback_chain_is_free_only():
    for primary in ("openrouter", "mistral", "inception", "groq"):
        assert fallback_order(primary) in (["openrouter", "mistral"],
                                            ["mistral", "openrouter"])
        assert not ({"inception", "groq"} & set(fallback_order(primary)))


def test_paid_model_ids_clamp_to_free_default():
    assert resolve_model_id("inception:mercury-2.5")[0] in {"openrouter", "mistral"}
    assert resolve_model_id("groq:anything")[0] in {"openrouter", "mistral"}


def test_catalog_exposes_only_free_runtime_choices():
    catalog = models_catalog()
    assert set(catalog["available"]) == {"openrouter", "mistral"}
    assert all(item["engine"] in {"openrouter", "mistral"}
               for item in catalog["models"])
