"""Provider-neutral web discovery and extraction contracts.

Search results are discovery evidence. Fetching accepts a selected search row,
not an arbitrary model-authored URL, so publication keeps source identity.
"""
from __future__ import annotations

import asyncio
import ipaddress
import socket
from collections.abc import Callable, Sequence
from datetime import datetime
from typing import Any, Literal, Protocol
from urllib.parse import urlparse

import httpx
from pydantic import BaseModel, Field, HttpUrl


class WebSearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=500)
    max_results: int = Field(default=5, ge=1, le=8)
    freshness: Literal["day", "week", "month", "year"] | None = None
    include_domains: list[str] = Field(default_factory=list, max_length=8)
    exclude_domains: list[str] = Field(default_factory=list, max_length=8)


class WebSearchResult(BaseModel):
    rank: int = Field(ge=1)
    url: HttpUrl
    title: str
    snippet: str
    published_at: datetime | None = None


class WebSearchResponse(BaseModel):
    provider: str
    observed_at: datetime
    query: str
    results: list[WebSearchResult]
    coverage: str
    warnings: list[str] = Field(default_factory=list)


class WebFetchRequest(BaseModel):
    search_evidence_id: str = Field(min_length=1)
    result_rank: int = Field(ge=1, le=8)


class WebPage(BaseModel):
    url: HttpUrl
    title: str
    publisher: str | None = None
    published_at: datetime | None = None
    retrieved_at: datetime
    markdown: str = Field(max_length=120_000)
    content_hash: str


class WebSearchProvider(Protocol):
    name: str

    async def search(self, request: WebSearchRequest) -> WebSearchResponse: ...


class WebFetchProvider(Protocol):
    name: str

    async def fetch(self, result: WebSearchResult) -> WebPage: ...


def _domain(value: str) -> str:
    parsed = urlparse("//" + value if "://" not in value else value)
    host = (parsed.hostname or "").strip(".").lower()
    if not host or any(char.isspace() for char in host):
        raise ValueError(f"invalid domain {value!r}")
    return host


def _is_public_ip(value: str) -> bool:
    ip = ipaddress.ip_address(value)
    return not any((ip.is_private, ip.is_loopback, ip.is_link_local,
                    ip.is_multicast, ip.is_reserved, ip.is_unspecified))


async def validate_public_url(url: str) -> str:
    """Reject non-HTTP and hostnames resolving outside the public Internet."""
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("web source must be an HTTP(S) URL")
    if parsed.username or parsed.password:
        raise ValueError("web source cannot carry credentials")
    host = parsed.hostname.strip(".")
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        infos = await asyncio.to_thread(
            socket.getaddrinfo, host, parsed.port or 443,
            type=socket.SOCK_STREAM)
        addresses = {item[4][0] for item in infos}
        if not addresses or not all(_is_public_ip(item) for item in addresses):
            raise ValueError("web source resolves to a non-public address")
    else:
        if not _is_public_ip(str(literal)):
            raise ValueError("web source uses a non-public address")
    return url


class DuckDuckGoSearch:
    """Best-effort, unofficial DDG discovery through the MIT `ddgs` client.

    DuckDuckGo's official Instant Answer API is not a full search API. Keep
    this adapter swappable and never describe it as an official API.
    """

    name = "duckduckgo-best-effort"

    def __init__(self, client_factory: Callable[[], Any] | None = None) -> None:
        self._client_factory = client_factory or self._default_client

    @staticmethod
    def _default_client() -> Any:
        try:
            from ddgs import DDGS
        except ImportError as exc:
            raise RuntimeError("install the optional `ddgs` package") from exc
        return DDGS(timeout=8)

    async def search(self, request: WebSearchRequest) -> WebSearchResponse:
        if request.include_domains and request.exclude_domains:
            raise ValueError("include_domains and exclude_domains are exclusive")
        query = request.query
        if request.include_domains:
            query += " " + " OR ".join(
                f"site:{_domain(item)}" for item in request.include_domains)
        if request.exclude_domains:
            query += " " + " ".join(
                f"-site:{_domain(item)}" for item in request.exclude_domains)
        timelimit = {"day": "d", "week": "w", "month": "m", "year": "y"}.get(
            request.freshness)

        def run() -> Sequence[dict[str, Any]]:
            return list(self._client_factory().text(
                query, backend="duckduckgo", timelimit=timelimit,
                max_results=request.max_results))

        raw = await asyncio.to_thread(run)
        results = []
        for item in raw[:request.max_results]:
            href = item.get("href") or item.get("url")
            if not href:
                continue
            await validate_public_url(str(href))
            results.append(WebSearchResult(
                rank=len(results) + 1, url=href,
                title=str(item.get("title") or "Untitled source"),
                snippet=str(item.get("body") or item.get("description") or "")))
        return WebSearchResponse(
            provider=self.name, observed_at=datetime.now().astimezone(),
            query=request.query, results=results,
            coverage="Unofficial best-effort DuckDuckGo results; snippets are discovery evidence only.",
            warnings=["DuckDuckGo exposes no official full-results API; availability may change."],
        )


