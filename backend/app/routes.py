"""HTTP boundary. Parse and clamp here. Graph trusts what it receives."""

import time
from collections import defaultdict
from pathlib import Path
import os
import re
from fastapi import APIRouter, Query, Request
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, field_validator

from .graph import run_chat
from .providers import models_catalog
from . import store
from .sse import emit_sse, with_heartbeat
from .config import settings

router = APIRouter()

CARDS_DIR = Path(__file__).resolve().parent.parent / "data" / "cards"

_DEBATE_FILE_RE = re.compile(r"^debate_[A-Za-z0-9]+_vs_[A-Za-z0-9]+_[0-9]+\.html$")

_hits: dict[str, list[float]] = defaultdict(list)
_SHADOW_TASKS: set = set()


def _sanitize_sse_event(etype: str, data: dict) -> dict:
    if etype == "tool_call" and isinstance(data, dict):
        return {key: data[key] for key in (
            "node", "name", "label", "summary", "agent",
        ) if key in data}
    if etype == "token":
        # Draft prose has not passed the final numerical/grounding guard yet.
        return {"text": ""}
    if etype == "thought_token" and isinstance(data, dict):
        return {key: data[key] for key in ("node", "agent") if key in data} | {
            "text": "Working through the evidence...",
        }
    if etype == "thought_stream" and isinstance(data, dict):
        text = str(data.get("text", ""))
        unsafe = (
            len(text) > 1000
            or any(marker in text for marker in (
                "Traceback", "/srv/", "/home/", "Exception:", "Error:",
                "SELECT ", "INSERT ", "UPDATE ", "DELETE ",
            ))
        )
        return {key: data[key] for key in ("node", "agent") if key in data} | {
            "text": ("Working through the evidence..." if unsafe else text),
        }
    if etype == "tool_result" and isinstance(data, dict):
        if data.get("status") in {"fail", "failed", "error"} or data.get("error"):
            out = {key: data[key] for key in (
                "node", "name", "label", "status", "rows", "ms", "agent",
            ) if key in data}
            out["status"] = "fail"
            out["error"] = "Tool failed"
            return out
        return {key: data[key] for key in (
            "node", "name", "label", "status", "rows", "ms", "summary",
            "sql", "agent",
        ) if key in data}
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
    public_fields = {
        "node_update": ("node", "status"),
        "custom_data": ("node", "tables", "unverified_numbers"),
        "final_answer": ("text", "carry"),
        "suggestions": ("items",),
        "graph_end": ("ok",),
    }
    fields = public_fields.get(etype)
    if fields is None or not isinstance(data, dict):
        return None
    return {key: data[key] for key in fields if key in data}


def _shadow_enabled() -> bool:
    return os.environ.get("DIME_RUNTIME_V2", "off").lower() == "shadow"


def _v1_shadow_outcome(
    *, answer: str, capabilities: list[str], evidence_count: int,
    had_error: bool, duration_ms: int,
):
    from v2.adapters.capabilities import CAPABILITIES
    from v2.runtime.shadow import RunOutcome

    by_tool = {item.tool_name: name for name, item in CAPABILITIES.items()}
    canonical_capabilities = [
        by_tool[name] for name in capabilities if name in by_tool
    ]
    status = "partial" if answer and had_error else "ok" if answer else "failed"
    return RunOutcome(
        status=status,
        answer=answer[:200_000],
        capabilities=list(dict.fromkeys(canonical_capabilities))[:32],
        evidence_count=evidence_count,
        supported_claims=None,
        total_claims=None,
        duration_ms=duration_ms,
    )


