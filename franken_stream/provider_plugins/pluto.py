"""Pluto TV provider — free live TV and on-demand content."""

import re
from typing import List, Optional
from urllib.parse import quote

import aiohttp

from .base import MediaItem, ProviderPlugin


class PlutoTVProvider(ProviderPlugin):
    name = "pluto_tv"
    base_url = "https://pluto.tv"
    legal = True
    requires_js = False

    # Boot API returns full catalog metadata (no key needed)
    BOOT_API = (
        "https://boot.pluto.tv/v4/start"
        "?appName=web&appVersion=7.0&deviceVersion=114.0.0"
        "&deviceType=web&deviceMake=firefox&deviceModel=web"
        "&serverSideAds=false&constraints=&drmCapabilities=&clientID=pluto-web"
    )
    SEARCH_API = "https://pluto.tv/search/results?query={query}&limit=20"

    async def search(self, query: str, media_type: str = "any") -> List[MediaItem]:
        url = self.SEARCH_API.format(query=quote(query))
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
        }
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(
                    url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    if resp.status != 200:
                        return []
                    data = await resp.json(content_type=None)

            results = []
            items = []
            if isinstance(data, dict):
                items = data.get("movies", []) + data.get("series", [])
            elif isinstance(data, list):
                items = data

            for item in items[:20]:
                item_id = str(item.get("_id", item.get("id", "")))
                title = item.get("name", item.get("title", ""))
                if not item_id or not title:
                    continue

                slug = item.get("slug", re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-"))
                is_series = "seasons" in item or item.get("type") == "series"
                mtype = "tv" if is_series else "movie"
                path = f"/series/{slug}" if is_series else f"/movies/{slug}/{item_id}/details"

                year = None
                release = item.get("firstAired", item.get("year", ""))
                if release:
                    m = re.search(r"\b(19|20)\d{2}\b", str(release))
                    if m:
                        year = int(m.group(0))

                results.append(
                    MediaItem(
                        id=f"pluto:{item_id}",
                        title=title,
                        url=f"https://pluto.tv{path}",
                        provider=self.name,
                        year=year,
                        media_type=mtype,
                        quality="720p",
                        thumbnail=item.get("featuredImage", {}).get("path") if isinstance(item.get("featuredImage"), dict) else None,
                    )
                )
            return results
        except Exception:
            return []

    async def extract_embed(self, page_url: str) -> Optional[str]:
        """Pluto TV uses HLS; return the page URL for yt-dlp."""
        return page_url
