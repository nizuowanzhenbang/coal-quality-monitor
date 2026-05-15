import { useEffect, useRef, useCallback } from 'react'
import { useAuthStore } from '../stores/auth'
import type { WsMessage } from '../types'

interface UseAlertWebSocketOptions {
  onNewAlert?: (data: Extract<WsMessage, { type: 'new_alert' }>['data']) => void
}

export function useAlertWebSocket({ onNewAlert }: UseAlertWebSocketOptions = {}) {
  const wsRef = useRef<WebSocket | null>(null)
  const retryCountRef = useRef(0)
  const retryTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const mountedRef = useRef(true)
  const token = useAuthStore((s) => s.token)

  const connect = useCallback(() => {
    if (!token || !mountedRef.current) return

    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const wsUrl = `${protocol}://${window.location.host}/api/ws/alerts?token=${token}`

    const ws = new WebSocket(wsUrl)
    wsRef.current = ws

    ws.onopen = () => {
      retryCountRef.current = 0
    }

    ws.onmessage = (event: MessageEvent) => {
      try {
        const msg = JSON.parse(event.data as string) as WsMessage
        if (msg.type === 'ping') {
          ws.send(JSON.stringify({ type: 'pong' }))
        } else if (msg.type === 'new_alert' && onNewAlert) {
          onNewAlert(msg.data)
        }
      } catch {
        // ignore parse errors
      }
    }

    ws.onclose = () => {
      if (!mountedRef.current) return
      const delay = Math.min(1000 * 2 ** retryCountRef.current, 30000)
      retryCountRef.current += 1
      retryTimerRef.current = setTimeout(() => {
        if (mountedRef.current) connect()
      }, delay)
    }

    ws.onerror = () => {
      ws.close()
    }
  }, [token, onNewAlert])

  useEffect(() => {
    mountedRef.current = true
    connect()
    return () => {
      mountedRef.current = false
      if (retryTimerRef.current) clearTimeout(retryTimerRef.current)
      if (wsRef.current) wsRef.current.close()
    }
  }, [connect])
}
