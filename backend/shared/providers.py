
from typing import Any, Literal
from dataclasses import dataclass
import asyncio
import time
from langchain_core.messages import BaseMessage
from langchain_openai import ChatOpenAI

from .config import settings

ProviderName = Literal["gemini", "nvidia", "mistral", "openrouter", "inception", "groq"]

class ProviderPolicyError(ValueError):
    pass

FREE_PROVIDER_ORDER: tuple[ProviderName, ...] = ("gemini", "nvidia", "groq", "openrouter", "mistral")

def active_provider_order() -> tuple[ProviderName, ...]:
    free = tuple(name for name in FREE_PROVIDER_ORDER if
        name != "groq" or (settings.dime_enable_groq and settings.groq_api_key))
    return ((*free, "inception")
            if settings.dime_enable_inception and settings.inception_api_key
            else free)

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
GEMINI_DEFAULT = "gemini-3.5-flash-lite"
GEMINI_MODELS: tuple[str, ...] = (
    GEMINI_DEFAULT,
    "gemini-3.5-flash",
    "gemini-3.8-flash",
    "gemma-4-31b-it",
)
GEMINI_ALLOWLIST = frozenset(GEMINI_MODELS)
NVIDIA_NIM_BASE_URL = "https://integrate.api.nvidia.com/v1"
NVIDIA_NIM_DEFAULT = "z-ai/glm-5.3-flash"
NVIDIA_NIM_MODELS: tuple[str, ...] = (
    NVIDIA_NIM_DEFAULT,
    "deepseek-ai/deepseek-v4.1-flash",
)
NVIDIA_NIM_ALLOWLIST = frozenset(NVIDIA_NIM_MODELS)
MISTRAL_DEFAULT = "ministral-8b-2512"
OPENROUTER_DEFAULT = "nvidia/nemotron-3-super-120b-a12b:free"
OPENROUTER_AUTO = "openrouter/free"
INCEPTION_DEFAULT = "mercury-2.5"
GROQ_DEFAULT = "openai/gpt-oss-20b"

OPENROUTER_ALLOWLIST: frozenset[str] = frozenset(
    {
        "nvidia/nemotron-3-super-120b-a12b:free",
        "nvidia/nemotron-3-ultra-550b-a55b:free",
    }
)

def is_free_model(provider: str, slug: str) -> bool:
    value = str(slug or "").strip()
    if provider == "gemini":
        return value in GEMINI_ALLOWLIST
    if provider == "nvidia":
        return value in NVIDIA_NIM_ALLOWLIST
    if provider == "openrouter":
        return value == OPENROUTER_AUTO or (
            value in OPENROUTER_ALLOWLIST and value.endswith(":free"))
    if provider == "groq":
        return value == GROQ_DEFAULT
    if provider == "mistral":
        return value == (settings.mistral_model or MISTRAL_DEFAULT)
    return False

def _gemini_model(slug: str | None = None) -> str:
    value = str(slug or settings.gemini_model or "").strip()
    return value if value in GEMINI_ALLOWLIST else GEMINI_DEFAULT

def _nvidia_nim_model(slug: str | None = None) -> str:
    value = str(slug or settings.nvidia_nim_model or "").strip()
    return value if value in NVIDIA_NIM_ALLOWLIST else NVIDIA_NIM_DEFAULT

def _openrouter_free_model(slug: str | None = None) -> str:
    value = str(slug or settings.openrouter_model or "").strip()
    if value in OPENROUTER_ALLOWLIST and is_free_model("openrouter", value):
        return value
    if value == OPENROUTER_AUTO:
        return value
    return OPENROUTER_DEFAULT

def _groq_free_model() -> str:
    value = str(settings.groq_model or "").strip()
    return value if value == GROQ_DEFAULT else GROQ_DEFAULT

def _mistral_free_model() -> str:
    return settings.mistral_model or MISTRAL_DEFAULT

def _default_provider() -> tuple[ProviderName, str]:
    if settings.gemini_api_key:
        return ("gemini", _gemini_model())
    if settings.nvidia_nim_api_key:
        return ("nvidia", _nvidia_nim_model())
    if settings.dime_enable_inception and settings.inception_api_key:
        return ("inception", settings.inception_model or INCEPTION_DEFAULT)
    if settings.dime_enable_groq and settings.groq_api_key:
        return ("groq", _groq_free_model())
    if settings.openrouter_api_key:
        return ("openrouter", _openrouter_free_model())
    return ("mistral", _mistral_free_model())

