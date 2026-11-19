from __future__ import annotations

import asyncio
import hashlib
import ipaddress
import os
import re
import socket
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
from langchain_core.tools import tool

from .common import sanitize_for_wire
from .errors import enrich_error

SEARCH_TIMEOUT_S = 8
FETCH_TIMEOUT_S = 12.0
FETCH_MAX_BYTES = 1_000_000
FETCH_MAX_CHARS = 12_000
FETCH_MAX_REDIRECTS = 5
REDIRECT_STATUSES = {301, 302, 303, 307, 308}
TEXT_CONTENT_TYPES = ("text/html", "application/xhtml+xml", "text/plain")
SEARCH_COLUMNS = ["rank", "title", "url", "snippet", "domain", "published_at"]
FETCH_COLUMNS = ["url", "title", "publisher", "text", "chars", "content_hash"]
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,text/plain;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _failure(name: str, error: str, columns: list[str], meta: dict[str, Any] | None = None) -> dict[str, Any]:
    res = {"ok": False, "tool": name, "rows": [], "columns": columns, "error": error}
    if meta is not None:
        res["meta"] = meta
    return sanitize_for_wire(enrich_error(name, res))


def _is_public_ip(value: str) -> bool:
    ip = ipaddress.ip_address(value)
    return not any((ip.is_private, ip.is_loopback, ip.is_link_local,
                    ip.is_multicast, ip.is_reserved, ip.is_unspecified))


async def _validate_public_url(url: str) -> str:
    candidate = url.strip()
    parsed = urlparse(candidate)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("web_fetch requires an HTTP(S) URL")
    if parsed.username or parsed.password:
        raise ValueError("web_fetch URL cannot carry credentials")
    host = parsed.hostname.strip(".").lower()
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        infos = await asyncio.to_thread(
            socket.getaddrinfo, host, port, type=socket.SOCK_STREAM)
        addresses = {item[4][0] for item in infos}
        if not addresses or not all(_is_public_ip(item) for item in addresses):
            raise ValueError("web_fetch URL resolves to a non-public address")
    else:
        if not _is_public_ip(str(literal)):
            raise ValueError("web_fetch URL uses a non-public address")
    return candidate


def _search_query_kwargs(timelimit: str | None) -> dict[str, Any]:
    mapping = {"day": "d", "week": "w", "month": "m", "year": "y"}
    if timelimit is None:
        return {}
    value = timelimit.strip().lower()
    if value not in mapping:
        raise ValueError("timelimit must be one of day, week, month, year")
    return {"timelimit": mapping[value]}


async def _search_ddgs(query: str, *, max_results: int, region: str,
                       safesearch: str, timelimit: str | None) -> list[dict[str, Any]]:
    from ddgs import DDGS

    query_kwargs = _search_query_kwargs(timelimit)

    def run() -> list[dict[str, Any]]:
        with DDGS(timeout=SEARCH_TIMEOUT_S) as ddgs:
            try:
                return list(ddgs.text(
                    query,
                    backend="auto",
                    region=region,
                    safesearch=safesearch,
                    max_results=max_results,
                    **query_kwargs,
                ))
            except Exception as exc:
                if type(exc).__name__ == "DDGSException" and "No results found" in str(exc):
                    return []
                raise

    return await asyncio.to_thread(run)


def _search_rows(raw_results: list[dict[str, Any]], max_results: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in raw_results:
        if not isinstance(item, dict):
            continue
        href = item.get("href") or item.get("url") or item.get("link")
        if not href:
            continue
        url = str(href).strip()
        if not url.lower().startswith(("http://", "https://")):
            continue
        rows.append({
            "rank": len(rows) + 1,
            "title": str(item.get("title") or "Untitled source"),
            "url": url,
            "snippet": str(item.get("body") or item.get("description") or item.get("snippet") or ""),
            "domain": (urlparse(url).netloc or "").lower(),
            "published_at": item.get("published") or item.get("published_at") or None,
        })
        if len(rows) >= max_results:
            break
    return rows


async def _read_response(client: httpx.AsyncClient, url: str) -> dict[str, Any]:
    current = await _validate_public_url(url)
    for _ in range(FETCH_MAX_REDIRECTS + 1):
        async with client.stream("GET", current, headers=HEADERS) as response:
            location = response.headers.get("location")
            if response.status_code in REDIRECT_STATUSES and location:
                current = await _validate_public_url(urljoin(current, location))
                continue
            if response.status_code >= 400:
                raise RuntimeError(f"HTTP {response.status_code}")
            content_type = response.headers.get("content-type", "")
            media_type = content_type.split(";", 1)[0].strip().lower()
            if media_type and media_type not in TEXT_CONTENT_TYPES:
                raise RuntimeError(f"unsupported content type {media_type}")
            chunks: list[bytes] = []
            total = 0
            truncated = False
            async for chunk in response.aiter_bytes():
                remaining = FETCH_MAX_BYTES - total
                if len(chunk) > remaining:
                    if remaining > 0:
                        chunks.append(chunk[:remaining])
                    total = FETCH_MAX_BYTES
                    truncated = True
                    break
                chunks.append(chunk)
                total += len(chunk)
            return {
                "url": current,
                "status_code": response.status_code,
                "content_type": content_type or media_type,
                "body": b"".join(chunks),
                "bytes_read": total,
                "truncated": truncated,
            }
    raise RuntimeError("too many redirects")


def _clean_text(text: str) -> str:
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line).strip()


