# Franken-Stream: Complete Setup Guide

Complete guide to install and use franken-stream v0.2.0+.

## 🚀 Quick Start (5 minutes)

### 1. Install
```bash
# Clone the repository
git clone https://github.com/Bino-Elgua/franken-stream.git
cd franken-stream

# Install in development mode
pip install -e .

# Or install normally
pip install .
```

### 2. Verify Installation
```bash
# Check that CLI works
franken-stream --help

# Show configuration
franken-stream config

# Validate config file
franken-stream validate
```

### 3. First Search
```bash
# Search for a movie
franken-stream watch "Inception"

# Or try a TV show
franken-stream tv "Breaking Bad"
```

## 📦 Installation Methods

### Method 1: Development Mode (Recommended for Testing)
```bash
git clone https://github.com/Bino-Elgua/franken-stream.git
cd franken-stream
pip install -e .
```

**Pros**: 
- Changes to code apply immediately
- Easy to test new features
- Can edit code and test instantly

**Cons**:
- Slower to import
- Takes more disk space

### Method 2: Production Mode
```bash
git clone https://github.com/Bino-Elgua/franken-stream.git
cd franken-stream
pip install .
```

**Pros**:
- Optimized installation
- Faster imports
- Production-ready

**Cons**:
- Need to reinstall after code changes

### Method 3: PyPI (Future)
```bash
pip install franken-stream
```

Currently not published to PyPI, but planned for v1.0.

## 🔧 Dependencies

### Required
All dependencies are installed automatically:
- **typer[all]** - CLI framework
- **requests** - HTTP client
- **beautifulsoup4** - HTML parsing
- **yt-dlp** - Video downloader
- **rich** - Terminal formatting

### Optional
Install separately if desired:

**mpv** (for direct playback):
```bash
# Linux (Ubuntu/Debian)
sudo apt install mpv

# macOS
brew install mpv

# Linux (Fedora)
sudo dnf install mpv

# Arch
sudo pacman -S mpv

# Windows
# Download from https://mpv.io or:
choco install mpv  # With Chocolatey
```

**pytest** (for development/testing):
```bash
pip install pytest
```

## 🎬 Basic Usage

### Watch Movies
```bash
# Interactive (with menu)
franken-stream watch "Inception"

# Non-interactive (for scripting)
franken-stream watch "Inception" --no-interactive

# With proxy (if network restricted)
franken-stream watch "Inception" --proxy http://proxy.company.com:8080

# Download instead of stream
franken-stream watch "Inception" --download

# To custom location
franken-stream watch "Inception" --download -o ~/videos

# Legal sources only
franken-stream watch "Inception" --legal-only
```

### Stream TV Shows
```bash
# Find show
franken-stream tv "Breaking Bad"

# Specific season
franken-stream tv "Breaking Bad" -s 5

# Specific episode
franken-stream tv "Breaking Bad" -s 5 -e 14

# With proxy
franken-stream tv "Breaking Bad" --proxy http://proxy:8080
```

### Provider Management
```bash
# Check provider health
franken-stream test-providers

# Quick health check
franken-stream test-providers --fast

# Update from GitHub
franken-stream update

# Validate config
franken-stream validate

# Show configuration
franken-stream config
```

## ⚙️ Configuration

### Location
Config file: `~/.franken-stream/providers.json`

### Default Content
```json
{
  "movie_search_bases": [
    "https://fmovies.to/search?keyword=",
    "https://myflixerz.to/search/",
    ...
  ],
  "embed_fallbacks": [
    "vidcloud9.com",
    "vidplay.online",
    ...
  ],
  "legal_fallbacks": [
    "https://www.youtube.com/results?search_query=",
    ...
  ]
}
```

### Customize

**Option 1: Edit Local File**
```bash
nano ~/.franken-stream/providers.json
# Edit and save
# Changes apply immediately next run
```

**Option 2: Use Your Own GitHub Repo**
```bash
# 1. Create repo: github.com/YOUR_USERNAME/stream-providers
# 2. Add providers.json to it
# 3. Edit franken_stream/providers.py:
#    self.github_url = "https://raw.githubusercontent.com/YOUR_USERNAME/stream-providers/main/providers.json"
# 4. Reinstall:
pip install -e .
# 5. Update:
franken-stream update
```

