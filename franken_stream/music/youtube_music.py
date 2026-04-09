"""YouTube Music provider — search via page scraping, no API key required."""

import json
import re
from typing import Dict, List, Optional

import requests


class YouTubeMusicProvider:
    """Search YouTube Music by scraping ytInitialData (no API key)."""

    SEARCH_URL = "https://music.youtube.com/search"
    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Cookie": "CONSENT=YES+cb",
    }

    def search(self, query: str) -> List[Dict]:
        """Search YouTube Music for songs matching *query*."""
        try:
            response = requests.get(
                self.SEARCH_URL,
                params={"q": query},
                headers=self.HEADERS,
                timeout=15,
            )
            response.raise_for_status()
        except Exception:
            return []

        match = re.search(r"ytInitialData\s*=\s*(\{.+?\});\s*</script>", response.text)
        if not match:
            return []

        try:
            data = json.loads(match.group(1))
        except json.JSONDecodeError:
            return []

        songs: List[Dict] = []
        try:
            contents = (
                data["contents"]["sectionListRenderer"]["contents"]
            )
            for section in contents:
                shelf = section.get("musicShelfRenderer", {})
                for item in shelf.get("contents", []):
                    renderer = item.get("musicResponsiveListItemRenderer")
                    if renderer:
                        song = self._parse_item(renderer)
                        if song:
                            songs.append(song)
        except (KeyError, TypeError):
            pass

        return songs

    def _parse_item(self, renderer: Dict) -> Optional[Dict]:
        try:
            video_id = renderer["playlistItemData"]["videoId"]
        except (KeyError, TypeError):
            return None

        try:
            cols = renderer["flexColumns"]
            title = (
                cols[0]["musicResponsiveListItemFlexColumnRenderer"]
                ["text"]["runs"][0]["text"]
            )
        except (KeyError, IndexError, TypeError):
            return None

        artist = "Unknown"
        try:
            artist = (
                renderer["flexColumns"][1]
                ["musicResponsiveListItemFlexColumnRenderer"]
                ["text"]["runs"][0]["text"]
            )
        except (KeyError, IndexError, TypeError):
            pass

        return {
            "title": title,
            "artist": artist,
            "url": f"https://music.youtube.com/watch?v={video_id}",
            "video_id": video_id,
            "type": "music",
            "source": "youtube-music",
        }
