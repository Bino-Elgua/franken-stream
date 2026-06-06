import { AnimatePresence, motion } from 'framer-motion'
import { useCallback, useEffect, useState } from 'react'
import MediaGrid from './components/MediaGrid'
import PremiumWebPlayer from './components/PremiumWebPlayer'
import ProviderStatus from './components/ProviderStatus'
import SearchBar from './components/SearchBar'
import WatchlistPanel from './components/WatchlistPanel'
import { useWebSocket } from './hooks/useWebSocket'
import type { MediaItem, PlaybackStatus, ProviderHealth, WatchlistEntry, WsMessage } from './types'

const GRID_BG = `
  linear-gradient(rgba(0,245,255,0.06) 1px, transparent 1px),
  linear-gradient(90deg, rgba(0,245,255,0.06) 1px, transparent 1px)
`

export default function App() {
  const [query, setQuery] = useState('')
  const [searching, setSearching] = useState(false)
  const [results, setResults] = useState<MediaItem[]>([])
  const [selected, setSelected] = useState<MediaItem | null>(null)
  const [providers, setProviders] = useState<ProviderHealth[]>([])
  const [watchlistOpen, setWatchlistOpen] = useState(false)
  const [playbackStatus, setPlaybackStatus] = useState<PlaybackStatus | null>(null)
  const [nowPlayingBar, setNowPlayingBar] = useState<string | null>(null)

  // WebSocket
  const onMessage = useCallback((msg: WsMessage) => {
    if (msg.type === 'status') {
      setPlaybackStatus({
        is_playing: msg.is_playing ?? false,
        title: msg.title ?? '',
        elapsed_seconds: msg.elapsed_seconds ?? 0,
        duration_seconds: msg.duration_seconds ?? 0,
        mpv_running: msg.mpv_running ?? false,
      })
    }
    if (msg.type === 'playback') {
      if (msg.event === 'spin-up' || msg.event === 'started') {
        setNowPlayingBar(msg.title ?? null)
        setTimeout(() => setNowPlayingBar(null), 5000)
      }
    }
  }, [])
  const { connected, requestStatus } = useWebSocket(onMessage)

  // Poll playback status every 10s when MPV is running
  useEffect(() => {
    const id = setInterval(() => { if (connected) requestStatus() }, 10_000)
    return () => clearInterval(id)
  }, [connected, requestStatus])

  // Load provider health
  useEffect(() => {
    fetch('/api/v1/providers')
      .then(r => r.json())
      .then(d => {
        if (Array.isArray(d.health)) setProviders(d.health)
      })
      .catch(() => {})
  }, [])

  const handleSearch = async (q: string) => {
    setQuery(q)
    setSearching(true)
    setResults([])
    try {
      const res = await fetch('/api/v1/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: q }),
      })
      if (!res.ok) throw new Error('Search failed')
      const data = await res.json()
      const items: MediaItem[] = (data.results ?? []).map((r: { title: string; url: string; provider?: string }, i: number) => ({
        id: i,
        title: r.title,
        url: r.url,
        provider: r.provider,
      }))
      setResults(items)
    } catch {
      setResults([])
    } finally {
      setSearching(false)
    }
  }

  const handleSelect = useCallback(async (item: MediaItem) => {
    setSelected({ ...item, loading: true, embedUrl: null })
    try {
      const res = await fetch('/api/embed', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: item.url, base_url: item.provider }),
      })
      if (res.ok) {
        const data = await res.json()
        setSelected(prev => prev ? { ...prev, loading: false, embedUrl: data.embed_url ?? null } : null)
        return
      }
    } catch {
      // ignore
    }
    setSelected(prev => prev ? { ...prev, loading: false } : null)
  }, [])

  const handleWatchlistPlay = useCallback((entry: WatchlistEntry) => {
    setWatchlistOpen(false)
    setSelected({ id: 0, title: entry.title, url: entry.url, provider: entry.provider })
  }, [])

  return (
    <div className="min-h-screen relative" style={{ fontFamily: 'Inter, sans-serif' }}>
      {/* Scanlines */}
      <div className="scanlines" />

      {/* Grid background */}
      <div className="fixed inset-0 z-0 opacity-100 pointer-events-none" style={{
        backgroundImage: GRID_BG,
        backgroundSize: '50px 50px',
      }} />
      <div className="fixed inset-0 z-0 pointer-events-none bg-gradient-to-t from-[#0a0a0f] via-transparent to-[#0a0a0f]" />

      {/* Header */}
      <motion.header
        initial={{ y: -80 }}
        animate={{ y: 0 }}
        className="fixed top-0 left-0 right-0 z-30 glass border-b border-cyan-500/15"
      >
        <div className="max-w-7xl mx-auto px-5 py-3 flex items-center justify-between gap-4">
          {/* Logo */}
          <div className="flex items-center gap-3 flex-shrink-0">
            <motion.div
              className="w-9 h-9 rounded-lg bg-gradient-to-br from-cyan-400 to-purple-600 flex items-center justify-center neon-glow"
              animate={{ rotate: [0, 360] }}
              transition={{ duration: 24, repeat: Infinity, ease: 'linear' }}
            >
              <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </motion.div>
            <div>
              <h1 className="font-orbitron text-base font-bold tracking-wider leading-none">
                FRANKEN<span className="text-cyan-400">STREAM</span>
              </h1>
              <p className="text-[10px] text-gray-500 font-mono mt-0.5">v2.0</p>
            </div>
          </div>

          {/* Actions */}
          <div className="flex items-center gap-3">
            {/* WS indicator */}
            <div className={`flex items-center gap-1.5 text-xs ${connected ? 'text-green-400' : 'text-gray-600'}`}>
              <span className={`w-2 h-2 rounded-full ${connected ? 'bg-green-400 animate-pulse' : 'bg-gray-600'}`} />
              <span className="hidden sm:inline font-mono">{connected ? 'Live' : 'Offline'}</span>
            </div>

            {/* Watchlist */}
            <button
              onClick={() => setWatchlistOpen(o => !o)}
              title="Open watchlist"
              className={`p-2 rounded-lg transition-colors ${watchlistOpen ? 'bg-cyan-500/20 text-cyan-400' : 'text-gray-400 hover:text-white'}`}
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z" />
              </svg>
            </button>
          </div>
        </div>

        {/* Now-playing toast */}
        <AnimatePresence>
          {nowPlayingBar && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              className="overflow-hidden"
            >
              <div className="flex items-center gap-2 px-5 py-1.5 bg-cyan-500/10 border-t border-cyan-500/20">
                <span className="w-2 h-2 bg-cyan-400 rounded-full animate-pulse" />
                <p className="text-xs text-cyan-400 font-mono">Now playing: {nowPlayingBar}</p>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </motion.header>

      {/* Main content */}
      <main className="relative z-10 pt-20 pb-12 px-5 max-w-7xl mx-auto">
        {/* Hero */}
        <div className="py-10 text-center">
          <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }}>
            <h2 className="font-orbitron text-3xl sm:text-4xl font-bold mb-3">
              <span className="text-transparent bg-clip-text bg-gradient-to-r from-cyan-400 via-purple-400 to-pink-400">
                Stream Search
              </span>
            </h2>
            <p className="text-gray-500 text-sm mb-8">Search across providers for movies and shows in real time</p>
          </motion.div>

          <SearchBar onSearch={handleSearch} searching={searching} />
        </div>

        <ProviderStatus providers={providers} />

        <MediaGrid items={results} query={query} searching={searching} onSelect={handleSelect} />
      </main>

      {/* Footer */}
      <footer className="relative z-10 border-t border-cyan-500/8 py-5 px-5">
        <div className="max-w-7xl mx-auto flex items-center justify-between text-xs text-gray-600">
          <p className="font-mono">Franken-Stream v2.0</p>
          <p>Search · Watch · Enjoy</p>
        </div>
      </footer>

      {/* Watchlist panel */}
      <WatchlistPanel
        isOpen={watchlistOpen}
        onClose={() => setWatchlistOpen(false)}
        onPlay={handleWatchlistPlay}
      />

      {/* Player modal */}
      <AnimatePresence>
        {selected && (
          <PremiumWebPlayer
            item={selected}
            playbackStatus={playbackStatus}
            onClose={() => setSelected(null)}
          />
        )}
      </AnimatePresence>
    </div>
  )
}
