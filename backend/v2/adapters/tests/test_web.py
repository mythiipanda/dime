from __future__ import annotations

import httpx
import pytest

from v2.adapters.web import (
    DuckDuckGoSearch, FirecrawlWeb, WebSearchRequest, WebSearchResult,
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


@pytest.mark.anyio
async def test_firecrawl_search_and_fetch_keep_source_identity(monkeypatch):
    calls = []
    async def handler(request):
        calls.append((request.url.path, request.read()))
        if request.url.path.endswith("/search"):
            return httpx.Response(200, json={"success": True, "data": {"web": [{
                "url": "https://example.com/report", "title": "Report",
                "description": "Result snippet"}]}})
        return httpx.Response(200, json={"success": True, "data": {
            "markdown": "# Report\nGrounded text", "metadata": {
                "sourceURL": "https://example.com/report", "title": "Report",
                "ogSiteName": "Example"}}})
    async def public(url): return url
    monkeypatch.setattr("v2.adapters.web.validate_public_url", public)
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = FirecrawlWeb(client=client)
    search = await provider.search(WebSearchRequest(query="Brown trade"))
    page = await provider.fetch(search.results[0])
    await client.aclose()
    assert search.results[0].snippet == "Result snippet"
    assert str(page.url) == "https://example.com/report"
    assert page.publisher == "Example"
    assert len(page.content_hash) == 64
    assert [item[0] for item in calls] == ["/v2/search", "/v2/scrape"]


def test_fetch_request_requires_search_rank():
    from pydantic import ValidationError
    from v2.adapters.web import WebFetchRequest
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
async def test_firecrawl_does_not_claim_unsupported_freshness(monkeypatch):
    async def handler(request):
        return httpx.Response(200, json={"success": True, "data": {"web": []}})
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    response = await FirecrawlWeb(client=client).search(
        WebSearchRequest(query="latest Celtics", freshness="week"))
    await client.aclose()
    assert "no documented freshness-window" in response.warnings[0]

@pytest.mark.anyio
async def test_firecrawl_sends_optional_key():
    async def handler(request):
        assert request.headers["Authorization"] == "Bearer fc-test"
        return httpx.Response(200, json={"success": True, "data": {"web": []}})
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    await FirecrawlWeb(api_key="fc-test", client=client).search(
        WebSearchRequest(query="Brown trade"))
    await client.aclose()


@pytest.mark.anyio
async def test_firecrawl_keyless_denial_is_actionable():
    async def handler(request):
        return httpx.Response(403, json={"success": False, "error": "suspicious IP"})
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    with pytest.raises(RuntimeError, match="configure a free API key"):
        await FirecrawlWeb(client=client).search(WebSearchRequest(query="Brown trade"))
    await client.aclose()


def test_firecrawl_accepts_configured_key(monkeypatch):
    monkeypatch.setenv("FIRECRAWL_API_KEY", "fc-configured")
    from app.config import Settings
    assert Settings().firecrawl_api_key == "fc-configured"

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
