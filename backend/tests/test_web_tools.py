import asyncio

import pytest

from analyst.tools import web


def _invoke(tool, args):
    return asyncio.run(tool.ainvoke(args))


def test_web_search_normalizes_ranked_rows_and_discovery_meta(monkeypatch):
    async def fake_search(query, *, max_results, region, safesearch, timelimit):
        assert query == "Jaylen Brown trade"
        assert max_results == 2
        assert region == "us-en"
        assert safesearch == "moderate"
        assert timelimit is None
        return [
            {"title": "Brown trade watch", "href": "https://example.com/brown",
             "body": "Latest reporting", "published": "2026-11-19T12:00:00Z"},
            {"title": "Celtics roster", "url": "https://celtics.com/news",
             "description": "Team page"},
            {"title": "Bad", "href": "ftp://example.com/file"},
        ]

    monkeypatch.setattr(web, "_search_ddgs", fake_search)
    result = _invoke(web.register()["web_search"], {
        "query": "Jaylen Brown trade", "max_results": 2,
    })

    assert result["ok"] is True
    assert result["tool"] == "web_search"
    assert result["columns"] == web.SEARCH_COLUMNS
    assert [row["rank"] for row in result["rows"]] == [1, 2]
    assert result["rows"][0]["url"] == "https://example.com/brown"
    assert result["rows"][0]["domain"] == "example.com"
    assert result["rows"][0]["published_at"] == "2026-11-19T12:00:00Z"
    assert result["rows"][1]["snippet"] == "Team page"
    assert result["meta"]["provider"] == "ddgs-best-effort"
    assert "discovery evidence" in result["meta"]["coverage"]
    assert result["meta"]["results_returned"] == 2


def test_web_search_rejects_empty_query_and_bad_timelimit_without_network():
    tools = web.register()

    empty = _invoke(tools["web_search"], {"query": "   "})
    assert empty["ok"] is False
    assert empty["tool"] == "web_search"
    assert empty["rows"] == []
    assert empty["columns"] == web.SEARCH_COLUMNS
    assert "query is required" in empty["error"]

    bad_window = _invoke(tools["web_search"], {"query": "NBA news", "timelimit": "hour"})
    assert bad_window["ok"] is False
    assert "timelimit" in bad_window["error"]


def test_web_fetch_returns_cited_page_row_from_fetcher(monkeypatch):
    async def fake_fetch(url):
        assert url == "https://example.com/story"
        return {
            "url": "https://www.example.com/final-story",
            "title": "Final story",
            "publisher": "www.example.com",
            "text": "Trade deadline reporting.",
            "chars": len("Trade deadline reporting."),
            "content_hash": "abc123",
            "published_at": "2026-11-19",
            "meta": {
                "requested_url": url,
                "final_url": "https://www.example.com/final-story",
                "status_code": 200,
                "provider": "direct-http",
            },
        }

    monkeypatch.setattr(web, "_fetch_page", fake_fetch)
    result = _invoke(web.register()["web_fetch"], {"url": "https://example.com/story"})

    assert result["ok"] is True
    assert result["tool"] == "web_fetch"
    assert result["columns"] == web.FETCH_COLUMNS
    assert len(result["rows"]) == 1
    row = result["rows"][0]
    assert row["url"] == "https://www.example.com/final-story"
    assert row["title"] == "Final story"
    assert row["text"] == "Trade deadline reporting."
    assert row["content_hash"] == "abc123"
    assert result["meta"]["status_code"] == 200


def test_web_fetch_rejects_non_public_and_credential_urls_without_request():
    tools = web.register()

    for url in ("http://127.0.0.1/private", "https://user:pass@example.com/x", "file:///etc/passwd"):
        result = _invoke(tools["web_fetch"], {"url": url})
        assert result["ok"] is False
        assert result["tool"] == "web_fetch"
        assert result["rows"] == []
        assert result["columns"] == web.FETCH_COLUMNS


def test_extract_html_uses_article_text_and_strips_scripts():
    body = b"""
    <html><head><title>NBA Trade Watch</title>
    <meta property="article:published_time" content="2026-11-19T13:00:00Z">
    </head><body><article>
      <script>secret()</script><p>Boston is listening on Brown.</p>
    </article><footer>ignore me</footer></body></html>
    """
    title, text, published = web._extract_html(body, "https://example.com/story")

    assert title == "NBA Trade Watch"
    assert text == "Boston is listening on Brown."
    assert "secret()" not in text
    assert "ignore me" not in text
    assert published == "2026-11-19T13:00:00Z"


def test_public_url_guard_rejects_private_literal_and_credentials():
    with pytest.raises(ValueError):
        asyncio.run(web._validate_public_url("http://169.254.169.254/latest/meta-data"))
    with pytest.raises(ValueError):
        asyncio.run(web._validate_public_url("https://user@example.com/path"))
