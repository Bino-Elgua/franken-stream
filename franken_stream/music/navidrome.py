"""Navidrome self-hosted music provider (Subsonic API)."""

from typing import Dict, List, Optional

import requests


class NavidromeProvider:
    """Self-hosted music streaming via Navidrome / any Subsonic-compatible server."""

    def __init__(self, server_url: str, username: str, password: str):
        self.server = server_url.rstrip("/")
        self.username = username
        self.password = password

    def _params(self, extra: Optional[Dict] = None) -> Dict:
        params = {
            "u": self.username,
            "p": self.password,
            "c": "franken-stream",
            "f": "json",
            "v": "1.16.1",
        }
        if extra:
            params.update(extra)
        return params

    def _get(self, endpoint: str, extra: Optional[Dict] = None):
        response = requests.get(
            f"{self.server}/rest/{endpoint}",
            params=self._params(extra),
            timeout=10,
        )
        response.raise_for_status()
        return response.json().get("subsonic-response", {})

    def search(self, query: str) -> List[Dict]:
        """Search the music library for songs, albums, and artists."""
        data = self._get("search3", {"query": query, "songCount": 20})
        songs = data.get("searchResult3", {}).get("song", [])
        return [self._format_song(s) for s in songs]

    def _format_song(self, song: Dict) -> Dict:
        cover_id = song.get("coverArt", "")
        cover_url = (
            f"{self.server}/rest/getCoverArt?{self._cover_params(cover_id)}"
            if cover_id
            else ""
        )
        stream_url = (
            f"{self.server}/rest/stream?id={song['id']}&"
            + "&".join(f"{k}={v}" for k, v in self._params().items())
        )
        return {
            "title": song.get("title", "Unknown"),
            "artist": song.get("artist", "Unknown"),
            "album": song.get("album", ""),
            "url": stream_url,
            "cover": cover_url,
            "duration": song.get("duration", 0),
            "type": "music",
            "source": "navidrome",
        }

    def _cover_params(self, cover_id: str) -> str:
        params = self._params({"id": cover_id, "size": 300})
        return "&".join(f"{k}={v}" for k, v in params.items())

    def get_playlists(self) -> List[Dict]:
        """List all playlists."""
        data = self._get("getPlaylists")
        playlists = data.get("playlists", {}).get("playlist", [])
        return [
            {
                "id": p["id"],
                "name": p["name"],
                "count": p.get("songCount", 0),
                "type": "playlist",
                "source": "navidrome",
            }
            for p in playlists
        ]

    def get_playlist_songs(self, playlist_id: str) -> List[Dict]:
        """Get songs in a specific playlist."""
        data = self._get("getPlaylist", {"id": playlist_id})
        songs = data.get("playlist", {}).get("entry", [])
        return [self._format_song(s) for s in songs]
