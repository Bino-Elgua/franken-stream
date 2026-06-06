"""Tests for PredictiveLoader."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from franken_stream.preloader import PredictiveLoader


@pytest.fixture
def mock_scraper():
    scraper = MagicMock()
    scraper.fetch_embed_from_page = AsyncMock(return_value="https://embed.example.com/stream")
    return scraper


class TestPreload:
    async def test_preload_fires_background_tasks(self, mock_scraper):
        loader = PredictiveLoader(mock_scraper, n=3)
        results = [("Movie A", "https://a.com"), ("Movie B", "https://b.com")]
        await loader.preload(results)
        assert len(loader._tasks) == 2

    async def test_preload_respects_n_limit(self, mock_scraper):
        loader = PredictiveLoader(mock_scraper, n=2)
        results = [
            ("Movie A", "https://a.com"),
            ("Movie B", "https://b.com"),
            ("Movie C", "https://c.com"),
        ]
        await loader.preload(results)
        assert len(loader._tasks) == 2
        assert "https://a.com" in loader._tasks
        assert "https://b.com" in loader._tasks
        assert "https://c.com" not in loader._tasks

    async def test_preload_does_not_duplicate_urls(self, mock_scraper):
        loader = PredictiveLoader(mock_scraper, n=5)
        results = [("Movie", "https://same.com")]
        await loader.preload(results)
        await loader.preload(results)  # second call for same URL
        assert len(loader._tasks) == 1

    async def test_preload_empty_results(self, mock_scraper):
        loader = PredictiveLoader(mock_scraper, n=3)
        await loader.preload([])
        assert len(loader._tasks) == 0


class TestGet:
    async def test_get_returns_preloaded_embed(self, mock_scraper):
        loader = PredictiveLoader(mock_scraper, n=3)
        await loader.preload([("Movie", "https://a.com")])
        # Allow the background task to complete
        await asyncio.sleep(0.1)
        result = await loader.get("https://a.com", timeout=1.0)
        assert result == "https://embed.example.com/stream"

    async def test_get_returns_none_for_unpreloaded_url(self, mock_scraper):
        loader = PredictiveLoader(mock_scraper, n=3)
        result = await loader.get("https://not-preloaded.com", timeout=0.1)
        assert result is None

    async def test_get_times_out_for_slow_fetch(self):
        scraper = MagicMock()

        async def slow_fetch(_url):
            await asyncio.sleep(5)
            return "https://embed.example.com"

        scraper.fetch_embed_from_page = slow_fetch
        loader = PredictiveLoader(scraper, n=3)
        await loader.preload([("Movie", "https://slow.com")])
        result = await loader.get("https://slow.com", timeout=0.05)
        assert result is None  # timed out


class TestCancelAll:
    async def test_cancel_all_clears_tasks(self, mock_scraper):
        loader = PredictiveLoader(mock_scraper, n=3)
        await loader.preload([("Movie", "https://a.com"), ("Show", "https://b.com")])
        loader.cancel_all()
        assert len(loader._tasks) == 0

    async def test_cancel_all_on_empty_loader_does_not_raise(self, mock_scraper):
        loader = PredictiveLoader(mock_scraper, n=3)
        loader.cancel_all()  # should not raise


class TestSafeFetch:
    async def test_safe_fetch_returns_none_on_exception(self):
        scraper = MagicMock()
        scraper.fetch_embed_from_page = AsyncMock(side_effect=Exception("network error"))
        loader = PredictiveLoader(scraper, n=3)
        result = await loader._safe_fetch("https://failing.com")
        assert result is None
