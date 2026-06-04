import { useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'

interface Props {
  onSearch: (q: string) => void
  searching: boolean
}

const SUGGESTIONS = ['Dune: Part Two', 'Oppenheimer', 'The Matrix', 'Inception', 'Interstellar']

export default function SearchBar({ onSearch, searching }: Props) {
  const [query, setQuery] = useState('')
  const [focused, setFocused] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  const submit = (q: string) => {
    const trimmed = q.trim()
    if (trimmed) { setQuery(trimmed); onSearch(trimmed) }
  }

  return (
    <motion.form
      onSubmit={(e) => { e.preventDefault(); submit(query) }}
      className="relative w-full max-w-3xl mx-auto"
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
    >
      <div className={`glass rounded-2xl p-[1px] transition-all duration-300 ${focused ? 'neon-glow' : ''}`}>
        <div className="flex items-center bg-[#0a0a0f]/80 rounded-[calc(1rem-1px)] px-6 py-4 gap-4">
          {/* Icon */}
          <motion.svg
            className="w-6 h-6 text-cyan-400 flex-shrink-0"
            fill="none" stroke="currentColor" viewBox="0 0 24 24"
            animate={searching ? { scale: [1, 1.15, 1], opacity: [0.6, 1, 0.6] } : {}}
            transition={{ repeat: Infinity, duration: 1.2 }}
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
              d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </motion.svg>

          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onFocus={() => setFocused(true)}
            onBlur={() => setTimeout(() => setFocused(false), 150)}
            placeholder="Search movies and shows…"
            className="flex-1 bg-transparent text-lg text-white placeholder-gray-500 outline-none"
          />

          <AnimatePresence>
            {query && (
              <motion.button type="button" onClick={() => setQuery('')}
                initial={{ opacity: 0, scale: 0 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0 }}
                className="text-gray-500 hover:text-white transition-colors"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </motion.button>
            )}
          </AnimatePresence>

          <motion.button
            type="submit"
            className="relative overflow-hidden rounded-lg px-5 py-2 font-orbitron text-sm font-semibold tracking-wider text-white"
            whileHover={{ scale: 1.04 }}
            whileTap={{ scale: 0.96 }}
            disabled={searching}
          >
            <div className="absolute inset-0 bg-gradient-to-r from-cyan-500 to-blue-600" />
            <span className="relative">{searching ? '…' : 'SEARCH'}</span>
          </motion.button>
        </div>
      </div>

      {/* Suggestions */}
      <AnimatePresence>
        {focused && (
          <motion.div
            initial={{ opacity: 0, y: -6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -6 }}
            className="absolute top-full left-0 right-0 mt-2 glass rounded-xl overflow-hidden z-50"
          >
            <div className="p-3">
              <p className="text-xs text-cyan-400 uppercase tracking-widest mb-2 font-orbitron px-2">Trending</p>
              {SUGGESTIONS.map((s, i) => (
                <motion.div
                  key={s}
                  initial={{ opacity: 0, x: -16 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.05 }}
                  onClick={() => { setQuery(s); submit(s) }}
                  className="flex items-center px-3 py-2 rounded-lg hover:bg-cyan-500/10 cursor-pointer group transition-colors"
                >
                  <span className="text-cyan-400/40 text-xs font-mono mr-3">0{i + 1}</span>
                  <span className="text-gray-300 group-hover:text-cyan-400 transition-colors text-sm">{s}</span>
                </motion.div>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.form>
  )
}
