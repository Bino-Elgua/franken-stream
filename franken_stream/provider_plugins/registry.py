"""Plugin registry with auto-discovery from ~/.franken-stream/plugins/."""

import importlib.util
import logging
from pathlib import Path
from typing import Dict, List, Optional

from .base import ProviderPlugin, MediaItem

logger = logging.getLogger(__name__)


class ProviderRegistry:
    """
    Central registry of all provider plugins.

    Built-in providers are registered at import time. Users can add their own
    by dropping a .py file into ~/.franken-stream/plugins/ containing one or
    more ProviderPlugin subclasses.
    """

    def __init__(self):
        self._providers: Dict[str, ProviderPlugin] = {}
        self._load_builtin()
        self._load_user_plugins()

    def _load_builtin(self) -> None:
        """Register bundled providers."""
        from .archive import InternetArchiveProvider
        from .tubi import TubiProvider
        from .pluto import PlutoTVProvider

        for cls in [InternetArchiveProvider, TubiProvider, PlutoTVProvider]:
            try:
                p = cls()
                self.register(p)
            except Exception as e:
                logger.warning("Failed to load built-in provider %s: %s", cls.__name__, e)

    def _load_user_plugins(self) -> None:
        """Load user plugins from ~/.franken-stream/plugins/."""
        plugin_dir = Path.home() / ".franken-stream" / "plugins"
        if not plugin_dir.exists():
            return

        for path in plugin_dir.glob("*.py"):
            try:
                spec = importlib.util.spec_from_file_location(path.stem, path)
                if spec is None or spec.loader is None:
                    continue
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (
                        isinstance(attr, type)
                        and issubclass(attr, ProviderPlugin)
                        and attr is not ProviderPlugin
                    ):
                        p = attr()
                        self.register(p)
                        logger.info("Loaded user plugin: %s", p.name)
            except Exception as e:
                logger.warning("Failed to load plugin %s: %s", path.name, e)

    def register(self, provider: ProviderPlugin) -> None:
        self._providers[provider.name] = provider

    def get(self, name: str) -> Optional[ProviderPlugin]:
        return self._providers.get(name)

    def all(self) -> List[ProviderPlugin]:
        return list(self._providers.values())

    def legal_only(self) -> List[ProviderPlugin]:
        return [p for p in self._providers.values() if p.legal]

    async def search_all(self, query: str, media_type: str = "any") -> List[MediaItem]:
        """Search all registered providers concurrently, deduplicate by URL."""
        import asyncio

        tasks = [
            asyncio.create_task(p.search(query, media_type))
            for p in self._providers.values()
        ]

        results: List[MediaItem] = []
        seen_urls: set = set()

        for coro in asyncio.as_completed(tasks):
            try:
                items = await coro
                for item in items:
                    if item.url not in seen_urls:
                        seen_urls.add(item.url)
                        results.append(item)
            except Exception:
                continue

        return results

    async def health_check_all(self) -> Dict[str, bool]:
        import asyncio
        results = await asyncio.gather(
            *[p.health_check() for p in self._providers.values()],
            return_exceptions=True,
        )
        return {
            name: (r is True)
            for name, r in zip(self._providers.keys(), results)
        }
