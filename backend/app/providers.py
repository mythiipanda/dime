"""Two providers. One dict. Ordered fallback. No discovery, no wrapper class.

Graph nodes receive a built ChatOpenAI and never parse model strings.
Routes clamp the model id at the boundary before anything else runs.
"""

from typing import Any, Literal
from dataclasses import dataclass
import time
import json
from langchain_core.messages import BaseMessage
from langchain_openai import ChatOpenAI

from .config import settings

ProviderName = Literal["mistral", "openrouter", "inception", "groq"]

# Owner-selected zero-paid-credit policy. Inception and Groq remain parseable
# for old persisted model ids, but are never selected or attempted.
FREE_PROVIDER_ORDER: tuple[ProviderName, ...] = ("openrouter", "mistral")

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


def is_free_model(provider: str, slug: str) -> bool:
    """One authority for whether a Dime model can incur zero paid credits."""
    value = str(slug or "").strip()
    if provider == "openrouter":
        return value == OPENROUTER_AUTO or (
            value in OPENROUTER_ALLOWLIST and value.endswith(":free"))
    if provider == "mistral":
        # Mistral ids do not carry pricing. The configured owner-approved
        # free-limit model is the only active choice for this provider.
        return value == (settings.mistral_model or MISTRAL_DEFAULT)
    return False


def _openrouter_free_model(slug: str | None = None) -> str:
    value = str(slug or settings.openrouter_model or "").strip()
    if value in OPENROUTER_ALLOWLIST and is_free_model("openrouter", value):
        return value
    if value == OPENROUTER_AUTO:
        return value
    return OPENROUTER_DEFAULT


def _mistral_free_model() -> str:
    return settings.mistral_model or MISTRAL_DEFAULT


def _default_provider() -> tuple[ProviderName, str]:
    if settings.openrouter_api_key:
        return ("openrouter", _openrouter_free_model())
    return ("mistral", _mistral_free_model())


def resolve_model_id(model_id: str | None) -> tuple[ProviderName, str]:
    """Clamp every boundary value to an owner-approved free model."""
    raw = (model_id or "").strip()
    if raw.startswith("openrouter:"):
        slug = raw.split(":", 1)[1]
        return ("openrouter", _openrouter_free_model(slug))
    if raw.startswith("mistral:"):
        return ("mistral", _mistral_free_model())
    if raw.startswith("inception:") or raw.startswith("groq:"):
        return _default_provider()
    if raw:
        if raw == OPENROUTER_AUTO or (raw in OPENROUTER_ALLOWLIST
                                      and is_free_model("openrouter", raw)):
            return ("openrouter", raw)
        if "/" in raw or ":free" in raw:
            return ("openrouter", _openrouter_free_model(raw))
        return _default_provider()
    return _default_provider()


def get_llm(name: ProviderName, model: str | None = None) -> ChatOpenAI | None:
    # Configured credentials are not activation. Future reactivation needs an
    # explicit policy change here; direct callers cannot bypass route clamping.
    if name not in FREE_PROVIDER_ORDER:
        return None
    if name == "mistral":
        if not settings.mistral_api_key:
            return None
        return ChatOpenAI(
            model=_mistral_free_model(),
            base_url="https://api.mistral.ai/v1",
            api_key=settings.mistral_api_key,
            timeout=settings.llm_timeout_s,
            max_retries=settings.llm_max_retries,
        )
    if not settings.openrouter_api_key:
        return None
    return ChatOpenAI(
        model=_openrouter_free_model(model),
        base_url="https://openrouter.ai/api/v1",
        api_key=settings.openrouter_api_key,
        timeout=settings.llm_timeout_s,
        max_retries=settings.llm_max_retries,
        default_headers={
            "HTTP-Referer": "https://github.com/mythiipanda/dime",
            "X-Title": "Dime NBA Analyst",
        },
    )



@dataclass(frozen=True)
class ProviderInvocation:
    """Accepted response plus bounded provider provenance."""
    response: Any
    provider: ProviderName
    model: str
    elapsed_ms: int
    provider_attempts: tuple[dict[str, Any], ...]

    @property
    def content(self) -> Any:
        return getattr(self.response, "content", None)

    def __getattr__(self, name: str) -> Any:
        return getattr(self.response, name)


def _failure_class(exc: BaseException) -> str:
    name = type(exc).__name__.casefold(); detail = str(exc).casefold()
    if "timeout" in name or "timed out" in detail: return "timeout"
    if any(code in detail for code in ("500", "502", "503", "504")): return "server_error"
    if "429" in detail or "rate" in name or "rate limit" in detail: return "rate_limit"
    if "connect" in name or "network" in detail: return "network"
    if "401" in detail or "403" in detail or "auth" in name: return "authentication"
    return "provider_error"

def fallback_order(primary: ProviderName) -> list[ProviderName]:
    """Free-only provider order; never attempt paid/exhausted providers."""
    allowed = list(FREE_PROVIDER_ORDER)
    if primary not in allowed:
        primary = allowed[0]
    return [primary, *(name for name in allowed if name != primary)]


# --- Provider probes (qm pattern: verify, don't assume) -------------
# A provider that errors in the fallback chain gets probed with a tiny
# synthetic request (never user data); a fresh FAILED probe skips it in
# later fallbacks until the TTL expires and it earns a retry. Silent
# provider drift (quota exhausted, model renamed) used to surface as
# slow turns failing through the whole chain one by one.
_PROBE_TTL_S = 600.0
_probe_state: dict[str, tuple[bool, float]] = {}


