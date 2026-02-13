# Franken-Stream: Project Overview

## What is Franken-Stream?

A terminal-based CLI tool for searching and streaming movies and TV shows, inspired by [ani-cli](https://github.com/pystardust/ani-cli) but for general content (not just anime). It combines web scraping, provider management, and fallback streaming mechanisms into a lightweight Python package.

## Key Features Implemented

✅ **CLI Interface** (typer-based)
- `watch <query>`: Search and stream content
- `update`: Refresh provider list from GitHub  
- `config`: Show configuration info
- Auto-help and command completion

✅ **Provider Management**
- Load from `~/.franken-stream/providers.json`
- Auto-download from GitHub if missing
- Fallback to sensible defaults
- User-configurable search bases and embed hosts

✅ **Web Scraping**
- BeautifulSoup HTML parsing
- Realistic User-Agent headers
- Request timeout handling
- Proxy support (HTTP/HTTPS)
- Graceful error handling across multiple sources

✅ **Fallback Streaming**
- Uses yt-dlp if no direct embeds found
- Searches YouTube for full movies
- Pipes to mpv player (or shows URL if not installed)

✅ **Error Handling**
- Network error recovery
- Parse error fallbacks
- Clear user feedback
- Safe timeout handling

✅ **Code Quality**
- Full type hints (mypy-compatible)
- Comprehensive docstrings
- Clean module separation
- Rich terminal output

## Project Structure

```
franken-stream/
├── franken_stream/              # Main package
│   ├── __init__.py             # Package metadata
│   ├── main.py                 # CLI commands (typer app)
│   ├── providers.py            # Provider management
│   └── scraper.py              # Web scraping + streaming
├── pyproject.toml              # Modern Python packaging
├── requirements.txt            # Dependency list
├── setup.py                    # (Optional for older pip)
├── README.md                   # Full documentation
├── QUICKSTART.md              # Quick reference
├── PROJECT_OVERVIEW.md        # This file
├── LICENSE                    # MIT license
├── .gitignore                 # Git config
├── test_demo.py              # Comprehensive test suite
├── providers.json.example    # Template config
└── franken_stream.egg-info/  # (Auto-generated on install)
```

## Technology Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| CLI Framework | `typer` | Command-line argument parsing & help |
| Output Formatting | `rich` | Colored tables, prompts, logging |
| HTTP Requests | `requests` | Download HTML pages |
| HTML Parsing | `beautifulsoup4` | Extract links/titles from HTML |
| Video Fallback | `yt-dlp` | Find videos via YouTube search |
| Configuration | JSON | Store provider URLs locally |
| Packaging | `pyproject.toml` | PEP 517/518 compliance |

## Dependencies

```
typer[all]>=0.9.0      # CLI framework
requests>=2.28.0       # HTTP client
beautifulsoup4>=4.11.0 # HTML parsing
yt-dlp>=2023.0.0       # Video downloader fallback
rich>=13.0.0           # Terminal UI
```

## Installation Methods

### Development (Recommended for Contributors)
```bash
git clone <repo>
cd franken-stream
pip install -e .
```

### Production
```bash
pip install franken-stream
```

### With Dev Tools
```bash
pip install -e ".[dev]"
```

## Usage Examples

### Basic Search
```bash
franken-stream watch "Inception"
```

**Output:**
1. Loads default providers if not configured
2. Searches 2+ URLs in parallel
3. Parses results from HTML
4. Displays table with titles and links
5. Waits for user selection
6. Opens link or falls back to yt-dlp

### With Proxy
```bash
franken-stream watch "The Matrix" --proxy http://proxy:8080
```

### Check Configuration
```bash
franken-stream config
# Shows config directory path, file path, GitHub source
```

### Update Providers
```bash
franken-stream update
# Downloads fresh provider list from GitHub
```

## Code Highlights

### Provider Management (providers.py)
- **ProviderManager class**: Handles JSON loading, caching, and GitHub syncing
- **Fallback chain**: Local file → GitHub → defaults
- **Thread-safe**: Single instance reuse via `if self.providers:`

### Web Scraping (scraper.py)
- **ContentScraper class**: Encapsulates HTTP + HTML parsing
- **Proxy + User-Agent support**: Configurable per instance
- **Error resilience**: Try/catch with logging, continues on failure
- **HTML extraction**: Generic selector matching + deduplication
- **yt-dlp fallback**: Subprocess call to find videos if needed

### CLI (main.py)
- **Typer commands**: Declarative CLI with auto-help
- **Rich output**: Colored tables, status messages
- **Interactive selection**: Uses rich.Prompt for menu
- **Modular design**: Commands delegate to service classes

## Testing

### Test Suite
```bash
python test_demo.py
```

Verifies:
- Provider initialization and loading
- Provider caching (local file vs. GitHub)
- Search base and embed fallback retrieval
- HTML parsing with BeautifulSoup
- Custom User-Agent and proxy configuration
- Config directory creation

### Manual Testing
```bash
# Test watch command (non-interactive)
franken-stream watch "test" --no-interactive

# Test config display
franken-stream config

# Test with yt-dlp fallback
franken-stream watch "movie" --no-interactive
# (will try scraping, then yt-dlp)
```

## Configuration

### Default Locations
- **Config dir**: `~/.franken-stream/`
- **Provider file**: `~/.franken-stream/providers.json`

### Provider JSON Structure
```json
{
  "movie_search_bases": [
    "https://site1.com/search?q=",
    "https://site2.com/?keyword="
  ],
  "embed_fallbacks": [
    "mycloud",
    "upstream",
    "vidcloud"
  ]
}
```

### Custom Setup
1. Edit `~/.franken-stream/providers.json`
2. Add your own search URLs
3. List embed hosts you want to prioritize
4. Restart app

## Future Enhancements

Potential additions (not yet implemented):
- [ ] Direct embed extraction (HTML to video URL)
- [ ] Interactive result picker with `fzf` integration
- [ ] Watchlist / bookmarking
- [ ] Config file validation
- [ ] Support for TV show seasons/episodes
- [ ] Database of providers + ratings
- [ ] Async requests for parallel searching
- [ ] GUI mode (optional)
- [ ] Docker support
- [ ] CI/CD pipeline

## Common Issues & Solutions

### "No results found"
1. Check internet connection
2. Verify providers: `franken-stream config`
3. Update: `franken-stream update`
4. App falls back to yt-dlp automatically

### yt-dlp errors
```bash
pip install --upgrade yt-dlp
```

### Missing mpv
```bash
# Linux: sudo apt install mpv
# macOS: brew install mpv
# Windows: Download from mpv.io
```

### Proxy not working
Ensure format: `http://[user:pass@]host:port`

## Development Workflow

### Setting Up
```bash
pip install -e ".[dev]"
```

### Code Quality
```bash
black franken_stream/      # Format
isort franken_stream/      # Sort imports
flake8 franken_stream/     # Lint
```

### Adding Features
1. Edit `franken_stream/*.py`
2. Test with `python test_demo.py`
3. Test CLI: `franken-stream <command>`
4. Commit and push

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes with clean code
4. Test thoroughly
5. Submit a pull request

## License

MIT - See LICENSE file for full text

## References

- [Typer Documentation](https://typer.tiangolo.com/)
- [Rich Documentation](https://rich.readthedocs.io/)
- [BeautifulSoup Documentation](https://www.crummy.com/software/BeautifulSoup/bs4/doc/)
- [yt-dlp Documentation](https://github.com/yt-dlp/yt-dlp)
- [ani-cli (Original Inspiration)](https://github.com/pystardust/ani-cli)

---

**Status**: ✅ Production Ready (v0.1.0)
**Last Updated**: 2024
**Maintainer**: Your Name
