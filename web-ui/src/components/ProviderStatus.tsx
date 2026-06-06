import { motion } from 'framer-motion'
import type { ProviderHealth } from '../types'

interface Props { providers: ProviderHealth[] }

function shortName(url: string) {
  try { return new URL(url).hostname.replace(/^www\./, '') } catch { return url }
}

export default function ProviderStatus({ providers }: Props) {
  if (!providers.length) return null
  const online = providers.filter(p => !p.disabled).length

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      className="glass rounded-xl p-4 mb-6"
    >
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-orbitron text-xs uppercase tracking-widest text-cyan-400">Providers</h3>
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 bg-green-400 rounded-full animate-pulse" />
          <span className="text-xs text-gray-400">{online}/{providers.length} active</span>
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
        {providers.map((p, i) => {
          const pct = Math.round(p.success_rate * 100)
          const ok = !p.disabled && p.success_rate >= 0.4
          return (
            <motion.div
              key={p.url}
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: i * 0.04 }}
              title={`${shortName(p.url)} — ${pct}% success, ${Math.round(p.avg_ms)}ms`}
              className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border text-xs transition-colors
                ${ok
                  ? 'bg-green-500/5 border-green-500/20 text-gray-300'
                  : 'bg-red-500/5 border-red-500/15 text-gray-500'}`}
            >
              <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${ok ? 'bg-green-400' : 'bg-red-400'}`} />
              <span className="truncate max-w-[120px]">{shortName(p.url)}</span>
              <span className={ok ? 'text-green-400/70' : 'text-red-400/60'}>{pct}%</span>
            </motion.div>
          )
        })}
      </div>
    </motion.div>
  )
}
