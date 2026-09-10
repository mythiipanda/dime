"""Two providers. One dict. Ordered fallback. No discovery, no wrapper class.

Graph nodes receive a built ChatOpenAI and never parse model strings.
Routes clamp the model id at the boundary before anything else runs.
"""

from typing import Any, Literal
import json
from langchain_core.messages import BaseMessage
from langchain_openai import ChatOpenAI

from .config import settings

ProviderName = Literal["mistral", "openrouter", "inception", "groq"]

MISTRAL_DEFAULT = "ministral-8b-2512"
OPENROUTER_DEFAULT = "nvidia/nemotron-3-super-120b-a12b:free"
OPENROUTER_AUTO = "openrouter/free"
INCEPTION_DEFAULT = "mercury-2.5"
GROQ_DEFAULT = "openai/gpt-oss-20b"

OPENROUTER_ALLOWLIST: frozenset[str] = frozenset(
    {
        "nvidia/nemotron-3-super-120b-a12b:free",
        "google/gemma-4-31b-it:free",
        "nvidia/nemotron-3.5-lightning:free",
    }
)


def _default_provider() -> tuple[ProviderName, str]:
    if settings.inception_api_key:
        return ("inception", settings.inception_model or INCEPTION_DEFAULT)
    if settings.groq_api_key:
        return ("groq", settings.groq_model or GROQ_DEFAULT)
    return ("mistral", settings.mistral_model or MISTRAL_DEFAULT)


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
    if raw.startswith("inception:"):
        slug = raw.split(":", 1)[1] or settings.inception_model
        return ("inception", slug)
    if raw.startswith("groq:"):
        slug = raw.split(":", 1)[1] or settings.groq_model
        return ("groq", slug)
    if raw:
        if ":free" in raw or "/" in raw:
            if raw == OPENROUTER_AUTO or raw in OPENROUTER_ALLOWLIST:
                return ("openrouter", raw)
            return ("openrouter", settings.openrouter_model or OPENROUTER_DEFAULT)
        return _default_provider()
    return _default_provider()


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
    if name == "inception":
        if not settings.inception_api_key:
            return None
        return ChatOpenAI(
            model=model or settings.inception_model or INCEPTION_DEFAULT,
            base_url="https://api.inceptionlabs.ai/v1",
            api_key=settings.inception_api_key,
            timeout=settings.llm_timeout_s,
            max_retries=settings.llm_max_retries,
        )
    if name == "groq":
        if not settings.groq_api_key:
            return None
        return ChatOpenAI(
            model=model or settings.groq_model or GROQ_DEFAULT,
            base_url="https://api.groq.com/openai/v1",
            api_key=settings.groq_api_key,
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
    rest: list[ProviderName] = ["mistral", "openrouter", "inception", "groq"]
    rest.remove(primary)
    return [primary, *rest]


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


async def astream_chunks_with_fallback(
    primary: ProviderName,
    model: str,
    messages: list[BaseMessage],
    **kwargs: Any,
):
    """Yield raw LangChain chunks, trying providers in order.

    Unlike astream_with_fallback this preserves tool_call_chunks so
    tool-bound calls can stream text tokens live AND still collect
    tool calls. Yields {"provider": name, "chunk": chunk}.
    """
    errors: list[str] = []
    for name in fallback_order(primary):
        client = get_llm(name, model if name == primary else None)
        if client is None:
            errors.append(f"{name}: missing key")
            continue
        try:
            async for chunk in client.astream(messages, **kwargs):
                yield {"provider": name, "chunk": chunk}
            return
        except Exception as exc:
            errors.append(f"{name}: {str(exc)[:160]}")
    raise RuntimeError("all providers failed: " + " | ".join(errors))


def accumulate_tool_calls(tc_chunks: list[dict]) -> list[dict]:
    """Reassemble LangChain tool_call_chunks into [{name, args, id}]."""
    by_idx: dict[int, dict] = {}
    for tc in tc_chunks:
        if not isinstance(tc, dict):
            continue
        try:
            idx = int(tc.get("index", 0) or 0)
        except Exception:
            idx = 0
        e = by_idx.setdefault(idx, {"name": "", "args": "", "id": ""})
        if tc.get("name"):
            e["name"] = tc["name"]
        if tc.get("id"):
            e["id"] = tc["id"]
        args = tc.get("args")
        if args:
            e["args"] += args if isinstance(args, str) else str(args)
    out: list[dict] = []
    for idx in sorted(by_idx):
        e = by_idx[idx]
        try:
            args = json.loads(e["args"] or "{}")
        except Exception:
            args = {}
        if not isinstance(args, dict):
            args = {}
        out.append({"name": e["name"], "args": args, "id": e["id"]})
    return out


def models_catalog() -> dict[str, Any]:
    default_id = f"{_default_provider()[0]}:{_default_provider()[1]}"
    options = [
        {
            "id": f"mistral:{settings.mistral_model or MISTRAL_DEFAULT}",
            "engine": "mistral",
            "default": default_id.startswith("mistral:"),
        }
    ]
    for slug in sorted(OPENROUTER_ALLOWLIST):
        options.append({"id": f"openrouter:{slug}", "engine": "openrouter"})
    options.append({"id": f"openrouter:{OPENROUTER_AUTO}", "engine": "openrouter"})
    options.append({
        "id": f"inception:{settings.inception_model or INCEPTION_DEFAULT}",
        "engine": "inception",
        "default": default_id.startswith("inception:"),
    })
    options.append({
        "id": f"groq:{settings.groq_model or GROQ_DEFAULT}",
        "engine": "groq",
        "default": default_id.startswith("groq:"),
    })
    available = {
        "mistral": bool(settings.mistral_api_key),
        "openrouter": bool(settings.openrouter_api_key),
        "inception": bool(settings.inception_api_key),
        "groq": bool(settings.groq_api_key),
    }
    return {"models": options, "available": available}
