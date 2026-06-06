"""Predictive embed preloader — starts extracting embeds while user reads results."""

import asyncio
import logging
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class PredictiveLoader:
    """
    Pre-extract embed URLs for top N search results in the background
    so that when the user picks a result, playback starts near-instantly.

    Usage:
        loader = PredictiveLoader(scraper)
        await loader.preload(results[:3])
        # ... user picks result ...
        embed_url = await loader.get(result_url, fallback_fn)
    """

    def __init__(self, scraper, n: int = 3):
        """
        Args:
            scraper: An AsyncContentScraper instance.
            n: Number of top results to preload (default 3).
        """
        self.scraper = scraper
        self.n = n
        self._tasks: Dict[str, asyncio.Task] = {}

    async def preload(self, results: List[Tuple[str, str]]) -> None:
        """Start background embed extraction for the top N results."""
        for title, url in results[: self.n]:
            if url not in self._tasks:
                task = asyncio.create_task(
                    self._safe_fetch(url), name=f"preload:{url[:50]}"
                )
                self._tasks[url] = task

    async def _safe_fetch(self, url: str) -> Optional[str]:
        try:
            return await self.scraper.fetch_embed_from_page(url)
        except Exception as e:
            logger.debug("Preload failed for %s: %s", url[:60], e)
            return None

    async def get(
        self,
        url: str,
        timeout: float = 0.5,
    ) -> Optional[str]:
        """
        Return the preloaded embed URL if available within `timeout` seconds.
        Returns None if not preloaded or not yet ready — caller should fall back
        to a direct fetch.
        """
        task = self._tasks.get(url)
        if task is None:
            return None
        try:
            return await asyncio.wait_for(asyncio.shield(task), timeout=timeout)
        except (asyncio.TimeoutError, Exception):
            return None

    def cancel_all(self) -> None:
        """Cancel all pending preload tasks."""
        for task in self._tasks.values():
            if not task.done():
                task.cancel()
        self._tasks.clear()
