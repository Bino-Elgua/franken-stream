import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import urlparse


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


class FTSCache:
    """
    SQLite FTS5 full-text search cache for instant title lookups.
    Stores search results across providers for sub-10ms repeated queries.
    """

    def __init__(self):
        self.db_path = Path.home() / ".franken-stream" / "fts_cache.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS results_fts USING fts5(
                    title,
                    url UNINDEXED,
                    provider UNINDEXED,
                    added_at UNINDEXED,
                    tokenize='porter unicode61'
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS fts_meta (
                    query TEXT PRIMARY KEY,
                    last_fetched REAL NOT NULL
                )
            """)
            conn.commit()
        finally:
            conn.close()

    def lookup(self, query: str, max_age_seconds: int = 3600) -> Optional[List]:
        """Return cached results for query if fresh, else None."""
        conn = sqlite3.connect(self.db_path)
        try:
            row = conn.execute(
                "SELECT last_fetched FROM fts_meta WHERE query = ?", (query,)
            ).fetchone()
            if not row or (time.time() - row[0]) > max_age_seconds:
                return None

            rows = conn.execute(
                "SELECT title, url FROM results_fts WHERE results_fts MATCH ? LIMIT 20",
                (query,),
            ).fetchall()
            return [(r[0], r[1]) for r in rows]
        except Exception:
            return None
        finally:
            conn.close()

    def store(self, query: str, results: List) -> None:
        """Store (title, url) results under query."""
        conn = sqlite3.connect(self.db_path)
        try:
            # Remove old entries for this query using rowid subquery (FTS5 safe)
            conn.execute(
                "DELETE FROM results_fts WHERE rowid IN (SELECT rowid FROM results_fts WHERE results_fts MATCH ?)",
                (query,),
            )
            for title, url in results:
                conn.execute(
                    "INSERT INTO results_fts (title, url, provider, added_at) VALUES (?, ?, ?, ?)",
                    (title, url, urlparse(url).netloc, time.time()),
                )
            conn.execute(
                "INSERT OR REPLACE INTO fts_meta (query, last_fetched) VALUES (?, ?)",
                (query, time.time()),
            )
            conn.commit()
        except Exception:
            pass
        finally:
            conn.close()
