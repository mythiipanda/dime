"""Two providers. One dict. Ordered fallback. No discovery, no wrapper class.

Graph nodes receive a built ChatOpenAI and never parse model strings.
Routes clamp the model id at the boundary before anything else runs.
"""

from typing import Any, Literal
from langchain_core.messages import BaseMessage
from langchain_openai import ChatOpenAI

from .config import settings

ProviderName = Literal["mistral", "openrouter"]

MISTRAL_DEFAULT = "ministral-8b-2512"
OPENROUTER_DEFAULT = "nvidia/nemotron-3-super-120b-a12b:free"
OPENROUTER_AUTO = "openrouter/free"

OPENROUTER_ALLOWLIST: frozenset[str] = frozenset(
    {
        "nvidia/nemotron-3-super-120b-a12b:free",
        "google/gemma-4-31b-it:free",
        "nvidia/nemotron-3.5-lightning:free",
    }
)


def resolve_model_id(model_id: str | None) -> tuple[ProviderName, str]:
    """Clamp a raw model string to one provider plus one allowed model."""
    raw = (model_id or "").strip()
    if raw.startswith("openrouter:"):
        slug = raw.split(":", 1)[1]
        if slug == OPENROUTER_AUTO or slug in OPENROUTER_ALLOWLIST:
            return ("openrouter", slug)
        return ("openrouter", settings.openrouter_model or OPENROUTER_DEFAULT)
    if raw.startswith("mistral:"):
        slug = raw.split(":", 1)[1] or settings.mistral_model
        return ("mistral", slug)
    if raw:
        if ":free" in raw or "/" in raw:
            if raw == OPENROUTER_AUTO or raw in OPENROUTER_ALLOWLIST:
                return ("openrouter", raw)
            return ("openrouter", settings.openrouter_model or OPENROUTER_DEFAULT)
        return ("mistral", settings.mistral_model or MISTRAL_DEFAULT)
    return ("mistral", settings.mistral_model or MISTRAL_DEFAULT)


def get_llm(name: ProviderName, model: str | None = None) -> ChatOpenAI | None:
    if name == "mistral":
        if not settings.mistral_api_key:
            return None
        return ChatOpenAI(
            model=model or settings.mistral_model or MISTRAL_DEFAULT,
            base_url="https://api.mistral.ai/v1",
            api_key=settings.mistral_api_key,
            timeout=settings.llm_timeout_s,
            max_retries=settings.llm_max_retries,
        )
    if not settings.openrouter_api_key:
        return None
    return ChatOpenAI(
        model=model or settings.openrouter_model or OPENROUTER_DEFAULT,
        base_url="https://openrouter.ai/api/v1",
        api_key=settings.openrouter_api_key,
        timeout=settings.llm_timeout_s,
        max_retries=settings.llm_max_retries,
        default_headers={
            "HTTP-Referer": "https://github.com/mythiipanda/dime",
            "X-Title": "Dime NBA Analyst",
        },
    )


def fallback_order(primary: ProviderName) -> list[ProviderName]:
    return [primary, "openrouter" if primary == "mistral" else "mistral"]


async def invoke_with_fallback(
    primary: ProviderName,
    model: str,
    messages: list[BaseMessage],
    **kwargs: Any,
) -> Any:
    """Try providers in order. Raise the last error only if all fail."""
    errors: list[str] = []
    for name in fallback_order(primary):
        client = get_llm(name, model if name == primary else None)
        if client is None:
            errors.append(f"{name}: missing key")
            continue
        try:
            return await client.ainvoke(messages, **kwargs)
        except Exception as exc:
            errors.append(f"{name}: {str(exc)[:160]}")
    raise RuntimeError("all providers failed: " + " | ".join(errors))


async def astream_with_fallback(
    primary: ProviderName,
    model: str,
    messages: list[BaseMessage],
    **kwargs: Any,
):
    """Yield text chunks, trying providers in order. One provider streams."""
    errors: list[str] = []
    for name in fallback_order(primary):
        client = get_llm(name, model if name == primary else None)
        if client is None:
            errors.append(f"{name}: missing key")
            continue
        try:
            async for chunk in client.astream(messages, **kwargs):
                text = getattr(chunk, "content", "") or ""
                if text:
                    yield {"provider": name, "text": str(text)}
            return
        except Exception as exc:
            errors.append(f"{name}: {str(exc)[:160]}")
    raise RuntimeError("all providers failed: " + " | ".join(errors))


def models_catalog() -> dict[str, Any]:
    options = [
        {
            "id": f"mistral:{settings.mistral_model or MISTRAL_DEFAULT}",
            "engine": "mistral",
            "default": True,
        }
    ]
    for slug in sorted(OPENROUTER_ALLOWLIST):
        options.append({"id": f"openrouter:{slug}", "engine": "openrouter"})
    options.append({"id": f"openrouter:{OPENROUTER_AUTO}", "engine": "openrouter"})
    available = {
        "mistral": bool(settings.mistral_api_key),
        "openrouter": bool(settings.openrouter_api_key),
    }
    return {"models": options, "available": available}
