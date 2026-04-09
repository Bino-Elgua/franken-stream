"""Podcast provider — iTunes search + RSS feed parsing, no API key required."""

from typing import Dict, List, Optional

import requests


class PodcastProvider:
    """
    Search podcasts via the iTunes Search API and fetch episodes from RSS feeds.

    No API key required — iTunes Search is a public API.
    feedparser is used for RSS parsing; falls back to basic XML if unavailable.
    """

    ITUNES_URL = "https://itunes.apple.com/search"

    def search(self, query: str, limit: int = 20) -> List[Dict]:
        """Search for podcasts matching *query*."""
        params = {
            "term": query,
            "media": "podcast",
            "entity": "podcast",
            "limit": limit,
        }
        try:
            response = requests.get(self.ITUNES_URL, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
        except Exception:
            return []

        results = []
        for item in data.get("results", []):
            artwork = item.get("artworkUrl600", "") or item.get("artworkUrl100", "")
            results.append({
                "title": item.get("collectionName", "Unknown"),
                "artist": item.get("artistName", "Unknown"),
                "feed_url": item.get("feedUrl", ""),
                "artwork": artwork,
                "episode_count": item.get("trackCount", 0),
                "genres": item.get("genres", []),
                "type": "podcast",
                "source": "itunes",
            })
        return results

    def get_episodes(self, feed_url: str, limit: int = 10) -> List[Dict]:
        """Fetch episodes from an RSS feed URL."""
        try:
            import feedparser  # type: ignore
            feed = feedparser.parse(feed_url)
            return [self._parse_feedparser_entry(e) for e in feed.entries[:limit]]
        except ImportError:
            return self._get_episodes_fallback(feed_url, limit)

    def _parse_feedparser_entry(self, entry) -> Dict:
        audio_url: Optional[str] = None
        for link in entry.get("links", []):
            if link.get("type", "").startswith("audio/"):
                audio_url = link["href"]
                break
        if not audio_url:
            for enc in entry.get("enclosures", []):
                if enc.get("type", "").startswith("audio/"):
                    audio_url = enc.get("href") or enc.get("url", "")
                    break

        return {
            "title": entry.get("title", "Unknown"),
            "description": entry.get("summary", "")[:300],
            "url": audio_url or "",
            "published": entry.get("published", ""),
            "duration": entry.get("itunes_duration", ""),
            "type": "podcast_episode",
            "source": "rss",
        }

    def _get_episodes_fallback(self, feed_url: str, limit: int) -> List[Dict]:
        """Minimal XML fallback when feedparser is not installed."""
        import re as _re

        try:
            response = requests.get(feed_url, timeout=15)
            response.raise_for_status()
            text = response.text
        except Exception:
            return []

        episodes = []
        items = _re.findall(r"<item>(.*?)</item>", text, _re.DOTALL)
        for item_xml in items[:limit]:
            title_m = _re.search(r"<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", item_xml)
            enc_m = _re.search(r'<enclosure[^>]+url=["\']([^"\']+)["\']', item_xml)
            pub_m = _re.search(r"<pubDate>(.*?)</pubDate>", item_xml)
            dur_m = _re.search(r"<itunes:duration>(.*?)</itunes:duration>", item_xml)

            episodes.append({
                "title": title_m.group(1).strip() if title_m else "Unknown",
                "description": "",
                "url": enc_m.group(1) if enc_m else "",
                "published": pub_m.group(1).strip() if pub_m else "",
                "duration": dur_m.group(1).strip() if dur_m else "",
                "type": "podcast_episode",
                "source": "rss",
            })
        return episodes
