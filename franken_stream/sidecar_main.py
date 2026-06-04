"""JSON-RPC sidecar entry point for franken-stream.

Reads JSON-RPC requests from stdin (one per line), sends responses to stdout,
and streams intermediate results (search.result notifications) to stderr.
"""

import asyncio
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict
from urllib.parse import quote

import hashlib

from franken_stream.async_scraper import AsyncContentScraper
from franken_stream.cache import FTSCache, SearchCache
from franken_stream.llm import LLMClient
from franken_stream.player import PremiumPlayer
from franken_stream.providers import ProviderManager
from franken_stream.scraper import ContentScraper
from franken_stream.watchlist import Watchlist


class SidecarHandler:
    """Handles JSON-RPC methods for the Rust orchestration layer."""

    def __init__(self):
        self.pm = ProviderManager()
        self.llm = LLMClient()
        self.scraper = ContentScraper(provider_manager=self.pm, llm_client=self.llm)
        self.search_cache = SearchCache()
        self.async_scraper = AsyncContentScraper(provider_manager=self.pm)
        self.fts_cache = FTSCache()
        self.player = PremiumPlayer()
        self.watchlist = Watchlist()

    async def handle_search(self, params: Dict[str, Any]) -> Dict[str, Any]:
        query = params.get("query", "").strip()
        if not query:
            return {"results": [], "total": 0}

        # FTS5 cache hit
        cached = self.fts_cache.lookup(query)
        if cached:
            return {
                "results": [{"title": t, "url": u} for t, u in cached],
                "total": len(cached),
                "cached": True,
            }

        bases = self.pm.get_ranked_search_bases()
        scraper_results, plugin_results = await asyncio.gather(
            self.async_scraper.search(query, bases),
            self.pm.search_plugins(query),
            return_exceptions=True,
        )
        if isinstance(scraper_results, Exception):
            scraper_results = []
        if isinstance(plugin_results, Exception):
            plugin_results = []

        seen: set = {u for _, u in scraper_results}
        results = list(scraper_results)
        for title, url in plugin_results:
            if url not in seen:
                seen.add(url)
                results.append((title, url))

        if results:
            self.fts_cache.store(query, results)

        return {
            "results": [{"title": t, "url": u} for t, u in results],
            "total": len(results),
            "cached": False,
        }

    def _search_providers(self, query: str, max_providers: int) -> Dict[str, Any]:
        bases = self.pm.get_ranked_search_bases()[:max_providers]
        encoded_query = quote(query.replace(" ", "+"))
        batches = []

        def fetch_one(base_url: str):
            start = time.time()
            try:
                full_url = f"{base_url}{encoded_query}"
                response = self.scraper.session.get(full_url, timeout=10)
                response.raise_for_status()
                elapsed_ms = (time.time() - start) * 1000

                from bs4 import BeautifulSoup

                soup = BeautifulSoup(response.content, "html.parser")
                items = ContentScraper._extract_results(soup)

                self.pm.record_result(base_url, len(items) > 0, elapsed_ms)
                return base_url, items, elapsed_ms
            except Exception:
                elapsed_ms = (time.time() - start) * 1000
                self.pm.record_result(base_url, False, elapsed_ms)
                return base_url, [], elapsed_ms

        with ThreadPoolExecutor(max_workers=min(len(bases), 6)) as executor:
            futures = {executor.submit(fetch_one, url): url for url in bases}
            for future in as_completed(futures):
                base_url, items, elapsed_ms = future.result()
                batches.append(
                    {
                        "provider": base_url,
                        "results": [
                            {"title": t, "url": u, "provider": base_url}
                            for t, u in items
                        ],
                        "elapsed_ms": round(elapsed_ms, 1),
                    }
                )

        return {"cached": False, "batches": batches}

    async def handle_get_health(self, _params: Dict) -> Dict[str, Any]:
        """Return provider health stats."""
        return {"providers": self.pm.get_health_summary()}

    async def handle_openclaw(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle structured intent requests from OpenClaw."""
        intent = params.get("intent")
        query = None
        action = "no_action"
        message = "No intent matched."

        if intent == "stream":
            query = params.get("title") or params.get("query")
            action = "search"
            message = f"Searching for {query}."
        elif intent == "stream_episode":
            show = params.get("show")
            season = params.get("season")
            episode = params.get("episode")
            if show and season is not None and episode is not None:
                query = f"{show} s{season:02d}e{episode:02d}"
                action = "search"
                message = f"Searching for {show} season {season} episode {episode}."
        elif intent == "search_natural":
            query = params.get("description")
            action = "search"
            message = f"Searching for {query}."
        elif intent == "recommend":
            mood = params.get("mood")
            genre = params.get("genre")
            query = f"{mood} {genre or ''} movie"
            action = "search"
            message = f"Finding recommendations for {mood}."
        elif intent == "control":
            return {
                "status": "success",
                "action_taken": "control",
                "data": {"received": params},
                "message": "Control intent received.",
            }

        if not query:
            return {
                "status": "needs_clarification",
                "action_taken": "none",
                "data": {},
                "message": "Please provide more details for the intent.",
            }

        payload = self._search_providers(query, max_providers=3)
        return {
            "status": "success",
            "action_taken": action,
            "data": {"results": payload.get("batches", [])},
            "message": message,
        }

    async def handle_embed(self, params: Dict[str, Any]) -> Dict[str, Any]:
        page_url = params.get("url", "")
        base_url = params.get("base_url")
        embed = await self.async_scraper.fetch_embed_from_page(page_url, base_url=base_url)
        if embed:
            return {"status": "found", "embed_url": embed}
        return {"status": "not_found"}

    async def handle_play(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Launch premium MPV player for a URL or auto-search query."""
        url = params.get("url", "").strip()
        title = params.get("title", "")
        query = params.get("query", "").strip()

        if not url and query:
            # Auto-search and pick first result
            bases = self.pm.get_ranked_search_bases()
            results = await self.async_scraper.search(query, bases)
            if not results:
                return {"status": "error", "message": f"No results for: {query}"}
            title, page_url = results[0]
            embed = await self.async_scraper.fetch_embed_from_page(page_url)
            url = embed or page_url

        if not url:
            return {"status": "error", "message": "url or query is required"}

        # Fetch embed if it looks like a detail page
        if any(p in url for p in ["/watch/", "/movie/", "/title/", "/stream/"]):
            embed = await self.async_scraper.fetch_embed_from_page(url)
            if embed:
                url = embed

        result = await self.player.play(url, title=title)
        if result.get("status") == "playing":
            media_id = hashlib.md5(url.encode()).hexdigest()[:12]
            self.watchlist.add(media_id, title or url, url)
        return result

    async def handle_control(self, params: Dict[str, Any]) -> Dict[str, Any]:
        action = params.get("action", "")
        ok = False

        if action == "pause":
            ok = await self.player.pause()
        elif action == "resume":
            ok = await self.player.resume()
        elif action == "stop":
            await self.player.stop()
            ok = True
        elif action == "seek":
            position = params.get("position")
            if position is not None:
                ok = await self.player.seek(int(position))
        elif action == "quit":
            await self.player.quit()
            ok = True
        else:
            return {"status": "error", "message": f"Unknown action: {action}"}

        return {"action": action, "ok": ok}

    async def handle_status(self, _params: Dict) -> Dict[str, Any]:
        return await self.player.get_status()

    async def handle_providers(self, _params: Dict) -> Dict[str, Any]:
        return {
            "search_bases": self.pm.get_ranked_search_bases(),
            "embed_fallbacks": self.pm.get_embed_fallbacks(),
            "health": self.pm.get_health_summary(),
        }

    async def handle_watchlist_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        in_progress_only = params.get("in_progress", False)
        items = self.watchlist.in_progress() if in_progress_only else self.watchlist.all()
        return {"items": items, "total": len(items)}

    async def handle_watchlist_add(self, params: Dict[str, Any]) -> Dict[str, Any]:
        title = params.get("title", "").strip()
        url = params.get("url", "").strip()
        if not title or not url:
            return {"status": "error", "message": "title and url required"}
        media_id = params.get("id") or hashlib.md5(url.encode()).hexdigest()[:12]
        self.watchlist.add(
            media_id,
            title,
            url,
            provider=params.get("provider", ""),
            year=params.get("year"),
            media_type=params.get("media_type", "movie"),
            quality=params.get("quality", "unknown"),
        )
        return {"status": "ok", "id": media_id}

    async def handle_watchlist_update(self, params: Dict[str, Any]) -> Dict[str, Any]:
        media_id = params.get("id", "")
        progress = params.get("progress_seconds")
        if not media_id or progress is None:
            return {"status": "error", "message": "id and progress_seconds required"}
        self.watchlist.update_progress(media_id, int(progress), params.get("duration_seconds"))
        return {"status": "ok"}

    async def handle_watchlist_remove(self, params: Dict[str, Any]) -> Dict[str, Any]:
        media_id = params.get("id", "")
        if not media_id:
            return {"status": "error", "message": "id required"}
        self.watchlist.remove(media_id)
        return {"status": "ok"}


async def main():
    handler = SidecarHandler()
    methods = {
        "search": handler.handle_search,
        "get_health": handler.handle_get_health,
        "get_embed": handler.handle_embed,
        "openclaw": handler.handle_openclaw,
        "play": handler.handle_play,
        "control": handler.handle_control,
        "status": handler.handle_status,
        "providers": handler.handle_providers,
        "watchlist.list": handler.handle_watchlist_list,
        "watchlist.add": handler.handle_watchlist_add,
        "watchlist.update": handler.handle_watchlist_update,
        "watchlist.remove": handler.handle_watchlist_remove,
    }

    loop = asyncio.get_event_loop()
    reader = asyncio.StreamReader()
    protocol = asyncio.StreamReaderProtocol(reader)
    await loop.connect_read_pipe(lambda: protocol, sys.stdin)

    while True:
        line = await reader.readline()
        if not line:
            break

        try:
            req = json.loads(line.decode())
        except json.JSONDecodeError:
            continue

        method_name = req.get("method")
        method_fn = methods.get(method_name)
        req_id = req.get("id")

        if method_fn:
            try:
                result = await method_fn(req.get("params", {}))
                if req_id is not None:
                    resp = {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": result,
                    }
                    sys.stdout.write(json.dumps(resp) + "\n")
                    sys.stdout.flush()
            except Exception as e:
                if req_id is not None:
                    resp = {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "error": {"code": -32000, "message": str(e)},
                    }
                    sys.stdout.write(json.dumps(resp) + "\n")
                    sys.stdout.flush()
        elif req_id is not None:
            resp = {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"Unknown method: {method_name}"},
            }
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    asyncio.run(main())
