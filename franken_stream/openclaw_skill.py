"""
OpenClaw skill for Franken-Stream.

Two public surfaces:
  1. IntentParser — converts a natural-language message into a structured
     intent dict that can be POSTed to the /openclaw endpoint.
  2. FrankenStreamSkill — wraps the intent parser and the existing CLI /
     new media providers, producing a result dict in the same shape that the
     Rust server returns.

Neither class calls the Rust server directly.  They are used by the sidecar
(sidecar_main.py) and can also be exercised from the command line:

    python -m franken_stream.openclaw_skill "Watch Inception"
    python -m franken_stream.openclaw_skill "Play jazz radio"
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Intent parser
# ---------------------------------------------------------------------------

class IntentParser:
    """
    Convert a natural-language message into a structured intent dict.

    The returned dict has the same shape expected by handle_openclaw() in
    sidecar_main.py:
        {
            "intent":  "<intent_name>",
            "params":  { ... }
        }
    """

    # Regex patterns for TV episode detection
    _TV_PATTERNS: List[Tuple[str, str]] = [
        (r"(.+?)\s+season\s+(\d+)\s+episode\s+(\d+)", "sep"),
        (r"(.+?)\s+s(\d+)e(\d+)",                      "compact"),
        (r"(.+?)\s+s(\d+)\s+e(\d+)",                   "spaced"),
    ]

    # Keywords that trigger a search-only result instead of auto-play
    _SEARCH_KEYWORDS = frozenset(
        ["find", "search", "what", "where", "is on", "available", "list"]
    )

    # Provider-quality keywords
    _QUALITY_MAP = {
        "4k": ["4k", "2160p", "uhd"],
        "1080p": ["1080p", "full hd", "fhd"],
        "720p": ["720p", "hd"],
    }

    # Audio-media trigger words
    _RADIO_KEYWORDS    = frozenset(["radio", "station", "fm", "am", "stream music"])
    _PODCAST_KEYWORDS  = frozenset(["podcast", "episode", "show", "listen to"])
    _AUDIOBOOK_KEYWORDS = frozenset(["audiobook", "audio book", "read me", "narrate", "librivox"])
    _LIVE_TV_KEYWORDS  = frozenset(["live", "live tv", "channel", "broadcast", "iptv", "breaking news"])
    _SCORES_KEYWORDS   = frozenset(["score", "scores", "match", "fixture", "standing", "goal",
                                    "football", "soccer", "premier league"])

    def parse(self, message: str) -> Dict[str, Any]:
        """Return an intent dict for *message*."""
        msg = message.strip()
        lower = msg.lower()

        # --- sports scores ---
        if any(kw in lower for kw in self._SCORES_KEYWORDS):
            team = self._strip_action_words(msg)
            return {"intent": "get_scores", "params": {"team": team, "live_only": "live" in lower}}

        # --- live TV ---
        if any(kw in lower for kw in self._LIVE_TV_KEYWORDS):
            query = self._strip_action_words(msg)
            category = self._extract_category(lower)
            return {"intent": "watch_live", "params": {"query": query, "category": category}}

        # --- radio ---
        if any(kw in lower for kw in self._RADIO_KEYWORDS):
            genre = self._extract_genre(lower)
            query = self._strip_action_words(msg)
            return {"intent": "play_radio", "params": {"query": query, "genre": genre}}

        # --- podcast ---
        if any(kw in lower for kw in self._PODCAST_KEYWORDS):
            query = self._strip_action_words(msg)
            return {"intent": "play_podcast", "params": {"query": query}}

        # --- audiobook ---
        if any(kw in lower for kw in self._AUDIOBOOK_KEYWORDS):
            query = self._strip_action_words(msg)
            by_author = "by " in lower or "--author" in lower
            return {
                "intent": "play_audiobook",
                "params": {"query": query, "search_by": "author" if by_author else "title"},
            }

        # --- TV episode ---
        for pattern, _ in self._TV_PATTERNS:
            m = re.search(pattern, msg, re.IGNORECASE)
            if m:
                return {
                    "intent": "stream_episode",
                    "params": {
                        "show": m.group(1).strip(),
                        "season": int(m.group(2)),
                        "episode": int(m.group(3)),
                    },
                }

        # --- search only (no auto-play) ---
        if any(kw in lower for kw in self._SEARCH_KEYWORDS):
            description = self._strip_action_words(msg)
            return {"intent": "search_natural", "params": {"description": description}}

        # --- recommend by mood/genre ---
        mood = self._extract_mood(lower)
        if mood:
            genre = self._extract_genre(lower)
            return {"intent": "recommend", "params": {"mood": mood, "genre": genre or ""}}

        # --- default: stream a movie ---
        title = self._strip_action_words(msg)
        quality = self._extract_quality(lower)
        return {"intent": "stream", "params": {"title": title, "quality": quality}}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _strip_action_words(self, msg: str) -> str:
        """Remove leading action verbs and trailing provider/quality qualifiers."""
        clean = re.sub(
            r"^(stream|watch|play|find|search|listen to|read me|"
            r"audiobook|podcast|radio|show me|get|give me|what are|"
            r"what is|where can i watch|is there)\s+",
            "",
            msg,
            flags=re.IGNORECASE,
        )
        clean = re.sub(
            r"\s+(in|from|on|at|using)\s+\S+$", "", clean, flags=re.IGNORECASE
        )
        return clean.strip()

    def _extract_quality(self, lower: str) -> str:
        for quality, keywords in self._QUALITY_MAP.items():
            if any(kw in lower for kw in keywords):
                return quality
        return "720p"

    def _extract_genre(self, lower: str) -> str:
        genres = [
            "jazz", "classical", "rock", "pop", "hip hop", "country", "electronic",
            "r&b", "metal", "indie", "blues", "reggae", "latin",
            "comedy", "action", "drama", "horror", "sci-fi", "thriller",
            "documentary", "romance", "animation",
        ]
        for g in genres:
            if g in lower:
                return g
        return ""

    def _extract_mood(self, lower: str) -> str:
        moods = ["relaxing", "exciting", "funny", "scary", "sad", "happy",
                 "intense", "romantic", "inspiring", "dark", "light-hearted"]
        for mood in moods:
            if mood in lower:
                return mood
        return ""

    def _extract_category(self, lower: str) -> Optional[str]:
        cats = ["news", "sports", "entertainment", "movies", "kids", "music",
                "documentary", "cooking", "lifestyle", "travel", "science", "business"]
        for cat in cats:
            if cat in lower:
                return cat
        return None


# ---------------------------------------------------------------------------
# Skill handler (used standalone and by sidecar)
# ---------------------------------------------------------------------------

class FrankenStreamSkill:
    """
    Execute parsed OpenClaw intents using the franken-stream providers.

    All results are returned as dicts in the shape:
        {
            "status":       "success" | "needs_clarification" | "error",
            "action_taken": "<string>",
            "data":         { "results": [...] },
            "message":      "<string>",
        }
    """

    def __init__(self, franken_bin: str = "franken-stream"):
        self.franken_bin = franken_bin
        self.parser = IntentParser()

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def handle_message(self, message: str) -> Dict[str, Any]:
        """Parse *message* and execute the resulting intent."""
        intent_dict = self.parser.parse(message)
        return self.handle_intent(intent_dict["intent"], intent_dict["params"])

    def handle_intent(self, intent: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Dispatch a pre-parsed intent."""
        dispatch = {
            "play_radio":          self._handle_play_radio,
            "play_podcast":        self._handle_play_podcast,
            "get_podcast_episodes": self._handle_get_podcast_episodes,
            "play_audiobook":      self._handle_play_audiobook,
            "watch_live":          self._handle_watch_live,
            "get_scores":          self._handle_get_scores,
        }
        fn = dispatch.get(intent)
        if fn:
            return fn(params)
        # Intents handled by sidecar_main (stream, stream_episode, etc.) fall
        # through and return needs_clarification so the caller can escalate.
        return {
            "status": "needs_clarification",
            "action_taken": "none",
            "data": {},
            "message": f"Intent '{intent}' must be handled by the sidecar.",
        }

    # ------------------------------------------------------------------
    # Media-type handlers
    # ------------------------------------------------------------------

    def _handle_play_radio(self, params: Dict) -> Dict[str, Any]:
        from franken_stream.music.radio_browser import RadioBrowserProvider
        provider = RadioBrowserProvider()
        try:
            stations = provider.search(
                name=params.get("query", ""),
                genre=params.get("genre", ""),
                country=params.get("country", ""),
                language=params.get("language", ""),
                limit=params.get("limit", 15),
            )
        except Exception as exc:
            return self._error(f"Radio search failed: {exc}")

        return self._ok(
            "search_radio",
            stations,
            f"Found {len(stations)} radio station(s).",
        )

    def _handle_play_podcast(self, params: Dict) -> Dict[str, Any]:
        from franken_stream.audio.podcasts import PodcastProvider
        provider = PodcastProvider()
        try:
            results = provider.search(params.get("query", ""), limit=params.get("limit", 15))
        except Exception as exc:
            return self._error(f"Podcast search failed: {exc}")

        return self._ok("search_podcast", results, f"Found {len(results)} podcast(s).")

    def _handle_get_podcast_episodes(self, params: Dict) -> Dict[str, Any]:
        feed_url = params.get("feed_url", "")
        if not feed_url:
            return {
                "status": "needs_clarification",
                "action_taken": "none",
                "data": {},
                "message": "Provide a 'feed_url' to fetch episodes.",
            }
        from franken_stream.audio.podcasts import PodcastProvider
        provider = PodcastProvider()
        try:
            episodes = provider.get_episodes(feed_url, limit=params.get("limit", 10))
        except Exception as exc:
            return self._error(f"Episode fetch failed: {exc}")

        return self._ok("fetch_episodes", episodes, f"Found {len(episodes)} episode(s).")

    def _handle_play_audiobook(self, params: Dict) -> Dict[str, Any]:
        from franken_stream.audio.audiobooks import LibriVoxProvider
        provider = LibriVoxProvider()
        query = params.get("query", "")
        by_author = params.get("search_by", "title") == "author"
        try:
            books = (
                provider.search_by_author(query)
                if by_author
                else provider.search(query)
            )
        except Exception as exc:
            return self._error(f"Audiobook search failed: {exc}")

        return self._ok("search_audiobook", books, f"Found {len(books)} audiobook(s).")

    def _handle_watch_live(self, params: Dict) -> Dict[str, Any]:
        from franken_stream.live_tv.m3u_scraper import LiveTVProvider
        provider = LiveTVProvider()
        query = params.get("query", "")
        try:
            channels = (
                provider.search(query)
                if query
                else provider.get_channels(
                    category=params.get("category"),
                    country=params.get("country"),
                    limit=params.get("limit", 25),
                )
            )
        except Exception as exc:
            return self._error(f"Live TV fetch failed: {exc}")

        return self._ok("search_live_tv", channels, f"Found {len(channels)} channel(s).")

    def _handle_get_scores(self, params: Dict) -> Dict[str, Any]:
        api_key = os.environ.get("SPORTS_API_KEY")
        from franken_stream.sports.api_sports import SportsProvider
        provider = SportsProvider(api_key=api_key)

        if not provider.available:
            return {
                "status": "needs_clarification",
                "action_taken": "none",
                "data": {},
                "message": (
                    "Set the SPORTS_API_KEY environment variable to enable "
                    "sports scores. Free tier: https://www.api-sports.io"
                ),
            }

        team = params.get("team", "")
        live_only = params.get("live_only", False)
        try:
            if live_only:
                matches = provider.get_live_matches()
            elif team:
                matches = provider.search_fixtures(team)
            else:
                matches = provider.get_fixtures_today()
        except Exception as exc:
            return self._error(f"Sports API error: {exc}")

        return self._ok("fetch_scores", matches, f"Found {len(matches)} match(es).")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _ok(action: str, results: List, message: str) -> Dict[str, Any]:
        return {
            "status": "success",
            "action_taken": action,
            "data": {"results": results},
            "message": message,
        }

    @staticmethod
    def _error(message: str) -> Dict[str, Any]:
        return {
            "status": "error",
            "action_taken": "none",
            "data": {},
            "message": message,
        }


# ---------------------------------------------------------------------------
# CLI entry point for quick testing
# ---------------------------------------------------------------------------

def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python -m franken_stream.openclaw_skill '<message>'")
        sys.exit(1)

    message = " ".join(sys.argv[1:])
    skill = FrankenStreamSkill()
    parser = IntentParser()

    intent_dict = parser.parse(message)
    print(f"Parsed intent: {json.dumps(intent_dict, indent=2)}", file=sys.stderr)

    result = skill.handle_message(message)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
