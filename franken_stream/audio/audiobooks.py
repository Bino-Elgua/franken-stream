"""LibriVox audiobook provider — free public domain audiobooks, no API key."""

from typing import Dict, List

import requests


class LibriVoxProvider:
    """Search and stream free audiobooks from LibriVox (public domain only)."""

    API_URL = "https://librivox.org/api/feed/audiobooks"

    def search(self, query: str, limit: int = 20) -> List[Dict]:
        """Search for audiobooks by title."""
        params = {
            "title": f"^{query}",
            "format": "json",
            "limit": limit,
            "offset": 0,
            "extended": 1,
        }
        try:
            response = requests.get(self.API_URL, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()
        except Exception:
            return []

        return [self._format_book(b) for b in data.get("books", [])]

    def search_by_author(self, author: str, limit: int = 20) -> List[Dict]:
        """Search for audiobooks by author last name."""
        params = {
            "author": author,
            "format": "json",
            "limit": limit,
            "extended": 1,
        }
        try:
            response = requests.get(self.API_URL, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()
        except Exception:
            return []

        return [self._format_book(b) for b in data.get("books", [])]

    def _format_book(self, book: Dict) -> Dict:
        authors = book.get("authors", [])
        if authors:
            a = authors[0]
            author_name = f"{a.get('first_name', '')} {a.get('last_name', '')}".strip()
        else:
            author_name = "Unknown"

        genres = book.get("genres", [])
        genre = genres[0].get("name", "Unknown") if genres else "Unknown"

        # Build RSS URL for chapter-level streaming
        rss_url = book.get("url_rss", "")
        librivox_url = book.get("url_librivox", "")
        if librivox_url and not librivox_url.startswith("http"):
            librivox_url = f"https://librivox.org{librivox_url}"

        return {
            "title": book.get("title", "Unknown"),
            "author": author_name,
            "language": book.get("language", "English"),
            "total_time": book.get("totaltimes", ""),
            "description": book.get("description", "")[:300],
            "url": librivox_url,
            "rss_url": rss_url,
            "cover": book.get("url_image", ""),
            "genre": genre,
            "type": "audiobook",
            "source": "librivox",
        }

    def get_chapters(self, rss_url: str) -> List[Dict]:
        """Fetch chapter list from the book's RSS feed."""
        if not rss_url:
            return []
        try:
            import feedparser  # type: ignore
            feed = feedparser.parse(rss_url)
            chapters = []
            for i, entry in enumerate(feed.entries, 1):
                audio_url = ""
                for enc in entry.get("enclosures", []):
                    if enc.get("type", "").startswith("audio/"):
                        audio_url = enc.get("href") or enc.get("url", "")
                        break
                chapters.append({
                    "chapter": i,
                    "title": entry.get("title", f"Chapter {i}"),
                    "url": audio_url,
                    "duration": entry.get("itunes_duration", ""),
                    "type": "audiobook_chapter",
                    "source": "librivox",
                })
            return chapters
        except ImportError:
            return []
