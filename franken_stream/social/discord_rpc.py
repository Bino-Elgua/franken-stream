"""Discord Rich Presence integration via pypresence (optional dependency)."""

import time
from typing import Optional


class DiscordRichPresence:
    """
    Show currently playing media in Discord's "Now Playing" status.

    Requires pypresence and a running Discord desktop client.
    All methods degrade gracefully when pypresence is not installed or
    Discord is not running — the rest of the application is unaffected.

    Usage:
        rpc = DiscordRichPresence()
        rpc.connect()
        rpc.update_presence("Inception", media_type="movie", duration=9000)
        # ... later ...
        rpc.clear()
    """

    # Default client ID — users can override with their own application
    DEFAULT_CLIENT_ID = "1234567890"

    def __init__(self, client_id: Optional[str] = None):
        self.client_id = client_id or self.DEFAULT_CLIENT_ID
        self._rpc = None
        self.connected = False

    def connect(self) -> bool:
        """
        Connect to the Discord IPC socket.

        Returns True on success, False if Discord is unavailable or
        pypresence is not installed.
        """
        try:
            from pypresence import Presence  # type: ignore

            self._rpc = Presence(self.client_id)
            self._rpc.connect()
            self.connected = True
            return True
        except ImportError:
            print("pypresence not installed — Discord RPC unavailable. "
                  "Install with: pip install pypresence")
            return False
        except Exception as exc:
            print(f"Discord RPC connect failed: {exc}")
            return False

    def update_presence(
        self,
        title: str,
        media_type: str = "movie",
        duration: int = 0,
        current_time: int = 0,
    ) -> bool:
        """
        Update the Discord Rich Presence status.

        Args:
            title:        Title of the media being played.
            media_type:   One of movie / tv / music / radio / podcast / live_tv.
            duration:     Total length in seconds (0 = unknown).
            current_time: Elapsed seconds (used to compute end timestamp).
        """
        if not self.connected or self._rpc is None:
            return False

        type_labels = {
            "movie": "Watching a movie",
            "tv": "Watching TV",
            "music": "Listening to music",
            "radio": "Listening to radio",
            "podcast": "Listening to a podcast",
            "audiobook": "Listening to an audiobook",
            "live_tv": "Watching live TV",
            "live_sport": "Watching live sport",
        }
        state = type_labels.get(media_type, f"Watching {media_type}")

        now = time.time()
        start_ts = int(now - current_time) if current_time else int(now)
        end_ts = int(now + (duration - current_time)) if duration and duration > current_time else None

        try:
            kwargs = {
                "state": state,
                "details": title[:128],
                "start": start_ts,
                "large_image": "franken_stream_logo",
                "large_text": "Franken-Stream",
                "small_image": "playing",
                "small_text": "Playing",
            }
            if end_ts:
                kwargs["end"] = end_ts

            self._rpc.update(**kwargs)
            return True
        except Exception as exc:
            print(f"Discord RPC update failed: {exc}")
            return False

    def set_paused(self, title: str, media_type: str = "movie") -> bool:
        """Update presence to show paused state."""
        if not self.connected or self._rpc is None:
            return False
        try:
            self._rpc.update(
                state="Paused",
                details=title[:128],
                large_image="franken_stream_logo",
                large_text="Franken-Stream",
                small_image="paused",
                small_text="Paused",
            )
            return True
        except Exception:
            return False

    def clear(self) -> bool:
        """Remove the Rich Presence status."""
        if not self.connected or self._rpc is None:
            return False
        try:
            self._rpc.clear()
            return True
        except Exception:
            return False

    def disconnect(self) -> None:
        """Disconnect from Discord IPC."""
        self.clear()
        if self._rpc:
            try:
                self._rpc.close()
            except Exception:
                pass
        self.connected = False
        self._rpc = None
