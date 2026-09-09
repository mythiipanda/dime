"""HTTP boundary. Parse and clamp here. Graph trusts what it receives."""

import time
from collections import defaultdict
from fastapi import APIRouter, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .graph import run_chat
from .providers import models_catalog
from . import store
from .sse import emit_sse, with_heartbeat
from .config import settings

router = APIRouter()

_hits: dict[str, list[float]] = defaultdict(list)


def _allowed(ip: str) -> bool:
    now = time.time()
    window = [t for t in _hits[ip] if now - t < 60]
    _hits[ip] = window
    if len(window) >= settings.chat_rate_per_minute:
        return False
    window.append(now)
    return True


@router.get("/health")
def health() -> dict:
    catalog = models_catalog()
    return {"ok": True, "providers": catalog["available"]}


@router.get("/models")
def models() -> dict:
    return models_catalog()


@router.get("/resolve")
def resolve(q: str = Query("")) -> dict:
    from .tools import resolve_entity

    return resolve_entity.invoke({"query": q[:80]})


class ChatBody(BaseModel):
    q: str
    model: str | None = None
    thread: str | None = None
    history: list[dict[str, str]] | None = None


async def _stream(
    question: str, model: str | None, thread: str | None = None,
    history: list[dict[str, str]] | None = None,
):
    history = history or (store.chat_history(thread, 6) if thread else [])
    if thread:
        store.save_chat(thread, "human", question[:2000])

    async def gen():
        import json as _json

        final = ""
        tables: list[dict] = []
        suggestions: list[str] = []
        async for event in run_chat(
            question[:2000], (model or "")[:200], history
        ):
            if event["type"] == "final_answer":
                final = str(event["data"].get("text", ""))
            elif event["type"] == "custom_data":
                data = event["data"]
                if isinstance(data.get("tables"), list):
                    tables = data["tables"]
            elif event["type"] == "suggestions":
                items = event["data"].get("items", [])
                if isinstance(items, list):
                    suggestions = [str(i) for i in items]
            yield emit_sse(event["type"], event["data"])
        if thread and final:
            store.save_chat(thread, "ai", final)
            store.save_run(thread, question[:2000], final, tables, suggestions)

    async for chunk in with_heartbeat(gen()):
        yield chunk


@router.get("/threads")
def threads() -> dict:
    return {"threads": store.list_threads()}


class TradeBody(BaseModel):
    team_a: str = ""
    players_a: str = ""
    team_b: str = ""
    players_b: str = ""


@router.post("/trade/check")
def trade_check(body: TradeBody) -> dict:
    from .tools import get_trade_check

    return get_trade_check.invoke({
        "team_a": body.team_a, "players_a": body.players_a,
        "team_b": body.team_b, "players_b": body.players_b,
    })


@router.get("/threads/{thread_id}/runs")
def thread_runs(thread_id: str) -> dict:
    return {"runs": store.list_runs(thread_id)}


@router.get("/threads/{thread_id}/export")
def thread_export(thread_id: str):
    from fastapi.responses import PlainTextResponse

    runs = store.list_runs(thread_id)
    lines = [f"# Dime analysis thread {thread_id}", ""]
    for r in reversed(runs):
        lines.append(f"## Q: {r['question']}")
        lines.append("")
        lines.append(r["answer"] or "")
        lines.append("")
        for t in r["tables"] if isinstance(r["tables"], list) else []:
            if isinstance(t, dict):
                lines.append(f"Source table: {t.get('tool', '?')}")
        lines.append("")
    return PlainTextResponse("\n".join(lines), media_type="text/markdown")


@router.get("/chat/stream")
async def chat_stream_get(
    request: Request, q: str = Query(""), model: str | None = Query(None),
    thread: str | None = Query(None),
):
    ip = request.client.host if request.client else "unknown"
    if not _allowed(ip):
        async def limited():
            yield emit_sse("error", {"message": "rate limited, retry soon"})

        return StreamingResponse(limited(), media_type="text/event-stream")
    return StreamingResponse(_stream(q, model, thread), media_type="text/event-stream")


@router.post("/chat/stream")
async def chat_stream_post(request: Request, body: ChatBody):
    ip = request.client.host if request.client else "unknown"
    if not _allowed(ip):
        async def limited():
            yield emit_sse("error", {"message": "rate limited, retry soon"})

        return StreamingResponse(limited(), media_type="text/event-stream")
    return StreamingResponse(
        _stream(body.q, body.model, body.thread, body.history),
        media_type="text/event-stream",
    )