def _extract_html(body: bytes, fallback_url: str) -> tuple[str, str, str | None]:
    from lxml import html as lxml_html

    doc = lxml_html.fromstring(body)
    for selector in ("script", "style", "noscript", "template", "svg", "iframe", "form"):
        for node in doc.xpath(f"//{selector}"):
            node.getparent().remove(node)
    title_nodes = doc.xpath("//title/text()")
    title = _clean_text(" ".join(str(node) for node in title_nodes)) or fallback_url
    main_nodes = doc.xpath("//article") or doc.xpath("//main") or doc.xpath("//body") or [doc]
    text = _clean_text(main_nodes[0].text_content())
    published = None
    for xpath in (
        "//meta[translate(@property,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz')='article:published_time']/@content",
        "//meta[translate(@name,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz')='date']/@content",
        "//meta[translate(@name,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz')='publish-date']/@content",
        "//time/@datetime",
    ):
        values = doc.xpath(xpath)
        if values:
            published = str(values[0]).strip() or None
            if published:
                break
    return title, text, published


async def _fetch_page(url: str) -> dict[str, Any]:
    requested = url.strip()
    timeout = httpx.Timeout(FETCH_TIMEOUT_S, connect=5.0)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
        try:
            response = await _read_response(client, requested)
        except ValueError as exc:
            raise
        except httpx.TimeoutException as exc:
            raise RuntimeError(f"web_fetch timed out after {FETCH_TIMEOUT_S:.1f}s") from exc
        except httpx.HTTPError as exc:
            raise RuntimeError(f"web_fetch request failed: {exc}") from exc
    media_type = response["content_type"].split(";", 1)[0].strip().lower()
    if media_type == "text/plain":
        charset = "utf-8"
        for part in response["content_type"].split(";")[1:]:
            if "charset=" in part.lower():
                charset = part.split("=", 1)[1].strip().strip('"')
        text = response["body"].decode(charset, errors="replace")
        title = urlparse(response["url"]).path.rsplit("/", 1)[-1] or response["url"]
        published = None
    else:
        title, text, published = _extract_html(response["body"], response["url"])
    text = text[:FETCH_MAX_CHARS]
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return {
        "url": response["url"],
        "title": title,
        "publisher": (urlparse(response["url"]).netloc or "").lower(),
        "text": text,
        "chars": len(text),
        "content_hash": digest,
        "published_at": published,
        "meta": {
            "requested_url": requested,
            "status_code": response["status_code"],
            "content_type": response["content_type"],
            "retrieved_at": _now(),
            "bytes_read": response["bytes_read"],
            "body_truncated": response["truncated"],
            "text_truncated": len(text) == FETCH_MAX_CHARS,
            "provider": "direct-http",
        },
    }


def register() -> dict[str, Any]:
    @tool("web_search", description=(
        "Search the public web for current NBA news, rumors, transactions, and external context. "
        "Returns cited rows with rank, title, URL, snippet, domain, and published date when available. "
        "Use only when warehouse or live NBA tools cannot answer, or when current external reporting is needed; "
        "snippets are discovery evidence, so call web_fetch before relying on page details."
    ))
    async def web_search(query: str, max_results: int = 5, timelimit: str | None = None,
                         region: str = "us-en", safesearch: str = "moderate") -> dict:
        if os.environ.get("PI_OFFLINE"):
            return _failure("web_search", "offline mode: web fetching disabled", SEARCH_COLUMNS,
                            {"provider": "ddgs-best-effort"})
        query = query.strip()
        if not query:
            return _failure("web_search", "query is required", SEARCH_COLUMNS)
        max_results = max(1, min(int(max_results), 10))
        meta = {
            "query": query,
            "max_results": max_results,
            "provider": "ddgs-best-effort",
            "region": region,
            "safesearch": safesearch,
            "coverage": "Unofficial best-effort DDGS results; snippets are discovery evidence only.",
        }
        try:
            raw = await _search_ddgs(query, max_results=max_results, region=region,
                                     safesearch=safesearch, timelimit=timelimit)
        except Exception as exc:
            return _failure("web_search", f"{type(exc).__name__}: {exc}", SEARCH_COLUMNS, meta)
        rows = _search_rows(raw, max_results)
        meta["results_returned"] = len(rows)
        meta["observed_at"] = _now()
        return sanitize_for_wire({
            "ok": True,
            "tool": "web_search",
            "rows": rows,
            "columns": SEARCH_COLUMNS,
            "meta": meta,
        })

    @tool("web_fetch", description=(
        "Fetch one public HTTP(S) page and extract readable text. Use after web_search or when the user supplies a URL. "
        "Returns a cited row with final URL, title, publisher, extracted text, and content hash. "
        "Fetch only pages needed for the answer; web_search snippets are not a substitute for page evidence."
    ))
    async def web_fetch(url: str) -> dict:
        if os.environ.get("PI_OFFLINE"):
            return _failure("web_fetch", "offline mode: web fetching disabled", FETCH_COLUMNS,
                            {"provider": "direct-http"})
        meta = {"requested_url": url.strip(), "provider": "direct-http"}
        try:
            page = await _fetch_page(url)
        except Exception as exc:
            return _failure("web_fetch", f"{type(exc).__name__}: {exc}", FETCH_COLUMNS, meta)
        if not page["text"]:
            return _failure("web_fetch", "web_fetch returned no readable text", FETCH_COLUMNS, page["meta"])
        row = {key: page[key] for key in FETCH_COLUMNS}
        return sanitize_for_wire({
            "ok": True,
            "tool": "web_fetch",
            "rows": [row],
            "columns": FETCH_COLUMNS,
            "meta": page["meta"],
        })

    return {"web_search": web_search, "web_fetch": web_fetch}
