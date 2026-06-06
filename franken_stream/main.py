"""Main CLI application for franken-stream."""

from typing import Optional
from pathlib import Path

import typer
from rich.console import Console
from rich.prompt import Prompt
from rich.table import Table

from franken_stream.providers import ProviderManager
from franken_stream.scraper import ContentScraper
from franken_stream.tui import run_tui

# Initialize CLI app and console
app = typer.Typer(
    help="Terminal media streamer for movies and TV shows.",
    no_args_is_help=False,
)

# Optional Web UI registration
try:
    from franken_stream import web
    app.add_typer(web.app, name="web", help="Start the browser-based Web UI")
except (ImportError, ModuleNotFoundError):
    # Web UI won't be available if dependencies (fastapi/uvicorn) are missing
    pass

console = Console()


@app.command()
def watch(
    query: str = typer.Argument(..., help="Movie or show title to search for"),
    proxy: Optional[str] = typer.Option(
        None, "--proxy", "-p", help="HTTP proxy URL (optional)"
    ),
    interactive: bool = typer.Option(
        True, "--interactive/--no-interactive", help="Interactive result selection"
    ),
    legal_only: bool = typer.Option(
        False, "--legal-only", help="Search legal sources only"
    ),
    download: bool = typer.Option(
        False, "--download", "-d", help="Download instead of stream"
    ),
    output: Optional[str] = typer.Option(
        None, "-o", help="Download output directory"
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Show detailed debug info"
    ),
    debug: bool = typer.Option(
        False, "--debug", help="Show full pipeline diagnostics (proxy, providers, embed URL)"
    ),
) -> None:
    """
    Search and stream a movie or TV show.

    Example:
        franken-stream watch "Inception"
        franken-stream watch "Breaking Bad" --proxy http://proxy:8080
        franken-stream watch "Matrix" --download -o ~/videos
        franken-stream watch "Movie" --legal-only
    """
    try:
        # Validate proxy syntax before attempting network calls
        if proxy:
            from urllib.parse import urlparse as _urlparse
            parsed_proxy = _urlparse(proxy)
            if not parsed_proxy.scheme or not parsed_proxy.hostname:
                console.print(f"[yellow]⚠[/yellow] Proxy URL looks malformed: {proxy}")
                console.print("[yellow]  Expected format: http://host:port or socks5://host:port[/yellow]")

        if debug:
            console.print("[cyan]═══ Debug Mode ═══[/cyan]")
            console.print(f"  Proxy: {proxy or 'None'}")

        # Load providers
        pm = ProviderManager()
        if legal_only:
            bases = pm.get_legal_sources()
        else:
            bases = pm.get_ranked_search_bases()

        if not bases:
            console.print(
                "[red]✗[/red] No search providers configured. "
                "Run: franken-stream update"
            )
            raise typer.Exit(1)

        # Initialize scraper with health tracking
        scraper = ContentScraper(proxy=proxy, provider_manager=pm)

        if proxy and (verbose or debug):
            console.print("[cyan]→[/cyan] Checking proxy connectivity...")
            if scraper.validate_proxy(proxy):
                console.print("[green]✓[/green] Proxy is reachable")
            else:
                console.print("[yellow]⚠[/yellow] Proxy appears unreachable — search may fail")

        if verbose or debug:
            console.print(f"[dim]  Providers loaded: {len(bases)}[/dim]")

        # Search for content
        console.print(f"\n[cyan]Searching for:[/cyan] {query}\n")
        results = scraper.search(query, bases, verbose=verbose)

        if not results:
            console.print("[yellow]⚠[/yellow] No results found locally.")
            console.print(
                "[cyan]→[/cyan] Trying fallback methods (DuckDuckGo, yt-dlp)..."
            )

            # Try DuckDuckGo
            ddg_results = scraper.search_duckduckgo(query)
            if ddg_results:
                results.extend(ddg_results)
                console.print(f"[green]✓[/green] Found {len(ddg_results)} via DDG")
            
            # If still nothing, try yt-dlp
            if not results:
                console.print("[cyan]→[/cyan] Falling back to yt-dlp...")
                if scraper.stream_with_yt_dlp(query):
                    return
                raise typer.Exit(1)

        # Display results
        _display_results(results)

        # Let user pick
        if interactive:
            _handle_selection(results, scraper, download, output, debug=debug)
        else:
            console.print(
                "[cyan]→[/cyan] Use --interactive to select a result"
            )

    except KeyboardInterrupt:
        console.print("\n[yellow]Cancelled.[/yellow]")
        raise typer.Exit(0)
    except Exception as e:
        console.print(f"[red]✗[/red] Error: {e}")
        raise typer.Exit(1)


