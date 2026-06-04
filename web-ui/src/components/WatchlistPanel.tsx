import { AnimatePresence, motion } from 'framer-motion'
import { useEffect, useState } from 'react'
import type { WatchlistEntry } from '../types'

interface Props {
  isOpen: boolean
  onClose: () => void
  onPlay: (entry: WatchlistEntry) => void
}

function pct(entry: WatchlistEntry) {
  if (!entry.duration_seconds || entry.duration_seconds === 0) return 0
  return Math.min(100, Math.round((entry.progress_seconds / entry.duration_seconds) * 100))
}

function fmt(seconds: number) {
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  return h > 0 ? `${h}h ${m}m` : `${m}m`
}

export default function WatchlistPanel({ isOpen, onClose, onPlay }: Props) {
  const [items, setItems] = useState<WatchlistEntry[]>([])
  const [tab, setTab] = useState<'all' | 'progress'>('progress')

  const load = async () => {
    try {
      const url = tab === 'progress' ? '/api/v1/watchlist/in-progress' : '/api/v1/watchlist'
      const res = await fetch(url)
      if (res.ok) {
        const data = await res.json()
        setItems(data.items ?? [])
      }
    } catch {
      // backend offline — keep empty
    }
  }

  useEffect(() => { if (isOpen) load() }, [isOpen, tab])

  const remove = async (id: string) => {
    await fetch(`/api/v1/watchlist/${id}`, { method: 'DELETE' }).catch(() => {})
    setItems(prev => prev.filter(e => e.id !== id))
  }

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          initial={{ x: '100%' }}
          animate={{ x: 0 }}
          exit={{ x: '100%' }}
          transition={{ type: 'spring', damping: 26, stiffness: 210 }}
          className="fixed right-0 top-0 bottom-0 w-80 glass border-l border-cyan-500/20 z-40 flex flex-col"
        >
          {/* Header */}
          <div className="flex items-center justify-between px-5 py-4 border-b border-cyan-500/15">
            <h3 className="font-orbitron text-sm font-bold text-cyan-400 uppercase tracking-wider">Watchlist</h3>
            <button onClick={onClose} className="text-gray-400 hover:text-white transition-colors">
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          {/* Tabs */}
          <div className="flex border-b border-cyan-500/10">
            {(['progress', 'all'] as const).map(t => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={`flex-1 py-2.5 text-xs font-mono uppercase tracking-wider transition-colors
                  ${tab === t ? 'text-cyan-400 border-b-2 border-cyan-400' : 'text-gray-500 hover:text-gray-300'}`}
              >
                {t === 'progress' ? 'Continue' : 'All'}
              </button>
            ))}
          </div>

          {/* List */}
          <div className="flex-1 overflow-y-auto p-3 space-y-2">
            {items.length === 0 ? (
              <div className="flex flex-col items-center py-16 text-center">
                <svg className="w-10 h-10 text-gray-600 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                    d="M7 4V20M17 4v16M3 8h4m10 0h4M3 12h18M3 16h4m10 0h4" />
                </svg>
                <p className="text-gray-500 text-sm">
                  {tab === 'progress' ? 'Nothing in progress' : 'Watchlist is empty'}
                </p>
              </div>
            ) : items.map((entry, i) => (
              <motion.div
                key={entry.id}
                initial={{ opacity: 0, x: 16 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.04 }}
                className="relative glass rounded-xl p-3 group"
              >
                <div className="flex items-start justify-between gap-2 mb-2">
                  <p
                    className="text-sm text-white font-medium leading-snug line-clamp-2 cursor-pointer hover:text-cyan-400 transition-colors flex-1"
                    onClick={() => onPlay(entry)}
                  >
                    {entry.title}
                  </p>
                  <button
                    onClick={() => remove(entry.id)}
                    className="text-gray-600 hover:text-red-400 transition-colors flex-shrink-0 mt-0.5"
                  >
                    <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                </div>

                {entry.progress_seconds > 0 && (
                  <div className="space-y-1">
                    <div className="h-1 bg-gray-700 rounded-full overflow-hidden">
                      <motion.div
                        className="h-full bg-gradient-to-r from-cyan-400 to-purple-500 rounded-full"
                        initial={{ width: 0 }}
                        animate={{ width: `${pct(entry)}%` }}
                        transition={{ duration: 0.6, delay: i * 0.04 }}
                      />
                    </div>
                    <div className="flex justify-between text-[10px] text-gray-500">
                      <span>{fmt(entry.progress_seconds)} watched</span>
                      <span>{pct(entry)}%</span>
                    </div>
                  </div>
                )}

                {entry.completed === 1 && (
                  <span className="text-[10px] text-green-400 font-mono">✓ Completed</span>
                )}
              </motion.div>
            ))}
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
