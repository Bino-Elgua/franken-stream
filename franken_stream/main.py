"""Main CLI application for franken-stream."""

from typing import Optional

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
) -> None:
    """
    Search and stream a movie or TV show.

    Example:
        franken-stream watch "Inception"
        franken-stream watch "Breaking Bad" --proxy http://proxy:8080
    """
    try:
        # Load providers
        pm = ProviderManager()
        bases = pm.get_search_bases()

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
            console.print("[yellow]⚠[/yellow] No results found.")
            console.print(
                "[cyan]→[/cyan] Falling back to yt-dlp... "
                "(requires yt-dlp and mpv)"
            )
            if scraper.stream_with_yt_dlp(query):
                return
            raise typer.Exit(1)

        # Display results
        _display_results(results)

        # Let user pick
        if interactive:
            _handle_selection(results, scraper)
        else:
            console.print(
                "[cyan]→[/cyan] Use --no-interactive to skip selection"
            )

    except KeyboardInterrupt:
        console.print("\n[yellow]Cancelled.[/yellow]")
        raise typer.Exit(0)
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


def _handle_selection(results: list, scraper: ContentScraper) -> None:
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

        # In a real implementation, you would:
        # 1. Check if URL contains an embed
        # 2. Try to extract video URL
        # 3. Play with mpv or browser
        console.print(
            "[yellow]→[/yellow] Manual streaming not yet implemented. "
            "Visit the link above in your browser."
        )

    except (ValueError, IndexError):
        console.print("[red]✗[/red] Invalid selection")


if __name__ == "__main__":
    app()
