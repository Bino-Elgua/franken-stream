# Franken-Stream: Future Enhancements

This document outlines potential improvements and features for future versions.

## Priority 1: Parser Robustness

**Problem**: Streaming sites change HTML frequently, breaking selectors.

**Solution**: Improve `scraper.py` with fallback patterns:

```python
# Add regex patterns for common embed structures
EMBED_PATTERNS = [
    r'iframe.*?src=["\']([^"\']+)["\']',  # iframes
    r'<a.*?href=["\']([^"\']*(?:embed|player)[^"\']*)["\']',  # embed links
    r'src=["\']([^"\']*\.m3u8[^"\']*)["\']',  # HLS streams
    r'src=["\']([^"\']*\.mp4[^"\']*)["\']',  # Direct MP4
]
```

**Implementation**: 
- Add fallback regex extraction to `_extract_results()`
- Test against common site structures
- Document patterns in docstring
- Keep lightweight (no Playwright dependency initially)

## Priority 2: Better Fallback Chain

**Current flow**: HTML → yt-dlp

**Enhanced flow**:
1. HTML scraping from configured bases
2. Search individual embeds if link found
3. DuckDuckGo search for "{query} watch free online"
4. yt-dlp YouTube search (as last resort)
5. Prompt user with "No results found" options

**Implementation**:
```python
def search_with_fallbacks(query: str) -> List[Tuple[str, str]]:
    """
    Search with progressive fallback chain.
    
    1. Try configured providers
    2. Try DuckDuckGo for free streaming links
    3. Fall back to yt-dlp
    """
    # Results stored with source metadata
    results_with_source = []
    
    # Existing: configured providers
    # New: add DDG search
    # New: add yt-dlp fallback
    
    return results_with_source
```

## Priority 3: TV Series Support

**Goal**: Handle TV shows with season/episode selection.

**Command**:
```bash
franken-stream tv "Breaking Bad"              # List seasons
franken-stream tv "Breaking Bad" --season 5   # List episodes
franken-stream tv "Breaking Bad" -s 5 -e 14   # Play specific episode
```

**Implementation**:
1. Add `tv()` command alongside `watch()`
2. Parse series pages for season/episode structure
3. Create season/episode selection menu
4. Generate search query: `"{show} s{season}e{episode}"`
5. Pass to scraper

**Files to modify**:
- `main.py` - Add `tv()` command
- `scraper.py` - Add series parsing helpers
- `providers.py` - Add "series_search_bases" to config

## Priority 4: Provider Health Check

**Goal**: Identify dead/slow providers, suggest updates.

**Command**:
```bash
franken-stream test-providers      # Test all URLs
franken-stream test-providers --fast # Quick test (2s timeout)
```

**Implementation**:
```python
def test_providers(timeout=10, fast=False):
    """
    Ping each provider URL, mark response times.
    
    Returns:
    - Healthy: ✓ (< 5s)
    - Slow: ⚠ (5-10s)  
    - Dead: ✗ (timeout/5xx)
    
    Output: Rich table with status, suggest removals
    """
```

**Output example**:
```
Provider Health Check
┌─────────────────────────────────┬────────┬──────────┐
│ URL                             │ Status │ Time     │
├─────────────────────────────────┼────────┼──────────┤
│ https://fmovies.to/search?...   │ ✓      │ 1.2s     │
│ https://solarmovie.pe/search/   │ ⚠      │ 8.5s     │
│ https://deadsite.com/search/    │ ✗      │ Timeout  │
└─────────────────────────────────┴────────┴──────────┘

Recommendations:
→ Remove: https://deadsite.com/search/ (offline)
→ Deprioritize: https://solarmovie.pe/search/ (slow)
```

## Priority 5: Legal Streaming Mode

**Goal**: Filter to legal sources only.

**Command**:
```bash
franken-stream watch "Movie" --legal-only
```

