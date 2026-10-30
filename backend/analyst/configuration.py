"""Product configuration without profile or credential-file discovery."""
import json
import os
from pathlib import Path


def model_limits(provider, model):
    # Reflection's direct API, not OpenRouter's different output limit.
    # https://developers.reflection.ai/models (2026-10-30)
    if provider == "reflection" and model == "Beam-1.0-501B-A23B":
        return {"context_window": 1048576, "max_tokens": 131072}
    catalogue = Path(__file__).parent / "node_modules/@earendil-works/pi-ai/dist/providers/data"
    name = {"gemini": "google"}.get(provider, provider)
    path = catalogue / f"{name}.json"
    if path.is_file():
        data = json.loads(path.read_text(encoding="utf-8"))
        for models in data.values():
            for entry in models.values():
                if entry["id"] == model:
                    return {"context_window": entry["contextWindow"], "max_tokens": entry["maxTokens"]}
    raise ValueError("Selected model has no supported token metadata")


def worker_environment():
    # Credentials travel only in the stdin descriptor. MCP gets no provider keys.
    names = ("SystemRoot", "WINDIR", "PATH", "LANG", "SSL_CERT_FILE", "SSL_CERT_DIR")
    # The measured default numerical thread pools exceeded the 1 GiB worker cap.
    # Each isolated analysis worker uses one numerical thread.
    return {**{name: os.environ[name] for name in names if name in os.environ},
            "OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1", "POLARS_MAX_THREADS": "1"}


def resolve_product_model(model_id=None):
    from shared.providers import resolve_model_id, get_llm
    from analyst.product_session import resolved_provider

    provider, name = resolve_model_id(model_id or os.environ.get("DIME_V2_MODEL"))
    return resolved_provider(provider, get_llm(provider, name), **model_limits(provider, name))
