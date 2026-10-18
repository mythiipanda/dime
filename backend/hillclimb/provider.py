from __future__ import annotations

import copy
import json
import os
import time
import urllib.error
import urllib.request


class ProviderError(RuntimeError):
    def __init__(self, message: str, evidence: dict | None = None):
        super().__init__(message)
        self.evidence = evidence or {}


CLOUD_CONTEXT = 131072
CLOUD_TOKEN_FIELD = "max_completion_tokens"

CLOUD_CONFIGS = {
    "cerebras:gpt-oss-120b": {
        "provider": "cerebras",
        "model": "gpt-oss-120b",
        "base_url": "https://api.cerebras.ai/v1",
        "key_env": "CEREBRAS_API_KEY",
        "context": 65536,
        "token_field": "max_completion_tokens",
    },
    "groq:openai/gpt-oss-120b": {
        "provider": "groq",
        "model": "openai/gpt-oss-120b",
        "base_url": "https://api.groq.com/openai/v1",
        "key_env": "GROQ_API_KEY",
        "context": 131072,
        "token_field": "max_completion_tokens",
    },
    "groq:qwen/qwen3.8-27b": {
        "provider": "groq",
        "model": "qwen/qwen3.8-27b",
        "base_url": "https://api.groq.com/openai/v1",
        "key_env": "GROQ_API_KEY",
        "context": 131072,
        "token_field": "max_completion_tokens",
    },
    "gemini:gemini-3.5-flash": {
        "provider": "gemini",
        "model": "gemini-3.5-flash",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "key_env": "GOOGLE_API_KEY",
        "context": 131072,
        "token_field": "max_completion_tokens",
    },
    "gemini:gemini-3.5-flash-lite": {
        "provider": "gemini",
        "model": "gemini-3.5-flash-lite",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "key_env": "GOOGLE_API_KEY",
        "context": 131072,
        "token_field": "max_completion_tokens",
    },
    "local:Ornith-Q4_K_M": {
        "provider": "local",
        "model": "Ornith-Q4_K_M",
        "base_url": "http://127.0.0.1:8080/v1",
        "key_env": "DIME_LOCAL_API_KEY",
        "context": 65536,
        "token_field": "max_tokens",
    },
    "flm:auto": {
        "provider": "flm",
        "model": "auto",
        "base_url": "https://flm.stonech.at/v1",
        "key_env": None,
        "context": 65536,
        "token_field": "max_tokens",
    },
    "nvidia:nemotron-3.5-super": {
        "provider": "nvidia",
        "model": "nvidia/nemotron-3.5-super-vl-120b-a12b",
        "base_url": "https://integrate.api.nvidia.com/v1",
        "key_env": "NVIDIA_NIM_API_KEY",
        "context": 131072,
        "token_field": "max_tokens",
    },
    "reflection:beam-1": {
        "provider": "reflection",
        "model": "Beam-1.0-501B-A23B",
        "base_url": "https://api.reflection.ai/openai/v1",
        "key_env": "REFLECTION_API_KEY",
        "context": 1048576,
        "token_field": "max_tokens",
    },
}

DEFAULT_PROVIDER_KEY = "cerebras:gpt-oss-120b"


def _active_key() -> str:
    key = (os.environ.get("DIME_CLOUD_PROVIDER") or "").strip()
    if not key:
        return DEFAULT_PROVIDER_KEY
    if key in CLOUD_CONFIGS:
        return key
    raise ProviderError(f"unknown DIME_CLOUD_PROVIDER: {key}")


ACTIVE_PROVIDER_KEY = _active_key()
ACTIVE_CONFIG = CLOUD_CONFIGS[ACTIVE_PROVIDER_KEY]

SERVER_BASE = ACTIVE_CONFIG["base_url"]
MODEL_ID = ACTIVE_CONFIG["model"]
KEY_ENV = ACTIVE_CONFIG["key_env"]

