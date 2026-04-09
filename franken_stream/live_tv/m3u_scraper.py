"""Live TV provider — parses M3U playlists from IPTV-org and similar sources."""

import re
from typing import Dict, List, Optional

import requests


class LiveTVProvider:
    """
    Fetch and search live TV channels from public M3U playlist sources.

    Primary source: iptv-org (8,000+ channels across 200+ countries).
    Falls back to secondary sources if the primary fails.
    """

    M3U_SOURCES = [
        "https://iptv-org.github.io/iptv/index.m3u",
        "https://raw.githubusercontent.com/Free-TV/IPTV/master/playlist.m3u8",
    ]

    # iptv-org provides per-category playlists; map friendly names to paths
    CATEGORY_PLAYLISTS = {
        "news": "https://iptv-org.github.io/iptv/categories/news.m3u",
        "sports": "https://iptv-org.github.io/iptv/categories/sports.m3u",
        "entertainment": "https://iptv-org.github.io/iptv/categories/entertainment.m3u",
        "movies": "https://iptv-org.github.io/iptv/categories/movies.m3u",
        "kids": "https://iptv-org.github.io/iptv/categories/kids.m3u",
        "music": "https://iptv-org.github.io/iptv/categories/music.m3u",
        "documentary": "https://iptv-org.github.io/iptv/categories/documentary.m3u",
        "cooking": "https://iptv-org.github.io/iptv/categories/cooking.m3u",
        "lifestyle": "https://iptv-org.github.io/iptv/categories/lifestyle.m3u",
        "travel": "https://iptv-org.github.io/iptv/categories/travel.m3u",
        "science": "https://iptv-org.github.io/iptv/categories/science.m3u",
        "business": "https://iptv-org.github.io/iptv/categories/business.m3u",
    }

    def get_channels(
        self,
        category: Optional[str] = None,
        country: Optional[str] = None,
        limit: int = 200,
    ) -> List[Dict]:
        """
        Return live TV channels, optionally filtered by category or country.

        Uses the category-specific playlist when *category* is provided,
        which is faster than fetching the full 8,000-channel index.
        """
        category_key = (category or "").lower()
        if category_key in self.CATEGORY_PLAYLISTS:
            sources = [self.CATEGORY_PLAYLISTS[category_key]]
        else:
            sources = self.M3U_SOURCES

        channels: List[Dict] = []
        for source in sources:
            try:
                response = requests.get(source, timeout=20)
                response.raise_for_status()
                parsed = self._parse_m3u(response.text, category_filter=category)
                channels.extend(parsed)
                if channels:
                    break
            except Exception:
                continue

        if country:
            country_lower = country.lower()
            channels = [
                c for c in channels
                if country_lower in c.get("country", "").lower()
            ]

        return channels[:limit]

    def search(self, query: str) -> List[Dict]:
        """Search for channels whose name contains *query*."""
        all_channels = self.get_channels()
        query_lower = query.lower()
        return [c for c in all_channels if query_lower in c["title"].lower()]

    def get_categories(self) -> List[str]:
        """Return the list of supported category names."""
        return sorted(self.CATEGORY_PLAYLISTS.keys())

    def _parse_m3u(
        self, text: str, category_filter: Optional[str] = None
    ) -> List[Dict]:
        channels: List[Dict] = []
        current: Dict = {}

        for line in text.splitlines():
            line = line.strip()
            if line.startswith("#EXTINF:"):
                current = self._parse_extinf(line)
                if category_filter:
                    group = current.get("group", "").lower()
                    if category_filter.lower() not in group:
                        current = {}
            elif line.startswith("http") and current:
                current["url"] = line
                channels.append(current)
                current = {}

        return channels

    def _parse_extinf(self, line: str) -> Dict:
        name_m = re.search(r",(.+)$", line)
        group_m = re.search(r'group-title="([^"]*)"', line)
        logo_m = re.search(r'tvg-logo="([^"]*)"', line)
        country_m = re.search(r'tvg-country="([^"]*)"', line)
        lang_m = re.search(r'tvg-language="([^"]*)"', line)
        id_m = re.search(r'tvg-id="([^"]*)"', line)

        return {
            "title": name_m.group(1).strip() if name_m else "Unknown",
            "group": group_m.group(1) if group_m else "General",
            "logo": logo_m.group(1) if logo_m else "",
            "country": country_m.group(1) if country_m else "",
            "language": lang_m.group(1) if lang_m else "",
            "tvg_id": id_m.group(1) if id_m else "",
            "type": "live_tv",
            "source": "iptv-org",
        }
