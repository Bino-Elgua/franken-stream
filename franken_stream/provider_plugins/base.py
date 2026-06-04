"""Base class for provider plugins."""

import abc
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class MediaItem:
    """A single search result from a provider."""
    id: str
    title: str
    url: str
    provider: str
    year: Optional[int] = None
    media_type: str = "movie"   # "movie" | "tv" | "unknown"
    quality: str = "unknown"
    thumbnail: Optional[str] = None
    description: Optional[str] = None


class ProviderPlugin(abc.ABC):
    """
    Abstract base for provider plugins.

    To add a new provider, subclass this, implement `search()` and
    `extract_embed()`, then drop the file in
    ~/.franken-stream/plugins/ or register it programmatically.
    """

    name: str = ""
    base_url: str = ""
    supported_types: List[str] = ["movie", "tv"]
    legal: bool = True
    rate_limit: float = 1.0   # requests per second
    requires_js: bool = False

    @abc.abstractmethod
    async def search(self, query: str, media_type: str = "any") -> List[MediaItem]:
        """Search for media. Return a list of MediaItem."""
        ...

    @abc.abstractmethod
    async def extract_embed(self, page_url: str) -> Optional[str]:
        """Extract a playable URL from a detail/watch page."""
        ...

    async def health_check(self) -> bool:
        """Return True if the provider is reachable. Override for custom logic."""
        import aiohttp
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(self.base_url, timeout=aiohttp.ClientTimeout(total=5)) as r:
                    return r.status < 500
        except Exception:
            return False
