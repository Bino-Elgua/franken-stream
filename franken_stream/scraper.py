"""Web scraping and content discovery."""

import subprocess
from typing import List, Optional, Tuple
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup
from rich.console import Console

console = Console()

# Default User-Agent to avoid blocking
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/119.0.0.0 Safari/537.36"
)


class ContentScraper:
    """Scrapes streaming content from various providers."""

    def __init__(self, proxy: Optional[str] = None, user_agent: Optional[str] = None):
        """
        Initialize scraper with optional proxy and custom User-Agent.

        Args:
            proxy: Optional proxy URL (e.g., http://proxy.example.com:8080)
            user_agent: Custom User-Agent header
        """
        self.proxy = proxy
        self.user_agent = user_agent or DEFAULT_USER_AGENT
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": self.user_agent})

        if proxy:
            self.session.proxies = {"http": proxy, "https": proxy}

    def search(
        self, query: str, base_urls: List[str]
    ) -> List[Tuple[str, str]]:
        """
        Search for content across multiple providers.

        Args:
            query: Search query (e.g., "Inception")
            base_urls: List of base URLs to search

        Returns:
            List of (title, url) tuples
        """
        results = []
        encoded_query = quote(query.replace(" ", "+"))

        for base_url in base_urls:
            try:
                full_url = f"{base_url}{encoded_query}"
                console.log(f"Searching: {full_url[:60]}...")
                response = self.session.get(full_url, timeout=10)
                response.raise_for_status()

                soup = BeautifulSoup(response.content, "html.parser")
                items = self._extract_results(soup)
                results.extend(items)
                console.log(f"[green]✓[/green] Found {len(items)} results")

            except requests.RequestException as e:
                console.log(f"[yellow]⚠[/yellow] Error searching {base_url}: {e}")
            except Exception as e:
                console.log(f"[red]✗[/red] Parsing error: {e}")

        return results

    @staticmethod
    def _extract_results(soup: BeautifulSoup) -> List[Tuple[str, str]]:
        """
        Extract movie/show titles and links from parsed HTML.

        Args:
            soup: BeautifulSoup object

        Returns:
            List of (title, url) tuples
        """
        results = []
        try:
            # Try common selectors for streaming sites
            for link in soup.find_all("a", href=True):
                text = link.get_text(strip=True)
                href = link.get("href", "")

                # Filter out navigation and empty links
                if text and len(text) > 2 and href and not href.startswith("#"):
                    # Make relative URLs absolute if needed
                    if href.startswith("/"):
                        parsed = soup.find("base")
                        if parsed:
                            base = parsed.get("href", "")
                            if base:
                                href = base.rstrip("/") + href

                    results.append((text, href))

            # Deduplicate by URL while preserving order
            seen = set()
            unique_results = []
            for title, url in results:
                if url not in seen:
                    seen.add(url)
                    unique_results.append((title, url))

            return unique_results[:20]  # Limit to top 20 results

        except Exception as e:
            console.log(f"[red]Error extracting results:[/red] {e}")
            return []

    def stream_with_yt_dlp(self, query: str) -> bool:
        """
        Fallback streaming using yt-dlp with mpv player.

        Args:
            query: Search query

        Returns:
            True if streaming started, False otherwise
        """
        try:
            console.log(f"Attempting to stream '{query}' with yt-dlp...")
            search_query = f"ytsearch:{query} full movie"

            # Get streaming URL using yt-dlp
            result = subprocess.run(
                [
                    "yt-dlp",
                    "-f",
                    "best",
                    "--get-url",
                    search_query,
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode == 0 and result.stdout.strip():
                url = result.stdout.strip().split("\n")[0]
                console.log(f"[green]✓[/green] Found stream: {url[:60]}...")

                # Try to play with mpv
                try:
                    subprocess.run(
                        ["mpv", url],
                        timeout=3600,
                    )
                    return True
                except FileNotFoundError:
                    console.log(
                        "[yellow]⚠[/yellow] mpv not found. "
                        "Please install mpv or use your player manually."
                    )
                    console.log(f"Stream URL: {url}")
                    return True
                except subprocess.TimeoutExpired:
                    return True  # Stream ended normally

            else:
                console.log(
                    "[red]✗[/red] Could not find stream with yt-dlp"
                )
                return False

        except FileNotFoundError:
            console.log(
                "[red]✗[/red] yt-dlp not found. "
                "Install with: pip install yt-dlp"
            )
            return False
        except subprocess.TimeoutExpired:
            console.log("[yellow]⚠[/yellow] yt-dlp search timed out")
            return False
        except Exception as e:
            console.log(f"[red]✗[/red] yt-dlp error: {e}")
            return False
