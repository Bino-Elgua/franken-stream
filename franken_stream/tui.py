"""Textual TUI dashboard for franken-stream."""

from typing import Optional
from pathlib import Path

from textual.app import ComposeResult, SystemCommand
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import (
    Button,
    Footer,
    Header,
    Input,
    Label,
    Static,
)
from textual.binding import Binding
from rich.panel import Panel
from rich.text import Text
from rich.table import Table

from franken_stream.providers import ProviderManager
from franken_stream.scraper import ContentScraper


class StatusBar(Static):
    """Bottom status bar showing current status."""

    DEFAULT_CSS = """
    StatusBar {
        dock: bottom;
        height: 1;
        background: $surface;
        color: $text;
        border-top: solid $primary;
    }
    """

    def __init__(self, message: str = "Ready"):
        super().__init__(message)
        self.message = message

    def update_status(self, message: str) -> None:
        """Update status message."""
        self.message = message
        self.update(message)


class Sidebar(Static):
    """Left sidebar with recent searches and navigation."""

    DEFAULT_CSS = """
    Sidebar {
        width: 25%;
        border-right: solid $primary;
        background: $panel;
        padding: 1;
    }
    """

    def __init__(self):
        super().__init__()
        self.searches = []

    def render(self) -> Panel:
        """Render sidebar content."""
        text = Text("Recent Searches\n", style="bold cyan")
        
        for i, search in enumerate(self.searches[-5:], 1):
            text.append(f"{i}. {search[:20]}\n", style="white")
        
        text.append("\n\n[bold]Keybindings[/bold]\n", style="bold green")
        text.append("/ - Search\n", style="dim white")
        text.append("b - Browse\n", style="dim white")
        text.append("h - History\n", style="dim white")
        text.append("u - Update\n", style="dim white")
        text.append("? - Help\n", style="dim white")
        text.append("q - Quit\n", style="dim white")
        
        return Panel(text, title="Menu", border_style="cyan")

    def add_search(self, query: str) -> None:
        """Add search to history."""
        if query not in self.searches:
            self.searches.append(query)


class DashboardContent(Static):
    """Main dashboard content area."""

    DEFAULT_CSS = """
    DashboardContent {
        width: 75%;
        height: 1fr;
        background: $background;
    }
    """

    def render(self) -> Panel:
        """Render dashboard grid."""
        text = Text()
        text.append("Franken-Stream", style="bold yellow")
        text.append("\n Terminal Media Streamer\n\n", style="dim")
        
        text.append("Categories:\n", style="bold cyan")
        text.append("  New Releases       |  Popular Movies\n", style="white")
        text.append("  TV Shows          |  My List\n", style="white")
        text.append("  Trending          |  Legal Only\n\n", style="white")
        
        text.append("Press [bold]/[/bold] to search or use arrow keys to browse", style="green")
        
        return Panel(text, title="Dashboard", border_style="green")


class SearchScreen(Screen):
    """Full-screen search interface."""

    BINDINGS = [
        Binding("escape", "cancel", "Back", show=True),
        Binding("enter", "search", "Search", show=True),
    ]

    DEFAULT_CSS = """
    SearchScreen {
        align: center middle;
    }
    
    #search_input {
        width: 60;
        margin: 1;
    }
    """

    def compose(self) -> ComposeResult:
        """Render search screen."""
        yield Vertical(
            Label("Search Movies & TV Shows", id="title"),
            Input(id="search_input", placeholder="Type query..."),
            id="search_container",
        )

    def on_mount(self) -> None:
        """Focus input on mount."""
        self.query_one("#search_input", Input).focus()

    def action_search(self) -> None:
        """Execute search."""
        query = self.query_one("#search_input", Input).value
        if query.strip():
            self.app.search_query = query
            self.app.pop_screen()

    def action_cancel(self) -> None:
        """Cancel and go back."""
        self.app.pop_screen()


class DashboardScreen(Screen):
    """Main dashboard screen."""

    BINDINGS = [
        Binding("/", "search", "Search", show=True),
        Binding("b", "browse", "Browse", show=True),
        Binding("h", "history", "History", show=True),
        Binding("u", "update", "Update", show=True),
        Binding("?", "help", "Help", show=True),
        Binding("q", "quit", "Quit", show=False),
    ]

    def compose(self) -> ComposeResult:
        """Render main screen."""
        yield Header()
        yield Horizontal(
            Sidebar(id="sidebar"),
            DashboardContent(id="dashboard"),
        )
        yield StatusBar(id="status_bar")
        yield Footer()

    def on_mount(self) -> None:
        """Initialize screen."""
        self.app.title = "Franken-Stream - Terminal Media Streamer"

    def action_search(self) -> None:
        """Open search screen."""
        self.app.push_screen(SearchScreen())
        status = self.query_one("#status_bar", StatusBar)
        status.update_status("Searching...")

    def action_browse(self) -> None:
        """Browse categories."""
        status = self.query_one("#status_bar", StatusBar)
        status.update_status("Browse not yet implemented")

    def action_history(self) -> None:
        """Show search history."""
        status = self.query_one("#status_bar", StatusBar)
        status.update_status("Showing history...")

    def action_update(self) -> None:
        """Update providers."""
        status = self.query_one("#status_bar", StatusBar)
        status.update_status("Updating providers...")
        
        pm = ProviderManager()
        if pm.update_providers():
            status.update_status("Providers updated ✓")
        else:
            status.update_status("Update failed")

    def action_help(self) -> None:
        """Show help."""
        status = self.query_one("#status_bar", StatusBar)
        status.update_status("Press ? again or see sidebar for keybindings")

    def action_quit(self) -> None:
        """Quit app."""
        self.app.exit()


class FrankenStreamApp:
    """Main TUI application."""

    def __init__(self):
        """Initialize app."""
        from textual.app import App as TextualApp

        class App(TextualApp):
            """Franken-Stream TUI App."""

            CSS = """
            Screen {
                background: $surface;
                color: $text;
            }
            
            Header {
                background: $primary;
                color: $text;
                dock: top;
                height: 1;
            }
            """

            BINDINGS = [
                ("ctrl+c", "quit", "Quit"),
            ]

            def __init__(self):
                super().__init__()
                self.search_query = None
                self.pm = ProviderManager()
                self.scraper = ContentScraper()

            def on_mount(self) -> None:
                """Mount main screen."""
                self.push_screen(DashboardScreen())

            def action_quit(self) -> None:
                """Exit application."""
                self.exit()

        self.app = App()

    def run(self) -> None:
        """Run the TUI application."""
        self.app.run()


def run_tui() -> None:
    """Entry point for TUI."""
    try:
        app = FrankenStreamApp()
        app.run()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"Error: {e}")
        raise