## 🔍 Searching

### How Search Works

1. **Local providers** - Queries configured base URLs
   - Searches 7 movie sites
   - Parses HTML with BeautifulSoup
   - Extracts titles and links

2. **Fallback chain** - If no results:
   - Regex embed extraction (iframes, video tags)
   - DuckDuckGo search for streaming links
   - yt-dlp YouTube search

### Examples

**Search and Stream**
```bash
$ franken-stream watch "Dune"

Searching for: Dune

Searching: https://fmovies.to/search?keyword=Dune...
✓ Found 8 results
✓ Found 5 results

Search Results
┏━━━┳──────────────┳───────────────────────┓
┃ # ┃ Title        ┃ URL                   ┃
├───┼──────────────┼───────────────────────┤
│ 1 │ Dune (2021)  │ https://fmovies.to/… │
│ 2 │ Dune Part 2  │ https://myflixerz...  │
└━━━┴──────────────┴───────────────────────┘

Select result [1-2]: 1

Selected: Dune (2021)
URL: https://fmovies.to/watch/dune-2021

→ Opening with mpv...
[video plays]
```

**Download**
```bash
$ franken-stream watch "Movie" --download -o ~/videos

...search results...

Downloading to /home/user/videos/...
[########################################] 100%

✓ Download complete
```

**TV Episode**
```bash
$ franken-stream tv "Breaking Bad" -s 5 -e 14

Searching: Breaking Bad s05e14

✓ Found 6 results

...select and stream...
```

## 🛟 Troubleshooting

### "No results found"

**Step 1: Check provider health**
```bash
franken-stream test-providers
```

Look for dead or slow providers. If many are dead, providers.json is outdated.

**Step 2: Update providers**
```bash
franken-stream update
```

Downloads fresh list from GitHub.

**Step 3: Check internet**
```bash
ping google.com
```

If offline, fallback to yt-dlp still works for YouTube uploads.

**Step 4: Try fallback explicitly**
```bash
franken-stream watch "query" --no-interactive
```

Will print yt-dlp fallback results if providers fail.

### "yt-dlp not found"

```bash
pip install --upgrade yt-dlp
```

### "mpv not found"

Videos will play via any available player. If mpv isn't installed:
- Copy/paste the URL into your browser
- Or install mpv (see Installation section above)

### "Network blocked"

Use a proxy:
```bash
franken-stream watch "movie" --proxy http://proxy.company.com:8080
```

Or configure system-wide:
```bash
export HTTP_PROXY=http://proxy:8080
export HTTPS_PROXY=http://proxy:8080
franken-stream watch "movie"
```

### "Config validation fails"

Check the config:
```bash
cat ~/.franken-stream/providers.json | python -m json.tool
```

If JSON is invalid, fix it:
```bash
nano ~/.franken-stream/providers.json
```

Or reset to defaults:
```bash
rm ~/.franken-stream/providers.json
franken-stream update  # Downloads defaults
```

### "Some sites are blocked in my region"

**Use a VPN or proxy:**
```bash
franken-stream watch "movie" --proxy http://vpn-proxy:8080
```

**Switch to legal sources:**
```bash
franken-stream watch "movie" --legal-only
```

### "Sites keep changing/blocking"

This is normal. Sites change frequently. Solutions:

1. **Report it**
   - Open issue on GitHub
   - Include which site is broken
   - Suggest alternative if you know one

2. **Contribute fix**
   - Fork stream-providers repo
   - Update providers.json
   - Submit PR

3. **Use fallback**
   - yt-dlp handles 1000+ hosts
   - Automatically tries YouTube uploads

## 📱 Platform-Specific

### Linux (Ubuntu/Debian)
```bash
# Install system deps
sudo apt update
sudo apt install python3-pip mpv

# Install franken-stream
pip3 install -e .
```

### macOS
```bash
# Install with Homebrew
brew install python mpv

# Install franken-stream
pip install -e .
```

