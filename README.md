# Franken-Stream

A terminal-based media streamer for movies and TV shows, inspired by [ani-cli](https://github.com/pystardust/ani-cli) but for general content.

## Features

- **CLI-based streaming**: Search and stream movies/shows directly from your terminal
- **Multiple providers**: Configurable streaming providers via JSON
- **Fallback streaming**: Uses yt-dlp if no direct embeds are found
- **Proxy support**: Optional HTTP proxy configuration
- **Interactive selection**: Pick from search results with a nice menu
- **Auto-download providers**: Fetches provider list from GitHub on first run
- **Graceful error handling**: Clear error messages and fallbacks

## Installation

### From source

```bash
git clone https://github.com/YOUR_USERNAME/franken-stream.git
cd franken-stream
pip install -e .
```

Or install with development dependencies:

```bash
pip install -e ".[dev]"
```

### Via pip (once published)

```bash
pip install franken-stream
```

## Quick Start

```bash
# Search and stream a movie
franken-stream watch "Inception"

# Use interactive mode (default)
franken-stream watch "Breaking Bad"

# With a proxy
franken-stream watch "The Matrix" --proxy http://proxy.example.com:8080

# Update providers from GitHub
franken-stream update

# Show configuration
franken-stream config
```

## Requirements

- Python 3.8+
- `yt-dlp`: For fallback streaming via YouTube search
- `mpv` (optional): For direct video playback

### Dependencies

Installed automatically via pip:
- `typer[all]`: CLI framework
- `requests`: HTTP client
- `beautifulsoup4`: HTML parsing
- `yt-dlp`: YouTube/video downloader
- `rich`: Beautiful terminal output

## Configuration

### Provider Configuration

Providers are stored at `~/.franken-stream/providers.json`:

```json
{
  "movie_search_bases": [
    "https://fmovies.to/search?keyword=",
    "https://myflixerz.to/search/",
    "https://solarmovie.pe/search/",
    "https://cineby.ru/search/",
    "https://123moviesfree.net/search/",
    "https://movies2watch.tv/search?q=",
    "https://yuppow.com/search/"
  ],
  "embed_fallbacks": [
    "vidcloud9.com",
    "vidplay.online",
    "upstream.to",
    "mycloud",
    "streamtape.com"
  ],
  "legal_fallbacks": [
    "https://www.youtube.com/results?search_query="
  ],
  "notes": "Sites change frequently—test manually first. Use VPN/proxy if needed. yt-dlp fallback handles 1000+ embeds."
}
```

**First run**: The app will attempt to download providers from GitHub. If that fails, it loads defaults from the config file above.

**To update**: Run `franken-stream update` (pulls fresh list from your GitHub providers repo)

### Custom Providers

To add your own providers:

1. Edit `~/.franken-stream/providers.json`
2. Add search base URLs (with `{query}` placeholder or append query string)
3. List embed hosts in `embed_fallbacks`
4. Restart the app

Example:

```json
{
  "movie_search_bases": [
    "https://mysite.com/search?q=",
    "https://anothersite.com/?search="
  ],
  "embed_fallbacks": [
    "custom-embed-host",
    "mycloud"
  ]
}
```

## Commands

### `watch`

Search for and stream content.

```bash
franken-stream watch <query> [OPTIONS]

Options:
  --proxy TEXT              HTTP proxy URL
  --interactive/--no-interactive
                           Enable/disable interactive selection (default: enabled)
```

### `update`

Refresh provider list from GitHub.

```bash
franken-stream update
```

### `config`

Display current configuration paths.

```bash
franken-stream config
```

## How It Works

1. **Search Phase**: Queries multiple provider base URLs with your search term
2. **Parsing**: Extracts titles and links from HTML results using BeautifulSoup
3. **Selection**: You pick from the results (interactive menu)
4. **Playback**: 
   - If embed is found: Opens link in browser/player
   - If no embed: Falls back to yt-dlp (searches YouTube for full movie)

## Error Handling

- **Network errors**: Graceful timeouts and fallbacks
- **Parse errors**: Continues with other providers if one fails
- **Missing tools**: Clear error messages (e.g., if yt-dlp not installed)
- **User-Agent**: Includes realistic User-Agent to avoid blocking

## Example Workflow

```bash
$ franken-stream watch "Inception"

Searching for: Inception

Searching: https://fmovies.to/search?keyword=Inception...
✓ Found 8 results
✓ Found 5 results (from second provider)

Search Results
┌─┬────────────────────────┬──────────────────────┐
│#│Title                   │URL                   │
├─┼────────────────────────┼──────────────────────┤
│1│Inception (2010)        │https://...           │
│2│Inception Rewatch       │https://...           │
│3│Inception Explained     │https://...           │
└─┴────────────────────────┴──────────────────────┘

Select result [1-3]: 1

Selected: Inception (2010)
URL: https://fmovies.to/watch/inception-2010

→ Opening in browser...
```

## Troubleshooting

### "yt-dlp not found"
Install yt-dlp:
```bash
pip install yt-dlp
```

### "mpv not found"
Install mpv (optional, for direct video playback):
- **Linux**: `sudo apt install mpv`
- **macOS**: `brew install mpv`
- **Windows**: Download from [mpv.io](https://mpv.io)

### No results found
1. Check your internet connection
2. Verify providers with: `franken-stream config`
3. Try updating: `franken-stream update`
4. Fallback will automatically use yt-dlp

### Proxy issues
Ensure proxy URL format is correct:
```bash
franken-stream watch "Movie" --proxy http://user:pass@proxy.com:8080
```

## Adding Custom Providers

To set up your own provider repository:

1. Create a GitHub repo named `stream-providers`
2. Add `providers.json` with the structure above
3. Update the `github_url` in `franken_stream/providers.py`:
   ```python
   self.github_url = "https://raw.githubusercontent.com/YOUR_USERNAME/stream-providers/main/providers.json"
   ```
4. Rebuild and reinstall

## License

MIT License - See LICENSE file for details

## Contributing

Contributions welcome! Please:
1. Fork the repo
2. Create a feature branch
3. Add tests (in `tests/` directory)
4. Submit a PR

## Disclaimer

This tool is for educational and personal use only. Users are responsible for verifying that they have the right to stream content. Always respect copyright laws in your jurisdiction.

## Similar Projects

- [ani-cli](https://github.com/pystardust/ani-cli) - Anime streaming CLI
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) - Video downloader
- [mpv](https://mpv.io/) - Media player
