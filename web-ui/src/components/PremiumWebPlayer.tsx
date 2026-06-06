import Hls from 'hls.js'
import { AnimatePresence, motion } from 'framer-motion'
import { useCallback, useEffect, useRef, useState } from 'react'
import type { MediaItem, PlaybackStatus } from '../types'

interface Props {
  item: MediaItem
  playbackStatus: PlaybackStatus | null
  onClose: () => void
}

type Mode = 'loading' | 'video' | 'iframe' | 'error'

function isDirectStream(url: string) {
  return /\.(m3u8|mp4|webm|ogg|mkv)(\?.*)?$/i.test(url)
}

function isHLS(url: string) {
  return /\.m3u8(\?.*)?$/i.test(url)
}

export default function PremiumWebPlayer({ item, playbackStatus, onClose }: Props) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const hlsRef = useRef<Hls | null>(null)
  const [mode, setMode] = useState<Mode>('loading')
  const [embedUrl, setEmbedUrl] = useState<string | null>(null)
  const [spinUpStatus, setSpinUpStatus] = useState<string>('')
  const [launchingMpv, setLaunchingMpv] = useState(false)

  const resolveUrl = useCallback(async () => {
    setMode('loading')

    // If we already have a preloaded embed URL, use it
    if (item.embedUrl) {
      setEmbedUrl(item.embedUrl)
      setMode(isDirectStream(item.embedUrl) ? 'video' : 'iframe')
      return
    }

    // Fetch embed from backend
    try {
      const res = await fetch('/api/embed', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: item.url, base_url: item.provider }),
      })
      if (res.ok) {
        const data = await res.json()
        const url = data.embed_url || item.url
        setEmbedUrl(url)
        setMode(isDirectStream(url) ? 'video' : 'iframe')
        return
      }
    } catch {
      // fall through
    }

    setEmbedUrl(item.url)
    setMode(isDirectStream(item.url) ? 'video' : 'iframe')
  }, [item])

  useEffect(() => {
    resolveUrl()
  }, [resolveUrl])

  // Wire HLS.js when mode becomes 'video'
  useEffect(() => {
    if (mode !== 'video' || !embedUrl || !videoRef.current) return

    if (isHLS(embedUrl) && Hls.isSupported()) {
      const hls = new Hls({ enableWorker: true })
      hlsRef.current = hls
      hls.loadSource(embedUrl)
      hls.attachMedia(videoRef.current)
      hls.on(Hls.Events.MANIFEST_PARSED, () => videoRef.current?.play().catch(() => {}))
      hls.on(Hls.Events.ERROR, (_e, data) => {
        if (data.fatal) { setMode('error') }
      })
      return () => { hls.destroy(); hlsRef.current = null }
    }

    // Native video (mp4/webm)
    videoRef.current.src = embedUrl
    videoRef.current.play().catch(() => {})
  }, [mode, embedUrl])

  const launchMpv = async () => {
    setLaunchingMpv(true)
    setSpinUpStatus('Searching and launching MPV…')
    try {
      const res = await fetch('/api/v1/player/spin-up', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: item.title }),
      })
      const data = await res.json()
      setSpinUpStatus(res.ok ? `Now playing: ${data.media?.title ?? item.title}` : (data.detail ?? 'Launch failed'))
    } catch {
      setSpinUpStatus('Failed to reach the player service')
    } finally {
      setLaunchingMpv(false)
    }
  }

  const playUrl = embedUrl || item.url

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 bg-black/95 flex items-center justify-center p-4 md:p-8"
      onClick={onClose}
    >
      <motion.div
        initial={{ scale: 0.92, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        exit={{ scale: 0.92, opacity: 0 }}
        className="relative w-full max-w-5xl rounded-2xl overflow-hidden glass neon-glow flex flex-col"
        style={{ maxHeight: '90vh' }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header bar */}
        <div className="flex items-center justify-between px-5 py-3 border-b border-cyan-500/20 bg-black/60">
          <div>
            <h2 className="font-orbitron text-sm font-bold text-cyan-400 truncate max-w-xs md:max-w-lg">
              {item.title}
            </h2>
            {item.year && <p className="text-xs text-gray-500 mt-0.5">{item.year}</p>}
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-white transition-colors ml-4">
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Player area */}
        <div className="relative" style={{ aspectRatio: '16/9' }}>
          {mode === 'loading' && (
            <div className="absolute inset-0 flex flex-col items-center justify-center gap-4">
              <motion.div
                animate={{ rotate: 360 }}
                transition={{ duration: 1.2, repeat: Infinity, ease: 'linear' }}
                className="w-12 h-12 border-2 border-cyan-400 border-t-transparent rounded-full"
              />
              <p className="text-cyan-400 font-mono text-sm">Resolving stream…</p>
            </div>
          )}

          {mode === 'video' && embedUrl && (
            <video
              ref={videoRef}
              controls
              className="w-full h-full object-contain bg-black vjs-franken"
              style={{ outline: 'none' }}
            />
          )}

          {mode === 'iframe' && embedUrl && (
            <iframe
              src={embedUrl}
              className="w-full h-full border-0"
              allowFullScreen
              allow="autoplay; encrypted-media"
              referrerPolicy="no-referrer"
            />
          )}

          {mode === 'error' && (
            <div className="absolute inset-0 flex flex-col items-center justify-center gap-3">
              <svg className="w-12 h-12 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <p className="text-red-400 text-sm">Stream failed to load</p>
              <button onClick={resolveUrl} className="text-xs text-cyan-400 hover:underline">Retry</button>
            </div>
          )}
        </div>

        {/* Controls footer */}
        <div className="px-5 py-4 bg-black/60 border-t border-cyan-500/10 flex flex-col gap-3">
          {/* MPV status from WebSocket */}
          {playbackStatus?.mpv_running && (
            <div className="flex items-center gap-2 text-xs text-green-400">
              <span className="w-2 h-2 bg-green-400 rounded-full animate-pulse" />
              MPV playing: {playbackStatus.title} — {Math.floor(playbackStatus.elapsed_seconds / 60)}m
            </div>
          )}

          {/* Spin-up feedback */}
          {spinUpStatus && (
            <p className="text-xs text-cyan-300 font-mono">{spinUpStatus}</p>
          )}

          <div className="flex flex-wrap gap-3">
            {/* Launch MPV */}
            <motion.button
              onClick={launchMpv}
              disabled={launchingMpv}
              whileHover={{ scale: 1.03 }}
              whileTap={{ scale: 0.97 }}
              className="relative overflow-hidden rounded-lg px-4 py-2 text-sm font-orbitron font-semibold text-white disabled:opacity-50"
            >
              <div className="absolute inset-0 bg-gradient-to-r from-purple-600 to-pink-600" />
              <span className="relative">{launchingMpv ? 'Launching…' : 'Launch MPV'}</span>
            </motion.button>

            {/* Open in browser */}
            <a
              href={playUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="relative overflow-hidden rounded-lg px-4 py-2 text-sm font-orbitron font-semibold text-white inline-block"
            >
              <div className="absolute inset-0 bg-gradient-to-r from-cyan-600 to-blue-700" />
              <span className="relative">Open in Browser</span>
            </a>

            {/* Toggle mode */}
            {mode !== 'loading' && (
              <button
                onClick={() => setMode(m => m === 'video' ? 'iframe' : 'video')}
                className="px-4 py-2 text-sm text-gray-400 hover:text-cyan-400 border border-gray-600 hover:border-cyan-500/40 rounded-lg transition-colors"
              >
                {mode === 'video' ? 'Use iframe' : 'Use player'}
              </button>
            )}
          </div>

          <p className="text-[10px] text-gray-600 break-all">{playUrl}</p>
        </div>
      </motion.div>
    </motion.div>
  )
}
