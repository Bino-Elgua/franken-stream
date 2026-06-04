import { useCallback, useEffect, useRef, useState } from 'react'
import type { WsMessage } from '../types'

const WS_URL = `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}/api/ws`
const PING_INTERVAL_MS = 20_000
const RECONNECT_DELAY_MS = 3_000

export function useWebSocket(onMessage: (msg: WsMessage) => void) {
  const [connected, setConnected] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)
  const pingRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const onMessageRef = useRef(onMessage)
  onMessageRef.current = onMessage

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return

    const ws = new WebSocket(WS_URL)
    wsRef.current = ws

    ws.onopen = () => {
      setConnected(true)
      pingRef.current = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ action: 'ping' }))
        }
      }, PING_INTERVAL_MS)
    }

    ws.onmessage = (e) => {
      try {
        const msg: WsMessage = JSON.parse(e.data)
        if (msg.type !== 'pong') onMessageRef.current(msg)
      } catch {
        // ignore malformed frames
      }
    }

    ws.onclose = () => {
      setConnected(false)
      if (pingRef.current) clearInterval(pingRef.current)
      setTimeout(connect, RECONNECT_DELAY_MS)
    }

    ws.onerror = () => ws.close()
  }, [])

  useEffect(() => {
    connect()
    return () => {
      if (pingRef.current) clearInterval(pingRef.current)
      wsRef.current?.close()
    }
  }, [connect])

  const requestStatus = useCallback(() => {
    wsRef.current?.send(JSON.stringify({ action: 'status' }))
  }, [])

  return { connected, requestStatus }
}
