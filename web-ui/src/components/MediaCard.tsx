import { useState } from 'react'
import { AnimatePresence, motion, useMotionValue, useTransform } from 'framer-motion'
import type { MediaItem } from '../types'

interface Props {
  item: MediaItem
  index: number
  onClick: () => void
}

export default function MediaCard({ item, index, onClick }: Props) {
  const [hovered, setHovered] = useState(false)
  const mx = useMotionValue(0)
  const my = useMotionValue(0)
  const rotX = useTransform(my, [-80, 80], [8, -8])
  const rotY = useTransform(mx, [-80, 80], [-8, 8])

  const imgSrc = `https://picsum.photos/seed/${encodeURIComponent(item.title)}/300/450`

  return (
    <motion.div
      layout
      initial={{ opacity: 0, scale: 0.85 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.85 }}
      transition={{ duration: 0.35, delay: index * 0.04 }}
      onClick={onClick}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => { setHovered(false); mx.set(0); my.set(0) }}
      onMouseMove={(e) => {
        const r = e.currentTarget.getBoundingClientRect()
        mx.set(e.clientX - r.left - r.width / 2)
        my.set(e.clientY - r.top - r.height / 2)
      }}
      style={{ rotateX: hovered ? rotX : 0, rotateY: hovered ? rotY : 0, transformStyle: 'preserve-3d' }}
      className="relative group cursor-pointer"
    >
      <div className="relative aspect-[2/3] rounded-xl overflow-hidden glass">
        <motion.img
          src={imgSrc}
          alt={item.title}
          className="w-full h-full object-cover"
          animate={{ scale: hovered ? 1.08 : 1 }}
          transition={{ duration: 0.35 }}
        />

        {/* Gradient overlay */}
        <div className="absolute inset-0 bg-gradient-to-t from-black/90 via-black/10 to-transparent" />

        {/* Holographic sheen */}
        <motion.div
          className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-500 pointer-events-none"
          style={{
            background: 'linear-gradient(110deg, transparent 35%, rgba(0,245,255,0.18) 45%, rgba(176,38,255,0.18) 55%, transparent 65%)',
          }}
        />

        {/* Badges */}
        <div className="absolute top-2 right-2 flex flex-col gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
          {item.quality && (
            <span className="px-2 py-0.5 bg-cyan-500/20 border border-cyan-500/40 rounded text-[10px] text-cyan-400 font-mono">
              {item.quality}
            </span>
          )}
          {item.year && (
            <span className="px-2 py-0.5 bg-purple-500/20 border border-purple-500/40 rounded text-[10px] text-purple-400 font-mono">
              {item.year}
            </span>
          )}
        </div>

        {/* Title + meta */}
        <div className="absolute inset-x-0 bottom-0 p-3">
          <h3 className="text-sm font-semibold text-white leading-snug mb-0.5 group-hover:text-cyan-400 transition-colors line-clamp-2">
            {item.title}
          </h3>
          <p className="text-xs text-gray-500 truncate">{item.provider || 'unknown'}</p>
        </div>

        {/* Play button */}
        <AnimatePresence>
          {hovered && (
            <motion.div
              initial={{ scale: 0, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} exit={{ scale: 0, opacity: 0 }}
              className="absolute inset-0 flex items-center justify-center"
            >
              <div className="w-14 h-14 rounded-full bg-cyan-500/25 backdrop-blur-sm border border-cyan-400 flex items-center justify-center neon-glow">
                <svg className="w-7 h-7 text-cyan-400 ml-1" fill="currentColor" viewBox="0 0 20 20">
                  <path d="M6.3 2.841A1.5 1.5 0 004 4.11V15.89a1.5 1.5 0 002.3 1.269l9.344-5.89a1.5 1.5 0 000-2.538L6.3 2.84z" />
                </svg>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </motion.div>
  )
}
