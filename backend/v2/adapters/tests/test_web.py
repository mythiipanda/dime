from __future__ import annotations

import httpx
import pytest

from v2.adapters.web import (
    DuckDuckGoSearch, WebSearchRequest, WebSearchResult,
    validate_public_url,
)


class DDGFixture:
    def text(self, query, **kwargs):
        assert kwargs["backend"] == "duckduckgo"
        assert "site:espn.com" in query
        return [{"title": "Brown role", "href": "https://espn.com/nba/brown",
                 "body": "Current reporting"}]


@pytest.mark.anyio
async def test_duckduckgo_is_typed_and_labeled_best_effort(monkeypatch):
    async def public(url): return url
    monkeypatch.setattr("v2.adapters.web.validate_public_url", public)
    response = await DuckDuckGoSearch(lambda: DDGFixture()).search(
        WebSearchRequest(query="Jaylen Brown role", include_domains=["espn.com"]))
    assert response.provider == "duckduckgo-best-effort"
    assert response.results[0].rank == 1
    assert "not official" not in response.coverage.lower()
    assert "no official full-results API" in response.warnings[0]


def test_fetch_request_requires_valid_search_rank_but_can_bind_dependency():
    from pydantic import ValidationError
    from v2.adapters.web import WebFetchRequest
    assert WebFetchRequest(result_rank=1).search_evidence_id is None
    with pytest.raises(ValidationError):
        WebFetchRequest(search_evidence_id="", result_rank=0)


@pytest.mark.anyio
@pytest.mark.parametrize("url", [
    "file:///etc/passwd", "http://127.0.0.1/a", "http://[::1]/a",
    "http://169.254.169.254/latest/meta-data",
])
async def test_url_guard_rejects_non_http_or_private_urls(url):
    with pytest.raises(ValueError):
        await validate_public_url(url)



@pytest.mark.anyio
async def test_jina_reader_fetches_selected_source_and_preserves_final_url(monkeypatch):
    from v2.adapters.web import JinaReader
    calls = []
    async def handler(request):
        calls.append(request)
        return httpx.Response(200, json={"data": {
            "url": "https://example.com/story", "title": "Story",
            "content": "# Story\nSourced details",
            "publishedTime": "2026-09-15T10:00:00Z"}})
    async def public(url): return url
    monkeypatch.setattr("v2.adapters.web.validate_public_url", public)
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    page = await JinaReader(client=client).fetch(WebSearchResult(
        rank=1, url="https://example.com/story", title="Search title", snippet=""))
    await client.aclose()
    assert calls[0].url.path == "/https://example.com/story"
    assert calls[0].headers["X-Robots-Txt"] == "true"
    assert str(page.url) == "https://example.com/story"
    assert page.title == "Story"
    assert page.published_at is not None
    assert len(page.content_hash) == 64


@pytest.mark.anyio
async def test_jina_reader_rejects_empty_payload(monkeypatch):
    from v2.adapters.web import JinaReader
    async def handler(request):
        return httpx.Response(200, json={"data": {"title": "No content"}})
    async def public(url): return url
    monkeypatch.setattr("v2.adapters.web.validate_public_url", public)
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    with pytest.raises(RuntimeError, match="no page content"):
        await JinaReader(client=client).fetch(WebSearchResult(
            rank=1, url="https://example.com", title="Example", snippet=""))
    await client.aclose()

@pytest.mark.anyio
async def test_jina_reader_sends_optional_free_key(monkeypatch):
    from v2.adapters.web import JinaReader
    async def public(url): return url
    async def handler(request):
        assert request.headers["Authorization"] == "Bearer jina-test"
        return httpx.Response(200, json={"data": {
            "url": "https://example.com", "title": "Example",
            "content": "Extracted content"}})
    monkeypatch.setattr("v2.adapters.web.validate_public_url", public)
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    await JinaReader(api_key="jina-test", client=client).fetch(WebSearchResult(
        rank=1, url="https://example.com", title="Example", snippet=""))
    await client.aclose()


def test_jina_key_is_optional_config(monkeypatch):
    monkeypatch.setenv("JINA_API_KEY", "jina-configured")
    from app.config import Settings
    assert Settings().jina_api_key == "jina-configured"


def test_jina_reader_defaults_to_settings_key(monkeypatch):
    monkeypatch.setattr("app.config.settings.jina_api_key", "jina-from-settings")
    from v2.adapters.web import JinaReader
    assert JinaReader()._api_key == "jina-from-settings"


def test_jina_reader_can_force_keyless_with_configured_key(monkeypatch):
    monkeypatch.setattr("app.config.settings.jina_api_key", "jina-from-settings")
    from v2.adapters.web import JinaReader
    assert JinaReader(api_key="")._api_key == ""

