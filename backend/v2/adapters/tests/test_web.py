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
async def test_local_fetch_extracts_main_content_and_follows_checked_redirect(monkeypatch):
    from v2.adapters.web import LocalWebFetch
    checked = []
    async def public(url):
        checked.append(url)
        return url
    async def handler(request):
        if request.url.path == "/start":
            return httpx.Response(302, headers={"location": "/article"})
        return httpx.Response(200, headers={"content-type": "text/html"}, text="""
          <html><head><title>Brown analysis</title></head><body>
          <nav>Noise</nav><article><h1>Brown analysis</h1>
          <p>Jaylen Brown has a central two-way role for Boston across a full season.</p>
          </article></body></html>""")
    monkeypatch.setattr("v2.adapters.web.validate_public_url", public)
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    page = await LocalWebFetch(client=client).fetch(WebSearchResult(
        rank=1, url="https://example.com/start", title="Search title", snippet=""))
    await client.aclose()
    assert checked == ["https://example.com/start", "https://example.com/article",
                       "https://example.com/article"]
    assert page.title == "Brown analysis"
    assert "central two-way role" in page.markdown
    assert len(page.markdown) < 500


@pytest.mark.anyio
async def test_local_fetch_rejects_non_html_and_oversize(monkeypatch):
    from v2.adapters.web import LocalWebFetch
    async def public(url): return url
    monkeypatch.setattr("v2.adapters.web.validate_public_url", public)
    async def json_handler(request):
        return httpx.Response(200, headers={"content-type": "application/json"}, text="{}")
    client = httpx.AsyncClient(transport=httpx.MockTransport(json_handler))
    with pytest.raises(RuntimeError, match="unsupported web content type"):
        await LocalWebFetch(client=client).fetch(WebSearchResult(
            rank=1, url="https://example.com/a", title="A", snippet=""))
    await client.aclose()
    async def html_handler(request):
        return httpx.Response(200, headers={"content-type": "text/html"},
                              content=b"<article>" + b"x" * 100 + b"</article>")
    client = httpx.AsyncClient(transport=httpx.MockTransport(html_handler))
    with pytest.raises(RuntimeError, match="response-size limit"):
        await LocalWebFetch(client=client, max_bytes=50).fetch(WebSearchResult(
            rank=1, url="https://example.com/a", title="A", snippet=""))
    await client.aclose()
