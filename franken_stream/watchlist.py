"""SQLite-backed watchlist with continue-watching support."""

import sqlite3
import time
from pathlib import Path
from typing import Dict, List, Optional


class Watchlist:
    """
    Persistent watchlist stored in ~/.franken-stream/watchlist.db.

    Tracks what the user has watched and their last playback position
    so they can resume where they left off.
    """

    def __init__(self):
        self.db_path = Path.home() / ".franken-stream" / "watchlist.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS watchlist (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    url TEXT NOT NULL,
                    provider TEXT,
                    year INTEGER,
                    media_type TEXT DEFAULT 'movie',
                    quality TEXT,
                    added_at REAL NOT NULL,
                    last_watched REAL,
                    progress_seconds INTEGER DEFAULT 0,
                    duration_seconds INTEGER,
                    completed INTEGER DEFAULT 0
                )
            """)
            conn.commit()
        finally:
            conn.close()

    def add(
        self,
        media_id: str,
        title: str,
        url: str,
        provider: str = "",
        year: Optional[int] = None,
        media_type: str = "movie",
        quality: str = "unknown",
    ) -> None:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("""
                INSERT OR IGNORE INTO watchlist
                (id, title, url, provider, year, media_type, quality, added_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (media_id, title, url, provider, year, media_type, quality, time.time()))
            conn.commit()
        finally:
            conn.close()

    def update_progress(
        self,
        media_id: str,
        progress_seconds: int,
        duration_seconds: Optional[int] = None,
    ) -> None:
        conn = sqlite3.connect(self.db_path)
        try:
            completed = 0
            if duration_seconds and progress_seconds >= duration_seconds * 0.9:
                completed = 1
            conn.execute("""
                UPDATE watchlist
                SET progress_seconds = ?,
                    duration_seconds = COALESCE(?, duration_seconds),
                    last_watched = ?,
                    completed = ?
                WHERE id = ?
            """, (progress_seconds, duration_seconds, time.time(), completed, media_id))
            conn.commit()
        finally:
            conn.close()

    def get(self, media_id: str) -> Optional[Dict]:
        conn = sqlite3.connect(self.db_path)
        try:
            row = conn.execute(
                "SELECT * FROM watchlist WHERE id = ?", (media_id,)
            ).fetchone()
            if not row:
                return None
            return self._row_to_dict(row)
        finally:
            conn.close()

    def all(self, limit: int = 50) -> List[Dict]:
        conn = sqlite3.connect(self.db_path)
        try:
            rows = conn.execute(
                "SELECT * FROM watchlist ORDER BY last_watched DESC NULLS LAST, added_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [self._row_to_dict(r) for r in rows]
        finally:
            conn.close()

    def in_progress(self) -> List[Dict]:
        """Items started but not finished."""
        conn = sqlite3.connect(self.db_path)
        try:
            rows = conn.execute("""
                SELECT * FROM watchlist
                WHERE progress_seconds > 0 AND completed = 0
                ORDER BY last_watched DESC
            """).fetchall()
            return [self._row_to_dict(r) for r in rows]
        finally:
            conn.close()

    def remove(self, media_id: str) -> None:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("DELETE FROM watchlist WHERE id = ?", (media_id,))
            conn.commit()
        finally:
            conn.close()

    def resume_args(self, media_id: str) -> List[str]:
        """Return mpv --start= argument list if there's saved progress."""
        entry = self.get(media_id)
        if entry and entry["progress_seconds"] > 30:
            return [f"--start={entry['progress_seconds']}"]
        return []

    @staticmethod
    def _row_to_dict(row) -> Dict:
        keys = [
            "id", "title", "url", "provider", "year", "media_type", "quality",
            "added_at", "last_watched", "progress_seconds", "duration_seconds", "completed"
        ]
        return dict(zip(keys, row))
