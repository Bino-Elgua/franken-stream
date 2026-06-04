"""Tubi TV provider — free with ads, 50k+ titles."""

import re
from typing import List, Optional
from urllib.parse import quote

import aiohttp

from .base import MediaItem, ProviderPlugin


class TubiProvider(ProviderPlugin):
    name = "tubi"
    base_url = "https://tubitv.com"
    legal = True
    requires_js = True  # full embed needs JS, but we can get metadata

    # Undocumented search API that returns JSON
    SEARCH_API = "https://tubitv.com/oz/search/{query}?nonVerified=1"

    async def search(self, query: str, media_type: str = "any") -> List[MediaItem]:
        url = self.SEARCH_API.format(query=quote(query))
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
            "Referer": "https://tubitv.com/",
        }
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(
                    url,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status != 200:
                        return []
                    data = await resp.json(content_type=None)

            results = []
            items = []
            # Response can be list or dict with "results" key
            if isinstance(data, list):
                items = data
            elif isinstance(data, dict):
                items = data.get("results", [])

            for item in items[:20]:
                content_id = str(item.get("id", ""))
                title = item.get("title", "")
                if not content_id or not title:
                    continue

                year = item.get("year")
                ctype = item.get("type", "movie")
                mtype = "tv" if ctype in ("s", "series") else "movie"

                slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
                path = f"/movies/{content_id}/{slug}" if mtype == "movie" else f"/series/{content_id}/{slug}"

                results.append(
                    MediaItem(
                        id=f"tubi:{content_id}",
                        title=title,
                        url=f"https://tubitv.com{path}",
                        provider=self.name,
                        year=year,
                        media_type=mtype,
                        quality="720p",
                        thumbnail=item.get("posterarts", [None])[0],
                    )
                )
            return results
        except Exception:
            return []

    async def extract_embed(self, page_url: str) -> Optional[str]:
        """Tubi requires JS for actual video; return the page URL for browser playback."""
        return page_url
