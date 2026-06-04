import { AnimatePresence, motion } from 'framer-motion'
import type { MediaItem } from '../types'
import MediaCard from './MediaCard'

interface Props {
  items: MediaItem[]
  query: string
  searching: boolean
  onSelect: (item: MediaItem) => void
}

export default function MediaGrid({ items, query, searching, onSelect }: Props) {
  return (
    <div className="mt-8">
      <div className="flex items-center justify-between mb-5">
        <h3 className="font-orbitron text-lg font-semibold text-white">
          {query ? `Results for "${query}"` : 'Discover'}
        </h3>
        {searching && (
          <div className="flex items-center gap-2 text-cyan-400">
            <motion.div
              animate={{ rotate: 360 }}
              transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
              className="w-4 h-4 border-2 border-cyan-400 border-t-transparent rounded-full"
            />
            <span className="text-xs font-mono">Searching providers…</span>
          </div>
        )}
      </div>

      {!searching && items.length === 0 ? (
        <motion.div
          initial={{ opacity: 0 }} animate={{ opacity: 1 }}
          className="flex flex-col items-center py-24 text-center"
        >
          <div className="w-20 h-20 rounded-full bg-cyan-500/8 flex items-center justify-center mb-4">
            <svg className="w-10 h-10 text-cyan-400/30" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
          </div>
          <p className="text-gray-500">Enter a title above to start searching</p>
        </motion.div>
      ) : (
        <motion.div layout className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
          <AnimatePresence>
            {items.map((item, i) => (
              <MediaCard key={item.url} item={item} index={i} onClick={() => onSelect(item)} />
            ))}
          </AnimatePresence>
        </motion.div>
      )}
    </div>
  )
}
