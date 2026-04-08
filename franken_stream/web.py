import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import typer

from franken_stream.providers import ProviderManager
from franken_stream.scraper import ContentScraper

app = typer.Typer(help="Web UI server commands")

WEB_UI_DIR = Path(__file__).resolve().parent / "web_ui"
INDEX_FILE = WEB_UI_DIR / "index.html"


class FrankenStreamHTTPRequestHandler(BaseHTTPRequestHandler):
    server_version = "FrankenStreamWeb/0.1"

    def _set_headers(self, status: int = HTTPStatus.OK, content_type: str = "application/json"):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_OPTIONS(self):
        self._set_headers()

    def do_GET(self):
        if self.path in ["/", "/index.html"]:
            return self._serve_index()

        if self.path == "/api/health":
            return self._handle_health()

        if self.path == "/api/providers":
            return self._handle_providers()

        return self._serve_static()

    def do_POST(self):
        if self.path == "/api/search":
            return self._handle_search()

        if self.path == "/api/embed":
            return self._handle_embed()

        self._set_headers(HTTPStatus.NOT_FOUND)
        self.wfile.write(json.dumps({"error": "Not found"}).encode())

    def _serve_index(self):
        if not INDEX_FILE.exists():
            self._set_headers(HTTPStatus.INTERNAL_SERVER_ERROR)
            self.wfile.write(json.dumps({"error": "Web UI index file not found"}).encode())
            return

        self._set_headers(HTTPStatus.OK, "text/html; charset=utf-8")
        self.wfile.write(INDEX_FILE.read_bytes())

    def _serve_static(self):
        normalized = self.path.lstrip("/")
        file_path = WEB_UI_DIR / normalized
        if file_path.exists() and file_path.is_file():
            content_type = "text/html"
            if file_path.suffix == ".js":
                content_type = "application/javascript"
            elif file_path.suffix == ".css":
                content_type = "text/css"
            elif file_path.suffix == ".json":
                content_type = "application/json"
            elif file_path.suffix in [".png", ".jpg", ".jpeg", ".gif"]:
                content_type = f"image/{file_path.suffix.lstrip('.')}"
            self._set_headers(HTTPStatus.OK, content_type)
            self.wfile.write(file_path.read_bytes())
            return

        self._set_headers(HTTPStatus.NOT_FOUND)
        self.wfile.write(json.dumps({"error": "File not found"}).encode())

    def _read_json_body(self):
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length <= 0:
                return None
            body = self.rfile.read(content_length)
            return json.loads(body.decode("utf-8"))
        except Exception:
            return None

    def _handle_search(self):
        payload = self._read_json_body()
        if not payload or "query" not in payload:
            self._set_headers(HTTPStatus.BAD_REQUEST)
            self.wfile.write(json.dumps({"error": "Missing query"}).encode())
            return

        query = payload.get("query", "").strip()
        if not query:
            self._set_headers(HTTPStatus.BAD_REQUEST)
            self.wfile.write(json.dumps({"error": "Query must not be empty"}).encode())
            return

        base_urls = self.server.provider_manager.get_ranked_search_bases()
        results = self.server.scraper.search_with_providers(query, base_urls)

        self._set_headers(HTTPStatus.OK)
        self.wfile.write(json.dumps({"query": query, "results": results}).encode())

    def _handle_embed(self):
        payload = self._read_json_body()
        if not payload or "url" not in payload:
            self._set_headers(HTTPStatus.BAD_REQUEST)
            self.wfile.write(json.dumps({"error": "Missing url"}).encode())
            return

        page_url = payload.get("url")
        base_url = payload.get("base_url")
        embed_url = self.server.scraper.fetch_embed_from_page(page_url, base_url=base_url)

        self._set_headers(HTTPStatus.OK)
        self.wfile.write(json.dumps({"embed_url": embed_url}).encode())

    def _handle_health(self):
        health_data = self.server.provider_manager.get_health_summary()
        self._set_headers(HTTPStatus.OK)
        self.wfile.write(json.dumps({"providers": health_data}).encode())

    def _handle_providers(self):
        search_bases = self.server.provider_manager.get_ranked_search_bases()
        self._set_headers(HTTPStatus.OK)
        self.wfile.write(json.dumps({"search_bases": search_bases}).encode())

    def log_message(self, format: str, *args) -> None:
        # Silence default logging for cleaner CLI
        return


class FrankenStreamWebServer(HTTPServer):
    def __init__(self, host: str, port: int):
        super().__init__((host, port), FrankenStreamHTTPRequestHandler)
        self.provider_manager = ProviderManager()
        self.scraper = ContentScraper(provider_manager=self.provider_manager)


def run_server(host: str = "127.0.0.1", port: int = 8000):
    server = FrankenStreamWebServer(host, port)
    print(f"Serving Franken-Stream Web UI at http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down web server...")
        server.server_close()


@app.callback(invoke_without_command=True)
def serve(
    host: str = typer.Option("127.0.0.1", "--host", "-h", help="Host to bind the web server."),
    port: int = typer.Option(8000, "--port", "-p", help="Port for the web server."),
) -> None:
    """Start the Franken-Stream Web UI server."""
    typer.echo(f"Starting Franken-Stream Web UI at http://{host}:{port}")
    run_server(host=host, port=port)
