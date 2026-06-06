"""Tests for the SQLite-backed Watchlist."""

import time
from pathlib import Path

import pytest

from franken_stream.watchlist import Watchlist


@pytest.fixture
def wl(tmp_path):
    w = Watchlist()
    w.db_path = tmp_path / "watchlist.db"
    w._init_db()
    return w


class TestWatchlistAdd:
    def test_add_creates_entry(self, wl):
        wl.add("id1", "Inception", "https://example.com/inception")
        entry = wl.get("id1")
        assert entry is not None
        assert entry["title"] == "Inception"
        assert entry["url"] == "https://example.com/inception"

    def test_add_with_all_fields(self, wl):
        wl.add("id2", "Dune", "https://example.com/dune",
               provider="tubi", year=2021, media_type="movie", quality="4K")
        entry = wl.get("id2")
        assert entry["provider"] == "tubi"
        assert entry["year"] == 2021
        assert entry["media_type"] == "movie"
        assert entry["quality"] == "4K"

    def test_add_is_idempotent(self, wl):
        wl.add("dup", "Movie", "https://example.com/movie")
        wl.add("dup", "Movie Updated", "https://example.com/movie")  # INSERT OR IGNORE
        entry = wl.get("dup")
        assert entry["title"] == "Movie"  # original preserved

    def test_added_at_is_set(self, wl):
        before = time.time()
        wl.add("ts", "Test", "https://example.com")
        after = time.time()
        entry = wl.get("ts")
        assert before <= entry["added_at"] <= after


class TestWatchlistProgress:
    def test_update_progress(self, wl):
        wl.add("p1", "Movie", "https://example.com")
        wl.update_progress("p1", 300, duration_seconds=3600)
        entry = wl.get("p1")
        assert entry["progress_seconds"] == 300
        assert entry["duration_seconds"] == 3600

    def test_completed_flag_set_at_90_percent(self, wl):
        wl.add("c1", "Movie", "https://example.com")
        wl.update_progress("c1", 91, duration_seconds=100)
        entry = wl.get("c1")
        assert entry["completed"] == 1

    def test_not_completed_below_90_percent(self, wl):
        wl.add("c2", "Movie", "https://example.com")
        wl.update_progress("c2", 50, duration_seconds=100)
        assert wl.get("c2")["completed"] == 0

    def test_last_watched_updated(self, wl):
        wl.add("lw", "Movie", "https://example.com")
        before = time.time()
        wl.update_progress("lw", 60)
        after = time.time()
        entry = wl.get("lw")
        assert before <= entry["last_watched"] <= after

    def test_duration_preserved_when_not_provided(self, wl):
        wl.add("dur", "Movie", "https://example.com")
        wl.update_progress("dur", 60, duration_seconds=3600)
        wl.update_progress("dur", 120)  # no duration
        assert wl.get("dur")["duration_seconds"] == 3600


class TestWatchlistQueries:
    def test_all_returns_all_entries(self, wl):
        wl.add("a1", "Movie A", "https://a.com")
        wl.add("a2", "Movie B", "https://b.com")
        items = wl.all()
        assert len(items) == 2

    def test_all_returns_empty_when_none(self, wl):
        assert wl.all() == []

    def test_in_progress_excludes_completed(self, wl):
        wl.add("ip1", "Not Started", "https://a.com")
        wl.add("ip2", "In Progress", "https://b.com")
        wl.add("ip3", "Completed", "https://c.com")
        wl.update_progress("ip2", 300)
        wl.update_progress("ip3", 95, duration_seconds=100)  # → completed
        result = wl.in_progress()
        ids = [e["id"] for e in result]
        assert "ip2" in ids
        assert "ip3" not in ids
        assert "ip1" not in ids

    def test_get_returns_none_for_missing(self, wl):
        assert wl.get("does_not_exist") is None

    def test_all_limit(self, wl):
        for i in range(10):
            wl.add(f"m{i}", f"Movie {i}", f"https://example.com/{i}")
        assert len(wl.all(limit=5)) == 5


class TestWatchlistRemove:
    def test_remove_deletes_entry(self, wl):
        wl.add("r1", "Movie", "https://example.com")
        wl.remove("r1")
        assert wl.get("r1") is None

    def test_remove_nonexistent_does_not_raise(self, wl):
        wl.remove("never_existed")

    def test_remove_does_not_affect_others(self, wl):
        wl.add("keep", "Stay", "https://a.com")
        wl.add("del", "Delete", "https://b.com")
        wl.remove("del")
        assert wl.get("keep") is not None


class TestResumeArgs:
    def test_resume_args_with_progress(self, wl):
        wl.add("res", "Movie", "https://example.com")
        wl.update_progress("res", 300)
        args = wl.resume_args("res")
        assert args == ["--start=300"]

    def test_resume_args_no_progress(self, wl):
        wl.add("nores", "Movie", "https://example.com")
        assert wl.resume_args("nores") == []

    def test_resume_args_small_progress_ignored(self, wl):
        wl.add("small", "Movie", "https://example.com")
        wl.update_progress("small", 20)
        assert wl.resume_args("small") == []

    def test_resume_args_missing_id(self, wl):
        assert wl.resume_args("ghost") == []
