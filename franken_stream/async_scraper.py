"""Async content scraper using aiohttp for maximum throughput."""

import asyncio
import re
import time
from typing import AsyncIterator, Dict, List, Optional, Tuple
from urllib.parse import quote_plus, urlparse

import aiohttp
from aiohttp import ClientTimeout, TCPConnector
from bs4 import BeautifulSoup

from franken_stream.circuit_breaker import CircuitBreaker

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/119.0.0.0 Safari/537.36"
)

EMBED_PATTERNS = [
    (r'iframe[^>]*src=["\']([^"\']+)["\']', "iframe src"),
    (r'<a[^>]*href=["\']([^"\']*(?:embed|player)[^"\']*)["\']', "embed link"),
    (r'src=["\']([^"\']*\.m3u8[^"\']*)["\']', "HLS stream"),
    (r'src=["\']([^"\']*\.mp4[^"\']*)["\']', "MP4 video"),
    (r'data-url=["\']([^"\']+)["\']', "data-url attribute"),
]

# Multiple CSS selector fallbacks per extraction type
RESULT_SELECTORS = [
    ("a.ml-mask",       lambda el: (el.get("title", el.get_text(strip=True)), el.get("href", ""))),
    ("a[href]",         lambda el: (el.get_text(strip=True), el.get("href", ""))),
    ("h2 a",            lambda el: (el.get_text(strip=True), el.get("href", ""))),
    (".item a",         lambda el: (el.get_text(strip=True), el.get("href", ""))),
    (".movie-card a",   lambda el: (el.get_text(strip=True), el.get("href", ""))),
]


class AsyncContentScraper:
    """
    Async scraper with connection pooling, circuit breakers, and streaming results.
    """

    def __init__(
        self,
        proxy: Optional[str] = None,
        user_agent: Optional[str] = None,
        provider_manager=None,
        max_connections: int = 100,
        max_per_host: int = 20,
    ):
        self.proxy = proxy
        self.user_agent = user_agent or DEFAULT_USER_AGENT
        self.provider_manager = provider_manager
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=5,
            recovery_timeout=300.0,
        )
        self._connector: Optional[TCPConnector] = None
        self._session: Optional[aiohttp.ClientSession] = None
        self._max_connections = max_connections
        self._max_per_host = max_per_host

    async def _ensure_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._connector = TCPConnector(
                limit=self._max_connections,
                limit_per_host=self._max_per_host,
                ttl_dns_cache=300,
                enable_cleanup_closed=True,
                force_close=False,
            )
            self._session = aiohttp.ClientSession(
                connector=self._connector,
                timeout=ClientTimeout(total=15, connect=5),
                headers={
                    "User-Agent": self.user_agent,
                    "Accept": "text/html,application/xhtml+xml",
                    "Accept-Language": "en-US,en;q=0.9",
                },
            )
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    async def _get_page(self, url: str, retries: int = 3) -> Optional[str]:
        """Fetch a URL with exponential backoff retry."""
        import random
        session = await self._ensure_session()
        for attempt in range(retries):
            try:
                kwargs: Dict = {}
                if self.proxy:
                    kwargs["proxy"] = self.proxy
                async with session.get(url, **kwargs) as resp:
                    if resp.status == 200:
                        return await resp.text()
                    return None
            except (aiohttp.ClientError, asyncio.TimeoutError):
                if attempt == retries - 1:
                    return None
                wait = (2 ** attempt) + random.uniform(0, 0.5)
                await asyncio.sleep(wait)
        return None

    def _extract_results(self, html: str, base_url: str) -> List[Tuple[str, str]]:
        """Try multiple CSS selectors in order, return first non-empty set."""
        if not html:
            return []
        soup = BeautifulSoup(html, "html.parser")
        host = urlparse(base_url).scheme + "://" + urlparse(base_url).netloc

        for selector, extractor in RESULT_SELECTORS:
            found = []
            for el in soup.select(selector):
                try:
                    title, href = extractor(el)
                    title = title.strip()
                    if not title or len(title) < 2:
                        continue
                    if href and href.startswith("/"):
                        href = host + href
                    if href and href.startswith("http") and title:
                        found.append((title, href))
                except Exception:
                    continue
            if found:
                return found[:15]
        return []

    async def _search_provider(
        self, base_url: str, query: str
    ) -> List[Tuple[str, str]]:
        """Search one provider, returning (title, url) pairs."""
        provider_name = urlparse(base_url).netloc
        if self.circuit_breaker.is_open(provider_name):
            return []

        search_url = base_url + quote_plus(query)
        start = time.monotonic()
        try:
            html = await self._get_page(search_url)
            elapsed_ms = (time.monotonic() - start) * 1000

            if html is None:
                self.circuit_breaker.record_failure(provider_name)
                if self.provider_manager:
                    self.provider_manager.record_result(base_url, False, elapsed_ms)
                return []

            results = self._extract_results(html, base_url)
            self.circuit_breaker.record_success(provider_name)
            if self.provider_manager:
                self.provider_manager.record_result(base_url, True, elapsed_ms)
            return results

        except Exception:
            self.circuit_breaker.record_failure(provider_name)
            elapsed_ms = (time.monotonic() - start) * 1000
            if self.provider_manager:
                self.provider_manager.record_result(base_url, False, elapsed_ms)
            return []

    async def search_streaming(
        self, query: str, bases: List[str]
    ) -> AsyncIterator[Tuple[str, str]]:
        """
        Yield (title, url) pairs as each provider responds.
        Results arrive within 1-2s instead of waiting for the slowest provider.
        """
        tasks = {
            asyncio.create_task(self._search_provider(base, query)): base
            for base in bases
        }
        seen_urls: set = set()

        for coro in asyncio.as_completed(list(tasks)):
            try:
                results = await coro
                for title, url in results:
                    if url not in seen_urls:
                        seen_urls.add(url)
                        yield title, url
            except Exception:
                continue

    async def search(
        self, query: str, bases: List[str]
    ) -> List[Tuple[str, str]]:
        """Collect all streaming results into a list."""
        results: List[Tuple[str, str]] = []
        async for item in self.search_streaming(query, bases):
            results.append(item)
        return results

    async def fetch_embed_from_page(
        self, page_url: str, base_url: Optional[str] = None
    ) -> Optional[str]:
        """Extract a playable embed URL from a detail page."""
        html = await self._get_page(page_url)
        if not html:
            return None

        host = base_url or (
            urlparse(page_url).scheme + "://" + urlparse(page_url).netloc
        )

        for pattern, _ in EMBED_PATTERNS:
            m = re.search(pattern, html, re.IGNORECASE)
            if m:
                url = m.group(1)
                if url.startswith("/"):
                    url = host + url
                if url.startswith(("http://", "https://", "//")):
                    return url
        return None

    async def validate_proxy(self, proxy_url: str) -> bool:
        """Return True if the proxy is reachable."""
        try:
            timeout = ClientTimeout(total=6)
            conn = TCPConnector()
            async with aiohttp.ClientSession(connector=conn, timeout=timeout) as s:
                async with s.get("https://www.example.com", proxy=proxy_url) as r:
                    return r.status < 500
        except Exception:
            return False
