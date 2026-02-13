"""Main CLI application for franken-stream."""

from typing import Optional
from pathlib import Path

import typer
from rich.console import Console
from rich.prompt import Prompt
from rich.table import Table

from franken_stream.providers import ProviderManager
from franken_stream.scraper import ContentScraper

# Initialize CLI app and console
app = typer.Typer(
    help="Terminal media streamer for movies and TV shows.",
    no_args_is_help=True,
)
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
        # Load providers
        pm = ProviderManager()
        bases = pm.get_legal_sources() if legal_only else pm.get_search_bases()

        if not bases:
            console.print(
                "[red]✗[/red] No search providers configured. "
                "Run: franken-stream update"
            )
            raise typer.Exit(1)

        # Initialize scraper
        scraper = ContentScraper(proxy=proxy)

        # Search for content
        console.print(f"\n[cyan]Searching for:[/cyan] {query}\n")
        results = scraper.search(query, bases)

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
            _handle_selection(results, scraper, download, output)
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
        scraper = ContentScraper(proxy=proxy)

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

        bases = pm.get_search_bases()
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
        scraper = ContentScraper()

        bases = pm.get_search_bases()
        if not bases:
            console.print("[red]✗[/red] No providers configured")
            raise typer.Exit(1)

        console.print("[cyan]Testing providers...\n[/cyan]")

        table = Table(title="Provider Health Check")
        table.add_column("URL", style="cyan", width=50)
        table.add_column("Status", style="green")
        table.add_column("Time", style="magenta")

        timeout = 2 if fast else 10
        healthy_count = 0
        slow_count = 0
        dead_count = 0

        for url in bases:
            is_healthy, elapsed = scraper.test_provider_url(url, timeout)

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

            table.add_row(url[:50], status, time_str)

        console.print(table)

        # Summary
        console.print(f"\n[green]Healthy:[/green] {healthy_count}")
        console.print(f"[yellow]Slow:[/yellow] {slow_count}")
        console.print(f"[red]Dead:[/red] {dead_count}")

        if dead_count > 0:
            console.print(
                "\n[yellow]→[/yellow] Consider removing dead providers from config"
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
) -> None:
    """Handle user selection from search results."""
    try:
        choice = Prompt.ask(
            "\n[cyan]Select result[/cyan]",
            choices=[str(i) for i in range(1, len(results) + 1)],
        )
        idx = int(choice) - 1
        title, url = results[idx]

        console.print(
            f"\n[cyan]Selected:[/cyan] {title}\n"
            f"[cyan]URL:[/cyan] {url}\n"
        )

        # Handle download or stream
        if download:
            scraper.download_video(url, output)
        else:
            # Try to stream
            if url.startswith(("http://", "https://")):
                try:
                    import subprocess

                    # Try mpv
                    subprocess.run(["mpv", url], timeout=3600)
                except FileNotFoundError:
                    console.print(
                        "[yellow]⚠[/yellow] mpv not found. "
                        "URL copied. Paste in your browser:"
                    )
                    console.print(f"[green]{url}[/green]")
                except Exception:
                    pass
            else:
                console.print(
                    "[yellow]→[/yellow] Manual streaming not yet implemented. "
                    "Visit the link above in your browser."
                )

    except (ValueError, IndexError):
        console.print("[red]✗[/red] Invalid selection")


if __name__ == "__main__":
    app()