CLOUD_METADATA = {
    "active_provider": ACTIVE_PROVIDER_KEY,
    "providers": dict(CLOUD_CONFIGS),
    "context": CLOUD_CONTEXT,
    "token_field": CLOUD_TOKEN_FIELD,
    "response_format": "json_schema",
}


def _is_cerebras_key(provider_key: str, base: str) -> bool:
    if provider_key.startswith("cerebras"):
        return True
    return base.startswith("https://api.cerebras.ai/v1")


_MAP_SCHEMA_KEYS = frozenset({"properties", "patternProperties", "$defs", "definitions", "dependentSchemas"})
_SINGLE_SCHEMA_KEYS = frozenset({"additionalProperties", "unevaluatedProperties", "items", "contains", "propertyNames", "not", "if", "then", "else", "unevaluatedItems", "contentSchema"})
_LIST_SCHEMA_KEYS = frozenset({"allOf", "anyOf", "oneOf", "prefixItems"})


def _lower_schema_node(node):
    if isinstance(node, bool):
        return node
    if not isinstance(node, dict):
        return copy.deepcopy(node)
    out: dict = {}
    for key, value in node.items():
        if key in ("const", "enum", "default", "examples"):
            continue
        if key in _MAP_SCHEMA_KEYS and isinstance(value, dict):
            rebuilt = {}
            for sub_key, sub_schema in value.items():
                if isinstance(sub_schema, (dict, bool)):
                    rebuilt[sub_key] = _lower_schema_node(sub_schema)
                else:
                    rebuilt[sub_key] = copy.deepcopy(sub_schema)
            out[key] = rebuilt
        elif key in _SINGLE_SCHEMA_KEYS:
            if isinstance(value, (dict, bool)):
                out[key] = _lower_schema_node(value)
            elif key == "items" and isinstance(value, list):
                out[key] = [_lower_schema_node(v) if isinstance(v, (dict, bool)) else copy.deepcopy(v) for v in value]
            else:
                out[key] = copy.deepcopy(value)
        elif key in _LIST_SCHEMA_KEYS and isinstance(value, list):
            out[key] = [_lower_schema_node(v) if isinstance(v, (dict, bool)) else copy.deepcopy(v) for v in value]
        elif key == "items" and isinstance(value, list):
            out[key] = [_lower_schema_node(v) if isinstance(v, (dict, bool)) else copy.deepcopy(v) for v in value]
        else:
            out[key] = copy.deepcopy(value)
    if "const" in node:
        const_value = copy.deepcopy(node["const"])
        if "enum" in node:
            original_enum = copy.deepcopy(node["enum"])
            from jsonschema import Draft202012Validator
            try:
                compatible = Draft202012Validator({"enum": original_enum}).is_valid(const_value)
            except Exception as exc:
                raise ProviderError(f"contradictory const and enum: validation failed: {exc}")
            if compatible:
                out["enum"] = [const_value]
            else:
                raise ProviderError(f"contradictory const and enum: {const_value!r} not in enum")
        else:
            out["enum"] = [const_value]
    elif "enum" in node:
        out["enum"] = copy.deepcopy(node["enum"])
    if "default" in node:
        out["default"] = copy.deepcopy(node["default"])
    if "examples" in node:
        out["examples"] = copy.deepcopy(node["examples"])
    return out


def _wire_descriptor(internal: dict) -> dict:
    lowered = _lower_schema_node(internal["schema"])
    return {
        "name": internal["name"],
        "strict": internal["strict"],
        "schema": {
            "type": "object",
            "properties": {"action": lowered},
            "required": ["action"],
            "additionalProperties": False,
        },
    }


def _reject_constant(value: str):
    raise ValueError(f"non-JSON constant: {value}")


def _loads_no_dup(text: str):
    def hook(pairs):
        obj = {}
        for k, v in pairs:
            if k in obj:
                raise ValueError(f"duplicate key: {k}")
            obj[k] = v
        return obj
    decoder = json.JSONDecoder(object_pairs_hook=hook, parse_constant=_reject_constant)
    idx = 0
    total = len(text)
    while idx < total and text[idx].isspace():
        idx += 1
    if idx >= total:
        raise ValueError("empty document")
    value, end = decoder.raw_decode(text, idx)
    if text[end:].strip() != "":
        raise ValueError("extra data after JSON document")
    return value


