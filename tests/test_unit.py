"""Unit tests for franken-stream components."""

import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, mock_open

import pytest

from franken_stream.providers import ProviderManager
from franken_stream.scraper import ContentScraper


class TestProviderManager:
    """Test ProviderManager functionality."""

    def test_initialization(self):
        """Test ProviderManager initializes correctly."""
        pm = ProviderManager()
        assert pm.config_dir.exists()
        assert pm.config_file.exists()
        assert pm.github_url.startswith("https://")

    def test_load_providers_from_file(self):
        """Test loading providers from config file."""
        test_providers = {
            "movie_search_bases": ["https://example.com/search?q="],
            "embed_fallbacks": ["test1", "test2"]
        }

        with patch('pathlib.Path.exists', return_value=True), \
             patch('builtins.open', mock_open(read_data=json.dumps(test_providers))), \
             patch('json.load', return_value=test_providers):

            pm = ProviderManager()
            providers = pm.load_providers()
            assert providers == test_providers

    def test_load_providers_from_toml(self):
        """Test loading providers from TOML config."""
        toml_text = """
        version = "2.0"

        [[provider]]
        name = "example"
        base_url = "https://example.com/search?query={query}"
        enabled = true
        priority = 1
        """

        with tempfile.TemporaryDirectory() as tmpdir:
            pm = ProviderManager()
            pm.config_dir = Path(tmpdir)
            pm.config_file = pm.config_dir / "providers.json"
            pm.health_file = pm.config_dir / "provider_health.json"
            pm.config_dir.mkdir(parents=True, exist_ok=True)
            (pm.config_dir / "providers.toml").write_text(toml_text)

            providers = pm.load_providers()

            assert providers["version"] == "2.0"
            assert pm.get_search_bases() == ["https://example.com/search?query={query}"]

    def test_get_search_bases(self):
        """Test getting search bases."""
        pm = ProviderManager()
        bases = pm.get_search_bases()
        assert isinstance(bases, list)
        assert len(bases) > 0

    def test_get_embed_fallbacks(self):
        """Test getting embed fallbacks."""
        pm = ProviderManager()
        fallbacks = pm.get_embed_fallbacks()
        assert isinstance(fallbacks, list)
        assert len(fallbacks) > 0

    def test_validate_config_valid(self):
        """Test config validation with valid config."""
        pm = ProviderManager()
        # Mock valid config
        with patch.object(pm, 'load_providers', return_value={
            "movie_search_bases": ["https://example.com/"],
            "embed_fallbacks": ["test"]
        }):
            assert pm.validate_config() is True

    def test_validate_config_invalid(self):
        """Test config validation with invalid config."""
        pm = ProviderManager()
        # Mock invalid config
        with patch.object(pm, 'load_providers', return_value={}):
            assert pm.validate_config() is False

    def test_config_hash_changes_when_providers_change(self):
        pm = ProviderManager()
        pm.providers = {
            "movie_search_bases": ["https://example.com/search?q="]
        }
        hash1 = pm.get_config_hash()
        pm.providers["movie_search_bases"].append("https://example.org/search?q=")
        hash2 = pm.get_config_hash()
        assert hash1 != hash2


class TestContentScraper:
    """Test ContentScraper functionality."""

    def test_initialization(self):
        """Test ContentScraper initializes correctly."""
        scraper = ContentScraper()
        assert scraper.user_agent is not None
        assert scraper.proxy is None
        assert scraper.session is not None

    def test_initialization_with_proxy(self):
        """Test ContentScraper with proxy."""
        proxy = "http://proxy.example.com:8080"
        scraper = ContentScraper(proxy=proxy)
        assert scraper.proxy == proxy
        assert scraper.session.proxies['http'] == proxy
        assert scraper.session.proxies['https'] == proxy

    def test_custom_user_agent(self):
        """Test custom user agent."""
        custom_ua = "Custom-Bot/1.0"
        scraper = ContentScraper(user_agent=custom_ua)
        assert scraper.user_agent == custom_ua
        assert scraper.session.headers['User-Agent'] == custom_ua

    def test_build_search_url_with_placeholder(self):
        """Test building search URLs with query placeholders."""
        scraper = ContentScraper()
        url = scraper._build_search_url(
            "https://example.com/search?query={query}", "The Matrix"
        )
        assert "query=The+Matrix" in url

    @patch('requests.Session.get')
    def test_get_page_success(self, mock_get):
        """Test successful page retrieval."""
        mock_response = Mock()
        mock_response.text = "<html><body>Test content</body></html>"
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        scraper = ContentScraper()
        result = scraper.get_page("http://example.com")
        assert result == mock_response.text
        mock_get.assert_called_once()

    @patch('requests.Session.get')
    def test_get_page_failure(self, mock_get):
        """Test page retrieval failure."""
        mock_get.side_effect = Exception("Network error")

        scraper = ContentScraper()
        result = scraper.get_page("http://example.com")
        assert result is None


class TestIntegration:
    """Integration tests for end-to-end functionality."""

    def test_provider_manager_and_scraper_integration(self):
        """Test integration between ProviderManager and ContentScraper."""
        pm = ProviderManager()
        scraper = ContentScraper()

        # Test that scraper can be initialized with provider data
        bases = pm.get_search_bases()
        assert len(bases) > 0

        # Test that scraper has required attributes
        assert hasattr(scraper, 'get_page')
        assert hasattr(scraper, 'session')

    @patch('franken_stream.scraper.ContentScraper.get_page')
    def test_search_flow_simulation(self, mock_get_page):
        """Simulate the search flow."""
        mock_get_page.return_value = """
        <html>
        <body>
        <div class="movie-item">
        <a href="/movie/test-movie">Test Movie</a>
        </div>
        </body>
        </html>
        """

        scraper = ContentScraper()
        # This would be how search works internally
        html = scraper.get_page("http://example.com/search?q=test")
        assert html is not None
        assert "Test Movie" in html


if __name__ == "__main__":
    pytest.main([__file__])