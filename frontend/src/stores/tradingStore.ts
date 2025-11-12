import { create } from 'zustand'
import { api } from '../services/api'
import { TradingSnapshot } from '../services/types'

type TradingState = TradingSnapshot & {
  loading: boolean
  error?: string
  fetchSnapshot: () => Promise<void>
}

const initialState: TradingSnapshot = {
  positions: [],
  orders: [],
  account: {
    totalEquity: 0,
    available: 0,
    locked: 0,
    todaysPnl: 0,
    cumulativePnl: 0,
    winRate: 0,
    riskExposure: 0,
  },
  priceHistory: [],
}

export const useTradingStore = create<TradingState>((set) => ({
  ...initialState,
  loading: false,
  async fetchSnapshot() {
    set({ loading: true, error: undefined })
    try {
      const data = await api.fetchTradingSnapshot()
      set({ ...data, loading: false })
    } catch (error) {
      console.error('[TradingStore] fetchSnapshot failed', error)
      set({ loading: false, error: '无法获取交易数据' })
    }
  },
}))