def _validate_cerebras_envelope(content: object, internal: dict, wire: dict) -> dict:
    if not isinstance(content, str):
        return _descriptor_error("structured content must be a string", type(content).__name__)
    try:
        parsed = _loads_no_dup(content)
    except ValueError as exc:
        return _descriptor_error("content is not one complete JSON document", str(exc)[:300])
    if not isinstance(parsed, dict):
        return _descriptor_error("envelope must be an object", type(parsed).__name__)
    if set(parsed.keys()) != {"action"}:
        return _descriptor_error("envelope must contain exactly one action field", sorted(parsed.keys()))
    decoded = parsed["action"]
    try:
        from jsonschema import Draft202012Validator
        wire_schema = wire.get("schema") if isinstance(wire, dict) else None
        if not isinstance(wire_schema, dict):
            return _descriptor_error("wire descriptor schema missing", type(wire_schema).__name__)
        wire_validator = Draft202012Validator(wire_schema)
        wire_errors = sorted(wire_validator.iter_errors(parsed), key=lambda e: list(e.path))
        if wire_errors:
            detail = "; ".join(e.message for e in wire_errors)[:1000]
            return _descriptor_error("envelope does not conform to wire schema", detail)
        validator = Draft202012Validator(internal["schema"])
        errors = sorted(validator.iter_errors(decoded), key=lambda e: list(e.path))
        if errors:
            detail = "; ".join(e.message for e in errors)[:1000]
            return _descriptor_error("action does not conform to original schema", detail)
    except ProviderError:
        raise
    except Exception as exc:
        return _descriptor_error("action validation failed", str(exc)[:300])
    return {"ok": True, "wire_parsed": parsed, "decoded_action": decoded}


def _key_env_for_url(url: str) -> str:
    for cfg in CLOUD_CONFIGS.values():
        if url.startswith(cfg["base_url"]):
            return cfg["key_env"] or ""
    return ACTIVE_CONFIG["key_env"] or ""


def _configured_secrets() -> list[str]:
    secrets: list[str] = []
    for cfg in CLOUD_CONFIGS.values():
        key_env = cfg.get("key_env")
        if not key_env:
            continue
        value = os.environ.get(key_env) or ""
        if value:
            secrets.append(value)
    return secrets


def _sanitize_text(text: str) -> tuple[str, bool]:
    redacted = text
    applied = False
    for secret in _configured_secrets():
        if secret and secret in redacted:
            redacted = redacted.replace(secret, "[REDACTED]")
            applied = True
    if "Bearer " in redacted:
        import re as _re
        next_text, count = _re.subn(r"Bearer\s+[A-Za-z0-9_\-\.]+", "Bearer [REDACTED]", redacted)
        if count:
            redacted = next_text
            applied = True
    return redacted, applied