**Legal sources to integrate**:
- Tubi (free, licensed)
- Pluto TV (free, live TV)
- Crackle (free, ads)
- Freevee (Amazon's free tier)
- YouTube official uploads
- Kanopy (library/university)
- Plex free tier

**Implementation**:
```python
# In providers.json
"legal_sources": {
  "tubi": "https://tubitv.com/search?q=",
  "pluto": "https://www.pluto.tv/search",
  "youtube": "https://www.youtube.com/results?search_query=",
  "crackle": "https://www.crackle.com/search"
}

# In CLI
@app.command()
def watch(query: str, legal_only: bool = False):
    if legal_only:
        # Only use legal_sources
        bases = pm.get_legal_sources()
    else:
        # Use all configured sources
        bases = pm.get_search_bases()
```

## Priority 6: Download Support

**Goal**: Stream or download videos.

**Command**:
```bash
franken-stream watch "Movie"               # Stream
franken-stream watch "Movie" --download    # Download to ~/Downloads
franken-stream watch "Movie" -d -o path/   # Custom path
```

**Implementation**:
```python
def stream_or_download(url: str, download=False, output_path=None):
    """
    Stream via mpv or download via yt-dlp.
    """
    if download:
        # Use yt-dlp to download
        path = output_path or Path.home() / "Downloads"
        subprocess.run([
            "yt-dlp",
            "-o", str(path / "%(title)s.%(ext)s"),
            url
        ])
    else:
        # Stream with mpv
        subprocess.run(["mpv", url])
```

## Priority 7: Caching & Offline Mode

**Goal**: Cache search results, work offline.

**Implementation**:
```python
# Cache searches for 24 hours
CACHE_DIR = Path.home() / ".franken-stream" / "cache"
CACHE_TTL = 86400  # seconds

def get_cached_results(query: str) -> Optional[List]:
    """Return cached results if fresh."""
    cache_file = CACHE_DIR / f"{query.lower().replace(' ', '_')}.json"
    if cache_file.exists():
        age = time.time() - cache_file.stat().st_mtime
        if age < CACHE_TTL:
            return json.loads(cache_file.read_text())
    return None

def cache_results(query: str, results: List):
    """Save results to cache."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = CACHE_DIR / f"{query.lower().replace(' ', '_')}.json"
    cache_file.write_text(json.dumps(results))
```

## Priority 8: Async Requests

**Goal**: Search multiple providers in parallel.

**Implementation**:
```python
import asyncio
import aiohttp

async def search_async(query: str, base_urls: List[str]) -> List:
    """Search all providers concurrently."""
    async with aiohttp.ClientSession() as session:
        tasks = [
            scrape_url(session, url, query)
            for url in base_urls
        ]
        results = await asyncio.gather(*tasks)
    return results
```

**Benefit**: 7 providers in ~3s instead of ~30s (if they're slow)

## Priority 9: Interactive fzf Integration

**Goal**: Better interactive selection.

**Current**: Rich table + prompt

**Enhanced**: fzf with preview

```bash
franken-stream watch "Movie" --picker fzf
# Opens fzf with:
# - Preview of URL
# - Hotkey: Ctrl+P to copy URL
# - Faster for many results
```

**Implementation**:
```python
import subprocess

def select_with_fzf(results: List[Tuple[str, str]]) -> Tuple[str, str]:
    """Use fzf for selection if available."""
    items = "\n".join([f"{title} → {url}" for title, url in results])
    try:
        result = subprocess.run(
            ["fzf", "--preview", "echo {2}"],
            input=items,
            capture_output=True,
            text=True
        )
        # Parse and return selection
    except FileNotFoundError:
        # Fallback to rich.Prompt
        return select_with_prompt(results)
```

## Priority 10: Config Validation

**Goal**: Validate providers.json on startup.

```python
def validate_providers(config: Dict) -> bool:
    """Check config structure and warn about issues."""
    required = ["movie_search_bases", "embed_fallbacks"]
    
    for key in required:
        if key not in config:
            console.print(f"[red]✗ Missing: {key}")
            return False
    
    if not isinstance(config["movie_search_bases"], list):
        console.print("[red]✗ movie_search_bases must be a list")
        return False
    
    # Warn if URLs look suspicious
    for url in config["movie_search_bases"]:
        if not url.startswith(("http://", "https://")):
            console.print(f"[yellow]⚠ Invalid URL: {url}")
    
    return True
```

## Implementation Roadmap

### v0.2.0 (Next)
- [ ] Improved HTML parsing robustness
- [ ] Better fallback chain (DuckDuckGo, etc.)
- [ ] Provider health check command

### v0.3.0 (TV Support)
- [ ] TV series command
- [ ] Season/episode selection
- [ ] Series parsing

### v0.4.0 (Enhancements)
- [ ] Async requests for speed
- [ ] fzf integration
- [ ] Download support

### v0.5.0 (Polish)
- [ ] Legal-only mode
- [ ] Caching/offline support
- [ ] Config validation

## Testing Checklist

When implementing features, test:

- [ ] Works on Termux/Android
- [ ] Works with proxy
- [ ] Handles network timeouts
- [ ] Falls back gracefully
- [ ] No crashes on bad URLs
- [ ] Help text is clear
- [ ] Works with different shells (bash, zsh, sh)
- [ ] Config file changes apply immediately

## Contributing

To implement any enhancement:

1. Fork the repo
2. Create feature branch: `git checkout -b feature/name`
3. Test thoroughly
4. Submit PR with description
5. Include docstrings and tests

---

**Current Version**: 0.1.0
**Next Planned**: 0.2.0 (Robustness improvements)