def resolve_model_id(model_id: str | None) -> tuple[ProviderName, str]:
    original = model_id or ""
    raw = original.strip()
    if original.startswith("groq:"):
        slug = original.split(":", 1)[1]
        if slug != GROQ_DEFAULT:
            raise ProviderPolicyError("unapproved Groq model")
        if not (settings.dime_enable_groq and settings.groq_api_key):
            raise ProviderPolicyError("Groq free-tier route is not activated")
        return ("groq", GROQ_DEFAULT)
    if original.startswith("gemini:"):
        slug = original.split(":", 1)[1]
        if slug.strip() not in GEMINI_ALLOWLIST:
            raise ProviderPolicyError("unapproved Gemini model")
        return ("gemini", slug.strip())
    if raw.startswith("nvidia:"):
        return ("nvidia", _nvidia_nim_model(raw.split(":", 1)[1]))
    if raw.startswith("openrouter:"):
        slug = raw.split(":", 1)[1]
        return ("openrouter", _openrouter_free_model(slug))
    if raw.startswith("mistral:"):
        return ("mistral", _mistral_free_model())
    if raw.startswith("inception:"):
        if settings.dime_enable_inception and settings.inception_api_key:
            return ("inception", settings.inception_model or INCEPTION_DEFAULT)
        return _default_provider()
    if raw:
        if raw in GEMINI_ALLOWLIST:
            return ("gemini", raw)
        if raw in NVIDIA_NIM_ALLOWLIST:
            return ("nvidia", raw)
        if raw == OPENROUTER_AUTO or (raw in OPENROUTER_ALLOWLIST
                                      and is_free_model("openrouter", raw)):
            return ("openrouter", raw)
        if "/" in raw or ":free" in raw:
            return ("openrouter", _openrouter_free_model(raw))
        return _default_provider()
    return _default_provider()

