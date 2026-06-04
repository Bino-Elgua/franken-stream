"""Tests for the FastAPI v1 API endpoints."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.testclient import TestClient

from franken_stream.web import web_app


# ── Fixture: test client with all heavy singletons mocked ────────────────────

@pytest.fixture
def client():
    mock_player = MagicMock()
    mock_player.play = AsyncMock(return_value={"status": "playing", "playback_id": "abc", "title": "Test"})
    mock_player.pause = AsyncMock(return_value=True)
    mock_player.resume = AsyncMock(return_value=True)
    mock_player.stop = AsyncMock(return_value=None)
    mock_player.seek = AsyncMock(return_value=True)
    mock_player.quit = AsyncMock(return_value=None)
    mock_player.get_status = AsyncMock(return_value={
        "is_playing": True, "playback_id": "abc", "title": "Test",
        "elapsed_seconds": 30.0, "duration_seconds": 5400.0, "mpv_running": True,
    })

    mock_watchlist = MagicMock()
    mock_watchlist.all = MagicMock(return_value=[])
    mock_watchlist.in_progress = MagicMock(return_value=[])
    mock_watchlist.add = MagicMock()
    mock_watchlist.update_progress = MagicMock()
    mock_watchlist.remove = MagicMock()

    with patch("franken_stream.web._player", mock_player), \
         patch("franken_stream.web._watchlist", mock_watchlist):
        with TestClient(web_app, raise_server_exceptions=True) as c:
            yield c


# ── Search ────────────────────────────────────────────────────────────────────

class TestV1Search:
    def test_returns_results(self, client):
        with patch("franken_stream.web.FTSCache") as mock_fts_cls, \
             patch("franken_stream.web.ProviderManager") as mock_pm_cls, \
             patch("franken_stream.web.AsyncContentScraper") as mock_scraper_cls, \
             patch("franken_stream.web._get_preloader") as mock_preloader:

            mock_fts = MagicMock()
            mock_fts.lookup = MagicMock(return_value=None)
            mock_fts.store = MagicMock()
            mock_fts_cls.return_value = mock_fts

            mock_pm = MagicMock()
            mock_pm.get_ranked_search_bases = MagicMock(return_value=["https://p.com/search?q="])
            mock_pm.search_plugins = AsyncMock(return_value=[])
            mock_pm_cls.return_value = mock_pm

            mock_scraper = MagicMock()
            mock_scraper.search = AsyncMock(return_value=[("Inception", "https://p.com/movie/inception")])
            mock_scraper.close = AsyncMock()
            mock_scraper_cls.return_value = mock_scraper

            mock_loader = MagicMock()
            mock_loader.preload = AsyncMock()
            mock_preloader.return_value = mock_loader

            res = client.post("/api/v1/search", json={"query": "inception"})

        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "ok"
        assert len(data["results"]) == 1
        assert data["results"][0]["title"] == "Inception"

    def test_returns_cached_results(self, client):
        with patch("franken_stream.web.FTSCache") as mock_fts_cls, \
             patch("franken_stream.web._get_preloader") as mock_preloader:
            mock_fts = MagicMock()
            mock_fts.lookup = MagicMock(return_value=[("Cached Film", "https://cached.com")])
            mock_fts_cls.return_value = mock_fts

            mock_loader = MagicMock()
            mock_loader.preload = AsyncMock()
            mock_preloader.return_value = mock_loader

            res = client.post("/api/v1/search", json={"query": "cached film"})

        assert res.status_code == 200
        data = res.json()
        assert data["cached"] is True
        assert data["results"][0]["title"] == "Cached Film"

    def test_rejects_empty_query(self, client):
        res = client.post("/api/v1/search", json={"query": ""})
        assert res.status_code == 400


# ── Provider endpoints ────────────────────────────────────────────────────────

class TestV1Providers:
    def test_v1_providers(self, client):
        with patch("franken_stream.web.ProviderManager") as mock_cls:
            pm = MagicMock()
            pm.get_ranked_search_bases.return_value = ["https://a.com"]
            pm.get_embed_fallbacks.return_value = ["vidcloud"]
            pm.get_health_summary.return_value = []
            mock_cls.return_value = pm
            res = client.get("/api/v1/providers")
        assert res.status_code == 200
        assert "search_bases" in res.json()


# ── Skills manifest ───────────────────────────────────────────────────────────

class TestSkillsManifest:
    def test_manifest_shape(self, client):
        res = client.get("/api/v1/skills/manifest")
        assert res.status_code == 200
        data = res.json()
        assert "skill" in data
        assert "actions" in data
        assert data["skill"]["id"] == "franken-stream"


# ── Play endpoints ────────────────────────────────────────────────────────────

class TestV1Play:
    def test_play_url(self, client):
        res = client.post("/api/v1/play", json={"url": "https://stream.example.com/v.m3u8", "title": "Movie"})
        assert res.status_code == 200
        assert res.json()["status"] == "playing"

    def test_play_missing_url(self, client):
        res = client.post("/api/v1/play", json={"title": "No URL"})
        assert res.status_code == 400


# ── Control endpoint ──────────────────────────────────────────────────────────

class TestV1Control:
    def test_pause(self, client):
        res = client.post("/api/v1/control", json={"action": "pause"})
        assert res.status_code == 200
        assert res.json()["action"] == "pause"

    def test_resume(self, client):
        res = client.post("/api/v1/control", json={"action": "resume"})
        assert res.status_code == 200

    def test_stop(self, client):
        res = client.post("/api/v1/control", json={"action": "stop"})
        assert res.status_code == 200
        assert res.json()["ok"] is True

    def test_seek_requires_position(self, client):
        res = client.post("/api/v1/control", json={"action": "seek"})
        assert res.status_code == 400

    def test_seek_with_position(self, client):
        res = client.post("/api/v1/control", json={"action": "seek", "position": 300})
        assert res.status_code == 200

    def test_unknown_action(self, client):
        res = client.post("/api/v1/control", json={"action": "fly"})
        assert res.status_code == 400


# ── Status endpoint ───────────────────────────────────────────────────────────

class TestV1Status:
    def test_status_shape(self, client):
        res = client.get("/api/v1/status")
        assert res.status_code == 200
        data = res.json()
        assert "is_playing" in data
        assert "elapsed_seconds" in data


# ── Watchlist endpoints ───────────────────────────────────────────────────────

class TestV1Watchlist:
    def test_list_all(self, client):
        res = client.get("/api/v1/watchlist")
        assert res.status_code == 200
        assert "items" in res.json()

    def test_list_in_progress(self, client):
        res = client.get("/api/v1/watchlist/in-progress")
        assert res.status_code == 200
        assert "items" in res.json()

    def test_add_item(self, client):
        res = client.post("/api/v1/watchlist", json={
            "title": "Oppenheimer",
            "url": "https://example.com/oppenheimer",
        })
        assert res.status_code == 200
        assert "id" in res.json()

    def test_add_item_missing_fields(self, client):
        res = client.post("/api/v1/watchlist", json={"title": "No URL"})
        assert res.status_code == 400

    def test_update_progress(self, client):
        res = client.patch("/api/v1/watchlist/abc123", json={"progress_seconds": 300})
        assert res.status_code == 200
        assert res.json()["status"] == "ok"

    def test_update_progress_missing_field(self, client):
        res = client.patch("/api/v1/watchlist/abc123", json={})
        assert res.status_code == 400

    def test_remove_item(self, client):
        res = client.delete("/api/v1/watchlist/abc123")
        assert res.status_code == 200
        assert res.json()["status"] == "ok"


# ── Player spin-up ────────────────────────────────────────────────────────────

class TestPlayerSpinUp:
    def test_spin_up_missing_query(self, client):
        res = client.post("/api/v1/player/spin-up", json={})
        assert res.status_code == 400

    def test_spin_up_no_results(self, client):
        with patch("franken_stream.web.FTSCache") as fts_cls, \
             patch("franken_stream.web.ProviderManager") as pm_cls, \
             patch("franken_stream.web.AsyncContentScraper") as scraper_cls:
            fts_cls.return_value.lookup = MagicMock(return_value=None)
            pm_cls.return_value.get_ranked_search_bases = MagicMock(return_value=[])
            scraper = MagicMock()
            scraper.search = AsyncMock(return_value=[])
            scraper.close = AsyncMock()
            scraper_cls.return_value = scraper
            res = client.post("/api/v1/player/spin-up", json={"query": "unknown film xyz"})
        assert res.status_code == 404


# ── Embed endpoint ────────────────────────────────────────────────────────────

class TestV1Embed:
    def test_embed_returns_embed_url(self, client):
        # media_id is a slug/identifier (path params can't contain slashes)
        with patch("franken_stream.web.ProviderManager"), \
             patch("franken_stream.web.AsyncContentScraper") as scraper_cls:
            scraper = MagicMock()
            scraper.fetch_embed_from_page = AsyncMock(return_value="https://embed.example.com/stream")
            scraper.close = AsyncMock()
            scraper_cls.return_value = scraper
            res = client.get("/api/v1/embed/movie-inception-2010")
        assert res.status_code == 200
        assert res.json()["embed_url"] == "https://embed.example.com/stream"

    def test_legacy_embed_post(self, client):
        with patch("franken_stream.web.ProviderManager"), \
             patch("franken_stream.web.ContentScraper") as scraper_cls:
            scraper = MagicMock()
            scraper.fetch_embed_from_page = MagicMock(return_value="https://embed.example.com")
            scraper_cls.return_value = scraper
            res = client.post("/api/embed", json={"url": "https://example.com/movie/1"})
        assert res.status_code == 200
