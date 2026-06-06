export interface MediaItem {
  id: number
  title: string
  url: string
  provider?: string
  year?: string
  type?: string
  quality?: string
  embedUrl?: string | null
  loading?: boolean
}

export interface ProviderHealth {
  url: string
  attempts: number
  success_rate: number
  avg_ms: number
  consecutive_failures: number
  disabled: boolean
}

export interface WatchlistEntry {
  id: string
  title: string
  url: string
  provider?: string
  year?: number
  media_type: string
  quality?: string
  added_at: number
  last_watched?: number
  progress_seconds: number
  duration_seconds?: number
  completed: number
}

export interface PlaybackStatus {
  is_playing: boolean
  playback_id?: string
  title: string
  elapsed_seconds: number
  duration_seconds: number
  mpv_running: boolean
}

export interface WsMessage {
  type: string
  event?: string
  title?: string
  is_playing?: boolean
  elapsed_seconds?: number
  duration_seconds?: number
  mpv_running?: boolean
}
