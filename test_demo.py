#!/usr/bin/env python3
"""Demo script testing franken-stream functionality."""

import json
from pathlib import Path

from franken_stream.providers import ProviderManager
from franken_stream.scraper import ContentScraper, DEFAULT_USER_AGENT

print("=" * 70)
print("FRANKEN-STREAM DEMO TEST")
print("=" * 70)

# Test 1: ProviderManager initialization
print("\n[TEST 1] ProviderManager Initialization")
print("-" * 70)
pm = ProviderManager()
print(f"Config directory: {pm.config_dir}")
print(f"Config file: {pm.config_file}")
print(f"GitHub source: {pm.github_url}")

# Test 2: Load providers
print("\n[TEST 2] Loading Providers")
print("-" * 70)
providers = pm.load_providers()
print(f"Loaded providers: {json.dumps(providers, indent=2)}")

# Test 3: Get search bases
print("\n[TEST 3] Search Bases")
print("-" * 70)
bases = pm.get_search_bases()
print(f"Available search bases: {len(bases)}")
for i, base in enumerate(bases, 1):
    print(f"  {i}. {base}")

# Test 4: Get embed fallbacks
print("\n[TEST 4] Embed Fallbacks")
print("-" * 70)
fallbacks = pm.get_embed_fallbacks()
print(f"Available fallback embeds: {len(fallbacks)}")
for i, fb in enumerate(fallbacks, 1):
    print(f"  {i}. {fb}")

# Test 5: ContentScraper initialization
print("\n[TEST 5] ContentScraper Initialization")
print("-" * 70)
scraper = ContentScraper()
print(f"User-Agent: {scraper.user_agent}")
print(f"Proxy: {scraper.proxy or 'None'}")

# Test 6: ContentScraper with custom User-Agent
print("\n[TEST 6] ContentScraper with Custom User-Agent")
print("-" * 70)
custom_ua = "Custom-Bot/1.0"
scraper_custom = ContentScraper(user_agent=custom_ua)
print(f"Custom User-Agent: {scraper_custom.user_agent}")

# Test 7: ContentScraper with proxy
print("\n[TEST 7] ContentScraper with Proxy")
print("-" * 70)
proxy = "http://proxy.example.com:8080"
scraper_proxy = ContentScraper(proxy=proxy)
print(f"Proxy configured: {scraper_proxy.proxy}")
print(f"Session proxies: {scraper_proxy.session.proxies}")

# Test 8: HTML parsing (simulated)
print("\n[TEST 8] HTML Parsing (Simulated)")
print("-" * 70)
from bs4 import BeautifulSoup

html = """
<html>
<body>
<a href="/movie/inception">Inception (2010)</a>
<a href="/movie/inception-rewatch">Inception Rewatch</a>
<a href="/movie/interstellar">Interstellar (2014)</a>
</body>
</html>
"""
soup = BeautifulSoup(html, "html.parser")
results = ContentScraper._extract_results(soup)
print(f"Parsed {len(results)} results:")
for title, url in results:
    print(f"  • {title} -> {url}")

# Test 9: Provider configuration directory
print("\n[TEST 9] Provider Configuration Directory")
print("-" * 70)
pm._ensure_config_dir()
if pm.config_dir.exists():
    print(f"✓ Config directory created/exists: {pm.config_dir}")
    # Check if providers.json exists
    if pm.config_file.exists():
        print(f"✓ Provider file exists: {pm.config_file}")
        try:
            with open(pm.config_file) as f:
                data = json.load(f)
            print(f"✓ Provider file is valid JSON")
            print(f"  - Search bases: {len(data.get('movie_search_bases', []))}")
            print(f"  - Embed fallbacks: {len(data.get('embed_fallbacks', []))}")
        except json.JSONDecodeError:
            print("✗ Provider file has invalid JSON")
    else:
        print(f"⚠ No provider file at {pm.config_file}")
else:
    print("✗ Failed to create config directory")

# Test 10: Default providers fallback
print("\n[TEST 10] Default Providers Fallback")
print("-" * 70)
defaults = pm._get_default_providers()
print(f"Default search bases: {len(defaults['movie_search_bases'])}")
print(f"Default embed fallbacks: {len(defaults['embed_fallbacks'])}")

print("\n" + "=" * 70)
print("ALL TESTS COMPLETED")
print("=" * 70)
