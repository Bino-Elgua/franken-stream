import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Callable, Dict, Optional


class SearchCache:
    """Lightweight SQLite-backed search cache."""

    def __init__(self, ttl_seconds: int = 3600):
        self.db_path = Path.home() / ".franken-stream" / "search_cache.db"
        self.ttl_seconds = ttl_seconds
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _initialize(self) -> None:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS search_cache (
                    query TEXT NOT NULL,
                    provider_hash TEXT NOT NULL,
                    response_json TEXT NOT NULL,
                    updated_at REAL NOT NULL,
                    PRIMARY KEY (query, provider_hash)
                )
                """
            )
            conn.commit()
        finally:
            conn.close()

    def _get_cached(self, query: str, provider_hash: str) -> Optional[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        try:
            row = conn.execute(
                "SELECT response_json, updated_at FROM search_cache WHERE query = ? AND provider_hash = ?",
                (query, provider_hash),
            ).fetchone()
            if not row:
                return None

            response_json, updated_at = row
            if time.time() - updated_at > self.ttl_seconds:
                conn.execute(
                    "DELETE FROM search_cache WHERE query = ? AND provider_hash = ?",
                    (query, provider_hash),
                )
                conn.commit()
                return None

            return json.loads(response_json)
        finally:
            conn.close()

    def _store(self, query: str, provider_hash: str, payload: Dict[str, Any]) -> None:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                "REPLACE INTO search_cache (query, provider_hash, response_json, updated_at) VALUES (?, ?, ?, ?)",
                (query, provider_hash, json.dumps(payload), time.time()),
            )
            conn.commit()
        finally:
            conn.close()

    def get_or_fetch(
        self,
        query: str,
        provider_hash: str,
        fetch_fn: Callable[[], Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Return cached search results or fetch and cache them."""
        cached = self._get_cached(query, provider_hash)
        if cached is not None:
            return cached

        result = fetch_fn()
        try:
            self._store(query, provider_hash, result)
        except Exception:
            pass
        return result
