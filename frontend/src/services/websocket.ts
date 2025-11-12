export type MarketMessage = {
  price: number
  time: number
  symbol: string
}

export const createMarketSocket = (
  symbol: string,
  onMessage: (msg: MarketMessage) => void,
): (() => void) => {
  const base = import.meta.env.VITE_WS_BASE ?? 'ws://localhost:8001/ws/market'
  const socket = new WebSocket(`${base}/${symbol.replace('/', '')}`)

  socket.onmessage = (event) => {
    try {
      const payload = JSON.parse(event.data) as MarketMessage
      onMessage(payload)
    } catch (error) {
      console.error('[WS] Failed to parse message', error)
    }
  }

  socket.onerror = (error) => {
    console.error('[WS] error', error)
  }

  return () => {
    socket.close()
  }
}