@pytest.mark.anyio
async def test_web_search_capability_normalizes_discovery_evidence():
    from datetime import UTC, datetime
    from v2.adapters.web import WebSearchCapability, WebSearchResponse
    from v2.contracts import PlanNode, TaskSpec

    class Search:
        name = "fixture-search"
        async def search(self, request):
            return WebSearchResponse(
                provider=self.name, observed_at=datetime(2026, 9, 15, tzinfo=UTC),
                query=request.query,
                results=[WebSearchResult(rank=1, url="https://example.com/story",
                                         title="Story", snippet="Discovery only")],
                coverage="fixture coverage")

    node = PlanNode(id="search", description="current reporting",
                    capability_hints=["web_search"],
                    arguments={"query": "Jaylen Brown role"},
                    completion_test="one source")
    envelope = await WebSearchCapability(Search()).execute(
        node, TaskSpec(goal="role", mode="quick", deliverable="answer"), [])
    assert envelope.capability == "web_search"
    assert envelope.source == "web:fixture-search"
    assert envelope.rows[0]["rank"] == 1
    assert envelope.lineage == []


@pytest.mark.anyio
async def test_web_fetch_capability_only_extracts_selected_parent_result():
    from datetime import UTC, datetime
    from v2.adapters.web import WebFetchCapability, WebPage
    from v2.contracts import EvidenceEnvelope, PlanNode, TaskSpec

    parent = EvidenceEnvelope(
        evidence_id="web_search:parent", capability="web_search",
        source="web:fixture", observed_at=datetime(2026, 9, 15, tzinfo=UTC),
        rows=[{"rank": 1, "url": "https://example.com/story",
               "title": "Story", "snippet": "Discovery"}])

    class Fetch:
        name = "fixture-fetch"
        async def fetch(self, result):
            assert result.rank == 1
            return WebPage(
                url=result.url, title=result.title,
                retrieved_at=datetime(2026, 9, 15, tzinfo=UTC),
                markdown="# Story\nFull sourced text", content_hash="a" * 64)

    node = PlanNode(id="fetch", description="page", depends_on=["search"],
                    capability_hints=["web_fetch"],
                    arguments={"search_evidence_id": parent.evidence_id,
                               "result_rank": 1}, completion_test="page text")
    envelope = await WebFetchCapability(Fetch()).execute(
        node, TaskSpec(goal="role", mode="quick", deliverable="answer"), [parent])
    assert envelope.lineage == [parent.evidence_id]
    assert envelope.rows["markdown"].startswith("# Story")
    assert envelope.source == "web:https://example.com/story"


@pytest.mark.anyio
async def test_web_fetch_capability_rejects_unselected_or_unrelated_source():
    from datetime import UTC, datetime
    from v2.adapters.web import WebFetchCapability
    from v2.contracts import EvidenceEnvelope, PlanNode, TaskSpec

    parent = EvidenceEnvelope(
        evidence_id="web_search:parent", capability="web_search",
        source="web:fixture", observed_at=datetime(2026, 9, 15, tzinfo=UTC),
        rows=[{"rank": 1, "url": "https://example.com/story",
               "title": "Story", "snippet": "Discovery"}])
    node = PlanNode(id="fetch", description="page",
                    capability_hints=["web_fetch"],
                    arguments={"search_evidence_id": "web_search:other",
                               "result_rank": 1}, completion_test="page text")
    with pytest.raises(ValueError, match="selected web_search parent"):
        await WebFetchCapability().execute(
            node, TaskSpec(goal="role", mode="quick", deliverable="answer"), [parent])


@pytest.mark.anyio
async def test_planned_web_dag_binds_fetch_to_content_addressed_parent():
    from datetime import UTC, datetime
    from v2.adapters.web import (WebFetchCapability, WebPage,
                                 WebSearchCapability, WebSearchResponse)
    from v2.contracts import Plan, PlanNode, TaskSpec
    from v2.runtime import PlanExecutor

    class Search:
        name = "fixture-search"
        async def search(self, request):
            return WebSearchResponse(provider=self.name, query=request.query,
                observed_at=datetime(2026, 9, 15, tzinfo=UTC),
                results=[WebSearchResult(rank=1, url="https://example.com/story",
                    title="Story", snippet="Discovery")], coverage="fixture")

    class Fetch:
        name = "fixture-fetch"
        async def fetch(self, result):
            return WebPage(url=result.url, title=result.title,
                retrieved_at=datetime(2026, 9, 15, tzinfo=UTC),
                markdown="Full source", content_hash="a" * 64)

    plan = Plan(nodes=[
        PlanNode(id="discover", description="current source",
            capability_hints=["web_search"],
            arguments={"query": "current Jaylen Brown role"},
            completion_test="one selected source"),
        PlanNode(id="extract", description="full page", depends_on=["discover"],
            capability_hints=["web_fetch"], arguments={"result_rank": 1},
            completion_test="page text"),
    ])
    result = await PlanExecutor({
        "web_search": WebSearchCapability(Search()),
        "web_fetch": WebFetchCapability(Fetch()),
    }).execute(TaskSpec(goal="role", mode="quick", deliverable="answer"), plan)
    assert result.evidence[1].lineage == [result.evidence[0].evidence_id]
    assert result.evidence[1].rows["markdown"] == "Full source"
