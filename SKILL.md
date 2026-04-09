# Franken-Stream — OpenClaw Skill

## Overview

Franken-Stream exposes a structured intent API that OpenClaw can call to search and stream movies, TV shows, internet radio, podcasts, audiobooks, live TV, and sports scores.

The skill is served by the **Rust HTTP server** (default `http://localhost:3001`) backed by the **Python sidecar** for actual media operations.

---

## API Endpoint

```
POST /openclaw
Content-Type: application/json
```

### Request

```json
{
  "intent": "<intent_name>",
  "params": { ... }
}
```

### Response

```json
{
  "status":       "success" | "needs_clarification" | "error",
  "action_taken": "<string>",
  "data":         { ... },
  "message":      "<human-readable string>"
}
```

---

## Supported Intents

### `stream` — Search and play a movie or show

```json
{
  "intent": "stream",
  "params": {
    "title": "Inception",
    "quality": "1080p"
  }
}
```

### `stream_episode` — Search a specific TV episode

```json
{
  "intent": "stream_episode",
  "params": {
    "show": "Breaking Bad",
    "season": 5,
    "episode": 14
  }
}
```

### `search_natural` — Free-text search

```json
{
  "intent": "search_natural",
  "params": {
    "description": "sci-fi thriller from 2020"
  }
}
```

### `recommend` — Search by mood / genre

```json
{
  "intent": "recommend",
  "params": {
    "mood": "relaxing",
    "genre": "comedy"
  }
}
```

### `play_radio` — Find and stream internet radio (90,000+ stations)

```json
{
  "intent": "play_radio",
  "params": {
    "query": "jazz",
    "genre": "jazz",
    "country": "United States",
    "language": "english"
  }
}
```

Response `data.results` is a list of station objects:
```json
{
  "title": "Jazz24",
  "url": "https://...",
  "genre": "jazz",
  "country": "United States",
  "bitrate": 128,
  "codec": "mp3",
  "type": "radio"
}
```

### `play_podcast` — Search podcasts

```json
{
  "intent": "play_podcast",
  "params": {
    "query": "Software Engineering Daily"
  }
}
```

Response `data.results` contains podcast objects with `feed_url` for episode
fetching.

### `get_podcast_episodes` — Fetch episodes from a podcast RSS feed

```json
{
  "intent": "get_podcast_episodes",
  "params": {
    "feed_url": "https://feeds.example.com/podcast.rss",
    "limit": 10
  }
}
```

### `play_audiobook` — Search LibriVox audiobooks (free, public domain)

```json
{
  "intent": "play_audiobook",
  "params": {
    "query": "Sherlock Holmes",
    "search_by": "title"
  }
}
```

`search_by` can be `"title"` (default) or `"author"`.

### `watch_live` — Browse live TV channels

```json
{
  "intent": "watch_live",
  "params": {
    "query": "BBC",
    "category": "news",
    "country": "United Kingdom"
  }
}
```

Supported categories: `news`, `sports`, `entertainment`, `movies`, `kids`,
`music`, `documentary`, `cooking`, `lifestyle`, `travel`, `science`, `business`.

### `get_scores` — Live sports scores (requires `SPORTS_API_KEY`)

```json
{
  "intent": "get_scores",
  "params": {
    "team": "Manchester United",
    "live_only": false
  }
}
```

### `control` — Pass-through for playback control signals

```json
{
  "intent": "control",
  "params": {
    "action": "pause"
  }
}
```

### `provider_health` — Retrieve provider health statistics

```json
{
  "intent": "provider_health",
  "params": {}
}
```

---

## Natural-Language Examples (for OpenClaw prompt engineering)

| User says | Recommended intent + params |
|---|---|
| "Stream Inception" | `stream` · `title: "Inception"` |
| "Watch Breaking Bad S5E14" | `stream_episode` · `show/season/episode` |
| "Find me a relaxing comedy" | `recommend` · `mood: "relaxing", genre: "comedy"` |
| "Play some jazz radio" | `play_radio` · `genre: "jazz"` |
| "Latest episode of Lex Fridman" | `play_podcast` · `query: "Lex Fridman"` |
| "Read me Sherlock Holmes" | `play_audiobook` · `query: "Sherlock Holmes"` |
| "Live news channels" | `watch_live` · `category: "news"` |
| "How's Man United doing?" | `get_scores` · `team: "Manchester United"` |
| "Provider status" | `provider_health` |

---

## Configuration

| Variable | Required | Description |
|---|---|---|
| `BIND_ADDR` | No | Rust server listen address (default `0.0.0.0:3001`) |
| `SIDECAR_MODULE` | No | Python sidecar module path |
| `SPORTS_API_KEY` | No | API-Sports key for live scores |
| `FRANKEN_STREAM_LLM_ENDPOINT` | No | LLM endpoint for CSS selector healing |

---

## Running the Server

```bash
# Start the Rust + Python sidecar stack
cargo run -p server

# Or just the Python sidecar (for testing intents directly)
python -m franken_stream.sidecar_main

# Install Python dependencies
pip install -r requirements.txt
```

---

## Skill Metadata

```yaml
name: franken_stream
version: 1.0.0
description: >
  Search and stream movies, TV shows, internet radio, podcasts, audiobooks,
  live TV channels, and sports scores across 55+ providers — no API keys
  required for core functionality.
os: [darwin, linux, win32]
requires:
  bins: [python3, mpv]
  ports: [3001]
```