def _redacted_copy(value):
    if isinstance(value, str):
        return _sanitize_text(value)[0]
    if isinstance(value, dict):
        return {k: _redacted_copy(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_redacted_copy(v) for v in value]
    if isinstance(value, tuple):
        return tuple(_redacted_copy(v) for v in value)
    return value


def _ssl_context_for(url: str):
    """Return an SSL context for the given URL.

    flm.stonech.at and api.reflection.ai have expired certificates; skip
    verification for those hosts only. All other hosts use default verification.
    """
    if "flm.stonech.at" in url or "api.reflection.ai" in url:
        import ssl
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx
    return None


def _post(url: str, body: dict, timeout: float) -> tuple[int, str]:
    key_env = _key_env_for_url(url)
    api_key = os.environ.get(key_env) or ""
    data = json.dumps(body).encode("utf-8")
    headers = {"Content-Type": "application/json", "User-Agent": "dime-agent/1.0"}
    if api_key:
        headers["Authorization"] = "Bearer " + api_key
    request = urllib.request.Request(
        url, data=data, method="POST", headers=headers)
    ctx = _ssl_context_for(url)
    try:
        if ctx:
            with urllib.request.urlopen(request, timeout=timeout, context=ctx) as response:
                return response.status, response.read().decode("utf-8", "replace")
        else:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.status, response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")


def _write_journal_line(path: str, entry: dict) -> None:
    line = json.dumps(entry, sort_keys=True, default=str) + "\n"
    line, _ = _sanitize_text(line)
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(line)
        fh.flush()
        os.fsync(fh.fileno())


def _journal_before_send(url: str, body: dict, timeout: float, internal_descriptor: dict | None = None, wire_descriptor: dict | None = None) -> None:
    path = os.environ.get("DIME_CLOUD_JOURNAL") or ""
    if not path:
        raise ProviderError("DIME_CLOUD_JOURNAL missing: fail-closed before HTTP")
    from backend_binding import validate_and_bind_backend, get_backend_root
    try:
        backend_root = get_backend_root()
        prov = validate_and_bind_backend(backend_root)
    except Exception as exc:
        raise ProviderError(f"fail-closed before HTTP: invalid backend binding: {exc}") from exc
    manifest = {
        "backend_root": prov.get("backend_root"),
        "source_hashes": prov.get("source_hashes"),
        "git_commit": prov.get("git_commit"),
        "source_version_hash": prov.get("source_version_hash"),
        "model": body.get("model"),
        "max_completion_tokens": body.get("max_completion_tokens"),
        "temperature": body.get("temperature"),
    }
    entry: dict = {
        "url": url,
        "request_body": body,
        "timeout_s": timeout,
        "ts": time.time(),
        "manifest": manifest,
    }
    if internal_descriptor is not None:
        entry["internal_descriptor"] = internal_descriptor
    if wire_descriptor is not None:
        entry["wire_descriptor"] = wire_descriptor
    _write_journal_line(path, entry)




def _journal_result(entry: dict) -> None:
    path = os.environ.get("DIME_CLOUD_JOURNAL") or ""
    if not path:
        raise ProviderError("DIME_CLOUD_JOURNAL missing: fail-closed on result journal")
    _write_journal_line(path, entry)


def _descriptor_error(message: str, detail: object = None) -> dict:
    return {"ok": False, "message": message, "detail": detail}


def _check_descriptor(descriptor: object) -> dict:
    if not isinstance(descriptor, dict):
        return _descriptor_error("descriptor must be an object")
    name = descriptor.get("name")
    strict = descriptor.get("strict")
    schema = descriptor.get("schema")
    if not isinstance(name, str) or not name:
        return _descriptor_error("descriptor.name must be a non-empty string")
    if not isinstance(strict, bool):
        return _descriptor_error("descriptor.strict must be a boolean")
    if not isinstance(schema, dict):
        return _descriptor_error("descriptor.schema must be an object")
    try:
        from jsonschema import Draft202012Validator
        Draft202012Validator.check_schema(schema)
    except Exception as exc:
        return _descriptor_error("descriptor.schema is not a valid draft 2020-12 schema", str(exc)[:300])
    return {"ok": True}


def _validate_structured_content(content: object, schema: dict) -> dict:
    from jsonschema import Draft202012Validator
    from action_decoder import decode_action_json
    if not isinstance(content, str):
        return _descriptor_error("structured content must be a string", type(content).__name__)
    try:
        parsed = decode_action_json(content)
    except ValueError as exc:
        return _descriptor_error("content is not one complete JSON document", str(exc)[:300])
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(parsed), key=lambda e: list(e.path))
    if errors:
        detail = "; ".join(e.message for e in errors)[:1000]
        return _descriptor_error("content does not conform to descriptor schema", detail)
    return {"ok": True, "parsed": parsed}