async def _record_v2_shadow(
    question: str, model: str | None, history: list[dict[str, str]],
    v1_outcome,
) -> None:
    import asyncio
    import uuid

    from .providers import resolve_model_id
    from v2.contracts import ConversationTurn
    from v2.runtime.assembly import build_runtime
    from v2.runtime.policy import ExecutionPolicy
    from v2.runtime.shadow import (
        RunOutcome, ShadowStore, compare_outcomes, outcome_from_v2,
    )

    started = time.monotonic()
    timeout_s = int(os.environ.get(
        "DIME_V2_SHADOW_TIMEOUT_SECONDS", str(max(30, settings.llm_timeout_s * 8))))
    if timeout_s < 1 or timeout_s > 3600:
        raise ValueError("shadow timeout must be between 1 and 3600 seconds")
    try:
        provider, model_name = resolve_model_id(
            model or os.environ.get("DIME_V2_MODEL"))
        run_id = f"shadow-{uuid.uuid4().hex}"
        ledger_dir = os.environ.get(
            "DIME_V2_LEDGER_DIR", str(CARDS_DIR.parent / "v2-ledgers"))
        checkpoint_dir = Path(os.environ.get(
            "DIME_V2_CHECKPOINT_DIR", str(CARDS_DIR.parent / "v2-checkpoints")))
        policy = ExecutionPolicy.shadow(ledger_dir=ledger_dir)
        policy = ExecutionPolicy.model_validate({
            **policy.model_dump(), "checkpoint_dir": checkpoint_dir,
        })
        runtime, _ = build_runtime(
            provider=provider, model_name=model_name, run_id=run_id,
            policy=policy)
        context = tuple(
            ConversationTurn(
                role="user" if item.get("role") in {"human", "user"}
                else "assistant",
                content=str(item.get("content", item.get("text", ""))),
            )
            for item in history
            if item.get("role") in {"human", "user", "ai", "assistant"}
            and str(item.get("content", item.get("text", ""))).strip()
        )[-8:]
        result = await asyncio.wait_for(
            runtime.run(question, run_id=run_id, context=context),
            timeout=timeout_s,
        )
        answer = "\n\n".join(item.claim.text for item in result.verified_claims)
        if result.gaps:
            gaps = " ".join(item.message for item in result.gaps)
            answer = (f"{answer}\n\nWhat I could not verify: {gaps}"
                      if answer else gaps)
        v2_outcome = outcome_from_v2(
            result, answer, int((time.monotonic() - started) * 1000))
    except BaseException as exc:
        v2_outcome = RunOutcome(
            status=("cancelled" if isinstance(exc, asyncio.CancelledError)
                    else "failed"),
            duration_ms=int((time.monotonic() - started) * 1000),
        )

    primary = await v1_outcome
    comparison = compare_outcomes(question, primary, v2_outcome)
    path = os.environ.get(
        "DIME_V2_SHADOW_STORE", str(CARDS_DIR.parent / "v2-shadow.jsonl"))
    ShadowStore(path).append(comparison)


def _consume_background_task(task) -> None:
    _SHADOW_TASKS.discard(task)
    try:
        task.exception()
    except BaseException:
        pass

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
    client: str | None = None


async def _stream(
    question: str, model: str | None, thread: str | None = None,
    history: list[dict[str, str]] | None = None, client: str = "",
):
    history = history or (store.chat_history(thread, 6) if thread else [])
    if thread:
        store.save_chat(thread, "human", question[:2000], owner=client[:80])

    async def gen():
        import asyncio
        import json as _json

        final = ""
        tables: list[dict] = []
        suggestions: list[str] = []
        capabilities: list[str] = []
        had_error = False
        started = time.monotonic()
        loop = asyncio.get_running_loop()
        v1_outcome = loop.create_future() if _shadow_enabled() else None
        shadow_task = None
        if v1_outcome is not None:
            shadow_task = asyncio.create_task(_record_v2_shadow(
                question[:2000], (model or "")[:200], history, v1_outcome))
            _SHADOW_TASKS.add(shadow_task)
            shadow_task.add_done_callback(_consume_background_task)
        try:
            async for event in run_chat(
                question[:2000], (model or "")[:200], history, thread
            ):
                if event["type"] == "final_answer":
                    final = str(event["data"].get("text", ""))
                elif event["type"] == "ledger_facts":
                    _lf = event["data"].get("facts")
                    if thread and isinstance(_lf, list):
                        try:
                            store.save_facts(thread, [str(f) for f in _lf],
                                             owner=client[:80])
                        except Exception:
                            pass
                elif event["type"] == "tool_call":
                    name = event["data"].get("name")
                    if isinstance(name, str) and name.strip():
                        capabilities.append(name)
                elif event["type"] == "error":
                    had_error = True
                elif event["type"] == "custom_data":
                    data = event["data"]
                    if isinstance(data.get("tables"), list):
                        tables = data["tables"]
                elif event["type"] == "suggestions":
                    items = event["data"].get("items", [])
                    if isinstance(items, list):
                        suggestions = [str(i) for i in items]
                if event["type"] == "ledger_facts":
                    continue  # internal plumbing - persisted above, not streamed
                public_data = _sanitize_sse_event(
                    event["type"], event["data"])
                if public_data is not None:
                    yield emit_sse(event["type"], public_data)
        finally:
            if v1_outcome is not None and not v1_outcome.done():
                v1_outcome.set_result(_v1_shadow_outcome(
                    answer=final,
                    capabilities=capabilities,
                    evidence_count=len(tables),
                    had_error=had_error,
                    duration_ms=int((time.monotonic() - started) * 1000),
                ))
        if thread and final:
            store.save_chat(thread, "ai", final, owner=client[:80])
            store.save_run(thread, question[:2000], final, tables, suggestions)

    async for chunk in with_heartbeat(gen()):
        yield chunk