class FirecrawlWeb:
    """Firecrawl search and one-page Markdown extraction.

    Firecrawl documents keyless access, but some server IPs are denied. An API
    key is optional at the contract boundary and should be configured for a
    reliable deployment.
    """

    name = "firecrawl"

    def __init__(self, *, api_key: str = "",
                 base_url: str = "https://api.firecrawl.dev/v2",
                 client: httpx.AsyncClient | None = None) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._client = client

    async def _post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(
            timeout=httpx.Timeout(15, connect=5), follow_redirects=False)
        headers = ({"Authorization": f"Bearer {self._api_key}"}
                   if self._api_key else {})
        try:
            response = await client.post(
                f"{self._base_url}/{path}", json=body, headers=headers)
            if response.status_code == 403 and not self._api_key:
                raise RuntimeError(
                    "Firecrawl keyless access was denied; configure a free API key")
            response.raise_for_status()
            payload = response.json()
        finally:
            if owns_client:
                await client.aclose()
        if not isinstance(payload, dict) or not payload.get("success"):
            raise RuntimeError(f"Firecrawl {path} returned no successful payload")
        return payload

    async def search(self, request: WebSearchRequest) -> WebSearchResponse:
        if request.include_domains and request.exclude_domains:
            raise ValueError("include_domains and exclude_domains are exclusive")
        body: dict[str, Any] = {"query": request.query,
                                "limit": request.max_results,
                                "sources": ["web"]}
        if request.include_domains:
            body["includeDomains"] = [_domain(item) for item in request.include_domains]
        if request.exclude_domains:
            body["excludeDomains"] = [_domain(item) for item in request.exclude_domains]
        payload = await self._post("search", body)
        web = (payload.get("data") or {}).get("web") or []
        results = []
        for item in web[:request.max_results]:
            url = item.get("url")
            if not url:
                continue
            await validate_public_url(str(url))
            results.append(WebSearchResult(
                rank=len(results) + 1, url=url,
                title=str(item.get("title") or "Untitled source"),
                snippet=str(item.get("description") or item.get("snippet") or "")))
        warnings = []
        if request.freshness:
            warnings.append(
                "Firecrawl search has no documented freshness-window parameter; "
                "published dates must be checked after extraction.")
        return WebSearchResponse(
            provider=self.name, observed_at=datetime.now().astimezone(),
            query=request.query, results=results,
            coverage="Firecrawl web search; snippets are discovery evidence only.",
            warnings=warnings)

    async def fetch(self, result: WebSearchResult) -> WebPage:
        import hashlib

        await validate_public_url(str(result.url))
        payload = await self._post("scrape", {
            "url": str(result.url), "formats": ["markdown"],
            "onlyMainContent": True, "maxAge": 0,
        })
        data = payload.get("data") or {}
        metadata = data.get("metadata") or {}
        final_url = str(metadata.get("sourceURL") or metadata.get("url") or result.url)
        await validate_public_url(final_url)
        markdown = str(data.get("markdown") or "")[:120_000]
        if not markdown.strip():
            raise RuntimeError("Firecrawl scrape returned no page content")
        return WebPage(
            url=final_url, title=str(metadata.get("title") or result.title),
            publisher=metadata.get("ogSiteName"), retrieved_at=datetime.now().astimezone(),
            markdown=markdown,
            content_hash=hashlib.sha256(markdown.encode()).hexdigest())
