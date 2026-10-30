"""Python-owned Pi producer. Used by the production chat route."""
from __future__ import annotations

import asyncio
import hashlib
import marshal
import json
import os
import signal
from pathlib import Path
import tempfile
import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict

from v2.api.events import Failure, FinalAnswer, GraphEnd, Token, ToolCall, ToolResult, WorkLog
from v2.api.sse import encode_event


_LOADED_MODULE_CODE_SHA256 = hashlib.sha256(marshal.dumps(__loader__.get_code(__name__))).hexdigest()


class SourceRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ref: uuid.UUID
    callId: str
    tool: Literal["sql_exec", "warehouse_schema"]
    response: dict


async def _stop_worker(proc, env):
    """Ask the Pi worker to settle, then reap its process tree if it stalls."""
    if proc is None or proc.returncode is not None:
        return
    try:
        proc.stdin.write(b'{"type":"cancel"}\n')
        await proc.stdin.drain()
        await asyncio.wait_for(proc.wait(), 5)
    except (BrokenPipeError, ConnectionResetError, asyncio.TimeoutError):
        if os.name == "nt":
            killer = await asyncio.create_subprocess_exec(
                str(Path(env["SystemRoot"]) / "System32" / "taskkill.exe"),
                "/PID", str(proc.pid), "/T", "/F",
                stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
            await killer.wait()
        else:
            os.killpg(proc.pid, signal.SIGKILL)
        await proc.wait()


def resolved_provider(provider, client, *, context_window, max_tokens):
    """Adapt Dime's resolved, policy-checked client; never read a profile or env file here.

    Token limits must come from the caller's supported model metadata.
    This adapter does not establish Pi compatibility with any live provider.
    """
    if client is None:
        raise ValueError("Selected provider is unavailable")
    if client.extra_body:
        raise ValueError("Provider requires request options not yet supported by Pi adapter")
    return {"provider": provider, "model": client.model_name,
            "baseUrl": str(client.openai_api_base),
            "apiKey": client.openai_api_key.get_secret_value(),
            "headers": client.default_headers or {},
            "contextWindow": context_window, "maxTokens": max_tokens}


def _save_exchange(conversations, store, client, thread, q, answer, run_id):
    previous = conversations.references(client, thread)
    store.save_chat(thread, "ai", answer, owner=client[:80])
    store.save_run(thread, q[:2000], answer, [], [], owner=client[:80], run_id=run_id)
    conversations.append_exchange(client, thread, q[:2000], answer[:2000],
                                  run_id=run_id, turn_id=run_id)
    if previous:
        conversations.create_branch(client, thread, previous[-1].sequence)


async def stream_product_session(*, q, model, node, python, env, warehouse,
                                 private_root, sources_dir, conversations, store,
                                 client=None, thread=None, history=(),
                                 worker=None, run_id=None):
    """Yield frontend SSE. The caller owns HTTP cancellation and the product stores.

    `env` is an explicit isolated environment, not inherited from this process.
    Source files are product evidence artifacts, never Pi conversation snapshots.
    """
    if (client is None) != (thread is None):
        raise ValueError("client and thread must travel together")
    run_id = run_id or f"run-{uuid.uuid4().hex}"
    proc = None
    answer = None
    failure = None
    from analyst.sources import prior_sources, source_refs
    records = []
    new_records = []
    streamed = False
    closed = False
    try:
        records = prior_sources(conversations, sources_dir, client, thread) if client else []
        context = conversations.read(client, thread) if client is not None else list(history)[-8:]
        context = [turn.model_dump() if hasattr(turn, "model_dump") else turn for turn in context]
        Path(private_root).mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=private_root, prefix="pi-") as directory:
            agent_dir = Path(directory) / "agent"
            agent_dir.mkdir()
            # Python dependencies require a home; keep it inside the owned session.
            env = {**env, "HOME": directory, "USERPROFILE": directory,
                   "TEMP": directory, "TMP": directory}
            try:
                if client is not None:
                    store.save_chat(thread, "human", q[:2000], owner=client[:80])
                proc = await asyncio.create_subprocess_exec(
                    node, str(worker or Path(__file__).with_name("worker.mjs")),
                    cwd=directory, env=env, stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
                    start_new_session=os.name != "nt",
                    limit=1024 * 1024)
                start = {"type": "start", "q": q, "history": context,
                         "model": model, "sources": records, "cwd": directory, "agentDir": str(agent_dir),
                         "bridge": {"python": python, "cwd": directory,
                                    "env": {**env, "DIME_WAREHOUSE": str(warehouse)}}}
                proc.stdin.write((json.dumps(start) + "\n").encode())
                await proc.stdin.drain()
                while line := await proc.stdout.readline():
                    event = json.loads(line)
                    kind = event["type"]
                    if kind == "source":
                        record = SourceRecord.model_validate(event["record"]).model_dump(mode="json")
                        records.append(record)
                        new_records.append(record)
                    elif kind in {"tool_call", "tool_result"}:
                        cls = ToolCall if kind == "tool_call" else ToolResult
                        yield encode_event(cls(node="tools", **event))
                    elif kind == "token":
                        streamed = True
                        yield encode_event(Token(text=event["text"]))
                    elif kind == "answer":
                        if answer is not None or failure is not None:
                            raise ValueError("Duplicate worker outcome")
                        answer = FinalAnswer(text=event["text"]).text
                    elif kind == "failure":
                        failure = Failure(**event)
                    elif kind == "closed":
                        closed = True
                    else:
                        raise ValueError("Unknown worker event")
                await proc.wait()
                if proc.returncode or not closed or (answer is None and failure is None):
                    raise RuntimeError("Pi worker ended without a settled outcome")
                if records or failure is None:
                    # Keep successful and failed sources even if the model later fails.
                    target = Path(sources_dir) / f"{run_id}.json"
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with target.open("x", encoding="utf-8") as artifact:
                        json.dump({"run_id": run_id, "sources": new_records,
                                   "source_refs": source_refs(records)}, artifact)
                if failure is None and client is not None:
                    _save_exchange(conversations, store, client, thread, q, answer, run_id)
            finally:
                await _stop_worker(proc, env)
    except asyncio.CancelledError:
        raise
    except Exception:
        failure = Failure(kind="transport", message="Dime could not finish this run.")
    if failure is not None:
        yield encode_event(failure)
    yield encode_event(WorkLog(run_id=run_id, status="partial"))
    if failure is None:
        carry = {"run_id": run_id, "verification": "unassessed", "answer_status": "unassessed",
                 "source_refs": source_refs(records)}
        if not streamed:
            yield encode_event(Token(text=answer))
        yield encode_event(FinalAnswer(text=answer, carry=carry))
    yield encode_event(GraphEnd())