@router.get("/threads")
def threads(client: str = Query("")) -> dict:
    return {"threads": store.list_threads(owner=client[:80])}


class TradeBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    team_a: str = ""
    players_a: str | list[str] = ""
    team_b: str = ""
    players_b: str | list[str] = ""
    season: str = "2025-26"

    @field_validator("players_a", "players_b")
    @classmethod
    def normalize_players(cls, value: str | list[str]) -> str:
        if isinstance(value, list):
            return ", ".join(item.strip() for item in value if item.strip())
        return value


@router.post("/trade/check")
def trade_check(body: TradeBody) -> dict:
    from .tools import get_trade_check

    return get_trade_check.invoke({
        "team_a": body.team_a, "players_a": body.players_a,
        "team_b": body.team_b, "players_b": body.players_b,
        "season": body.season,
    })


class SqlRerunBody(BaseModel):
    sql: str = ""


@router.post("/sql/rerun")
async def api_sql_rerun(body: SqlRerunBody) -> dict:
    """One-click re-run of a warehouse SQL shown by text_to_sql.

    Boundary: parse and clamp here; read-only validation lives in the
    shared league._validate_readonly_sql used by text_to_sql.
    """
    from .tools.league import rerun_sql

    sql = (body.sql or "").strip()
    if not sql:
        return {"ok": False, "error": "sql required", "rows": {}}
    if len(sql) > 8000:
        return {"ok": False, "error": "sql too long", "rows": {}}
    out = await rerun_sql(sql)
    if not out.get("ok"):
        return {"ok": False, "error": out.get("error", "rerun failed"),
                "rows": {}}
    return {"ok": True, "rows": {
        "columns": out["columns"], "rows": out["rows"],
        "ms": out.get("ms", 0), "capped": out.get("capped", False),
    }}


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
            if not isinstance(t, dict):
                continue
            lines.append(f"Source table: {t.get('tool', '?')}")
            meta = t.get("meta") if isinstance(t.get("meta"), dict) else {}
            source = meta.get("source")
            fetched_at = meta.get("fetched_at")
            season = meta.get("season")
            identity = [
                f"source {source}" if source else "",
                f"season {season}" if season else "",
                f"fetched {str(fetched_at)[:10]}" if fetched_at else "",
            ]
            if any(identity):
                lines.append("Evidence: " + ", ".join(filter(None, identity)))
            limits = [meta.get("qualification"), meta.get("coverage")]
            warnings = meta.get("warnings")
            if isinstance(warnings, list):
                limits.extend(str(item) for item in warnings if str(item).strip())
            for limit in limits:
                if isinstance(limit, str) and limit.strip():
                    lines.append(f"Limit: {limit}")
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
    client = request.headers.get("x-dime-client", "") or ""
    return StreamingResponse(_stream(q, model, thread, client=client), media_type="text/event-stream")


@router.post("/chat/stream")
async def chat_stream_post(request: Request, body: ChatBody):
    ip = request.client.host if request.client else "unknown"
    if not _allowed(ip):
        async def limited():
            yield emit_sse("error", {"message": "rate limited, retry soon"})

        return StreamingResponse(limited(), media_type="text/event-stream")
    client = body.client or request.headers.get("x-dime-client", "") or ""
    return StreamingResponse(
        _stream(body.q, body.model, body.thread, body.history,
                client=client[:80]),
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
    out = json.loads(res) if isinstance(res, str) else res
    # Snapshots accumulate one per day; before the second one lands (and
    # through the offseason) the tool errors. The Today page should show
    # an honest empty state, not a failure, so translate to empty rows.
    if isinstance(out, dict) and not out.get("ok") and "not enough snapshots" in str(out.get("error", "")):
        return {"tool": "get_leaderboard_deltas", "ok": True,
                "rows": {"climbers": [], "fallers": [], "new_entries": []},
                "meta": {"reason": "snapshots_pending", "season": season}}
    return out


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
