import { useEffect, useState } from 'react'
import { createMarketSocket } from '../services/websocket'

export const useMarketData = (symbol: string) => {
  const [price, setPrice] = useState<number>()

  useEffect(() => {
    if (!symbol) return
    let cleanup: (() => void) | undefined
    try {
      cleanup = createMarketSocket(symbol, (payload) => {
        setPrice(payload.price)
      })
    } catch (error) {
      console.warn('[WS] fallback to mock stream', error)
    }

    return () => {
      if (cleanup) cleanup()
    }
  }, [symbol])

  return price
}
