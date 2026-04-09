"""Watch Party — synchronized media playback over WebSocket."""

import json
import threading
from typing import Callable, Dict, Optional

import requests


class WatchParty:
    """
    Synchronize playback (play / pause / seek) with remote friends via
    a franken-stream watch-party server.

    The server component is a simple WebSocket relay; this client handles
    sending and receiving sync messages.  All methods degrade gracefully
    when websocket-client is not installed.

    Quick start:
        # Host
        party = WatchParty("ws://my-server:8765")
        room_id = party.create_room("https://…/movie.mp4", "Inception")
        print(f"Share this room ID: {room_id}")

        # Guest
        party = WatchParty("ws://my-server:8765")
        party.join_room("<room_id>")
        party.on("seek", lambda d: player.seek(d["position"]))
    """

    def __init__(self, server_url: str):
        # Normalise: replace ws(s):// with http(s):// for REST calls
        self.server_ws = server_url.rstrip("/")
        self.server_http = (
            server_url.replace("wss://", "https://")
                      .replace("ws://", "http://")
                      .rstrip("/")
        )
        self._ws = None
        self._room_id: Optional[str] = None
        self._callbacks: Dict[str, Callable] = {}
        self._connected = False

    # ------------------------------------------------------------------
    # Room management (REST)
    # ------------------------------------------------------------------

    def create_room(self, media_url: str, media_title: str) -> str:
        """Create a new watch-party room and return its ID."""
        response = requests.post(
            f"{self.server_http}/api/rooms",
            json={"media_url": media_url, "media_title": media_title},
            timeout=10,
        )
        response.raise_for_status()
        self._room_id = response.json()["room_id"]
        return self._room_id

    def get_room_info(self, room_id: str) -> Dict:
        """Fetch current room state (media URL, current position, etc.)."""
        response = requests.get(
            f"{self.server_http}/api/rooms/{room_id}",
            timeout=10,
        )
        response.raise_for_status()
        return response.json()

    # ------------------------------------------------------------------
    # WebSocket connection
    # ------------------------------------------------------------------

    def join_room(self, room_id: str) -> bool:
        """
        Connect to an existing room and start listening for sync messages.

        Returns True if the connection was established, False otherwise.
        """
        try:
            import websocket  # type: ignore
        except ImportError:
            print("websocket-client not installed — watch party unavailable. "
                  "Install with: pip install websocket-client")
            return False

        self._room_id = room_id
        ws_url = f"{self.server_ws}/ws/{room_id}"

        self._ws = websocket.WebSocketApp(
            ws_url,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close,
            on_open=self._on_open,
        )

        thread = threading.Thread(target=self._ws.run_forever, daemon=True)
        thread.start()
        return True

    def disconnect(self) -> None:
        """Disconnect from the watch-party room."""
        if self._ws:
            self._ws.close()
        self._connected = False
        self._ws = None

    # ------------------------------------------------------------------
    # Event callbacks
    # ------------------------------------------------------------------

    def on(self, action: str, callback: Callable) -> None:
        """Register a callback for a specific sync action (play/pause/seek/chat)."""
        self._callbacks[action] = callback

    def _on_open(self, ws) -> None:
        self._connected = True

    def _on_message(self, ws, message: str) -> None:
        try:
            data = json.loads(message)
        except json.JSONDecodeError:
            return
        action = data.get("action")
        if action and action in self._callbacks:
            try:
                self._callbacks[action](data.get("data", {}))
            except Exception as exc:
                print(f"Watch party callback error [{action}]: {exc}")

    def _on_error(self, ws, error) -> None:
        print(f"Watch party WebSocket error: {error}")

    def _on_close(self, ws, close_status_code, close_msg) -> None:
        self._connected = False

    # ------------------------------------------------------------------
    # Sync actions (sent to all participants)
    # ------------------------------------------------------------------

    def _send(self, action: str, data: Dict) -> bool:
        if not self._ws or not self._connected:
            return False
        try:
            self._ws.send(json.dumps({"action": action, "data": data}))
            return True
        except Exception:
            return False

    def play(self, current_time: float) -> bool:
        """Broadcast a play event with the current playback position."""
        return self._send("play", {"time": current_time})

    def pause(self, current_time: float) -> bool:
        """Broadcast a pause event with the current playback position."""
        return self._send("pause", {"time": current_time})

    def seek(self, position: float) -> bool:
        """Broadcast a seek event to a specific position (seconds)."""
        return self._send("seek", {"position": position})

    def chat(self, username: str, message: str) -> bool:
        """Send a chat message to all participants."""
        return self._send("chat", {"username": username, "message": message})