def get_llm(name: ProviderName, model: str | None = None) -> ChatOpenAI | None:
    if name not in active_provider_order():
        return None
    if name == "gemini":
        if not settings.gemini_api_key:
            return None
        return ChatOpenAI(
            model=_gemini_model(model),
            base_url=GEMINI_BASE_URL,
            api_key=settings.gemini_api_key,
            timeout=settings.llm_timeout_s,
            max_retries=settings.llm_max_retries,
        )
    if name == "nvidia":
        if not settings.nvidia_nim_api_key:
            return None
        return ChatOpenAI(
            model=_nvidia_nim_model(model),
            base_url=NVIDIA_NIM_BASE_URL,
            api_key=settings.nvidia_nim_api_key,
            timeout=settings.llm_timeout_s,
            max_retries=settings.llm_max_retries,
            extra_body={"chat_template_kwargs": {"enable_thinking": False}},
        )
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
    if name == "groq":
        if model is not None and model != GROQ_DEFAULT:
            raise ProviderPolicyError("unapproved Groq model")
        if not (settings.dime_enable_groq and settings.groq_api_key):
            return None
        return ChatOpenAI(
            model=_groq_free_model(),
            base_url="https://api.groq.com/openai/v1",
            api_key=settings.groq_api_key,
            timeout=settings.llm_timeout_s,
            max_retries=0,
        )
    if name == "inception":
        return ChatOpenAI(
            model=settings.inception_model or INCEPTION_DEFAULT,
            base_url="https://api.inceptionlabs.ai/v1",
            api_key=settings.inception_api_key,
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
    if "429" in detail or "rate" in name or "rate limit" in detail: return "rate_limit"
    if any(code in detail for code in ("500", "502", "503", "504")): return "server_error"
    if "connect" in name or "network" in detail: return "network"
    if "401" in detail or "403" in detail or "auth" in name: return "authentication"
    return "provider_error"

def fallback_order(primary: ProviderName) -> list[ProviderName]:
    del primary
    return list(active_provider_order())

_PROBE_TTL_S = 600.0
_probe_state: dict[str, tuple[bool, float]] = {}

def probe_verdict(name: str) -> bool | None:
    import time as _t

    got = _probe_state.get(name)
    if got is None:
        return None
    ok, ts = got
    return ok if (_t.time() - ts) < _PROBE_TTL_S else None

async def probe_provider(name: ProviderName) -> bool:
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
    import asyncio as _a
    import time as _t

    got = _probe_state.get(name)
    if got is not None and (_t.time() - got[1]) < 60.0:
        return
    try:
        _a.get_running_loop().create_task(probe_provider(name))
    except RuntimeError:
        pass

async def invoke_with_fallback(
    primary: ProviderName,
    model: str,
    messages: list[BaseMessage],
    **kwargs: Any,
) -> ProviderInvocation:
    attempts: list[dict[str, Any]] = []
    started_all = time.perf_counter()
    for number, name in enumerate(fallback_order(primary), 1):
        accepted_model = (
            _gemini_model(model if name == primary else None)
            if name == "gemini" else
            _nvidia_nim_model(model if name == primary else None)
            if name == "nvidia" else
            _openrouter_free_model(model if name == primary else None)
            if name == "openrouter" else
            _mistral_free_model() if name == "mistral" else
            _groq_free_model() if name == "groq" else
            settings.inception_model or INCEPTION_DEFAULT
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
            response = await ainvoke_with_first_token_timeout(
                client, messages,
                settings.dime_first_token_timeout_s, **kwargs)
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

async def ainvoke_with_first_token_timeout(
    client: Any,
    messages: list[BaseMessage],
    timeout_s: float,
    **kwargs: Any,
):
    return await asyncio.wait_for(
        client.ainvoke(messages, **kwargs), timeout_s)

async def _stream_with_first_token_timeout(
    client: Any,
    messages: list[BaseMessage],
    timeout_s: float,
    **kwargs: Any,
):
    stream = client.astream(messages, **kwargs)
    try:
        first = await asyncio.wait_for(stream.__anext__(), timeout_s)
    except (asyncio.TimeoutError, TimeoutError):
        await _aclose_quietly(stream)
        raise TimeoutError(f"no first token within {timeout_s}s")
    except StopAsyncIteration:
        return
    except BaseException:
        await _aclose_quietly(stream)
        raise
    yield first
    try:
        async for chunk in stream:
            yield chunk
    finally:
        await _aclose_quietly(stream)

async def _aclose_quietly(stream: Any) -> None:
    try:
        aclose = getattr(stream, "aclose", None)
        if aclose is not None:
            await aclose()
    except Exception:
        pass

stream_with_first_token_timeout = _stream_with_first_token_timeout

async def astream_with_fallback(
    primary: ProviderName,
    model: str,
    messages: list[BaseMessage],
    **kwargs: Any,
):
    errors: list[str] = []
    for name in fallback_order(primary):
        verdict = probe_verdict(name)
        if verdict is False:
            errors.append(f"{name}: probe failed recently")
            continue
        accepted_model = (
            _gemini_model(model if name == primary else None)
            if name == "gemini" else
            _nvidia_nim_model(model if name == primary else None)
            if name == "nvidia" else
            _openrouter_free_model(model if name == primary else None)
            if name == "openrouter" else
            _mistral_free_model() if name == "mistral" else
            _groq_free_model() if name == "groq" else
            settings.inception_model or INCEPTION_DEFAULT
        )
        client = get_llm(name, accepted_model)
        if client is None:
            errors.append(f"{name}: missing key")
            continue
        try:
            async for chunk in _stream_with_first_token_timeout(
                    client, messages,
                    settings.dime_first_token_timeout_s, **kwargs):
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
    errors: list[str] = []
    for name in fallback_order(primary):
        verdict = probe_verdict(name)
        if verdict is False:
            errors.append(f"{name}: probe failed recently")
            continue
        accepted_model = (
            _gemini_model(model if name == primary else None)
            if name == "gemini" else
            _nvidia_nim_model(model if name == primary else None)
            if name == "nvidia" else
            _openrouter_free_model(model if name == primary else None)
            if name == "openrouter" else
            _mistral_free_model() if name == "mistral" else
            _groq_free_model() if name == "groq" else
            settings.inception_model or INCEPTION_DEFAULT
        )
        client = get_llm(name, accepted_model)
        if client is None:
            errors.append(f"{name}: missing key")
            continue
        try:
            async for chunk in _stream_with_first_token_timeout(
                    client, messages,
                    settings.dime_first_token_timeout_s, **kwargs):
                yield {"provider": name, "chunk": chunk}
            return
        except Exception as exc:
            errors.append(f"{name}: {str(exc)[:160]}")
            note_provider_failure(name)
    raise RuntimeError("all providers failed: " + " | ".join(errors))



def models_catalog() -> dict[str, Any]:
    default_id = f"{_default_provider()[0]}:{_default_provider()[1]}"
    slugs = sorted(slug for slug in OPENROUTER_ALLOWLIST
                   if is_free_model("openrouter", slug))
    options = [
        {"id": f"gemini:{slug}", "engine": "gemini",
         "default": default_id == f"gemini:{slug}"}
        for slug in GEMINI_MODELS
    ] + [
        {"id": f"nvidia:{slug}", "engine": "nvidia",
         "default": default_id == f"nvidia:{slug}"}
        for slug in NVIDIA_NIM_MODELS
    ] + [
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
    if settings.dime_enable_groq and settings.groq_api_key:
        groq = _groq_free_model()
        options.append({"id": f"groq:{groq}", "engine": "groq",
                        "default": default_id == f"groq:{groq}"})
    if settings.dime_enable_inception and settings.inception_api_key:
        inception = settings.inception_model or INCEPTION_DEFAULT
        options.append({"id": f"inception:{inception}", "engine": "inception",
                        "default": default_id == f"inception:{inception}"})
    available = {
        "gemini": bool(settings.gemini_api_key),
        "nvidia": bool(settings.nvidia_nim_api_key),
        "openrouter": bool(settings.openrouter_api_key),
        "mistral": bool(settings.mistral_api_key),
    }
    if settings.dime_enable_groq and settings.groq_api_key:
        available["groq"] = True
    if settings.dime_enable_inception and settings.inception_api_key:
        available["inception"] = True
    for option in options:
        option["available"] = bool(available.get(option["engine"], False))
    return {"models": options, "available": available}
