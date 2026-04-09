"""Radio Browser provider — 90,000+ free stations, no API key required."""

from typing import Dict, List, Optional

import requests


class RadioBrowserProvider:
    """Search and stream internet radio from radio-browser.info (no API key)."""

    API_URL = "https://de1.api.radio-browser.info/json"
    HEADERS = {"User-Agent": "franken-stream/1.0"}

    def search(
        self,
        name: str = "",
        genre: str = "",
        country: str = "",
        language: str = "",
        limit: int = 20,
    ) -> List[Dict]:
        """Search radio stations by name, genre, country, or language."""
        params = {
            "name": name,
            "tag": genre,
            "country": country,
            "language": language,
            "limit": limit,
            "order": "clickcount",
            "reverse": "true",
            "hidebroken": "true",
        }
        # Drop empty params to avoid polluting the query
        params = {k: v for k, v in params.items() if v not in ("", 0)}

        response = requests.get(
            f"{self.API_URL}/stations/search",
            params=params,
            headers=self.HEADERS,
            timeout=10,
        )
        response.raise_for_status()
        return [self._format_station(s) for s in response.json()]

    def get_by_uuid(self, station_uuid: str) -> Optional[Dict]:
        """Fetch a specific station by UUID."""
        response = requests.get(
            f"{self.API_URL}/stations/byuuid/{station_uuid}",
            headers=self.HEADERS,
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
        return self._format_station(data[0]) if data else None

    def get_popular(self, limit: int = 20) -> List[Dict]:
        """Return the most-clicked stations globally."""
        return self.search(limit=limit)

    def get_by_tag(self, tag: str, limit: int = 20) -> List[Dict]:
        """Return stations matching a genre/tag."""
        return self.search(genre=tag, limit=limit)

    def _format_station(self, s: Dict) -> Dict:
        tags = s.get("tags", "")
        genre = tags.split(",")[0].strip() if tags else "Unknown"
        return {
            "title": s.get("name", "Unknown"),
            "url": s.get("url_resolved") or s.get("url", ""),
            "genre": genre,
            "country": s.get("country", "Unknown"),
            "language": s.get("language", ""),
            "bitrate": s.get("bitrate", 0),
            "codec": s.get("codec", "mp3"),
            "homepage": s.get("homepage", ""),
            "favicon": s.get("favicon", ""),
            "type": "radio",
            "source": "radio-browser",
        }
