import json
from http import HTTPStatus
from pathlib import Path

import typer
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

from franken_stream.providers import ProviderManager
from franken_stream.scraper import ContentScraper

app = typer.Typer(help="Web UI server commands")

# Create FastAPI app
web_app = FastAPI(title="Franken-Stream Web UI", version="0.1.0")

WEB_UI_DIR = Path(__file__).resolve().parent / "web_ui"
INDEX_FILE = WEB_UI_DIR / "index.html"


# Mount static files
if WEB_UI_DIR.exists():
    web_app.mount("/static", StaticFiles(directory=str(WEB_UI_DIR)), name="static")


@web_app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the main web UI"""
    if not INDEX_FILE.exists():
        raise HTTPException(status_code=404, detail="Web UI not found")
    return FileResponse(INDEX_FILE, media_type="text/html")


@web_app.get("/api/health")
async def get_health():
    """Get provider health status"""
    try:
        pm = ProviderManager()
        health_data = pm.get_health_summary()
        return {"status": "ok", "providers": health_data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@web_app.get("/api/providers")
async def get_providers():
    """Get available search providers"""
    try:
        pm = ProviderManager()
        search_bases = pm.get_ranked_search_bases()
        return {"status": "ok", "search_bases": search_bases}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@web_app.post("/api/search")
async def search(request: Request):
    """Search for movies/shows"""
    try:
        data = await request.json()
        query = data.get("query", "").strip()

        if not query:
            raise HTTPException(status_code=400, detail="Query is required")

        pm = ProviderManager()
        scraper = ContentScraper(provider_manager=pm)

        # Search with ranked providers
        bases = pm.get_ranked_search_bases()
        results = scraper.search(query, bases, verbose=False)

        return {
            "status": "ok",
            "query": query,
            "results": [{"title": title, "url": url} for title, url in results]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@web_app.post("/api/embed")
async def get_embed(request: Request):
    """Extract embed URL from a page"""
    try:
        data = await request.json()
        page_url = data.get("url")
        base_url = data.get("base_url")

        if not page_url:
            raise HTTPException(status_code=400, detail="URL is required")

        pm = ProviderManager()
        scraper = ContentScraper(provider_manager=pm)

        embed_url = scraper.fetch_embed_from_page(page_url, base_url=base_url)

        return {"status": "ok", "embed_url": embed_url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.callback(invoke_without_command=True)
def serve(
    host: str = typer.Option("127.0.0.1", "--host", "-h", help="Host to bind the web server."),
    port: int = typer.Option(8000, "--port", "-p", help="Port for the web server."),
) -> None:
    """Start the Franken-Stream Web UI server."""
    typer.echo(f"Starting Franken-Stream Web UI at http://{host}:{port}")
    uvicorn.run(web_app, host=host, port=port)
