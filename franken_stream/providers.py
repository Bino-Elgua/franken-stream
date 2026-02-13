"""Provider management and configuration."""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from rich.console import Console

console = Console()


class ProviderManager:
    """Handles loading, caching, and updating streaming providers."""

    def __init__(self):
        """Initialize provider manager with config directory."""
        self.config_dir = Path.home() / ".franken-stream"
        self.config_file = self.config_dir / "providers.json"
        self.github_url = (
            "https://raw.githubusercontent.com/"
            "YOUR_GITHUB_USERNAME/stream-providers/main/providers.json"
        )
        self.providers: Optional[Dict[str, Any]] = None

    def _ensure_config_dir(self) -> None:
        """Create config directory if it doesn't exist."""
        self.config_dir.mkdir(parents=True, exist_ok=True)

    def load_providers(self) -> Dict[str, Any]:
        """
        Load providers from local file or download from GitHub.

        Returns:
            Dictionary with movie_search_bases and embed_fallbacks.
        """
        if self.providers:
            return self.providers

        self._ensure_config_dir()

        # Try to load from local file
        if self.config_file.exists():
            try:
                with open(self.config_file, "r") as f:
                    self.providers = json.load(f)
                console.log(
                    f"[green]✓[/green] Loaded providers from "
                    f"{self.config_file}"
                )
                return self.providers
            except json.JSONDecodeError as e:
                console.log(
                    f"[red]✗[/red] Error parsing providers.json: {e}"
                )

        # Download from GitHub or use defaults
        return self._fetch_or_create_providers()

    def _fetch_or_create_providers(self) -> Dict[str, Any]:
        """Fetch providers from GitHub or create default ones."""
        try:
            console.log("Fetching providers from GitHub...")
            response = requests.get(self.github_url, timeout=10)
            response.raise_for_status()
            self.providers = response.json()
            self._save_providers()
            console.log("[green]✓[/green] Downloaded providers from GitHub")
            return self.providers
        except (requests.RequestException, ValueError) as e:
            console.log(
                f"[yellow]⚠[/yellow] Could not fetch from GitHub: {e}"
            )
            console.log("Using default providers...")
            self.providers = self._get_default_providers()
            self._save_providers()
            return self.providers

    @staticmethod
    def _get_default_providers() -> Dict[str, Any]:
        """Return default provider configuration."""
        return {
            "movie_search_bases": [
                "https://fmovies.to/search?keyword=",
                "https://www.123movies.co/search/",
            ],
            "embed_fallbacks": [
                "mycloud",
                "upstream",
                "vidcloud",
                "streamwish",
            ],
        }

    def _save_providers(self) -> None:
        """Save providers to local JSON file."""
        try:
            with open(self.config_file, "w") as f:
                json.dump(self.providers, f, indent=2)
        except IOError as e:
            console.log(f"[red]✗[/red] Could not save providers: {e}")

    def update_providers(self) -> bool:
        """
        Refresh providers from GitHub.

        Returns:
            True if successful, False otherwise.
        """
        try:
            console.log("Updating providers from GitHub...")
            response = requests.get(self.github_url, timeout=10)
            response.raise_for_status()
            self.providers = response.json()
            self._save_providers()
            console.log("[green]✓[/green] Providers updated successfully")
            return True
        except requests.RequestException as e:
            console.log(
                f"[red]✗[/red] Failed to update providers: {e}"
            )
            return False

    def get_search_bases(self) -> List[str]:
        """Get list of movie search base URLs."""
        providers = self.load_providers()
        return providers.get("movie_search_bases", [])

    def get_embed_fallbacks(self) -> List[str]:
        """Get list of embed fallback hosts."""
        providers = self.load_providers()
        return providers.get("embed_fallbacks", [])
