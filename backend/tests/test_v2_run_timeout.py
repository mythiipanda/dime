import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from v2.api import routes
from v2.api.events import FinalAnswer, GraphEnd, Token
from v2.api.sse import encode_event


@pytest.fixture
def pi_route(monkeypatch):
    from analyst import product_session, configuration
    from shared.config import settings
    monkeypatch.setattr(routes, "_require_projects", lambda: None)
    monkeypatch.setattr("shared.providers.resolve_model_id", lambda value: ("fixture", "fixture"))
    monkeypatch.setattr("shared.providers.get_llm", lambda *args: None)
    monkeypatch.setattr(configuration, "model_limits", lambda *args: {})
    monkeypatch.setattr(product_session, "resolved_provider", lambda *args, **kwargs: {})
    monkeypatch.setattr(settings, "dime_v2_run_timeout_s", 0.05)
    return product_session


def test_hung_run_hits_timeout_ceiling(pi_route, monkeypatch):
    async def scenario():
        closed = asyncio.Event()
        async def producer(**kwargs):
            try:
                await asyncio.Future()
                yield "never"
            finally:
                closed.set()
        monkeypatch.setattr(pi_route, "stream_product_session", producer)
        response = await routes.quick_answer_stream(routes.QuickAnswerBody(q="hung"))
        chunks = [c async for c in response.body_iterator]
        assert '"kind":"timeout"' in "".join(chunks)
        assert "".join(chunks).count("event: graph_end") == 1
        assert "event: final_answer" not in "".join(chunks)
        assert closed.is_set()
    asyncio.run(scenario())


def test_healthy_run_streams_every_event_and_stops(pi_route, monkeypatch):
    async def scenario():
        async def producer(**kwargs):
            for event in (Token(text="answer"), FinalAnswer(text="answer"), GraphEnd()):
                yield encode_event(event)
        monkeypatch.setattr(pi_route, "stream_product_session", producer)
        response = await routes.quick_answer_stream(routes.QuickAnswerBody(q="healthy"))
        chunks = [c async for c in response.body_iterator]
        assert [c.splitlines()[0] for c in chunks] == ["event: token", "event: final_answer", "event: graph_end"]
        assert response.headers["x-dime-run-id"].startswith("run-")
    asyncio.run(scenario())


def test_events_reach_the_client_while_the_run_is_still_working(pi_route, monkeypatch):
    async def scenario():
        release = asyncio.Event()
        closed = asyncio.Event()
        async def producer(**kwargs):
            try:
                yield encode_event(Token(text="first"))
                await release.wait()
                yield encode_event(GraphEnd())
            finally:
                closed.set()
        monkeypatch.setattr(pi_route, "stream_product_session", producer)
        response = await routes.quick_answer_stream(routes.QuickAnswerBody(q="stream"))
        assert "first" in await anext(response.body_iterator)
        assert not release.is_set()
        await response.body_iterator.aclose()
        assert closed.is_set()
    asyncio.run(scenario())


def test_production_default_is_still_the_six_minute_ceiling():
    from shared.config import settings
    assert settings.dime_v2_run_timeout_s == 360.0


@pytest.mark.parametrize("method", ["GET", "POST"])
def test_http_pi_contract(pi_route, monkeypatch, method):
    from fastapi import FastAPI
    from v2.api.events import Failure
    from shared.config import settings
    app = FastAPI()
    app.include_router(routes.router, prefix="/api")
    routes._CHAT_HITS.clear()
    monkeypatch.setattr(settings, "chat_rate_per_minute", 20)
    async def producer(**kwargs):
        assert kwargs["q"] == "question"
        assert kwargs["client"] is None
        yield encode_event(Token(text="first"))
        yield encode_event(FinalAnswer(text="first", carry={"verification":"unassessed"}))
        yield encode_event(GraphEnd())
    monkeypatch.setattr(pi_route, "stream_product_session", producer)
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://fixture") as client:
            kwargs = {"params" if method == "GET" else "json": {"q":"question"}}
            response = await client.request(method, "/api/v2/chat/stream", **kwargs)
            assert response.status_code == 200
            assert response.headers["content-type"].startswith("text/event-stream")
            assert response.headers["x-dime-run-id"].startswith("run-")
            assert response.text.count("event: graph_end") == 1
            assert "event: final_answer" in response.text
            assert "verified_claims" not in response.text
            invalid = await client.post("/api/v2/chat/stream", json={"q":" "})
            assert invalid.status_code == 422
            monkeypatch.setattr(routes, "_chat_allowed", lambda ip: False)
            limited = await client.post("/api/v2/chat/stream", json={"q":"question"})
            assert '"kind":"rate_limited"' in limited.text
            assert limited.text.count("event: graph_end") == 1
    asyncio.run(scenario())
