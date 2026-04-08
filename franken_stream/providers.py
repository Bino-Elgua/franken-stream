"""Provider management and configuration."""

import hashlib
import json
import os
import statistics
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from rich.console import Console

console = Console()

# Cache TTL: 24 hours
CACHE_TTL = 86400


@dataclass
class ProviderStats:
    """Tracks health metrics for a single provider."""

    attempts: int = 0
    successes: int = 0
    response_times_ms: List[float] = field(default_factory=list)
    last_failure: Optional[str] = None  # ISO format string
    consecutive_failures: int = 0

    @property
    def success_rate(self) -> float:
        return self.successes / self.attempts if self.attempts > 0 else 0.5

    @property
    def avg_response_ms(self) -> float:
        if self.response_times_ms:
            return statistics.median(self.response_times_ms[-10:])
        return 1000.0

    def record_attempt(self, success: bool, response_ms: float) -> None:
        self.attempts += 1
        if success:
            self.successes += 1
            self.consecutive_failures = 0
        else:
            self.consecutive_failures += 1
            self.last_failure = datetime.now().isoformat()
        self.response_times_ms.append(response_ms)
        self.response_times_ms = self.response_times_ms[-100:]


class ProviderManager:
    """Handles loading, caching, and updating streaming providers."""

    def __init__(self):
        """Initialize provider manager with config directory."""
        self.config_dir = Path.home() / ".franken-stream"
        self.config_file = self.config_dir / "providers.json"
        self.health_file = self.config_dir / "provider_health.json"
        self.github_url = (
            "https://raw.githubusercontent.com/"
            "Bino-Elgua/stream-providers/main/providers.json"
        )
        self.providers: Optional[Dict[str, Any]] = None
        self.health: Dict[str, ProviderStats] = self._load_health()

    def _ensure_config_dir(self) -> None:
        """Create config directory if it doesn't exist."""
        self.config_dir.mkdir(parents=True, exist_ok=True)

    def load_providers(self) -> Dict[str, Any]:
        """
        Load providers from local JSON/TOML file or download from GitHub.

        Returns:
            Dictionary with movie_search_bases and embed_fallbacks.
        """
        if self.providers:
            return self.providers

        self._ensure_config_dir()

        config_file = self.config_file
        toml_file = self.config_dir / "providers.toml"

        if not config_file.exists() and toml_file.exists():
            config_file = toml_file

        if config_file.exists():
            try:
                with open(config_file, "rb") as f:
                    content = f.read()
                    if isinstance(content, str):
                        content = content.encode()
                    if config_file.suffix == ".toml":
                        self.providers = self._parse_toml(content)
                    else:
                        self.providers = json.loads(content.decode())
                console.log(
                    f"[green]✓[/green] Loaded providers from "
                    f"{config_file}"
                )
                return self.providers
            except Exception as e:
                console.log(
                    f"[red]✗[/red] Error parsing {config_file.name}: {e}"
                )

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

    @staticmethod
    def _parse_toml(content: bytes) -> Dict[str, Any]:
        try:
            import tomllib

            return tomllib.loads(content.decode())
        except ModuleNotFoundError:
            try:
                import tomli as tomllib

                return tomllib.loads(content.decode())
            except ImportError as exc:
                raise RuntimeError(
                    "TOML support requires Python 3.11+ or tomli installed"
                ) from exc

    def get_config_hash(self) -> str:
        """Return a stable hash of the loaded provider configuration."""
        providers = self.load_providers()
        serialized = json.dumps(providers, sort_keys=True).encode("utf-8")
        return hashlib.sha256(serialized).hexdigest()

    def _is_suppressed_provider(self, url: str) -> bool:
        stats = self.health.get(url)
        if not stats:
            return False

        if stats.success_rate < 0.3 and stats.consecutive_failures >= 3:
            if stats.last_failure:
                try:
                    last_fail = datetime.fromisoformat(stats.last_failure)
                    if datetime.now() - last_fail < timedelta(hours=1):
                        return True
                except ValueError:
                    pass
        return False

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
        if isinstance(providers, dict) and "provider" in providers:
            entries = [
                p for p in providers.get("provider", []) if p.get("enabled", True)
            ]
            entries.sort(key=lambda p: p.get("priority", 50))
            bases = []
            for entry in entries:
                base_url = entry.get("base_url") or entry.get("search_url")
                if base_url:
                    bases.append(base_url)
            if bases:
                return bases

        return providers.get("movie_search_bases", [])

    def get_embed_fallbacks(self) -> List[str]:
        """Get list of embed fallback hosts."""
        providers = self.load_providers()
        return providers.get("embed_fallbacks", [])

    def get_legal_sources(self) -> List[str]:
        """Get list of legal streaming sources."""
        providers = self.load_providers()
        if isinstance(providers, dict) and "provider" in providers:
            return [
                p.get("base_url")
                for p in providers.get("provider", [])
                if p.get("enabled", True) and p.get("legal", False)
                and p.get("base_url")
            ]
        return providers.get("legal_fallbacks", [])

    def _load_health(self) -> Dict[str, ProviderStats]:
        """Load provider health data from disk."""
        if self.health_file.exists():
            try:
                data = json.loads(self.health_file.read_text())
                return {k: ProviderStats(**v) for k, v in data.items()}
            except (json.JSONDecodeError, TypeError):
                pass
        return {}

    def _save_health(self) -> None:
        """Persist provider health data to disk."""
        self._ensure_config_dir()
        data = {
            url: {
                "attempts": s.attempts,
                "successes": s.successes,
                "response_times_ms": s.response_times_ms,
                "last_failure": s.last_failure,
                "consecutive_failures": s.consecutive_failures,
            }
            for url, s in self.health.items()
        }
        self.health_file.write_text(json.dumps(data, indent=2))

    def record_result(self, url: str, success: bool, response_ms: float) -> None:
        """Record a provider request outcome for health scoring."""
        if url not in self.health:
            self.health[url] = ProviderStats()
        self.health[url].record_attempt(success, response_ms)
        self._save_health()

    def get_ranked_search_bases(self) -> List[str]:
        """Return search base URLs sorted by reliability score (best first)."""
        bases = self.get_search_bases()

        def _score(url: str) -> float:
            stats = self.health.get(url, ProviderStats())
            reliability = stats.success_rate * 0.7
            speed = (1.0 / (1.0 + stats.avg_response_ms / 1000)) * 0.3
            penalty = 0.0
            if stats.consecutive_failures > 2:
                penalty += 0.3 * stats.consecutive_failures
            if stats.last_failure:
                try:
                    last_fail = datetime.fromisoformat(stats.last_failure)
                    if datetime.now() - last_fail < timedelta(minutes=5):
                        penalty += 0.5
                except ValueError:
                    pass
            return reliability + speed - penalty

        ranked = sorted(bases, key=_score, reverse=True)
        filtered = [url for url in ranked if not self._is_suppressed_provider(url)]
        return filtered or ranked

    def get_health_summary(self) -> List[Dict[str, Any]]:
        """Return health stats for all tracked providers."""
        summary = []
        for url in self.get_search_bases():
            stats = self.health.get(url, ProviderStats())
            summary.append({
                "url": url,
                "attempts": stats.attempts,
                "success_rate": round(stats.success_rate, 2),
                "avg_ms": round(stats.avg_response_ms, 1),
                "consecutive_failures": stats.consecutive_failures,
                "last_failure": stats.last_failure,
                "disabled": self._is_suppressed_provider(url),
            })
        return summary

    def validate_config(self) -> bool:
        """
        Validate providers configuration.

        Returns:
            True if config is valid, False otherwise
        """
        try:
            config = self.load_providers()

            # Check required fields
            required = ["movie_search_bases", "embed_fallbacks"]
            for key in required:
                if key not in config:
                    console.log(f"[red]✗ Missing required field: {key}")
                    return False

                if not isinstance(config[key], list):
                    console.log(
                        f"[red]✗ {key} must be a list, got {type(config[key])}"
                    )
                    return False

            # Warn if URLs look suspicious
            for url in config.get("movie_search_bases", []):
                if not isinstance(url, str):
                    console.log(f"[yellow]⚠ Invalid URL type: {url}")
                    continue

                if not url.startswith(("http://", "https://")):
                    console.log(f"[yellow]⚠ URL not HTTP(S): {url}")

            console.log("[green]✓[/green] Config is valid")
            return True

        except json.JSONDecodeError as e:
            console.log(f"[red]✗ Invalid JSON: {e}")
            return False
        except Exception as e:
            console.log(f"[red]✗ Validation error: {e}")
            return False
