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

from franken_stream.providers import ProviderManager
from franken_stream.scraper import ContentScraper


class SidecarHandler:
    """Handles JSON-RPC methods for the Rust orchestration layer."""

    def __init__(self):
        self.pm = ProviderManager()
        self.scraper = ContentScraper(provider_manager=self.pm)

    async def handle_search(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Search providers concurrently, streaming results via stderr."""
        query = params.get("query", "")
        max_providers = params.get("max_providers", 5)

        bases = self.pm.get_ranked_search_bases()[:max_providers]
        encoded_query = quote(query.replace(" ", "+"))
        total_results = 0

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
                if items:
                    # Stream each batch to stderr as a notification
                    notification = {
                        "jsonrpc": "2.0",
                        "method": "search.result",
                        "params": {
                            "provider": base_url,
                            "results": [
                                {"title": t, "url": u, "provider": base_url}
                                for t, u in items
                            ],
                            "elapsed_ms": round(elapsed_ms, 1),
                        },
                    }
                    print(json.dumps(notification), file=sys.stderr, flush=True)
                    total_results += len(items)

        # If no results from providers, try fallbacks
        if total_results == 0:
            ddg_results = self.scraper.search_duckduckgo(query)
            if ddg_results:
                notification = {
                    "jsonrpc": "2.0",
                    "method": "search.result",
                    "params": {
                        "provider": "duckduckgo",
                        "results": [
                            {"title": t, "url": u, "provider": "duckduckgo"}
                            for t, u in ddg_results
                        ],
                    },
                }
                print(json.dumps(notification), file=sys.stderr, flush=True)
                total_results += len(ddg_results)

        return {"status": "complete", "total": total_results}

    async def handle_get_health(self, _params: Dict) -> Dict[str, Any]:
        """Return provider health stats."""
        return {"providers": self.pm.get_health_summary()}

    async def handle_embed(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Extract embed URL from a detail page."""
        page_url = params.get("url", "")
        base_url = params.get("base_url")
        embed = self.scraper.fetch_embed_from_page(page_url, base_url=base_url)
        if embed:
            return {"status": "found", "embed_url": embed}
        return {"status": "not_found"}


async def main():
    handler = SidecarHandler()
    methods = {
        "search": handler.handle_search,
        "get_health": handler.handle_get_health,
        "get_embed": handler.handle_embed,
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
