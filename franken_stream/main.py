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
from franken_stream import web

# Initialize CLI app and console
app = typer.Typer(
    help="Terminal media streamer for movies and TV shows.",
    no_args_is_help=False,
)
app.add_typer(web.app, name="web", help="Start the browser-based Web UI")
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


@app.command()
def radio(
    query: str = typer.Argument("", help="Station name or genre to search"),
    genre: Optional[str] = typer.Option(None, "--genre", "-g", help="Music genre / tag"),
    country: Optional[str] = typer.Option(None, "--country", "-c", help="Country name"),
    language: Optional[str] = typer.Option(None, "--language", "-l", help="Language"),
    limit: int = typer.Option(15, "--limit", "-n", help="Max results to show"),
) -> None:
    """
    Search and play internet radio stations (90,000+ stations, no API key).

    Examples:
        franken-stream radio jazz
        franken-stream radio --genre "classical" --country Germany
        franken-stream radio --language French
    """
    from franken_stream.music.radio_browser import RadioBrowserProvider

    provider = RadioBrowserProvider()

    try:
        stations = provider.search(
            name=query,
            genre=genre or "",
            country=country or "",
            language=language or "",
            limit=limit,
        )
    except Exception as exc:
        console.print(f"[red]✗[/red] Radio search failed: {exc}")
        raise typer.Exit(1)

    if not stations:
        console.print("[yellow]⚠[/yellow] No stations found.")
        raise typer.Exit(1)

    table = Table(title="Radio Stations")
    table.add_column("#", style="magenta", width=3)
    table.add_column("Name", style="cyan")
    table.add_column("Genre", style="green")
    table.add_column("Country", style="yellow")
    table.add_column("Bitrate", style="blue", width=8)

    for i, s in enumerate(stations, 1):
        table.add_row(
            str(i),
            s["title"][:40],
            s["genre"][:20],
            s["country"][:15],
            f"{s['bitrate']}k" if s["bitrate"] else "—",
        )
    console.print(table)

    try:
        choice = Prompt.ask(
            "\n[cyan]Select station[/cyan]",
            choices=[str(i) for i in range(1, len(stations) + 1)],
        )
        station = stations[int(choice) - 1]
        console.print(f"\n[cyan]Playing:[/cyan] {station['title']}")
        import subprocess
        subprocess.Popen(
            ["mpv", station["url"], "--no-video", f"--title={station['title']}",
             "--force-window=immediate"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    except (KeyboardInterrupt, ValueError, IndexError):
        console.print("\n[yellow]Cancelled.[/yellow]")


@app.command()
def podcast(
    query: str = typer.Argument(..., help="Podcast title or topic to search"),
    episode: Optional[int] = typer.Option(
        None, "--episode", "-e", help="Episode number to play directly"
    ),
) -> None:
    """
    Search podcasts and play episodes (no API key required).

    Examples:
        franken-stream podcast "Software Engineering Daily"
        franken-stream podcast "Python" --episode 3
    """
    from franken_stream.audio.podcasts import PodcastProvider

    provider = PodcastProvider()

    try:
        podcasts_found = provider.search(query)
    except Exception as exc:
        console.print(f"[red]✗[/red] Podcast search failed: {exc}")
        raise typer.Exit(1)

    if not podcasts_found:
        console.print("[yellow]⚠[/yellow] No podcasts found.")
        raise typer.Exit(1)

    table = Table(title="Podcasts")
    table.add_column("#", style="magenta", width=3)
    table.add_column("Title", style="cyan")
    table.add_column("Author", style="green")
    table.add_column("Episodes", style="yellow", width=9)

    for i, p in enumerate(podcasts_found, 1):
        table.add_row(str(i), p["title"][:50], p["artist"][:25], str(p["episode_count"]))
    console.print(table)

    try:
        choice = Prompt.ask(
            "\n[cyan]Select podcast[/cyan]",
            choices=[str(i) for i in range(1, len(podcasts_found) + 1)],
        )
        selected = podcasts_found[int(choice) - 1]
    except (KeyboardInterrupt, ValueError, IndexError):
        console.print("\n[yellow]Cancelled.[/yellow]")
        return

    if not selected.get("feed_url"):
        console.print("[red]✗[/red] No RSS feed URL for this podcast.")
        raise typer.Exit(1)

    console.print(f"\n[cyan]Fetching episodes for:[/cyan] {selected['title']}")
    episodes = provider.get_episodes(selected["feed_url"])

    if not episodes:
        console.print("[yellow]⚠[/yellow] No episodes found.")
        raise typer.Exit(1)

    ep_table = Table(title="Episodes")
    ep_table.add_column("#", style="magenta", width=3)
    ep_table.add_column("Title", style="cyan")
    ep_table.add_column("Published", style="green")
    ep_table.add_column("Duration", style="yellow")

    for i, ep in enumerate(episodes, 1):
        ep_table.add_row(
            str(i),
            ep["title"][:55],
            ep.get("published", "")[:16],
            ep.get("duration", "—"),
        )
    console.print(ep_table)

    ep_num = episode
    if ep_num is None:
        try:
            ep_choice = Prompt.ask(
                "\n[cyan]Select episode[/cyan]",
                choices=[str(i) for i in range(1, len(episodes) + 1)],
            )
            ep_num = int(ep_choice)
        except (KeyboardInterrupt, ValueError):
            console.print("\n[yellow]Cancelled.[/yellow]")
            return

    ep = episodes[ep_num - 1]
    if not ep.get("url"):
        console.print("[red]✗[/red] No audio URL for this episode.")
        raise typer.Exit(1)

    console.print(f"[cyan]Playing:[/cyan] {ep['title']}")
    import subprocess
    subprocess.Popen(
        ["mpv", ep["url"], "--no-video", f"--title={ep['title']}",
         "--force-window=immediate"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )


@app.command()
def audiobook(
    query: str = typer.Argument(..., help="Book title or author to search"),
    author: bool = typer.Option(
        False, "--author", "-a", help="Search by author name instead of title"
    ),
) -> None:
    """
    Search and stream free public-domain audiobooks from LibriVox.

    Examples:
        franken-stream audiobook "Sherlock Holmes"
        franken-stream audiobook "Dickens" --author
    """
    from franken_stream.audio.audiobooks import LibriVoxProvider

    provider = LibriVoxProvider()

    try:
        if author:
            books = provider.search_by_author(query)
        else:
            books = provider.search(query)
    except Exception as exc:
        console.print(f"[red]✗[/red] Audiobook search failed: {exc}")
        raise typer.Exit(1)

    if not books:
        console.print("[yellow]⚠[/yellow] No audiobooks found.")
        raise typer.Exit(1)

    table = Table(title="Audiobooks (LibriVox)")
    table.add_column("#", style="magenta", width=3)
    table.add_column("Title", style="cyan")
    table.add_column("Author", style="green")
    table.add_column("Language", style="yellow")
    table.add_column("Duration", style="blue")

    for i, b in enumerate(books, 1):
        table.add_row(
            str(i),
            b["title"][:45],
            b["author"][:25],
            b["language"][:10],
            b.get("total_time", "—")[:8],
        )
    console.print(table)

    try:
        choice = Prompt.ask(
            "\n[cyan]Select book[/cyan]",
            choices=[str(i) for i in range(1, len(books) + 1)],
        )
        book = books[int(choice) - 1]
    except (KeyboardInterrupt, ValueError, IndexError):
        console.print("\n[yellow]Cancelled.[/yellow]")
        return

    if not book.get("rss_url"):
        console.print(f"[green]Book URL:[/green] {book.get('url', '—')}")
        return

    console.print(f"\n[cyan]Fetching chapters for:[/cyan] {book['title']}")
    chapters = provider.get_chapters(book["rss_url"])

    if not chapters:
        # Fall back to streaming the RSS feed directly
        console.print("[cyan]→[/cyan] Streaming via RSS feed…")
        import subprocess
        subprocess.Popen(
            ["mpv", book["rss_url"], "--no-video",
             f"--title={book['title']}", "--force-window=immediate"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        return

    ch_table = Table(title="Chapters")
    ch_table.add_column("#", style="magenta", width=3)
    ch_table.add_column("Chapter", style="cyan")
    ch_table.add_column("Duration", style="yellow")

    for ch in chapters:
        ch_table.add_row(str(ch["chapter"]), ch["title"][:55], ch.get("duration", "—"))
    console.print(ch_table)

    try:
        ch_choice = Prompt.ask(
            "\n[cyan]Select chapter[/cyan]",
            choices=[str(ch["chapter"]) for ch in chapters],
        )
        chapter = next(ch for ch in chapters if ch["chapter"] == int(ch_choice))
    except (KeyboardInterrupt, ValueError, StopIteration):
        console.print("\n[yellow]Cancelled.[/yellow]")
        return

    if not chapter.get("url"):
        console.print("[red]✗[/red] No audio URL for this chapter.")
        raise typer.Exit(1)

    console.print(f"[cyan]Playing:[/cyan] {chapter['title']}")
    import subprocess
    subprocess.Popen(
        ["mpv", chapter["url"], "--no-video",
         f"--title={chapter['title']}", "--force-window=immediate"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )


@app.command()
def live(
    query: str = typer.Argument("", help="Channel name to search for"),
    category: Optional[str] = typer.Option(
        None, "--category", "-c",
        help="Category: news, sports, entertainment, movies, kids, music, documentary…"
    ),
    country: Optional[str] = typer.Option(None, "--country", help="Country filter"),
) -> None:
    """
    Browse and watch live TV channels (8,000+ free channels via IPTV-org).

    Examples:
        franken-stream live --category news
        franken-stream live "BBC" --country UK
        franken-stream live --category sports
    """
    from franken_stream.live_tv.m3u_scraper import LiveTVProvider

    provider = LiveTVProvider()

    console.print("[cyan]Loading channels…[/cyan]")
    try:
        if query:
            channels = provider.search(query)
        else:
            channels = provider.get_channels(category=category, country=country)
    except Exception as exc:
        console.print(f"[red]✗[/red] Live TV fetch failed: {exc}")
        raise typer.Exit(1)

    if not channels:
        console.print("[yellow]⚠[/yellow] No channels found.")
        if category:
            cats = ", ".join(provider.get_categories())
            console.print(f"[cyan]Available categories:[/cyan] {cats}")
        raise typer.Exit(1)

    table = Table(title=f"Live TV Channels ({len(channels)} results)")
    table.add_column("#", style="magenta", width=4)
    table.add_column("Name", style="cyan")
    table.add_column("Group", style="green")
    table.add_column("Country", style="yellow")

    for i, ch in enumerate(channels[:25], 1):
        table.add_row(str(i), ch["title"][:45], ch.get("group", "")[:20], ch.get("country", "")[:12])
    console.print(table)

    try:
        choice = Prompt.ask(
            "\n[cyan]Select channel[/cyan]",
            choices=[str(i) for i in range(1, min(len(channels), 25) + 1)],
        )
        ch = channels[int(choice) - 1]
    except (KeyboardInterrupt, ValueError, IndexError):
        console.print("\n[yellow]Cancelled.[/yellow]")
        return

    console.print(f"[cyan]Playing:[/cyan] {ch['title']}")
    import subprocess
    subprocess.Popen(
        ["mpv", ch["url"], "--force-window=immediate",
         f"--title={ch['title']}", "--cache=5000"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )


@app.command()
def scores(
    team: Optional[str] = typer.Argument(None, help="Team name to search fixtures for"),
    live_only: bool = typer.Option(False, "--live", "-l", help="Show only live matches"),
) -> None:
    """
    Show live sports scores (requires SPORTS_API_KEY env var for API-Sports).

    Examples:
        franken-stream scores --live
        franken-stream scores "Manchester United"
    """
    import os
    from franken_stream.sports.api_sports import SportsProvider

    api_key = os.environ.get("SPORTS_API_KEY")
    provider = SportsProvider(api_key=api_key)

    if not provider.available:
        console.print(
            "[yellow]⚠[/yellow] No SPORTS_API_KEY set. "
            "Set the environment variable to enable sports scores.\n"
            "Free tier: https://www.api-sports.io (100 req/day)"
        )
        raise typer.Exit(1)

    try:
        if live_only:
            matches = provider.get_live_matches()
        elif team:
            matches = provider.search_fixtures(team)
        else:
            matches = provider.get_fixtures_today()
    except Exception as exc:
        console.print(f"[red]✗[/red] Sports API error: {exc}")
        raise typer.Exit(1)

    if not matches:
        console.print("[yellow]⚠[/yellow] No matches found.")
        raise typer.Exit(0)

    table = Table(title="Matches")
    table.add_column("Home", style="cyan")
    table.add_column("Score", style="green", width=7)
    table.add_column("Away", style="cyan")
    table.add_column("League", style="yellow")
    table.add_column("Status", style="magenta")

    for m in matches:
        elapsed = f" {m['elapsed']}'" if m.get("elapsed") else ""
        table.add_row(
            m["home"][:22],
            m["score"],
            m["away"][:22],
            m["league"][:25],
            f"{m['status']}{elapsed}",
        )
    console.print(table)


@app.command(name="discord-rpc")
def discord_rpc(
    action: str = typer.Argument(
        "connect", help="connect | disconnect | status"
    ),
    client_id: Optional[str] = typer.Option(
        None, "--client-id", help="Discord application client ID"
    ),
) -> None:
    """
    Manage Discord Rich Presence integration.

    Requires pypresence: pip install pypresence

    Examples:
        franken-stream discord-rpc connect
        franken-stream discord-rpc disconnect
    """
    from franken_stream.social.discord_rpc import DiscordRichPresence

    rpc = DiscordRichPresence(client_id=client_id)

    if action == "connect":
        if rpc.connect():
            console.print("[green]✓[/green] Discord Rich Presence connected.")
            rpc.update_presence("Franken-Stream", media_type="movie")
        else:
            console.print("[red]✗[/red] Could not connect to Discord.")
            raise typer.Exit(1)

    elif action == "disconnect":
        rpc.connect()
        rpc.disconnect()
        console.print("[yellow]✓[/yellow] Discord Rich Presence disconnected.")

    elif action == "status":
        console.print("[cyan]pypresence[/cyan] required. Install: pip install pypresence")

    else:
        console.print(f"[red]✗[/red] Unknown action '{action}'. Use: connect, disconnect, status")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
