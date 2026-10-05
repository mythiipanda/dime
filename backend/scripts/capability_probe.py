#!/usr/bin/env python3
"""Measure every declared endpoint once per rung and rewrite the table.

The capability table answers one question per rung: has a probe seen this
endpoint take it? Whatever the probe could not settle is written as
``unmeasured``, which the adapter reads as no support, so no endpoint inherits
a rung nobody witnessed. Credentials come from the loaded settings and are
never printed, logged, or written into the table.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Sequence

import httpx

BACKEND = Path(__file__).resolve().parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from shared.config import settings
from shared.providers import (
    GEMINI_BASE_URL,
    INCEPTION_DEFAULT,
    NVIDIA_NIM_BASE_URL,
    _gemini_model,
    _groq_free_model,
    _mistral_free_model,
    _nvidia_nim_model,
    _openrouter_free_model,
)
from v2.adapters.structured import (
    CAPABILITY_TABLE_PATH,
    FailureKind,
    OutputStrategy,
    Support,
    classify_failure,
    load_capability_table,
    normalize_endpoint,
    wire_schema_for,
)
from v2.contracts import TaskSpec

PROBE = "capability_probe"
PROMPT = ("Record the request 'compare the 2023-24 Celtics and Nuggets "
          "offensive ratings' as a task.")
FLAGS = ("strict_json_schema", "tool_calling", "strict_tool_definitions")


@dataclass(frozen=True)
class Target:
    provider: str
    base_url: str
    model: str
    credential: str
    thinking_off: bool = False

    @property
    def endpoint(self) -> str:
        return normalize_endpoint(self.base_url)

    @property
    def headers(self) -> dict[str, str]:
        if self.provider != "openrouter":
            return {}
        return {"HTTP-Referer": "https://github.com/mythiipanda/dime",
                "X-Title": "Dime NBA Analyst"}

    def api_key(self) -> str:
        return str(getattr(settings, self.credential, "") or "").strip()


def declared_targets() -> tuple[Target, ...]:
    """One target per endpoint the adapter may route a stage to."""
    return (
        Target("gemini", GEMINI_BASE_URL, _gemini_model(), "gemini_api_key"),
        Target("nvidia", NVIDIA_NIM_BASE_URL, _nvidia_nim_model(),
               "nvidia_nim_api_key", thinking_off=True),
        Target("mistral", "https://api.mistral.ai/v1", _mistral_free_model(),
               "mistral_api_key"),
        Target("openrouter", "https://openrouter.ai/api/v1",
               _openrouter_free_model(), "openrouter_api_key"),
        Target("inception", "https://api.inceptionlabs.ai/v1",
               settings.inception_model or INCEPTION_DEFAULT, "inception_api_key"),
        Target("groq", "https://api.groq.com/openai/v1", _groq_free_model(),
               "groq_api_key"),
    )


def strict_request(model: str) -> dict[str, Any]:
    return {
        "model": model,
        "messages": [{"role": "user", "content": PROMPT}],
        "response_format": {"type": "json_schema", "json_schema": {
            "name": "task_spec", "strict": True, "schema": wire_schema_for(
                OutputStrategy.STRICT_SCHEMA,
                TaskSpec.model_json_schema()).schema}},
        "temperature": 0,
    }


def tool_request(model: str, *, strict: bool) -> dict[str, Any]:
    function: dict[str, Any] = {
        "name": "task_spec", "parameters": wire_schema_for(
            OutputStrategy.TOOL_CALL, TaskSpec.model_json_schema()).schema}
    if strict:
        function["strict"] = True
    return {
        "model": model,
        "messages": [{"role": "user", "content": PROMPT}],
        "tools": [{"type": "function", "function": function}],
        "tool_choice": "required",
        "temperature": 0,
    }


def took_the_rung(body: httpx.Response, strategy: OutputStrategy) -> bool:
    try:
        message = body.json()["choices"][0]["message"]
    except (ValueError, KeyError, IndexError, TypeError):
        return False
    if strategy is OutputStrategy.TOOL_CALL:
        return bool(message.get("tool_calls"))
    return isinstance(message.get("content"), str)


def support_for(body: httpx.Response,
                strategy: OutputStrategy) -> tuple[Support, str]:
    if body.status_code == 200 and took_the_rung(body, strategy):
        return Support.MEASURED, "accepted"
    kind = classify_failure(status_code=body.status_code, detail=body.text[:400])
    if kind is FailureKind.SCHEMA_REJECTED:
        return Support.REFUSED, kind.value
    return Support.UNMEASURED, kind.value


async def ask(client: httpx.AsyncClient, target: Target, request: dict[str, Any],
              strategy: OutputStrategy, timeout_s: float
              ) -> tuple[Support, str, float]:
    payload = dict(request)
    if target.thinking_off:
        payload["extra_body"] = {
            "chat_template_kwargs": {"enable_thinking": False}}
    started = time.monotonic()
    try:
        body = await client.post(
            f"{target.base_url.rstrip('/')}/chat/completions", json=payload,
            headers={"Authorization": f"Bearer {target.api_key()}",
                     **target.headers},
            timeout=timeout_s)
    except httpx.HTTPError as exc:
        return Support.UNMEASURED, type(exc).__name__, 0.0
    support, detail = support_for(body, strategy)
    return support, detail, round(time.monotonic() - started, 1)


async def measure(target: Target, client: httpx.AsyncClient,
                  timeout_s: float) -> tuple[dict[str, Support], list[str]]:
    flags: dict[str, Support] = {}
    trail: list[str] = []

    async def probe(flag: str, request: dict[str, Any],
                    strategy: OutputStrategy) -> Support:
        support, detail, seconds = await ask(
            client, target, request, strategy, timeout_s)
        trail.append(f"{flag}={support.value}/{detail}/{seconds}s")
        return support

    flags["strict_json_schema"] = await probe(
        "strict_json_schema", strict_request(target.model),
        OutputStrategy.STRICT_SCHEMA)
    flags["tool_calling"] = await probe(
        "tool_calling", tool_request(target.model, strict=False),
        OutputStrategy.TOOL_CALL)
    if flags["tool_calling"] is Support.MEASURED:
        flags["strict_tool_definitions"] = await probe(
            "strict_tool_definitions",
            tool_request(target.model, strict=True), OutputStrategy.TOOL_CALL)
    elif flags["tool_calling"] is Support.REFUSED:
        flags["strict_tool_definitions"] = Support.REFUSED
    else:
        flags["strict_tool_definitions"] = Support.UNMEASURED
    return flags, trail


def row_for(target: Target, entry: dict[str, Any], flags: dict[str, Support],
            measured_at: str) -> dict[str, Any]:
    row = {"base_url": entry["base_url"],
           **{flag: flags[flag].value for flag in FLAGS}}
    if any(support is not Support.UNMEASURED
           for support in flags.values()):
        row["measurement"] = {"probe": PROBE, "measured_at": measured_at,
                              "models": [target.model]}
    return row


STRENGTH: dict[Support, int] = {
    Support.UNMEASURED: 0, Support.REFUSED: 1, Support.MEASURED: 2}


def merge_row(kept: dict[str, Any] | None, observed: dict[str, Any]
              ) -> dict[str, Any]:
    """The strongest evidence either the table or this run holds.

    A probe that times out, hits a rate limit, or meets an expired credential
    says nothing about the endpoint, so it must not erase what a previous
    probe witnessed. A rung only ever moves from unmeasured to an observed
    answer, and the strongest observed answer wins.
    """
    if kept is None:
        return observed
    merged = dict(observed)
    for flag in FLAGS:
        if STRENGTH[Support(kept[flag])] > STRENGTH[Support(observed[flag])]:
            merged[flag] = kept[flag]
    older, newer = kept.get("measurement"), observed.get("measurement")
    if older is None:
        return merged
    if newer is None:
        merged["measurement"] = older
        return merged
    merged["measurement"] = {**newer, "models": sorted(
        {*older["models"], *newer["models"]})}
    return merged


async def run(timeout_s: float, out: Path) -> int:
    measured_at = datetime.now(UTC).date().isoformat()
    known = load_capability_table(CAPABILITY_TABLE_PATH)
    entries = json.loads(CAPABILITY_TABLE_PATH.read_text())["endpoints"]
    targets = {target.endpoint: target for target in declared_targets()}
    rows: list[dict[str, Any]] = []
    async with httpx.AsyncClient() as client:
        for entry in entries:
            endpoint = normalize_endpoint(str(entry["base_url"]))
            target = targets.get(endpoint)
            if target is None:
                print(f"{endpoint:58s} no probe target, left as declared")
                rows.append(entry)
                continue
            if not target.api_key():
                print(f"{target.provider:11s} {target.model:44s} no credential "
                      "configured, left as measured")
                rows.append(entry)
                continue
            flags, trail = await measure(target, client, timeout_s)
            fresh = row_for(target, entry, flags, measured_at)
            rows.append(merge_row(entry, fresh))
            print(f"{target.provider:11s} {target.model:44s} "
                  + "  ".join(trail))
    out.write_text(json.dumps({"endpoints": rows}, indent=2) + "\n")
    load_capability_table(out)
    print(f"wrote {out}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout-s", type=float, default=600.0)
    parser.add_argument("--out", type=Path, default=CAPABILITY_TABLE_PATH)
    parsed = parser.parse_args(argv)
    return asyncio.run(run(parsed.timeout_s, parsed.out))


if __name__ == "__main__":
    raise SystemExit(main())
