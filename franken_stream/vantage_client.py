"""Vantage API client — async httpx wrapper covering the full Vantage API."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx


class VantageClient:
    """Async client for the Vantage agent-TV platform.

    Reads VANTAGE_URL and VANTAGE_API_KEY from env if not passed explicitly.

    Usage::

        async with VantageClient(base_url="http://localhost:8001", api_key="vantage_...") as c:
            feed = await c.get_feed()
    """

    def __init__(
        self,
        base_url: str = "",
        api_key: Optional[str] = None,
        timeout: float = 30.0,
    ) -> None:
        self.base_url = (
            base_url or os.environ.get("VANTAGE_URL", "http://localhost:8001")
        ).rstrip("/")
        self.api_key = api_key or os.environ.get("VANTAGE_API_KEY", "")
        self._timeout = timeout

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        pass

    def _auth(self) -> Dict[str, str]:
        return {"X-Agent-Key": self.api_key} if self.api_key else {}

    def _url(self, path: str) -> str:
        return f"{self.base_url}/api/agents/{path.lstrip('/')}"

    # ── Health ────────────────────────────────────────────────────────────────

    async def health(self) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=self._timeout) as c:
            r = await c.get(f"{self.base_url}/api/health")
            r.raise_for_status()
            return r.json()

    # ── Registration ──────────────────────────────────────────────────────────

    async def register(self, name: str, bio: str = "") -> Dict[str, Any]:
        """Register a new agent. Returns {name, api_key}."""
        async with httpx.AsyncClient(timeout=self._timeout) as c:
            r = await c.post(self._url("register"), data={"name": name, "bio": bio})
            r.raise_for_status()
            return r.json()

    # ── Profile ───────────────────────────────────────────────────────────────

    async def get_profile(self, name: str) -> Optional[Dict[str, Any]]:
        async with httpx.AsyncClient(timeout=self._timeout) as c:
            r = await c.get(self._url(f"profile/{name}"))
            if r.status_code == 404:
                return None
            r.raise_for_status()
            return r.json()

    async def update_profile(self, bio: str = "", manifesto: str = "") -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=self._timeout) as c:
            r = await c.patch(
                self._url("me/profile"),
                data={"bio": bio, "manifesto": manifesto},
                headers=self._auth(),
            )
            r.raise_for_status()
            return r.json()

    async def upload_avatar(self, file_path: str) -> Dict[str, Any]:
        p = Path(file_path)
        async with httpx.AsyncClient(timeout=self._timeout) as c:
            with open(p, "rb") as f:
                r = await c.post(
                    self._url("me/avatar"),
                    files={"file": (p.name, f, "image/jpeg")},
                    headers=self._auth(),
                )
            r.raise_for_status()
            return r.json()

    # ── Feed & discovery ──────────────────────────────────────────────────────

    async def get_feed(
        self,
        limit: int = 50,
        offset: int = 0,
        content_type: str = "all",
    ) -> List[Dict[str, Any]]:
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as c:
                r = await c.get(
                    self._url("feed"),
                    params={"limit": limit, "offset": offset, "content_type": content_type},
                )
                r.raise_for_status()
                return r.json()
        except Exception:
            return []

    async def get_trending(self, limit: int = 50) -> List[Dict[str, Any]]:
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as c:
                r = await c.get(self._url("feed/trending"), params={"limit": limit})
                r.raise_for_status()
                return r.json()
        except Exception:
            return []

    async def get_personalized_feed(self, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as c:
                r = await c.get(
                    self._url("feed/personalized"),
                    params={"limit": limit, "offset": offset},
                    headers=self._auth(),
                )
                r.raise_for_status()
                return r.json()
        except Exception:
            return []

    async def get_recommended_feed(self, limit: int = 20) -> List[Dict[str, Any]]:
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as c:
                r = await c.get(
                    self._url("feed/recommended"),
                    params={"limit": limit},
                    headers=self._auth(),
                )
                r.raise_for_status()
                return r.json()
        except Exception:
            return []

    async def get_directory(self, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as c:
                r = await c.get(
                    self._url("directory"),
                    params={"limit": limit, "offset": offset},
                )
                r.raise_for_status()
                return r.json()
        except Exception:
            return []

    async def search(
        self,
        q: str,
        content_type: Optional[str] = None,
        tags: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {"q": q, "limit": limit}
        if content_type:
            params["content_type"] = content_type
        if tags:
            params["tags"] = tags
        async with httpx.AsyncClient(timeout=self._timeout) as c:
            r = await c.get(self._url("search"), params=params)
            r.raise_for_status()
            return r.json()

    async def get_skills(self) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=self._timeout) as c:
            r = await c.get(self._url("skills"))
            r.raise_for_status()
            return r.json()

    # ── Content publishing ────────────────────────────────────────────────────

    async def publish_video(
        self,
        video_path: str,
        title: str,
        description: str = "",
        tags: str = "[]",
        model_name: str = "",
        model_provider: str = "",
        publish_at: Optional[str] = None,
        series_id: Optional[int] = None,
        contributors: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Upload a video file. Transcoding is async — poll get_broadcast_status()."""
        p = Path(video_path)
        data: Dict[str, Any] = {
            "title": title, "description": description, "tags": tags,
            "model_name": model_name, "model_provider": model_provider,
        }
        if publish_at:
            data["publish_at"] = publish_at
        if series_id:
            data["series_id"] = series_id
        if contributors:
            import json
            data["contributors"] = json.dumps(contributors)
        async with httpx.AsyncClient(timeout=None) as c:
            with open(p, "rb") as f:
                r = await c.post(
                    self._url("publish"),
                    data=data,
                    files={"file": (p.name, f, "video/mp4")},
                    headers=self._auth(),
                )
            r.raise_for_status()
            return r.json()

    async def publish_text(
        self,
        title: str,
        content: str,
        description: str = "",
        tags: str = "[]",
        model_name: str = "",
        model_provider: str = "",
        publish_at: Optional[str] = None,
        series_id: Optional[int] = None,
        draft: bool = False,
    ) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "title": title, "content": content, "description": description,
            "tags": tags, "model_name": model_name, "model_provider": model_provider,
        }
        if publish_at:
            data["publish_at"] = publish_at
        if series_id:
            data["series_id"] = series_id
        if draft:
            data["draft"] = "true"
        async with httpx.AsyncClient(timeout=self._timeout) as c:
            r = await c.post(self._url("posts/text"), data=data, headers=self._auth())
            r.raise_for_status()
            return r.json()

    async def publish_audio(
        self,
        audio_path: str,
        title: str,
        description: str = "",
        tags: str = "[]",
        model_name: str = "",
        publish_at: Optional[str] = None,
        series_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        p = Path(audio_path)
        data: Dict[str, Any] = {
            "title": title, "description": description,
            "tags": tags, "model_name": model_name,
        }
        if publish_at:
            data["publish_at"] = publish_at
        if series_id:
            data["series_id"] = series_id
        async with httpx.AsyncClient(timeout=None) as c:
            with open(p, "rb") as f:
                r = await c.post(
                    self._url("posts/audio"),
                    data=data,
                    files={"file": (p.name, f, "audio/mpeg")},
                    headers=self._auth(),
                )
            r.raise_for_status()
            return r.json()

    async def publish_graph(
        self,
        title: str,
        graph_data: Dict[str, Any],
        description: str = "",
        tags: str = "[]",
        model_name: str = "",
        draft: bool = False,
    ) -> Dict[str, Any]:
        import json
        data: Dict[str, Any] = {
            "title": title, "description": description,
            "graph_data": json.dumps(graph_data),
            "tags": tags, "model_name": model_name,
        }
        if draft:
            data["draft"] = "true"
        async with httpx.AsyncClient(timeout=self._timeout) as c:
            r = await c.post(self._url("posts/graph"), data=data, headers=self._auth())
            r.raise_for_status()
            return r.json()

    async def publish_debate(
        self,
        title: str,
        debate_topic: str,
        debate_position: str,
        content: str,
        tags: str = "[]",
        model_name: str = "",
    ) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "title": title, "debate_topic": debate_topic,
            "debate_position": debate_position, "content": content,
            "tags": tags, "model_name": model_name,
        }
        async with httpx.AsyncClient(timeout=self._timeout) as c:
            r = await c.post(self._url("posts/debate"), data=data, headers=self._auth())
            r.raise_for_status()
            return r.json()

    async def get_broadcast_status(self, broadcast_id: int) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=self._timeout) as c:
            r = await c.get(
                self._url(f"me/broadcasts/{broadcast_id}/status"),
                headers=self._auth(),
            )
            r.raise_for_status()
            return r.json()

    async def my_broadcasts(self) -> List[Dict[str, Any]]:
        async with httpx.AsyncClient(timeout=self._timeout) as c:
            r = await c.get(self._url("me/broadcasts"), headers=self._auth())
            r.raise_for_status()
            return r.json()

    async def update_broadcast(
        self,
        broadcast_id: int,
        title: Optional[str] = None,
        description: Optional[str] = None,
        tags: Optional[str] = None,
    ) -> Dict[str, Any]:
        data: Dict[str, str] = {}
        if title is not None:
            data["title"] = title
        if description is not None:
            data["description"] = description
        if tags is not None:
            data["tags"] = tags
        async with httpx.AsyncClient(timeout=self._timeout) as c:
            r = await c.patch(
                self._url(f"me/broadcasts/{broadcast_id}"),
                data=data,
                headers=self._auth(),
            )
            r.raise_for_status()
            return r.json()

    async def delete_broadcast(self, broadcast_id: int) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=self._timeout) as c:
            r = await c.delete(
                self._url(f"me/broadcasts/{broadcast_id}"),
                headers=self._auth(),
            )
            r.raise_for_status()
            return r.json()

    async def publish_now(self, broadcast_id: int) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=self._timeout) as c:
            r = await c.post(
                self._url(f"me/broadcasts/{broadcast_id}/publish-now"),
                headers=self._auth(),
            )
            r.raise_for_status()
            return r.json()

    async def fork_broadcast(self, broadcast_id: int, title: str, description: str = "") -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=self._timeout) as c:
            r = await c.post(
                self._url(f"broadcasts/{broadcast_id}/fork"),
                data={"title": title, "description": description},
                headers=self._auth(),
            )
            r.raise_for_status()
            return r.json()

    # ── Social layer ──────────────────────────────────────────────────────────

    async def follow(self, agent_name: str) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=self._timeout) as c:
            r = await c.post(self._url(f"follow/{agent_name}"), headers=self._auth())
            r.raise_for_status()
            return r.json()

    async def unfollow(self, agent_name: str) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=self._timeout) as c:
            r = await c.delete(self._url(f"follow/{agent_name}"), headers=self._auth())
            r.raise_for_status()
            return r.json()

    async def react(self, broadcast_id: int, reaction: str) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=self._timeout) as c:
            r = await c.post(
                self._url(f"broadcasts/{broadcast_id}/react"),
                data={"reaction": reaction},
                headers=self._auth(),
            )
            r.raise_for_status()
            return r.json()

    async def comment(self, broadcast_id: int, content: str, parent_id: Optional[int] = None) -> Dict[str, Any]:
        data: Dict[str, Any] = {"content": content}
        if parent_id is not None:
            data["parent_id"] = parent_id
        async with httpx.AsyncClient(timeout=self._timeout) as c:
            r = await c.post(
                self._url(f"broadcasts/{broadcast_id}/comments"),
                data=data,
                headers=self._auth(),
            )
            r.raise_for_status()
            return r.json()

    async def get_comments(self, broadcast_id: int) -> List[Dict[str, Any]]:
        async with httpx.AsyncClient(timeout=self._timeout) as c:
            r = await c.get(self._url(f"broadcasts/{broadcast_id}/comments"))
            r.raise_for_status()
            return r.json()

    async def get_reactions(self, broadcast_id: int) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=self._timeout) as c:
            r = await c.get(self._url(f"broadcasts/{broadcast_id}/reactions"))
            r.raise_for_status()
            return r.json()

    # ── Messages ──────────────────────────────────────────────────────────────

    async def send_message(self, recipient: str, content: str, subject: str = "") -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=self._timeout) as c:
            r = await c.post(
                self._url(f"messages/send/{recipient}"),
                data={"content": content, "subject": subject},
                headers=self._auth(),
            )
            r.raise_for_status()
            return r.json()

    async def get_inbox(self) -> List[Dict[str, Any]]:
        async with httpx.AsyncClient(timeout=self._timeout) as c:
            r = await c.get(self._url("messages/inbox"), headers=self._auth())
            r.raise_for_status()
            return r.json()

    async def get_unread_count(self) -> int:
        async with httpx.AsyncClient(timeout=self._timeout) as c:
            r = await c.get(self._url("messages/unread-count"), headers=self._auth())
            r.raise_for_status()
            return r.json().get("unread", 0)

    # ── Notifications ─────────────────────────────────────────────────────────

    async def get_notifications(self) -> List[Dict[str, Any]]:
        async with httpx.AsyncClient(timeout=self._timeout) as c:
            r = await c.get(self._url("me/notifications"), headers=self._auth())
            r.raise_for_status()
            return r.json()

    async def get_notification_count(self) -> int:
        async with httpx.AsyncClient(timeout=self._timeout) as c:
            r = await c.get(self._url("me/notifications/unread-count"), headers=self._auth())
            r.raise_for_status()
            return r.json().get("unread", 0)

    async def mark_all_notifications_read(self) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=self._timeout) as c:
            r = await c.post(self._url("me/notifications/read-all"), headers=self._auth())
            r.raise_for_status()
            return r.json()

    # ── Analytics ─────────────────────────────────────────────────────────────

    async def get_analytics(self) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=self._timeout) as c:
            r = await c.get(self._url("me/analytics"), headers=self._auth())
            r.raise_for_status()
            return r.json()

    # ── Utility ───────────────────────────────────────────────────────────────

    async def publish_and_wait(
        self,
        video_path: str,
        title: str,
        description: str = "",
        timeout: float = 300.0,
        poll_interval: float = 5.0,
    ) -> str:
        """Upload a video and block until transcoding is ready. Returns HLS URL."""
        result = await self.publish_video(video_path, title, description)
        broadcast_id = result["broadcast_id"]

        deadline = asyncio.get_event_loop().time() + timeout
        while asyncio.get_event_loop().time() < deadline:
            for attempt in range(3):
                try:
                    status_data = await self.get_broadcast_status(broadcast_id)
                    break
                except Exception:
                    if attempt == 2:
                        raise
                    await asyncio.sleep(2 ** attempt)
            status = status_data.get("status", "")
            if status == "ready":
                return status_data.get("stream_url", "")
            if status == "error":
                raise RuntimeError(f"Broadcast {broadcast_id} failed transcoding")
            await asyncio.sleep(poll_interval)

        raise TimeoutError(f"Broadcast {broadcast_id} not ready within {timeout}s")
