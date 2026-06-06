"""
Premium MPV player controller using JSON IPC (Unix socket).

Spawns MPV as a background daemon with a Unix domain socket and lets the
agent (or web API) fully control playback: play, pause, resume, seek, stop,
and query status — all over async JSON-RPC.
"""

import asyncio
import json
import shutil
import subprocess
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

# MPV Unix IPC socket path
IPC_SOCKET = "/tmp/franken-mpv-premium.sock"

# Launch flags for a top-of-the-line viewing experience
_MPV_FLAGS = [
    f"--input-ipc-server={IPC_SOCKET}",
    "--idle=yes",              # Keep the process alive when nothing is playing
    "--no-border",             # Clean, modern borderless window
    "--ontop",                 # Float above other windows
    "--geometry=80%x80%",      # Elegant default size, centred
    "--hwdec=auto-safe",       # Hardware-accelerated decoding where available
    "--vo=gpu",                # High-quality GPU video output
    "--scale=ewa_lanczossharp",
    "--cscale=ewa_lanczossharp",
    "--tscale=oversample",
    "--profile=gpu-hq",        # High-quality profile (MPV built-in)
    "--keep-open=yes",         # Don't close window at end of video
    "--title=Franken-Stream",
]


class PremiumPlayer:
    """
    Async controller for a persistent MPV instance via JSON IPC.

    Usage:
        player = PremiumPlayer()
        await player.play("https://…/stream.m3u8", title="Oppenheimer")
        status = await player.get_status()
        await player.seek(300)  # jump to 5 min
        await player.stop()
    """

    def __init__(self, ipc_socket: str = IPC_SOCKET):
        self.ipc_socket = ipc_socket
        self._process: Optional[subprocess.Popen] = None
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._req_id: int = 0
        self._lock = asyncio.Lock()
        # Current session metadata
        self.playback_id: Optional[str] = None
        self.title: str = ""

    # ── Internal connection management ────────────────────────────────────────

    async def _try_connect(self) -> bool:
        """Attempt to open a connection to an already-running MPV socket."""
        try:
            if not Path(self.ipc_socket).exists():
                return False
            self._reader, self._writer = await asyncio.open_unix_connection(self.ipc_socket)
            return True
        except Exception:
            self._reader = self._writer = None
            return False

    async def _ensure_running(self) -> bool:
        """
        Make sure MPV is running and we are connected.
        If the socket is stale or MPV is not running, (re-)launches it.
        """
        if self._writer and not self._writer.is_closing():
            return True

        if await self._try_connect():
            return True

        mpv_path = shutil.which("mpv")
        if not mpv_path:
            raise RuntimeError(
                "mpv is not installed.\n"
                "  macOS:   brew install mpv\n"
                "  Debian:  sudo apt install mpv\n"
                "  Windows: winget install mpv"
            )

        # Remove stale socket file so MPV can bind to it fresh
        Path(self.ipc_socket).unlink(missing_ok=True)

        self._process = subprocess.Popen(
            [mpv_path] + _MPV_FLAGS,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )

        # Poll until the socket file appears (max 3 seconds)
        for _ in range(30):
            await asyncio.sleep(0.1)
            if Path(self.ipc_socket).exists():
                break

        return await self._try_connect()

    async def _send(self, command: list) -> Optional[Dict[str, Any]]:
        """
        Send a JSON-RPC command to MPV and return its response.

        MPV's IPC protocol is line-delimited JSON:
          Request:  {"command": [...], "request_id": N}
          Response: {"data": ..., "error": "success"|..., "request_id": N}
          Events:   {"event": "...", ...}  — no request_id; we skip these.
        """
        async with self._lock:
            if not self._writer:
                return None
            try:
                self._req_id += 1
                req_id = self._req_id
                payload = {"command": command, "request_id": req_id}
                self._writer.write((json.dumps(payload) + "\n").encode())
                await self._writer.drain()

                # Read lines until we find the response for our request
                for _ in range(30):
                    line = await asyncio.wait_for(self._reader.readline(), timeout=3.0)
                    if not line:
                        break
                    try:
                        msg = json.loads(line.decode())
                    except json.JSONDecodeError:
                        continue
                    if msg.get("request_id") == req_id:
                        return msg
                    # Otherwise it's an async MPV event — ignore and keep reading
            except Exception:
                # Socket lost — reset so next call will reconnect
                self._reader = self._writer = None
        return None

    # ── Public playback API ───────────────────────────────────────────────────

    async def play(self, url: str, title: str = "") -> Dict[str, Any]:
        """
        Load and immediately play `url` in the MPV window.
        Spawns MPV if it is not already running.
        """
        if not await self._ensure_running():
            return {"status": "error", "message": "Could not start MPV"}

        self.playback_id = str(uuid.uuid4())[:8]
        self.title = title or url

        resp = await self._send(["loadfile", url, "replace"])
        if resp and resp.get("error") == "success":
            if title:
                await self._send(["set_property", "title", f"Franken-Stream: {title}"])
            return {
                "status": "playing",
                "playback_id": self.playback_id,
                "title": self.title,
            }
        return {"status": "error", "message": "MPV loadfile command failed"}

    async def pause(self) -> bool:
        """Pause playback. Returns True on success."""
        resp = await self._send(["set_property", "pause", True])
        return bool(resp and resp.get("error") == "success")

    async def resume(self) -> bool:
        """Resume playback. Returns True on success."""
        resp = await self._send(["set_property", "pause", False])
        return bool(resp and resp.get("error") == "success")

    async def seek(self, position_seconds: int) -> bool:
        """Seek to an absolute timestamp in seconds."""
        resp = await self._send(["seek", position_seconds, "absolute"])
        return bool(resp and resp.get("error") == "success")

    async def stop(self) -> None:
        """Stop playback (does not close MPV; it stays idle)."""
        await self._send(["stop"])
        self.playback_id = None
        self.title = ""

    async def quit(self) -> None:
        """Quit MPV entirely."""
        await self._send(["quit"])
        if self._writer:
            self._writer.close()
        if self._process:
            self._process.terminate()
        self._reader = self._writer = None
        self.playback_id = None
        self.title = ""

    async def get_status(self) -> Dict[str, Any]:
        """
        Return current playback state.
        Safe to call even when MPV is not running.
        """
        if not self._writer or self._writer.is_closing():
            if not await self._try_connect():
                return {
                    "is_playing": False,
                    "playback_id": self.playback_id,
                    "title": self.title,
                    "elapsed_seconds": 0,
                    "duration_seconds": 0,
                    "mpv_running": False,
                }

        pause_resp = await self._send(["get_property", "pause"])
        pos_resp = await self._send(["get_property", "time-pos"])
        dur_resp = await self._send(["get_property", "duration"])

        is_paused = pause_resp.get("data") if pause_resp else True
        pos = pos_resp.get("data") if pos_resp else 0
        dur = dur_resp.get("data") if dur_resp else 0

        return {
            "is_playing": not bool(is_paused),
            "playback_id": self.playback_id,
            "title": self.title,
            "elapsed_seconds": round(float(pos or 0), 1),
            "duration_seconds": round(float(dur or 0), 1),
            "mpv_running": True,
        }
