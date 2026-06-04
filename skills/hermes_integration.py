"""Example Hermes/OpenAI-compatible agent skill for Franken-Stream."""

import json
import requests


class FrankenStreamSkill:
    """Franken-Stream skill for agent frameworks (Hermes, OpenClaw, custom)."""

    def __init__(self, base_url: str = "http://localhost:8000/api/v1"):
        self.base_url = base_url
        self._session = requests.Session()
        self._session.headers["Content-Type"] = "application/json"

    def search(self, query: str, media_type: str = "any", max_results: int = 10) -> list:
        """Search for movies or TV shows. Returns list of result dicts with id/title/year/type/quality."""
        resp = self._session.post(
            f"{self.base_url}/search",
            json={"query": query, "type": media_type, "max_results": max_results},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json().get("results", [])

    def play(self, media_id: str = None, url: str = None, title: str = "", quality: str = "best") -> dict:
        """Play a media item. Pass media_id from search results or a direct URL."""
        payload = {"quality": quality, "title": title}
        if media_id:
            payload["id"] = media_id
        elif url:
            payload["url"] = url
        else:
            raise ValueError("Either media_id or url is required")
        resp = self._session.post(f"{self.base_url}/play", json=payload, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def control(self, action: str, position: int = None) -> dict:
        """Control playback: action is one of pause/resume/stop/seek."""
        payload = {"action": action}
        if position is not None:
            payload["position"] = position
        resp = self._session.post(f"{self.base_url}/control", json=payload, timeout=10)
        resp.raise_for_status()
        return resp.json()

    def status(self) -> dict:
        """Get current playback status."""
        resp = self._session.get(f"{self.base_url}/status", timeout=5)
        resp.raise_for_status()
        return resp.json()

    def providers(self) -> dict:
        """List available providers and health stats."""
        resp = self._session.get(f"{self.base_url}/providers", timeout=10)
        resp.raise_for_status()
        return resp.json()
