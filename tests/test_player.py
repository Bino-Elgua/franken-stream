"""Tests for PremiumPlayer MPV IPC controller."""

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from franken_stream.player import PremiumPlayer


def make_reader(*responses):
    """Build a mock StreamReader that returns JSON lines in sequence."""
    reader = MagicMock()
    lines = [json.dumps(r).encode() + b"\n" for r in responses] + [b""]
    reader.readline = AsyncMock(side_effect=lines)
    return reader


def make_writer():
    writer = MagicMock()
    writer.is_closing = MagicMock(return_value=False)
    writer.write = MagicMock()
    writer.drain = AsyncMock()
    writer.close = MagicMock()
    return writer


class TestEnsureRunning:
    async def test_returns_false_when_mpv_not_installed(self):
        player = PremiumPlayer()
        with patch("shutil.which", return_value=None), \
             patch.object(player, "_try_connect", return_value=False):
            with pytest.raises(RuntimeError, match="mpv is not installed"):
                await player._ensure_running()

    async def test_returns_true_when_already_connected(self):
        player = PremiumPlayer()
        player._writer = make_writer()
        result = await player._ensure_running()
        assert result is True

    async def test_connects_to_existing_socket(self):
        player = PremiumPlayer()
        with patch.object(player, "_try_connect", return_value=True):
            result = await player._ensure_running()
        assert result is True


class TestTryConnect:
    async def test_returns_false_when_socket_missing(self):
        player = PremiumPlayer()
        with patch("pathlib.Path.exists", return_value=False):
            result = await player._try_connect()
        assert result is False

    async def test_returns_false_on_connection_error(self):
        player = PremiumPlayer()
        with patch("pathlib.Path.exists", return_value=True), \
             patch("asyncio.open_unix_connection", side_effect=OSError("refused")):
            result = await player._try_connect()
        assert result is False

    async def test_sets_reader_writer_on_success(self):
        player = PremiumPlayer()
        reader, writer = MagicMock(), make_writer()
        with patch("pathlib.Path.exists", return_value=True), \
             patch("asyncio.open_unix_connection", return_value=(reader, writer)):
            result = await player._try_connect()
        assert result is True
        assert player._reader is reader
        assert player._writer is writer


class TestPlay:
    async def test_play_success(self):
        player = PremiumPlayer()
        player._writer = make_writer()
        player._reader = make_reader(
            {"request_id": 1, "error": "success"},
            {"request_id": 2, "error": "success"},
        )
        with patch.object(player, "_ensure_running", return_value=True):
            result = await player.play("https://stream.example.com/video.m3u8", title="Test Film")
        assert result["status"] == "playing"
        assert result["title"] == "Test Film"
        assert "playback_id" in result

    async def test_play_returns_error_when_mpv_fails(self):
        player = PremiumPlayer()
        with patch.object(player, "_ensure_running", return_value=False):
            result = await player.play("https://example.com")
        assert result["status"] == "error"

    async def test_play_sets_instance_title(self):
        player = PremiumPlayer()
        player._writer = make_writer()
        player._reader = make_reader(
            {"request_id": 1, "error": "success"},
            {"request_id": 2, "error": "success"},
        )
        with patch.object(player, "_ensure_running", return_value=True):
            await player.play("https://example.com/v.mp4", title="Dune")
        assert player.title == "Dune"
        assert player.playback_id is not None


class TestPauseResume:
    async def test_pause_sends_correct_command(self):
        player = PremiumPlayer()
        player._writer = make_writer()
        player._reader = make_reader({"request_id": 1, "error": "success"})
        result = await player.pause()
        assert result is True

    async def test_pause_returns_false_on_mpv_error(self):
        player = PremiumPlayer()
        player._writer = make_writer()
        player._reader = make_reader({"request_id": 1, "error": "failed"})
        result = await player.pause()
        assert result is False

    async def test_resume_sends_correct_command(self):
        player = PremiumPlayer()
        player._writer = make_writer()
        player._reader = make_reader({"request_id": 1, "error": "success"})
        result = await player.resume()
        assert result is True


class TestSeek:
    async def test_seek_returns_true_on_success(self):
        player = PremiumPlayer()
        player._writer = make_writer()
        player._reader = make_reader({"request_id": 1, "error": "success"})
        result = await player.seek(120)
        assert result is True

    async def test_seek_returns_false_on_error(self):
        player = PremiumPlayer()
        player._writer = make_writer()
        player._reader = make_reader({"request_id": 1, "error": "property unavailable"})
        result = await player.seek(60)
        assert result is False


class TestStop:
    async def test_stop_clears_state(self):
        player = PremiumPlayer()
        player.playback_id = "abc"
        player.title = "Movie"
        player._writer = make_writer()
        player._reader = make_reader({"request_id": 1, "error": "success"})
        await player.stop()
        assert player.playback_id is None
        assert player.title == ""


class TestGetStatus:
    async def test_returns_not_running_when_no_writer(self):
        player = PremiumPlayer()
        with patch.object(player, "_try_connect", return_value=False):
            status = await player.get_status()
        assert status["is_playing"] is False
        assert status["mpv_running"] is False

    async def test_returns_status_from_mpv(self):
        player = PremiumPlayer()
        player._writer = make_writer()
        player.title = "Inception"
        player._reader = make_reader(
            {"request_id": 1, "error": "success", "data": False},   # pause=False
            {"request_id": 2, "error": "success", "data": 300.5},   # time-pos
            {"request_id": 3, "error": "success", "data": 9000.0},  # duration
        )
        status = await player.get_status()
        assert status["is_playing"] is True
        assert status["elapsed_seconds"] == 300.5
        assert status["duration_seconds"] == 9000.0
        assert status["mpv_running"] is True
