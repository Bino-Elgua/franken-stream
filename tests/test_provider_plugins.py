"""Tests for provider plugin system."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from franken_stream.provider_plugins.base import MediaItem, ProviderPlugin
from franken_stream.provider_plugins.registry import ProviderRegistry


# ── Concrete stub for abstract base ──────────────────────────────────────────

class StubProvider(ProviderPlugin):
    name = "stub"
    base_url = "https://stub.example.com"
    legal = True

    def __init__(self, items=None):
        self._items = items or []

    async def search(self, query, media_type="any"):
        return self._items

    async def extract_embed(self, page_url):
        return None


# ── MediaItem ─────────────────────────────────────────────────────────────────

class TestMediaItem:
    def test_defaults(self):
        item = MediaItem(id="1", title="Test", url="https://t.com", provider="stub")
        assert item.media_type == "movie"
        assert item.quality == "unknown"
        assert item.year is None

    def test_all_fields(self):
        item = MediaItem(
            id="x", title="Dune", url="https://a.com",
            provider="tubi", year=2021, media_type="movie",
            quality="HD", thumbnail="https://t.com/img.jpg",
            description="Epic sci-fi",
        )
        assert item.year == 2021
        assert item.description == "Epic sci-fi"


# ── ProviderPlugin ABC ────────────────────────────────────────────────────────

class TestProviderPluginBase:
    def test_stub_is_instantiable(self):
        p = StubProvider()
        assert p.name == "stub"
        assert p.legal is True

    async def test_stub_search_returns_items(self):
        items = [MediaItem(id="1", title="Movie", url="https://a.com", provider="stub")]
        p = StubProvider(items=items)
        result = await p.search("movie")
        assert result == items

    async def test_health_check_returns_bool_on_connection_error(self):
        p = StubProvider()
        with patch("aiohttp.ClientSession") as mock_cls:
            mock_cls.return_value.__aenter__ = AsyncMock(side_effect=Exception("no network"))
            result = await p.health_check()
        assert isinstance(result, bool)


# ── ProviderRegistry ──────────────────────────────────────────────────────────

class TestProviderRegistry:
    def test_loads_builtin_providers(self):
        reg = ProviderRegistry()
        names = {p.name for p in reg.all()}
        assert "internet_archive" in names
        assert "tubi" in names
        assert "pluto_tv" in names

    def test_register_adds_provider(self):
        reg = ProviderRegistry()
        stub = StubProvider()
        reg.register(stub)
        assert reg.get("stub") is stub

    def test_get_returns_none_for_unknown(self):
        reg = ProviderRegistry()
        assert reg.get("nonexistent") is None

    def test_legal_only_filters(self):
        reg = ProviderRegistry()
        for p in reg.legal_only():
            assert p.legal is True

    def test_all_returns_list(self):
        reg = ProviderRegistry()
        assert isinstance(reg.all(), list)
        assert len(reg.all()) >= 3

    async def test_search_all_aggregates_results(self):
        reg = ProviderRegistry()
        item_a = MediaItem(id="a", title="Movie A", url="https://a.com", provider="stub_a")
        item_b = MediaItem(id="b", title="Movie B", url="https://b.com", provider="stub_b")

        class ProvA(StubProvider):
            name = "stub_a"
        class ProvB(StubProvider):
            name = "stub_b"

        reg._providers = {
            "stub_a": ProvA([item_a]),
            "stub_b": ProvB([item_b]),
        }
        results = await reg.search_all("test")
        urls = {r.url for r in results}
        assert "https://a.com" in urls
        assert "https://b.com" in urls

    async def test_search_all_deduplicates_by_url(self):
        reg = ProviderRegistry()
        same_item = MediaItem(id="s", title="Same", url="https://same.com", provider="stub")

        class P1(StubProvider):
            name = "p1"
        class P2(StubProvider):
            name = "p2"

        reg._providers = {"p1": P1([same_item]), "p2": P2([same_item])}
        results = await reg.search_all("same")
        urls = [r.url for r in results]
        assert urls.count("https://same.com") == 1

    async def test_search_all_tolerates_plugin_exception(self):
        reg = ProviderRegistry()

        class BrokenProvider(ProviderPlugin):
            name = "broken"
            base_url = ""
            async def search(self, query, media_type="any"):
                raise RuntimeError("provider down")
            async def extract_embed(self, url):
                return None

        reg._providers = {"broken": BrokenProvider()}
        results = await reg.search_all("test")
        assert results == []

    async def test_health_check_all_returns_dict(self):
        reg = ProviderRegistry()
        reg._providers = {"stub": StubProvider()}

        with patch.object(StubProvider, "health_check", new_callable=lambda: lambda self: AsyncMock(return_value=True)()):
            pass  # just ensure method exists

        results = await reg.health_check_all()
        assert isinstance(results, dict)
        assert "stub" in results
