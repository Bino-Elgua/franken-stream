"""Web scraping and content discovery."""

import re
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

# Regex patterns for robust embed extraction
EMBED_PATTERNS = [
    (r'iframe[^>]*src=["\']([^"\']+)["\']', "iframe src"),
    (r'<a[^>]*href=["\']([^"\']*(?:embed|player)[^"\']*)["\']', "embed link"),
    (r'src=["\']([^"\']*\.m3u8[^"\']*)["\']', "HLS stream"),
    (r'src=["\']([^"\']*\.mp4[^"\']*)["\']', "MP4 video"),
    (r'data-url=["\']([^"\']+)["\']', "data-url attribute"),
]


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
        self, query: str, base_urls: List[str], verbose: bool = False
    ) -> List[Tuple[str, str]]:
        """
        Search for content across multiple providers.

        Args:
            query: Search query (e.g., "Inception")
            base_urls: List of base URLs to search
            verbose: Print detailed debug info

        Returns:
            List of (title, url) tuples
        """
        results = []
        encoded_query = quote(query.replace(" ", "+"))

        for base_url in base_urls:
            try:
                full_url = f"{base_url}{encoded_query}"
                if verbose:
                    console.log(f"[cyan]→ Searching: {full_url}")
                else:
                    console.log(f"Searching: {full_url[:60]}...")
                
                response = self.session.get(full_url, timeout=10)
                response.raise_for_status()

                soup = BeautifulSoup(response.content, "html.parser")
                items = self._extract_results(soup, verbose=verbose)
                results.extend(items)
                
                if verbose:
                    console.log(f"[green]✓ Found {len(items)} results from {base_url}")
                else:
                    console.log(f"[green]✓[/green] Found {len(items)} results")

            except requests.exceptions.ConnectionError as e:
                if verbose:
                    console.log(f"[yellow]⚠ Connection failed for {base_url}: {e}")
                # Silently skip connection errors
            except requests.exceptions.Timeout:
                if verbose:
                    console.log(f"[yellow]⚠ Timeout searching {base_url}")
                # Silently skip timeouts
            except requests.exceptions.HTTPError as e:
                if verbose:
                    console.log(f"[yellow]⚠ HTTP error {e.response.status_code} for {base_url}")
                # Silently skip HTTP errors
            except requests.RequestException as e:
                if verbose:
                    console.log(f"[yellow]⚠[/yellow] Error searching {base_url}: {e}")
            except Exception as e:
                if verbose:
                    console.log(f"[red]✗[/red] Parsing error: {e}")

        return results

    @staticmethod
    def _extract_results(
        soup: BeautifulSoup, verbose: bool = False
    ) -> List[Tuple[str, str]]:
        """
        Extract movie/show titles and links from parsed HTML with fallbacks.

        Args:
            soup: BeautifulSoup object
            verbose: Print debug info

        Returns:
            List of (title, url) tuples
        """
        results = []
        try:
            # Primary: Try common streaming site selectors
            selectors = [
                ("a.film-name", "film-name"),  # myflixerz, cineby
                ("a.title", "title"),
                ("a[href*='/watch/']", "watch link"),
                ("a[href*='/movie/']", "movie link"),
                ("a[href*='/embed/']", "embed link"),
                ("h3 a", "heading link"),
                ("div.card a", "card link"),
                ("div.film-poster a", "poster link"),
                (".mli-info a", "mli-info link"),
            ]

            for selector, selector_type in selectors:
                matches = soup.select(selector)
                if matches:
                    if verbose:
                        console.log(f"[cyan]  Found {len(matches)} with selector: {selector}")
                    for link in matches:
                        text = link.get_text(strip=True)
                        href = link.get("href", "")

                        # Filter bad results
                        if (
                            text
                            and len(text) > 2
                            and len(text) < 100  # Avoid nav menu text
                            and href
                            and not href.startswith("#")
                            and not any(
                                bad in text.lower()
                                for bad in ["home", "search", "menu", "nav", "login", "sign"]
                            )
                        ):
                            results.append((text, href))
                    if results:
                        break  # Use first selector that worked

            # Fallback: Try regex patterns if no results
            if not results:
                html_str = str(soup)
                for pattern, pattern_type in EMBED_PATTERNS:
                    matches = re.findall(pattern, html_str)
                    for match in matches:
                        if match and match.startswith(("http", "/", ".")):
                            title = match.split("/")[-1][:50]
                            results.append((f"{title} ({pattern_type})", match))
                if results and verbose:
                    console.log(f"[cyan]  Fallback: Regex matched {len(results)} patterns")

            # Deduplicate by URL while preserving order
            seen = set()
            unique_results = []
            for title, url in results:
                if url not in seen and title not in seen:
                    seen.add(url)
                    seen.add(title)
                    unique_results.append((title, url))

            return unique_results[:20]  # Limit to top 20 results

        except Exception as e:
            if verbose:
                console.log(f"[red]Error extracting results:[/red] {e}")
            return []

    def fetch_embed_from_page(self, page_url: str, base_url: Optional[str] = None) -> Optional[str]:
        """
        Fetch a page and extract embedded video URL with multiple strategies.

        Args:
            page_url: URL of the movie/show page
            base_url: Base URL for constructing full URLs from relative paths

        Returns:
            Embed URL if found, None otherwise
        """
        try:
            # Handle relative URLs
            if not page_url.startswith("http"):
                if base_url:
                    page_url = base_url.rstrip("/") + "/" + page_url.lstrip("/")
                else:
                    return None

            console.log(f"[cyan]→ Fetching embed from: {page_url[:60]}...")
            response = self.session.get(page_url, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, "html.parser")
            html_str = str(soup)

            # Strategy 1: Look for iframes with specific selectors
            selectors = [
                ".player-container iframe",
                "#player iframe",
                "#watch-iframe iframe",
                "iframe[src*='embed']",
                "iframe[src*='player']",
                "iframe[src*='watch']",
            ]
            
            for selector in selectors:
                iframes = soup.select(selector)
                for iframe in iframes:
                    src = iframe.get("src", "")
                    if src:
                        embed_url = self._make_absolute_url(src, page_url)
                        console.log(f"[green]✓ Found iframe embed:[/green] {embed_url[:60]}...")
                        return embed_url

            # Strategy 2: All iframes (fallback)
            for iframe in soup.find_all("iframe"):
                src = iframe.get("src", "")
                if src and any(
                    pattern in src.lower()
                    for pattern in ["embed", "player", "watch", "vid", "m3u8", "mp4"]
                ):
                    embed_url = self._make_absolute_url(src, page_url)
                    console.log(f"[green]✓ Found iframe embed:[/green] {embed_url[:60]}...")
                    return embed_url

            # Strategy 3: Look for video tags
            for video in soup.find_all("video"):
                src = video.get("src", "")
                if src:
                    embed_url = self._make_absolute_url(src, page_url)
                    console.log(f"[green]✓ Found video tag:[/green] {embed_url[:60]}...")
                    return embed_url

                # Check source tags inside video
                for source in video.find_all("source"):
                    src = source.get("src", "")
                    if src and any(
                        ext in src.lower() for ext in [".mp4", ".m3u8", "stream"]
                    ):
                        embed_url = self._make_absolute_url(src, page_url)
                        console.log(f"[green]✓ Found video source:[/green] {embed_url[:60]}...")
                        return embed_url

            # Strategy 4: Regex search for direct URLs
            url_pattern = r'(https?://[^\s\'"]+\.(m3u8|mp4))'
            matches = re.findall(url_pattern, html_str)
            if matches:
                embed_url = matches[0][0]
                console.log(f"[green]✓ Found direct URL:[/green] {embed_url[:60]}...")
                return embed_url

            # Strategy 5: Regex fallback on all patterns
            for pattern, pattern_type in EMBED_PATTERNS:
                matches = re.findall(pattern, html_str)
                if matches:
                    embed_url = matches[0]
                    if embed_url.startswith("http"):
                        console.log(f"[green]✓ Found {pattern_type}:[/green] {embed_url[:60]}...")
                        return embed_url

            console.log("[yellow]⚠ No embed found on detail page")
            return None

        except requests.exceptions.Timeout:
            console.log(f"[yellow]⚠ Timeout fetching {page_url}")
            return None
        except requests.exceptions.HTTPError as e:
            if e.response.status_code in [403, 404]:
                console.log(f"[yellow]⚠ Access denied/not found: {e.response.status_code}")
            else:
                console.log(f"[yellow]⚠ HTTP error: {e.response.status_code}")
            return None
        except Exception as e:
            console.log(f"[yellow]⚠ Could not fetch embed: {e}")
            return None

    @staticmethod
    def _make_absolute_url(url: str, page_url: str) -> str:
        """
        Convert relative URL to absolute URL.

        Args:
            url: URL (relative or absolute)
            page_url: Base page URL for constructing absolute URLs

        Returns:
            Absolute URL
        """
        if url.startswith("http://") or url.startswith("https://"):
            return url
        
        if url.startswith("//"):
            # Protocol-relative URL
            return "https:" + url
        
        if url.startswith("/"):
            # Absolute path
            from urllib.parse import urlparse
            parsed = urlparse(page_url)
            return f"{parsed.scheme}://{parsed.netloc}{url}"
        
        # Relative path
        from urllib.parse import urljoin
        return urljoin(page_url, url)

    def search_duckduckgo(self, query: str) -> List[Tuple[str, str]]:
        """
        Fallback search using DuckDuckGo for free streaming links.

        Args:
            query: Search query

        Returns:
            List of (title, url) tuples from DDG results
        """
        try:
            console.log(f"Searching DuckDuckGo for '{query}'...")
            ddg_query = f"{query} watch free online site:youtube.com OR site:reddit.com"
            url = "https://duckduckgo.com/html/"
            
            params = {"q": ddg_query}
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, "html.parser")
            results = []

            # Extract DDG results
            for result in soup.find_all("a", class_="result__url"):
                link_text = result.get_text(strip=True)
                link_href = result.get("href", "")
                if link_text and link_href:
                    results.append((link_text[:60], link_href))

            return results[:10]

        except Exception as e:
            console.log(f"[yellow]⚠[/yellow] DuckDuckGo search failed: {e}")
            return []

    def play_url(self, url: str, is_embed: bool = False) -> bool:
        """
        Play a URL using yt-dlp + mpv for best compatibility.

        Args:
            url: Video URL to play
            is_embed: True if URL is an embed (use yt-dlp for HLS/subtitles)

        Returns:
            True if playback started, False otherwise
        """
        try:
            console.log(f"[cyan]→ Preparing playback...")
            
            # Use yt-dlp for embeds to handle HLS, subtitles, etc.
            if is_embed:
                console.log("[cyan]  Getting stream URL via yt-dlp...")
                result = subprocess.run(
                    [
                        "yt-dlp",
                        "-f", "best",
                        "--no-playlist",
                        "--get-url",
                        url
                    ],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                
                if result.returncode == 0 and result.stdout.strip():
                    stream_url = result.stdout.strip().split("\n")[0]
                    console.log(f"[green]✓ Got stream URL[/green]")
                    url = stream_url
                else:
                    console.log("[yellow]⚠ yt-dlp could not extract stream, trying direct...")
            
            # Try mpv
            console.log("[cyan]→ Starting mpv...")
            subprocess.run(
                ["mpv", "--hwdec=auto", url],
                timeout=3600,
            )
            return True

        except FileNotFoundError:
            console.log(
                "[yellow]⚠ mpv not found. Install with: pkg install mpv"
            )
            console.log(f"[green]Stream URL: {url}[/green]")
            console.log("[cyan]Paste this URL in your browser or use: yt-dlp {url}")
            return True  # Still success (user can play manually)
        except subprocess.TimeoutExpired:
            return True  # Normal end of playback
        except Exception as e:
            console.log(f"[red]✗ Playback error: {e}")
            return False

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

    def download_video(
        self, url: str, output_path: Optional[str] = None
    ) -> bool:
        """
        Download video using yt-dlp.

        Args:
            url: Video URL
            output_path: Output directory (default: ~/Downloads)

        Returns:
            True if download started, False otherwise
        """
        try:
            from pathlib import Path

            if output_path is None:
                output_path = str(Path.home() / "Downloads")

            console.log(f"Downloading to {output_path}...")
            result = subprocess.run(
                [
                    "yt-dlp",
                    "-o",
                    f"{output_path}/%(title)s.%(ext)s",
                    url,
                ],
                timeout=3600,
            )

            if result.returncode == 0:
                console.log(f"[green]✓[/green] Download complete")
                return True
            else:
                console.log("[red]✗[/red] Download failed")
                return False

        except FileNotFoundError:
            console.log(
                "[red]✗[/red] yt-dlp not found. Install: pip install yt-dlp"
            )
            return False
        except subprocess.TimeoutExpired:
            console.log("[yellow]⚠[/yellow] Download timed out")
            return False
        except Exception as e:
            console.log(f"[red]✗[/red] Download error: {e}")
            return False

    def test_provider_url(self, url: str, timeout: int = 10) -> Tuple[bool, float]:
        """
        Test if a provider URL is reachable.

        Args:
            url: Provider URL to test
            timeout: Request timeout in seconds

        Returns:
            Tuple of (is_healthy, response_time_in_seconds)
        """
        try:
            import time

            start = time.time()
            response = self.session.head(url, timeout=timeout)
            elapsed = time.time() - start

            is_healthy = response.status_code < 400
            return is_healthy, elapsed

        except requests.Timeout:
            return False, float(timeout)
        except requests.RequestException:
            return False, 0.0
        except Exception:
            return False, 0.0