@app.command()
def tv(
    query: str = typer.Argument(..., help="TV show name"),
    season: Optional[int] = typer.Option(
        None, "-s", "--season", help="Season number"
    ),
    episode: Optional[int] = typer.Option(
        None, "-e", "--episode", help="Episode number"
    ),
    proxy: Optional[str] = typer.Option(
        None, "--proxy", "-p", help="HTTP proxy URL (optional)"
    ),
) -> None:
    """
    Search for and stream TV shows with season/episode support.

    Example:
        franken-stream tv "Breaking Bad"
        franken-stream tv "Breaking Bad" --season 5
        franken-stream tv "Breaking Bad" -s 5 -e 14
    """
    try:
        pm = ProviderManager()
        scraper = ContentScraper(proxy=proxy, provider_manager=pm)

        # Build search query
        search_query = query
        if season and episode:
            search_query = f"{query} s{season:02d}e{episode:02d}"
            console.print(
                f"[cyan]Searching:[/cyan] {query} S{season} E{episode}\n"
            )
        elif season:
            search_query = f"{query} season {season}"
            console.print(f"[cyan]Searching:[/cyan] {query} Season {season}\n")
        else:
            console.print(f"[cyan]Searching:[/cyan] {query}\n")

        bases = pm.get_ranked_search_bases()
        results = scraper.search(search_query, bases)

        if not results:
            console.print("[yellow]⚠[/yellow] No episodes found.")
            if scraper.stream_with_yt_dlp(search_query):
                return
            raise typer.Exit(1)

        _display_results(results)
        _handle_selection(results, scraper)

    except KeyboardInterrupt:
        console.print("\n[yellow]Cancelled.[/yellow]")
        raise typer.Exit(0)
    except Exception as e:
        console.print(f"[red]✗[/red] Error: {e}")
        raise typer.Exit(1)


@app.command()
def test_providers(
    fast: bool = typer.Option(
        False, "--fast", help="Quick test (2 second timeout)"
    ),
) -> None:
    """Test provider URLs for health and response time."""
    try:
        pm = ProviderManager()
        scraper = ContentScraper(provider_manager=pm)

        bases = pm.get_ranked_search_bases()
        if not bases:
            console.print("[red]✗[/red] No providers configured")
            raise typer.Exit(1)

        console.print("[cyan]Testing providers (ranked by reliability)...\n[/cyan]")

        table = Table(title="Provider Health Check")
        table.add_column("#", style="dim", width=3)
        table.add_column("URL", style="cyan", width=45)
        table.add_column("Status", style="green")
        table.add_column("Time", style="magenta")
        table.add_column("Rate", style="yellow", width=6)
        table.add_column("Avg", style="blue", width=8)

        timeout = 2 if fast else 10
        healthy_count = 0
        slow_count = 0
        dead_count = 0

        for rank, url in enumerate(bases, 1):
            is_healthy, elapsed = scraper.test_provider_url(url, timeout)
            pm.record_result(url, is_healthy, elapsed * 1000)

            stats = pm.health.get(url)
            rate_str = f"{stats.success_rate:.0%}" if stats else "—"
            avg_str = f"{stats.avg_response_ms:.0f}ms" if stats else "—"

            if is_healthy:
                if elapsed > 5:
                    status = "⚠ Slow"
                    slow_count += 1
                else:
                    status = "✓ OK"
                    healthy_count += 1
                time_str = f"{elapsed:.2f}s"
            else:
                status = "✗ Dead"
                dead_count += 1
                time_str = "Timeout"

            table.add_row(str(rank), url[:45], status, time_str, rate_str, avg_str)

        console.print(table)

        console.print(f"\n[green]Healthy:[/green] {healthy_count}")
        console.print(f"[yellow]Slow:[/yellow] {slow_count}")
        console.print(f"[red]Dead:[/red] {dead_count}")

        if dead_count > 0:
            console.print(
                "\n[yellow]→[/yellow] Dead providers will be deprioritized automatically"
            )

    except Exception as e:
        console.print(f"[red]✗[/red] Error: {e}")
        raise typer.Exit(1)


@app.command()
def update() -> None:
    """Update streaming providers from GitHub."""
    try:
        pm = ProviderManager()
        if pm.update_providers():
            console.print(
                "[green]✓[/green] Providers updated successfully"
            )
        else:
            raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]✗[/red] Update failed: {e}")
        raise typer.Exit(1)


@app.command()
def validate() -> None:
    """Validate configuration file."""
    try:
        pm = ProviderManager()
        if pm.validate_config():
            console.print("[green]✓[/green] Configuration is valid")
        else:
            raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]✗[/red] Validation error: {e}")
        raise typer.Exit(1)


