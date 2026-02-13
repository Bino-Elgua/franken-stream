"""Textual TUI dashboard for franken-stream."""

from typing import Optional

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import (
    Header,
    Footer,
    Static,
    Input,
    Label,
)
from textual.containers import Container, Vertical, Horizontal
from textual.binding import Binding
from rich.panel import Panel
from rich.text import Text

from franken_stream.providers import ProviderManager
from franken_stream.scraper import ContentScraper


class StatusBar(Static):
    """Bottom status bar."""

    DEFAULT_CSS = """
    StatusBar {
        dock: bottom;
        height: 1;
        background: $surface;
        color: $text;
        border-top: solid $primary;
        content-align: left middle;
    }
    """

    def __init__(self, message: str = "Ready", **kwargs):
        super().__init__(message, **kwargs)

    def update_status(self, message: str) -> None:
        """Update status message."""
        self.update(message)


class SearchScreen(Screen):
    """Full-screen search interface."""

    BINDINGS = [
        Binding("escape", "cancel", "Back"),
        Binding("enter", "search", "Search"),
    ]

    DEFAULT_CSS = """
    Screen {
        align: center middle;
    }
    
    #search_container {
        width: 60;
        height: 10;
        border: solid $primary;
        background: $surface;
    }
    
    #search_input {
        width: 100%;
        margin: 1;
    }
    """

    def compose(self) -> ComposeResult:
        """Render search screen."""
        with Vertical(id="search_container"):
            yield Label("Search Movies & TV Shows")
            yield Input(
                id="search_input",
                placeholder="Type query and press Enter..."
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
        Binding("/", "search", "Search"),
        Binding("b", "browse", "Browse"),
        Binding("h", "history", "History"),
        Binding("u", "update", "Update"),
        Binding("?", "help", "Help"),
        Binding("q", "quit", "Quit"),
    ]

    DEFAULT_CSS = """
    DashboardScreen {
        background: $background;
    }
    
    #sidebar {
        width: 25;
        border-right: solid $primary;
        background: $panel;
        padding: 1;
    }
    
    #dashboard {
        width: 1fr;
        height: 1fr;
        background: $background;
    }
    
    #status_bar {
        dock: bottom;
        height: 1;
        background: $surface;
    }
    """

    def compose(self) -> ComposeResult:
        """Render main screen."""
        yield Header()
        with Horizontal():
            # Sidebar
            yield Static(
                self._render_sidebar(),
                id="sidebar"
            )
            # Main dashboard
            yield Static(
                self._render_dashboard(),
                id="dashboard"
            )
        yield StatusBar(id="status_bar")
        yield Footer()

    def on_mount(self) -> None:
        """Initialize screen."""
        self.app.title = "Franken-Stream"
        self.app.pm = ProviderManager()

    def _render_sidebar(self) -> Panel:
        """Render sidebar content."""
        text = Text("RECENT SEARCHES\n", style="bold cyan")
        text.append("─" * 20 + "\n", style="dim")
        
        searches = getattr(self.app, "searches", [])
        for i, search in enumerate(searches[-5:], 1):
            text.append(f"{i}. {search[:18]}\n", style="white")
        
        text.append("\n[bold cyan]KEYBINDINGS[/bold cyan]\n")
        text.append("─" * 20 + "\n", style="dim")
        text.append("/  Search\n", style="dim white")
        text.append("b  Browse\n", style="dim white")
        text.append("h  History\n", style="dim white")
        text.append("u  Update\n", style="dim white")
        text.append("?  Help\n", style="dim white")
        text.append("q  Quit\n", style="dim white")
        
        return Panel(text, expand=False, border_style="cyan")

    def _render_dashboard(self) -> Panel:
        """Render dashboard content."""
        text = Text()
        text.append("FRANKEN-STREAM\n", style="bold yellow")
        text.append("Terminal Media Streamer\n\n", style="dim")
        
        text.append("CATEGORIES:\n", style="bold cyan")
        text.append("  New Releases       Popular Movies\n", style="white")
        text.append("  TV Shows           My List\n", style="white")
        text.append("  Trending           Legal Only\n\n", style="white")
        
        text.append("Press ", style="green")
        text.append("/", style="bold green")
        text.append(" to search or ", style="green")
        text.append("?", style="bold green")
        text.append(" for help", style="green")
        
        return Panel(text, expand=True, border_style="green")

    def action_search(self) -> None:
        """Open search screen."""
        self.app.push_screen(SearchScreen())

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
        
        if hasattr(self.app, "pm") and self.app.pm:
            if self.app.pm.update_providers():
                status.update_status("Providers updated ✓")
            else:
                status.update_status("Update failed")

    def action_help(self) -> None:
        """Show help."""
        status = self.query_one("#status_bar", StatusBar)
        status.update_status("Press ? for keybindings (see sidebar)")

    def action_quit(self) -> None:
        """Quit app."""
        self.app.exit()


class FrankenStreamApp:
    """Main TUI application wrapper."""

    def __init__(self):
        """Initialize app."""
        from textual.app import App as TextualApp

        class App(TextualApp):
            """Franken-Stream TUI."""

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

            BINDINGS = [("ctrl+c", "quit", "Quit")]

            def __init__(self):
                super().__init__()
                self.search_query = None
                self.searches = []
                self.pm = None

            def on_mount(self) -> None:
                """Mount main screen."""
                self.push_screen(DashboardScreen())

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
        import traceback
        traceback.print_exc()
        raise
