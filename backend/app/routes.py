"""HTTP boundary. Parse and clamp here. Graph trusts what it receives."""

import time
from collections import defaultdict
from pathlib import Path
import os
import re
from fastapi import APIRouter, Query, Request
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from .graph import run_chat
from .providers import models_catalog
from . import store
from .sse import emit_sse, with_heartbeat
from .config import settings

router = APIRouter()

CARDS_DIR = Path(__file__).resolve().parent.parent / "data" / "cards"

_DEBATE_FILE_RE = re.compile(r"^debate_[A-Za-z0-9]+_vs_[A-Za-z0-9]+_[0-9]+\.html$")

_hits: dict[str, list[float]] = defaultdict(list)


def _sanitize_sse_event(etype: str, data: dict) -> dict:
    if etype in ("tool_call", "tool_result", "thought_token"):
        # Streaming contract: tool activity + live LLM token events pass
        # through unchanged.
        return data if isinstance(data, dict) else {}
    if etype == "error":
        node = data.get("node") if isinstance(data, dict) else None
        out: dict = {"status": "fail",
                     "message": "Something went wrong, try again"}
        if node:
            out["node"] = node
        return out
    if etype == "message" and isinstance(data, dict):
        if "tool_call" in data or "tool_result" in data or "error" in data:
            node = data.get("node")
            out = {"status": "fail", "rows": 0}
            if node:
                out["node"] = node
            return out
        return {k: data[k] for k in ("node", "label", "status", "rows")
                if k in data}
    return data


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
            yield emit_sse(event["type"],
                           _sanitize_sse_event(event["type"], event["data"]))
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


# --- Today / Watchlist / Movers / Briefing endpoints for frontend ---

@router.get("/today")
async def api_today(season: str = Query("2025-26")):
    from .tools.today import get_today
    import json
    res = get_today.invoke({"season": season})
    return json.loads(res) if isinstance(res, str) else res


@router.get("/watchlist")
async def api_watchlist(season: str = Query("2025-26")):
    from .tools.watchlist import get_watchlist
    import json
    res = get_watchlist.invoke({"season": season})
    return json.loads(res) if isinstance(res, str) else res


class WatchlistBody(BaseModel):
    entity_type: str
    entity_id: str
    season: str = "2025-26"


@router.post("/watchlist")
async def api_watchlist_add(body: WatchlistBody):
    from .tools.watchlist import add_watchlist_item
    import json
    res = add_watchlist_item.invoke({
        "entity_type": body.entity_type,
        "entity_id": body.entity_id,
        "season": body.season,
    })
    return json.loads(res) if isinstance(res, str) else res


@router.delete("/watchlist")
async def api_watchlist_remove(
    entity_type: str = Query(...),
    entity_id: str = Query(...),
):
    from .tools.watchlist import remove_watchlist_item
    import json
    res = remove_watchlist_item.invoke({
        "entity_type": entity_type,
        "entity_id": entity_id,
    })
    return json.loads(res) if isinstance(res, str) else res


@router.get("/movers")
async def api_movers(
    season: str = Query("2025-26"),
    days: int = Query(7, ge=1, le=30),
):
    from .tools.league import get_leaderboard_deltas
    import json
    res = get_leaderboard_deltas.invoke({"season": season, "days": days})
    return json.loads(res) if isinstance(res, str) else res


@router.get("/briefing")
async def api_briefing(season: str = Query("2025-26")):
    from .tools.today import get_morning_briefing
    import json
    res = get_morning_briefing.invoke({"season": season})
    return json.loads(res) if isinstance(res, str) else res


@router.get("/debate-card")
def api_debate_card(
    a: str = Query(""),
    b: str = Query(""),
    season: str = Query("2025-26"),
) -> dict:
    from .tools import get_debate_card
    from .tools._core import clamp_season

    qa = (a or "").strip()[:80]
    qb = (b or "").strip()[:80]
    if not qa or not qb:
        return {"ok": False, "error": "two player names required"}
    clamped = clamp_season(season)
    try:
        res = get_debate_card.invoke({"a": qa, "b": qb, "season": clamped})
    except Exception:
        return {"ok": False, "error": "debate card failed"}
    if not isinstance(res, dict) or not res.get("ok"):
        err = res.get("error", "debate card failed") if isinstance(res, dict) else "debate card failed"
        return {"ok": False, "error": err}
    rows = res.get("rows", {}) if isinstance(res.get("rows"), dict) else {}
    raw_path = str(rows.get("path", ""))
    basename = os.path.basename(raw_path)
    players = rows.get("players", [qa, qb])
    return {
        "ok": True,
        "path": basename,
        "players": players,
        "url": f"/api/v1/debate-card/file?name={basename}",
        "rows": {
            "path": basename,
            "players": players,
            "url": f"/api/v1/debate-card/file?name={basename}",
        },
        "meta": {"season": clamped},
    }


@router.get("/debate-card/file")
def api_debate_card_file(name: str = Query("")) -> FileResponse:
    from fastapi import HTTPException

    if not _DEBATE_FILE_RE.fullmatch(name or ""):
        raise HTTPException(status_code=400, detail="invalid file name")
    target = CARDS_DIR / name
    if not target.is_file():
        raise HTTPException(status_code=404, detail="not found")
    return FileResponse(
        target,
        media_type="text/html",
        headers={"Cache-Control": "public, max-age=3600"},
    )