@app.command()
def config() -> None:
    """Show configuration information."""
    pm = ProviderManager()
    pm._ensure_config_dir()

    table = Table(title="Franken-Stream Configuration")
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Config Dir", str(pm.config_dir))
    table.add_row("Config File", str(pm.config_file))
    table.add_row("GitHub Source", pm.github_url)

    console.print(table)

    if pm.config_file.exists():
        console.print(
            f"\n[green]✓[/green] Config file exists at {pm.config_file}"
        )
        
        # Show stats
        try:
            bases = pm.get_search_bases()
            fallbacks = pm.get_embed_fallbacks()
            legal = pm.get_legal_sources()
            
            console.print(f"  - Search bases: {len(bases)}")
            console.print(f"  - Embed fallbacks: {len(fallbacks)}")
            console.print(f"  - Legal sources: {len(legal)}")
        except Exception as e:
            console.print(f"  [yellow]⚠[/yellow] Could not read stats: {e}")
    else:
        console.print(
            f"\n[yellow]⚠[/yellow] Config file not found. "
            "Run: franken-stream update"
        )


def _display_results(results: list) -> None:
    """Display search results in a formatted table."""
    table = Table(title="Search Results")
    table.add_column("#", style="magenta", width=3)
    table.add_column("Title", style="cyan")
    table.add_column("URL", style="green", overflow="fold")

    for i, (title, url) in enumerate(results[:15], 1):
        table.add_row(str(i), title[:60], url[:80])

    console.print(table)


def _handle_selection(
    results: list,
    scraper: ContentScraper,
    download: bool = False,
    output: Optional[str] = None,
    debug: bool = False,
) -> None:
    """Handle user selection from search results."""
    try:
        choice = Prompt.ask(
            "\n[cyan]Select result[/cyan]",
            choices=[str(i) for i in range(1, len(results) + 1)],
        )
        idx = int(choice) - 1
        title, url = results[idx]

        if debug:
            console.print(f"[cyan]  Selected:[/cyan] {title}")
            console.print(f"[cyan]  URL:[/cyan] {url}")

        console.print(
            f"\n[cyan]Selected:[/cyan] {title}\n"
            f"[cyan]URL:[/cyan] {url}\n"
        )

        # Determine if this is a detail page and extract embed
        is_embed = False
        is_detail_page = "/watch/" in url or "/movie/" in url or "/title/" in url

        if is_detail_page:
            console.print("[cyan]→[/cyan] Fetching player embed...")

            # Try to get the full base URL for relative URL construction
            base_url = None
            if url.startswith("/"):
                # Relative URL - need to determine base
                console.print("[yellow]⚠ Relative URL detected, using fallback base...")

            embed_url = scraper.fetch_embed_from_page(url, base_url=base_url)
            if debug:
                if embed_url:
                    console.print(f"[cyan]  Embed URL:[/cyan] {embed_url[:100]}")
                else:
                    console.print("[yellow]  No embed found — trying direct URL[/yellow]")
                    console.print("[yellow]  Troubleshooting:[/yellow]")
                    console.print("    1. Site may require JavaScript (use browser)")
                    console.print("    2. Run 'franken-stream test-providers' to check health")
                    console.print("    3. Try 'franken-stream update' for fresh provider list")
            if embed_url:
                is_embed = True
                url = embed_url

        # Handle download or stream
        if download:
            scraper.download_video(url, output)
        else:
            # Try to stream
            if url.startswith(("http://", "https://", "//")):
                if is_detail_page and not is_embed:
                    console.print(
                        "[yellow]→[/yellow] No embed extracted, "
                        "opening in browser..."
                    )
                    console.print(f"[green]{url}[/green]")
                else:
                    scraper.play_url(url, is_embed=is_embed)
            else:
                console.print(
                    "[yellow]→[/yellow] Opening in browser "
                    "(streaming not available)."
                )
                console.print(f"[green]{url}[/green]")

    except (ValueError, IndexError):
        console.print("[red]✗[/red] Invalid selection")


@app.callback(invoke_without_command=True)
def default_command(ctx: typer.Context) -> None:
    """
    Launch Franken-Stream TUI or CLI based on arguments.
    
    Run with no args to launch full-screen TUI dashboard.
    Use --cli flag to force CLI mode.
    """
    # If no command was invoked, launch TUI
    if ctx.invoked_subcommand is None:
        # Check if --cli flag was used
        if "--cli" not in ctx.args and "-c" not in ctx.args:
            # Launch TUI
            try:
                run_tui()
            except ImportError:
                console.print(
                    "[yellow]⚠[/yellow] Textual not installed. "
                    "Install: pip install textual"
                )
                console.print("[cyan]→[/cyan] Falling back to CLI mode\n")
                app()
            except Exception:
                # Fallback to CLI if TUI fails
                app()


if __name__ == "__main__":
    app()