### Windows
```bash
# Use PowerShell or Command Prompt
pip install -e .

# Install mpv (optional)
choco install mpv  # If using Chocolatey
# Or download from https://mpv.io
```

### Android (Termux)
```bash
# Install Termux from F-Droid or Play Store

# In Termux:
pkg install python python-pip

# Install franken-stream
pip install -e .

# Install mpv (optional)
pkg install mpv
```

## 🧪 Testing

### Run Test Suite
```bash
python test_demo.py          # Basic tests
python test_enhanced.py      # Comprehensive v0.2.0+ tests
```

### Manual Testing
```bash
# Test watch command
franken-stream watch "test" --no-interactive

# Test TV command
franken-stream tv "test" -s 1 -e 1

# Test providers
franken-stream test-providers --fast

# Test validation
franken-stream validate

# Test config
franken-stream config
```

## 🔐 Privacy & Security

### User-Agent
Franken-stream uses a realistic User-Agent to avoid basic bot detection:
```
Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36...
```

### Proxy
Configure a proxy to hide your IP:
```bash
franken-stream watch "query" --proxy http://proxy:8080
```

### VPN
Use a VPN for additional privacy:
```bash
# On Linux/macOS
sudo openvpn config.ovpn
franken-stream watch "query"

# Or route through proxy
export HTTP_PROXY=http://vpn-proxy:8080
franken-stream watch "query"
```

## 📚 Advanced Usage

### Batch Searching (Scripting)
```bash
#!/bin/bash
for movie in "Inception" "Matrix" "Interstellar"; do
  echo "Searching: $movie"
  franken-stream watch "$movie" --no-interactive --legal-only
done
```

### Custom Configuration
```bash
# Copy providers.json to custom location
cp ~/.franken-stream/providers.json ~/myconfig.json

# Edit it
nano ~/myconfig.json

# Use it
cp ~/myconfig.json ~/.franken-stream/providers.json
franken-stream update
```

### Provider Monitoring
```bash
# Check provider health regularly
0 6 * * * franken-stream test-providers >> ~/franken-stream.log
```
(Add to crontab with `crontab -e`)

## 🤝 Contributing

### Report Issues
```bash
# Go to GitHub
# https://github.com/Bino-Elgua/franken-stream/issues
# Include:
# - What you tried
# - What error you got
# - Your OS and Python version
```

### Submit Features
```bash
# Fork the repository
# Create a feature branch
# Test thoroughly
# Submit a PR with description
```

### Update Providers
```bash
# Fork stream-providers repo
# Edit providers.json
# Test with:
franken-stream test-providers
# Submit PR
```

## 📖 Further Reading

- **[README.md](README.md)** - Full documentation
- **[README_FULL.md](README_FULL.md)** - Complete v0.2.0+ guide
- **[QUICKSTART.md](QUICKSTART.md)** - Fast reference
- **[ENHANCEMENTS.md](ENHANCEMENTS.md)** - Future features
- **[CLI_DEMO.md](CLI_DEMO.md)** - Usage examples

## ❓ FAQ

**Q: Is this legal?**
A: It's a search tool. Legality depends on content and your jurisdiction. Use `--legal-only` for licensed sources.

**Q: Will I get in trouble?**
A: It depends on your location and what you watch. Use a VPN and respect copyright.

**Q: Why is the site blocked?**
A: Streaming sites move frequently. Run `franken-stream update` to get fresh providers.

**Q: Can I add my own providers?**
A: Yes! Edit `~/.franken-stream/providers.json` or fork `stream-providers` repo.

**Q: How often are providers updated?**
A: Community-driven. Submit PRs when you find dead/working sites.

**Q: Does this work on phone?**
A: Yes! Install Termux (Android) or use iOS terminal apps.

**Q: Can I download videos?**
A: Yes! Use `--download` flag:
```bash
franken-stream watch "movie" --download -o ~/videos
```

**Q: Why is streaming slow?**
A: Sites may be throttled or blocked. Try `--proxy` or different provider.

## 🎉 You're Ready!

Now run:
```bash
franken-stream watch "your favorite movie"
```

Enjoy! 🍿
