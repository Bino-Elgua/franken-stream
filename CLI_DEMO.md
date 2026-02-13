# Franken-Stream CLI Demo

## Installation

```bash
$ git clone https://github.com/YOUR_USERNAME/franken-stream.git
$ cd franken-stream
$ pip install -e .

Successfully installed franken-stream-0.1.0
```

## Available Commands

### Help

```bash
$ franken-stream --help

 Usage: franken-stream [OPTIONS] COMMAND [ARGS]...

 Terminal media streamer for movies and TV shows.

╭─ Options ────────────────────────────────────────────────────────────────────╮
│ --install-completion          Install completion for the current shell.      │
│ --show-completion             Show completion for the current shell, to copy │
│                               it or customize the installation.              │
│ --help                        Show this message and exit.                    │
╰──────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ───────────────────────────────────────────────────────────────────╮
│ watch   Search and stream a movie or TV show.                                │
│ update  Update streaming providers from GitHub.                              │
│ config  Show configuration information.                                      │
╰──────────────────────────────────────────────────────────────────────────────╯
```

### 1. Config Command

```bash
$ franken-stream config

                          Franken-Stream Configuration
┏━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Setting       ┃ Value                                                        ┃
┡━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ Config Dir    │ /home/user/.franken-stream                                   │
│ Config File   │ /home/user/.franken-stream/providers.json                    │
│ GitHub Source │ https://raw.githubusercontent.com/YOU/stream-providers/main  │
└───────────────┴──────────────────────────────────────────────────────────────┘

✓ Config file exists at /home/user/.franken-stream/providers.json
```

### 2. Update Command

```bash
$ franken-stream update

Updating providers from GitHub...
✓ Providers updated successfully

# Fetches: https://raw.githubusercontent.com/YOU/stream-providers/main/providers.json
```

### 3. Watch Command (Basic)

```bash
$ franken-stream watch "Inception"

Searching for: Inception

Searching: https://fmovies.to/search?keyword=Inception...
✓ Found 8 results
Searching: https://www.123movies.co/search/Inception...
✓ Found 5 results

Search Results
┏━━━┳━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ # ┃ Title                  ┃ URL                                        ┃
┡━━━╇━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ 1 │ Inception (2010)       │ https://fmovies.to/watch/inception-2010    │
│ 2 │ Inception Full Movie   │ https://123movies.co/watch/inception       │
│ 3 │ Inception Watch Online │ https://fmovies.to/watch/inception-hd      │
│ 4 │ Inception (Rewatch)    │ https://123movies.co/watch/inception-rewatch
│ 5 │ Inception Explained    │ https://videos.example.com/inception-exp   │
└━━━┴━━━━━━━━━━━━━━━━━━━━━━━━┴━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┘

Select result [1-5]: 1

Selected: Inception (2010)
URL: https://fmovies.to/watch/inception-2010

→ Opening in browser...
```

### 4. Watch with Proxy

```bash
$ franken-stream watch "Breaking Bad" --proxy http://proxy.company.com:8080

✓ Proxy configured: http://proxy.company.com:8080

Searching for: Breaking Bad

Searching: https://fmovies.to/search?keyword=Breaking+Bad...
✓ Found 12 results

Search Results
┏━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ # ┃ Title                           ┃ URL                         ┃
├───┼─────────────────────────────────┼─────────────────────────────┤
│ 1 │ Breaking Bad (Complete Series)  │ https://fmovies.to/breaking │
│ 2 │ Breaking Bad Season 1           │ https://fmovies.to/bb-s1    │
│ 3 │ Breaking Bad Finale             │ https://fmovies.to/bb-final │
└━━━┴─────────────────────────────────┴─────────────────────────────┘

Select result [1-3]: 1
```

### 5. Watch Non-Interactive

```bash
$ franken-stream watch "The Matrix" --no-interactive

Searching for: The Matrix

✓ Found 10 results

Search Results
┏━━━┳━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ # ┃ Title                ┃ URL                                    ┃
├───┼──────────────────────┼────────────────────────────────────────┤
│ 1 │ The Matrix (1999)    │ https://fmovies.to/matrix-1999        │
│ 2 │ The Matrix Reloaded  │ https://fmovies.to/matrix-reloaded    │
│ 3 │ The Matrix Resurrect │ https://fmovies.to/matrix-resurrections
└━━━┴──────────────────────┴────────────────────────────────────────┘

→ Use --interactive to select a result
```

### 6. Fallback to yt-dlp

```bash
$ franken-stream watch "Obscure Movie Title"

Searching for: Obscure Movie Title

⚠ Error searching https://fmovies.to/search?keyword=...
✗ No results found.
→ Falling back to yt-dlp... (requires yt-dlp and mpv)

Attempting to stream 'Obscure Movie Title' with yt-dlp...
✓ Found stream: https://manifest.googlevideo.com/api/manifest/hls_playlist...

[mpv output - now playing video]
```

## Help for Each Command

### Watch Help

```bash
$ franken-stream watch --help

 Usage: franken-stream watch [OPTIONS] QUERY

 Search and stream a movie or TV show.

 Example:
 franken-stream watch "Inception"
 franken-stream watch "Breaking Bad" --proxy http://proxy:8080

╭─ Arguments ──────────────────────────────────────────────────────────────────╮
│ *    query      TEXT  Movie or show title to search for [required]           │
╰──────────────────────────────────────────────────────────────────────────────╯
╭─ Options ────────────────────────────────────────────────────────────────────╮
│ --proxy        -p                      TEXT  HTTP proxy URL (optional)       │
│ --interactive      --no-interactive          Interactive result selection    │
│                                              [default: interactive]          │
│ --help                                       Show this message and exit.     │
╰──────────────────────────────────────────────────────────────────────────────╯
```

## Configuration Files

### Default Providers (~/.franken-stream/providers.json)

```json
{
  "movie_search_bases": [
    "https://fmovies.to/search?keyword=",
    "https://www.123movies.co/search/"
  ],
  "embed_fallbacks": [
    "mycloud",
    "upstream",
    "vidcloud",
    "streamwish"
  ]
}
```

### Custom Example

Edit `~/.franken-stream/providers.json`:

```json
{
  "movie_search_bases": [
    "https://mysite.com/search?q=",
    "https://site2.com/?s=",
    "https://other.com/find?query="
  ],
  "embed_fallbacks": [
    "custom-host",
    "mycloud",
    "upstream"
  ]
}
```

Then restart: `franken-stream watch "query"`

## Error Scenarios

### Network Error

```bash
$ franken-stream watch "Movie"

Searching for: Movie

⚠ Error searching https://fmovies.to/...: Connection timeout
⚠ Error searching https://123movies.co/...: Host not found
✗ No results found.
→ Falling back to yt-dlp...
```

### yt-dlp Not Installed

```bash
$ franken-stream watch "Movie"

✗ yt-dlp not found. Install with: pip install yt-dlp
```

### No Config File

```bash
$ franken-stream watch "Movie"

⚠ Could not fetch from GitHub: 404 Not Found
Using default providers...

Searching for: Movie
```

## Real-World Workflow

```bash
# 1. Install
pip install -e .

# 2. Check setup
franken-stream config

# 3. Update providers if needed
franken-stream update

# 4. Search for a movie
franken-stream watch "Dune Part Two"

# 5. Select from results and watch
# [Select 1]
# → Opens in browser or plays with mpv

# 6. Enjoy!
```

---

For more examples and detailed documentation, see [README.md](README.md)