def probe_verdict(name: str) -> bool | None:
    """True/False from a fresh probe; None when unknown or stale."""
    import time as _t

    got = _probe_state.get(name)
    if got is None:
        return None
    ok, ts = got
    return ok if (_t.time() - ts) < _PROBE_TTL_S else None


async def probe_provider(name: ProviderName) -> bool:
    """Synthetic liveness probe: 4 tokens, 8s deadline, no user data."""
    import asyncio as _a
    import time as _t
    from langchain_core.messages import HumanMessage as _HM

    client = get_llm(name)
    if client is None:
        _probe_state[name] = (False, _t.time())
        return False
    try:
        out = await _a.wait_for(
            client.ainvoke([_HM(content="Reply with the single word: ok")],
                           max_tokens=4),
            timeout=8.0)
        ok = bool(getattr(out, "content", "") or "")
    except Exception:
        ok = False
    _probe_state[name] = (ok, _t.time())
    return ok


def note_provider_failure(name: str) -> None:
    """Fire-and-forget probe after a live failure; stale OKs re-probe."""
    import asyncio as _a
    import time as _t

    got = _probe_state.get(name)
    if got is not None and (_t.time() - got[1]) < 60.0:
        return  # already probed in the last minute
    try:
        _a.get_running_loop().create_task(probe_provider(name))
    except RuntimeError:
        pass  # no loop (sync caller): probe happens on next failure


async def invoke_with_fallback(
    primary: ProviderName,
    model: str,
    messages: list[BaseMessage],
    **kwargs: Any,
) -> ProviderInvocation:
    """Try providers in order; return response with bounded provenance."""
    attempts: list[dict[str, Any]] = []
    started_all = time.perf_counter()
    for number, name in enumerate(fallback_order(primary), 1):
        accepted_model = (
            _openrouter_free_model(model if name == primary else None)
            if name == "openrouter" else _mistral_free_model()
        )
        verdict = probe_verdict(name)
        if verdict is False:
            attempts.append({"provider": name, "model": accepted_model,
                "attempt_number": number, "message_class": "probe_failed",
                "latency_ms": 0})
            continue
        client = get_llm(name, accepted_model)
        if client is None:
            attempts.append({"provider": name, "model": accepted_model,
                "attempt_number": number, "message_class": "missing_key",
                "latency_ms": 0})
            continue
        started = time.perf_counter()
        try:
            response = await client.ainvoke(messages, **kwargs)
            return ProviderInvocation(response=response, provider=name,
                model=accepted_model,
                elapsed_ms=int((time.perf_counter() - started_all) * 1000),
                provider_attempts=tuple(attempts))
        except Exception as exc:
            attempts.append({"provider": name, "model": accepted_model,
                "attempt_number": number, "exception_type": type(exc).__name__,
                "message_class": _failure_class(exc),
                "latency_ms": int((time.perf_counter() - started) * 1000)})
            note_provider_failure(name)
    detail = " | ".join(
        f"{a['provider']}:{a['message_class']}" for a in attempts)
    raise RuntimeError("all providers failed: " + detail)


async def astream_with_fallback(
    primary: ProviderName,
    model: str,
    messages: list[BaseMessage],
    **kwargs: Any,
):
    """Yield text chunks, trying providers in order. One provider streams."""
    errors: list[str] = []
    for name in fallback_order(primary):
        verdict = probe_verdict(name)
        if verdict is False:
            errors.append(f"{name}: probe failed recently")
            continue
        accepted_model = (
            _openrouter_free_model(model if name == primary else None)
            if name == "openrouter" else _mistral_free_model()
        )
        client = get_llm(name, accepted_model)
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
            note_provider_failure(name)
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
        verdict = probe_verdict(name)
        if verdict is False:
            errors.append(f"{name}: probe failed recently")
            continue
        accepted_model = (
            _openrouter_free_model(model if name == primary else None)
            if name == "openrouter" else _mistral_free_model()
        )
        client = get_llm(name, accepted_model)
        if client is None:
            errors.append(f"{name}: missing key")
            continue
        try:
            async for chunk in client.astream(messages, **kwargs):
                yield {"provider": name, "chunk": chunk}
            return
        except Exception as exc:
            errors.append(f"{name}: {str(exc)[:160]}")
            note_provider_failure(name)
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
    """Expose only model options accepted by the same free-model predicate."""
    default_id = f"{_default_provider()[0]}:{_default_provider()[1]}"
    slugs = sorted(slug for slug in OPENROUTER_ALLOWLIST
                   if is_free_model("openrouter", slug))
    options = [
        {"id": f"openrouter:{slug}", "engine": "openrouter",
         "default": default_id == f"openrouter:{slug}"}
        for slug in slugs
    ]
    if is_free_model("openrouter", OPENROUTER_AUTO):
        options.append({"id": f"openrouter:{OPENROUTER_AUTO}",
                        "engine": "openrouter",
                        "default": default_id == f"openrouter:{OPENROUTER_AUTO}"})
    mistral = _mistral_free_model()
    if is_free_model("mistral", mistral):
        options.append({"id": f"mistral:{mistral}", "engine": "mistral",
                        "default": default_id == f"mistral:{mistral}"})
    return {"models": options, "available": {
        "openrouter": bool(settings.openrouter_api_key),
        "mistral": bool(settings.mistral_api_key),
    }}
