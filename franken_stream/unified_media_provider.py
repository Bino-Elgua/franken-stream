"""Unified media provider — one interface for all franken-stream media types."""

import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional

from franken_stream.audio.audiobooks import LibriVoxProvider
from franken_stream.audio.podcasts import PodcastProvider
from franken_stream.live_tv.m3u_scraper import LiveTVProvider
from franken_stream.music.radio_browser import RadioBrowserProvider
from franken_stream.music.youtube_music import YouTubeMusicProvider
from franken_stream.social.discord_rpc import DiscordRichPresence
from franken_stream.sports.api_sports import SportsProvider


# Optional Navidrome — only usable when the user has configured a server
def _make_navidrome(server: str, user: str, password: str):
    from franken_stream.music.navidrome import NavidromeProvider
    return NavidromeProvider(server, user, password)


class UnifiedMediaProvider:
    """
    Single entry-point to search and play all supported media types:

    - Movies / TV shows  (existing 55+ provider scraper)
    - Internet radio     (Radio Browser — 90,000+ stations)
    - Podcasts           (iTunes + RSS)
    - Audiobooks         (LibriVox — public domain)
    - YouTube Music      (scraping, no API key)
    - Live TV            (IPTV-org M3U — 8,000+ channels)
    - Sports scores      (API-Sports — optional API key)
    - Navidrome / Subsonic music (optional, self-hosted)

    Social add-ons (optional):
    - Discord Rich Presence (pypresence)
    - Watch Party            (websocket-client)
    """

    MEDIA_TYPES = {
        "movie", "tv", "music", "radio", "podcast",
        "audiobook", "live_tv", "live_sport",
    }

    def __init__(
        self,
        sports_api_key: Optional[str] = None,
        navidrome_server: Optional[str] = None,
        navidrome_user: Optional[str] = None,
        navidrome_password: Optional[str] = None,
        discord_client_id: Optional[str] = None,
    ):
        self.radio = RadioBrowserProvider()
        self.podcasts = PodcastProvider()
        self.audiobooks = LibriVoxProvider()
        self.youtube_music = YouTubeMusicProvider()
        self.live_tv = LiveTVProvider()
        self.sports = SportsProvider(api_key=sports_api_key)
        self.discord = DiscordRichPresence(client_id=discord_client_id)

        self.navidrome = None
        if navidrome_server and navidrome_user and navidrome_password:
            self.navidrome = _make_navidrome(
                navidrome_server, navidrome_user, navidrome_password
            )

        self._watch_party = None

    # ------------------------------------------------------------------
    # Universal search
    # ------------------------------------------------------------------

    def search_all(
        self,
        query: str,
        media_type: str = "auto",
        max_workers: int = 6,
    ) -> Dict[str, List[Dict]]:
        """
        Search across all configured media types concurrently.

        Args:
            query:       Search string.
            media_type:  One of the MEDIA_TYPES constants, or "auto" for all.
            max_workers: Thread-pool size for concurrent searches.

        Returns:
            Dict mapping category name → list of result dicts.
        """
        tasks: Dict[str, callable] = {}

        mt = media_type.lower()

        if mt in ("auto", "radio", "music"):
            tasks["radio"] = lambda: self.radio.search(query)

        if mt in ("auto", "podcast"):
            tasks["podcasts"] = lambda: self.podcasts.search(query)

        if mt in ("auto", "audiobook"):
            tasks["audiobooks"] = lambda: self.audiobooks.search(query)

        if mt in ("auto", "music"):
            tasks["youtube_music"] = lambda: self.youtube_music.search(query)
            if self.navidrome:
                tasks["local_music"] = lambda: self.navidrome.search(query)

        if mt in ("auto", "live_tv", "tv"):
            tasks["live_tv"] = lambda: self.live_tv.search(query)

        results: Dict[str, List[Dict]] = {k: [] for k in tasks}

        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            future_to_key = {pool.submit(fn): key for key, fn in tasks.items()}
            for future in as_completed(future_to_key):
                key = future_to_key[future]
                try:
                    results[key] = future.result(timeout=15)
                except Exception:
                    results[key] = []

        return results

    # ------------------------------------------------------------------
    # Playback
    # ------------------------------------------------------------------

    def play(
        self,
        item: Dict,
        start_watch_party: bool = False,
        watch_party_server: Optional[str] = None,
    ) -> bool:
        """
        Play a media item and optionally update Discord presence / start a watch party.

        Args:
            item:                  Media dict with at least "url" and "type" keys.
            start_watch_party:     If True, create a watch-party room.
            watch_party_server:    WebSocket URL of the watch-party server.

        Returns:
            True if playback was launched successfully.
        """
        media_type = item.get("type", "movie")
        title = item.get("title", "Unknown")
        url = item.get("url", "")

        if not url:
            return False

        # Discord Rich Presence (best-effort)
        if self.discord.connected:
            self.discord.update_presence(
                title=title,
                media_type=media_type,
                duration=item.get("duration", 0),
            )

        # Watch party
        if start_watch_party and watch_party_server:
            from franken_stream.social.watch_party import WatchParty
            self._watch_party = WatchParty(watch_party_server)
            try:
                room_id = self._watch_party.create_room(url, title)
                print(f"Watch party room created: {room_id}")
            except Exception as exc:
                print(f"Watch party setup failed: {exc}")

        # Route to appropriate playback method
        if media_type in ("music", "radio", "podcast", "podcast_episode",
                          "audiobook", "audiobook_chapter"):
            return self._play_audio(item)
        elif media_type == "live_tv":
            return self._play_live(item)
        else:
            return self._play_video(item)

    def _play_video(self, item: Dict) -> bool:
        url = item.get("url", "")
        title = item.get("title", "Franken-Stream")
        try:
            subprocess.Popen(
                ["mpv", url, "--force-window=immediate", f"--title={title}"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return True
        except FileNotFoundError:
            print(f"mpv not found. Open manually: {url}")
            return False

    def _play_audio(self, item: Dict) -> bool:
        url = item.get("url", "")
        title = item.get("title", "Franken-Stream")
        try:
            subprocess.Popen(
                [
                    "mpv", url,
                    "--no-video",
                    "--force-window=immediate",
                    f"--title={title}",
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return True
        except FileNotFoundError:
            print(f"mpv not found. Open manually: {url}")
            return False

    def _play_live(self, item: Dict) -> bool:
        url = item.get("url", "")
        title = item.get("title", "Live TV")
        try:
            subprocess.Popen(
                [
                    "mpv", url,
                    "--force-window=immediate",
                    f"--title={title}",
                    "--cache=5000",
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return True
        except FileNotFoundError:
            print(f"mpv not found. Open manually: {url}")
            return False

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def connect_discord(self) -> bool:
        """Connect Discord Rich Presence (optional)."""
        return self.discord.connect()

    def disconnect_discord(self) -> None:
        """Disconnect Discord Rich Presence."""
        self.discord.disconnect()

    def get_watch_party(self):
        """Return the active WatchParty instance (if any)."""
        return self._watch_party
