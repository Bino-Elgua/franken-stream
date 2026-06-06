"""Tests for AsyncContentScraper."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from franken_stream.async_scraper import AsyncContentScraper


class MockResponse:
    def __init__(self, text: str = "", status: int = 200):
        self._text = text
        self.status = status

    async def text(self):
        return self._text

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        pass


def make_session(response: MockResponse):
    """Build a mock aiohttp ClientSession whose .get() yields response."""
    session = MagicMock()
    session.closed = False
    session.get = MagicMock(return_value=response)
    return session


class TestExtractResults:
    """_extract_results is synchronous — test directly."""

    def setup_method(self):
        self.scraper = AsyncContentScraper()

    def test_returns_empty_for_blank_html(self):
        assert self.scraper._extract_results("", "https://example.com") == []

    def test_extracts_anchor_hrefs(self):
        html = """
        <html><body>
          <a href="https://example.com/movie/inception">Inception (2010)</a>
          <a href="https://example.com/movie/matrix">The Matrix</a>
        </body></html>
        """
        results = self.scraper._extract_results(html, "https://example.com")
        titles = [t for t, _ in results]
        assert any("Inception" in t for t in titles)

    def test_resolves_relative_hrefs(self):
        html = '<a href="/movie/test">Test Movie</a>'
        results = self.scraper._extract_results(html, "https://example.com/search?q=test")
        assert any("https://example.com/movie/test" == u for _, u in results)

    def test_skips_short_titles(self):
        html = '<a href="https://example.com/x">X</a>'
        results = self.scraper._extract_results(html, "https://example.com")
        assert results == []

    def test_caps_results_at_15(self):
        links = "".join(
            f'<a href="https://example.com/movie/{i}">Movie Title {i:02d}</a>'
            for i in range(25)
        )
        html = f"<html><body>{links}</body></html>"
        results = self.scraper._extract_results(html, "https://example.com")
        assert len(results) <= 15


class TestSearchProvider:
    async def test_skips_open_circuit(self):
        scraper = AsyncContentScraper()
        scraper.circuit_breaker.record_failure("example.com")
        scraper.circuit_breaker.record_failure("example.com")
        scraper.circuit_breaker.record_failure("example.com")
        scraper.circuit_breaker.record_failure("example.com")
        scraper.circuit_breaker.record_failure("example.com")
        # circuit is now OPEN
        result = await scraper._search_provider("https://example.com/search?q=", "test")
        assert result == []
        await scraper.close()

    async def test_records_failure_on_none_response(self):
        scraper = AsyncContentScraper()
        with patch.object(scraper, "_get_page", return_value=None):
            await scraper._search_provider("https://fail.example.com/search?q=", "test")
        state = scraper.circuit_breaker.state_of("fail.example.com")
        from franken_stream.circuit_breaker import CircuitState
        # 1 failure is recorded
        cb = scraper.circuit_breaker._get("fail.example.com")
        assert cb.failure_count == 1

    async def test_returns_results_on_success(self):
        scraper = AsyncContentScraper()
        html = """<html><body>
          <a href="https://example.com/movie/inception">Inception (2010)</a>
        </body></html>"""
        with patch.object(scraper, "_get_page", return_value=html):
            results = await scraper._search_provider("https://example.com/search?q=", "inception")
        assert len(results) >= 1
        assert any("Inception" in t for t, _ in results)
        await scraper.close()


class TestSearch:
    async def test_search_returns_deduplicated_results(self):
        scraper = AsyncContentScraper()
        html = '<a href="https://provider.com/movie/test">Test Movie (2020)</a>'
        with patch.object(scraper, "_get_page", return_value=html):
            results = await scraper.search(
                "test", ["https://p1.com/search?q=", "https://p2.com/search?q="]
            )
        urls = [u for _, u in results]
        assert len(urls) == len(set(urls))
        await scraper.close()

    async def test_search_returns_empty_on_all_failures(self):
        scraper = AsyncContentScraper()
        with patch.object(scraper, "_get_page", return_value=None):
            results = await scraper.search("test", ["https://fail.com/search?q="])
        assert results == []
        await scraper.close()

    async def test_search_streaming_yields_results(self):
        scraper = AsyncContentScraper()
        html = '<a href="https://s.com/movie/one">Movie One</a>'
        with patch.object(scraper, "_get_page", return_value=html):
            items = []
            async for item in scraper.search_streaming("one", ["https://s.com/search?q="]):
                items.append(item)
        assert len(items) >= 1
        await scraper.close()


class TestFetchEmbed:
    async def test_returns_none_on_failed_fetch(self):
        scraper = AsyncContentScraper()
        with patch.object(scraper, "_get_page", return_value=None):
            result = await scraper.fetch_embed_from_page("https://example.com/movie/1")
        assert result is None
        await scraper.close()

    async def test_extracts_iframe_src(self):
        html = '<iframe src="https://embed.example.com/player/abc"></iframe>'
        scraper = AsyncContentScraper()
        with patch.object(scraper, "_get_page", return_value=html):
            result = await scraper.fetch_embed_from_page("https://example.com/movie/1")
        assert result == "https://embed.example.com/player/abc"
        await scraper.close()

    async def test_extracts_hls_stream(self):
        html = '<video src="https://cdn.example.com/stream.m3u8"></video>'
        scraper = AsyncContentScraper()
        with patch.object(scraper, "_get_page", return_value=html):
            result = await scraper.fetch_embed_from_page("https://example.com/movie/1")
        assert result == "https://cdn.example.com/stream.m3u8"
        await scraper.close()

    async def test_resolves_relative_iframe_src(self):
        html = '<iframe src="/embed/player/123"></iframe>'
        scraper = AsyncContentScraper()
        with patch.object(scraper, "_get_page", return_value=html):
            result = await scraper.fetch_embed_from_page("https://example.com/movie/1")
        assert result == "https://example.com/embed/player/123"
        await scraper.close()

    async def test_returns_none_when_no_pattern_matches(self):
        html = "<html><body><p>No embeds here.</p></body></html>"
        scraper = AsyncContentScraper()
        with patch.object(scraper, "_get_page", return_value=html):
            result = await scraper.fetch_embed_from_page("https://example.com/movie/1")
        assert result is None
        await scraper.close()


class TestClose:
    async def test_close_is_idempotent(self):
        scraper = AsyncContentScraper()
        await scraper._ensure_session()
        await scraper.close()
        await scraper.close()  # should not raise