class Provider:
    def __init__(self, base: str | None = None, model: str | None = None):
        key = _active_key()
        cfg = CLOUD_CONFIGS[key]
        # Local models need a higher HTTP ceiling: 64k-context prefill on an
        # 8 GB GPU can exceed the cloud-oriented 45 s cap and would otherwise
        # surface as a spurious transport timeout.
        self.http_timeout_cap = 45.0
        if cfg.get("provider") in ("local", "nvidia"):
            self.http_timeout_cap = 180.0
            self.http_timeout_cap = 180.0
        if base is not None and model is not None:
            self.provider_key = key
            self.base = base
            self.model = model
            self.key_env = _key_env_for_url(base)
        elif base is not None:
            self.provider_key = key
            self.base = base
            self.model = cfg["model"]
            self.key_env = _key_env_for_url(base)
        elif model is not None:
            self.provider_key = key
            self.base = cfg["base_url"]
            self.model = model
            self.key_env = cfg["key_env"] or ""
        else:
            self.provider_key = key
            self.config = cfg
            self.base = cfg["base_url"]
            self.model = cfg["model"]
            self.key_env = cfg["key_env"] or ""
            self.chat_url = self.base + "/chat/completions"
            self.context = cfg["context"]
            self.token_field = cfg["token_field"]
            return
        allowed = {(c["base_url"], c["model"]) for c in CLOUD_CONFIGS.values()}
        if (self.base, self.model) not in allowed:
            raise ProviderError(f"custom base/model not an allowed candidate: {self.base} {self.model}")
        self.config = cfg
        self.chat_url = self.base + "/chat/completions"
        self.context = cfg["context"]
        self.token_field = cfg["token_field"]

    def remaining(self, deadline: float) -> float:
        return deadline - time.monotonic()

    def _timeout(self, deadline: float, cap: float) -> float:
        left = self.remaining(deadline)
        if left <= 0:
            raise ProviderError("run deadline exceeded before HTTP call")
        return min(cap, left, self.http_timeout_cap)

    def measure(self, messages: list[dict], deadline: float,
                cap: float = 75.0) -> dict:
        self._timeout(deadline, cap)
        prompt = json.dumps(messages, ensure_ascii=False, default=str)
        prompt_chars = len(prompt)
        utf8_bytes = len(prompt.encode("utf-8"))
        overhead = len(messages) * 32 + 64
        prompt_tokens = utf8_bytes + overhead
        return {
            "prompt": prompt,
            "prompt_chars": prompt_chars,
            "prompt_tokens": prompt_tokens,
            "prompt_tokens_estimate": True,
            "prompt_tokens_method": "conservative_utf8_bytes_plus_message_overhead_upper_bound_estimate",
            "prompt_tokens_utf8_bytes": utf8_bytes,
            "prompt_tokens_overhead": overhead,
            "apply_template_status": "not_available_cloud",
            "tokenize_status": "not_available_cloud",
        }

    def generate(self, messages: list[dict], max_tokens: int, deadline: float,
                 response_format: dict | None = None,
                 cap: float = 75.0) -> dict:
        prompt_text = json.dumps(messages, ensure_ascii=False, default=str)
        prompt_utf8 = len(prompt_text.encode("utf-8"))
        prompt_overhead = len(messages) * 32 + 64
        prompt_estimate = prompt_utf8 + prompt_overhead
        if prompt_estimate + int(max_tokens) > self.context:
            return {
                "url": self.chat_url,
                "model": self.model,
                "retries": 0,
                "outcome": "context_exceeded",
                "prompt_tokens": prompt_estimate,
                "prompt_tokens_estimate": True,
                "prompt_tokens_method": "conservative_utf8_bytes_plus_message_overhead_upper_bound_estimate",
                "prompt_tokens_utf8_bytes": prompt_utf8,
                "prompt_tokens_overhead": prompt_overhead,
                "max_tokens": int(max_tokens),
                "context": self.context,
                "truncation": "none",
            }
        if self.key_env and not (os.environ.get(self.key_env) or ""):
            raise ProviderError(f"{self.key_env} missing: fail-closed before HTTP")
        cerebras = _is_cerebras_key(self.provider_key, self.base) if response_format is not None else False
        gemini = self.base.startswith("https://generativelanguage.googleapis.com") if response_format is not None else False
        internal_descriptor: dict | None = None
        wire_descriptor: dict | None = None
        token_field = self.token_field or "max_completion_tokens"
        body = {
            "model": self.model,
            "messages": messages,
            token_field: int(max_tokens),
            "temperature": 0,
            "stream": False,
        }
        if response_format is not None:
            if gemini:
                internal_descriptor = response_format
                body["response_format"] = {"type": "json_object"}
            elif cerebras:
                internal_descriptor = response_format
                checked = _check_descriptor(internal_descriptor)
                wire_descriptor = _wire_descriptor(internal_descriptor) if checked["ok"] else None
                body["response_format"] = {"type": "json_schema", "json_schema": wire_descriptor} if wire_descriptor is not None else {"type": "json_schema", "json_schema": internal_descriptor}
                if not checked["ok"]:
                    record_pre = {
                        "url": self.chat_url,
                        "model": self.model,
                        "retries": 0,
                        "request_body": body,
                        "outcome": "invalid_response_format",
                        "validation_error": checked["message"],
                        "validation_detail": checked.get("detail"),
                    }
                    return record_pre
            else:
                checked = _check_descriptor(response_format)
                body["response_format"] = {"type": "json_schema", "json_schema": response_format}
                if not checked["ok"]:
                    record_pre = {
                        "url": self.chat_url,
                        "model": self.model,
                        "retries": 0,
                        "request_body": body,
                        "outcome": "invalid_response_format",
                        "validation_error": checked["message"],
                        "validation_detail": checked.get("detail"),
                    }
                    return record_pre
        timeout = self._timeout(deadline, cap)
        _journal_before_send(self.chat_url, body, timeout, internal_descriptor, wire_descriptor)
        started = time.monotonic()
        record = {
            "url": self.chat_url,
            "model": self.model,
            "timeout_s": timeout,
            "retries": 0,
            "request_body": _redacted_copy(body),
        }
        if internal_descriptor is not None:
            record["internal_descriptor"] = _redacted_copy(internal_descriptor)
        if wire_descriptor is not None:
            record["wire_descriptor"] = _redacted_copy(wire_descriptor)
        try:
            status, text = _post(self.chat_url, body, timeout)
        except Exception as exc:
            raw_exc = str(exc)[:300]
            clean_exc, redacted = _sanitize_text(raw_exc)
            update = {
                "outcome": "transport_error",
                "exception_type": type(exc).__name__,
                "exception": clean_exc,
                "elapsed_ms": int((time.monotonic() - started) * 1000),
            }
            if redacted:
                update["sanitized"] = True
            record.update(update)
            _journal_result({
                "url": self.chat_url,
                "model": self.model,
                "outcome": "transport_error",
                "exception_type": type(exc).__name__,
                "exception": clean_exc,
                "response_evidence": {"exception_type": type(exc).__name__},
                "ts": time.time(),
            })
            return record
        clean_text, redacted = _sanitize_text(text)
        record["elapsed_ms"] = int((time.monotonic() - started) * 1000)
        record["status_code"] = status
        record["raw_response_text"] = clean_text
        if redacted:
            record["sanitized"] = True
        try:
            parsed = json.loads(clean_text)
        except ValueError:
            record["outcome"] = "non_json"
            _journal_result({
                "url": self.chat_url,
                "model": self.model,
                "outcome": "non_json",
                "status_code": status,
                "response_evidence": {"status_code": status, "raw_response_text": clean_text[:1000]},
                "ts": time.time(),
            })
            return record
        record["raw_response_body"] = _redacted_copy(parsed)
        if isinstance(parsed, dict) and "error" in parsed:
            record["outcome"] = "http_error"
            _journal_result({
                "url": self.chat_url,
                "model": self.model,
                "outcome": "http_error",
                "status_code": status,
                "response_evidence": {"status_code": status, "raw_response_body": _redacted_copy(parsed)},
                "ts": time.time(),
            })
            return record
        choices = parsed.get("choices") if isinstance(parsed, dict) else None
        first = choices[0] if isinstance(choices, list) and choices else {}
        message = first.get("message") if isinstance(first, dict) else {}
        message = message if isinstance(message, dict) else {}
        record.update({
            "outcome": "chat" if 200 <= status < 300 else "http_error",
            "finish_reason": first.get("finish_reason") if isinstance(first, dict) else None,
            "content": _redacted_copy(message.get("content") or message.get("reasoning_content") or ""),
            "reasoning_content": _redacted_copy(message.get("reasoning_content") or ""),
            "usage": _redacted_copy(parsed.get("usage")) if isinstance(parsed, dict) else None,
        })
        if response_format is not None and record["outcome"] == "chat":
            if cerebras and internal_descriptor is not None and wire_descriptor is not None:
                wire_content = record["content"]
                record["wire_content"] = wire_content
                verdict = _validate_cerebras_envelope(wire_content, internal_descriptor, wire_descriptor)
                if not verdict["ok"]:
                    record["outcome"] = "schema_validation_error"
                    record["validation_error"] = verdict["message"]
                    record["validation_detail"] = verdict.get("detail")
                    _journal_result({
                        "url": self.chat_url,
                        "model": self.model,
                        "outcome": record["outcome"],
                        "validation_error": verdict["message"],
                        "validation_detail": verdict.get("detail"),
                        "wire_content": _redacted_copy(wire_content),
                        "response_evidence": {
                            "finish_reason": record.get("finish_reason"),
                            "usage": record.get("usage"),
                            "status_code": record.get("status_code"),
                        },
                        "ts": time.time(),
                    })
                else:
                    decoded = _redacted_copy(verdict["decoded_action"])
                    record["structured_parsed"] = _redacted_copy(verdict["wire_parsed"])
                    record["decoded_action"] = decoded
                    record["internal_descriptor"] = _redacted_copy(internal_descriptor)
                    record["wire_descriptor"] = _redacted_copy(wire_descriptor)
                    record["content"] = json.dumps(decoded)
                    _journal_result({
                        "url": self.chat_url,
                        "model": self.model,
                        "outcome": "chat",
                        "decoded_action": decoded,
                        "response_evidence": {
                            "finish_reason": record.get("finish_reason"),
                            "usage": record.get("usage"),
                            "status_code": record.get("status_code"),
                        },
                        "ts": time.time(),
                    })
            else:
                verdict = _validate_structured_content(record["content"], response_format["schema"])
                if not verdict["ok"]:
                    record["outcome"] = "schema_validation_error"
                    record["validation_error"] = verdict["message"]
                    record["validation_detail"] = verdict.get("detail")
                    _journal_result({
                        "url": self.chat_url,
                        "model": self.model,
                        "outcome": record["outcome"],
                        "validation_error": verdict["message"],
                        "validation_detail": verdict.get("detail"),
                        "response_evidence": {
                            "finish_reason": record.get("finish_reason"),
                            "usage": record.get("usage"),
                            "status_code": record.get("status_code"),
                        },
                        "ts": time.time(),
                    })
                else:
                    record["structured_parsed"] = _redacted_copy(verdict["parsed"])
                    _journal_result({
                        "url": self.chat_url,
                        "model": self.model,
                        "outcome": "chat",
                        "response_evidence": {
                            "finish_reason": record.get("finish_reason"),
                            "usage": record.get("usage"),
                            "status_code": record.get("status_code"),
                        },
                        "ts": time.time(),
                    })
        else:
            _journal_result({
                "url": self.chat_url,
                "model": self.model,
                "outcome": record["outcome"],
                "status_code": status,
                "response_evidence": {
                    "finish_reason": record.get("finish_reason"),
                    "usage": record.get("usage"),
                    "status_code": status,
                },
                "ts": time.time(),
            })
        return record
