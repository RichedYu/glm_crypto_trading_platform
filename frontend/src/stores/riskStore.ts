import { create } from 'zustand'
import { api } from '../services/api'
import { RiskSnapshot } from '../services/types'

type RiskState = RiskSnapshot & {
  loading: boolean
  error?: string
  fetchSnapshot: () => Promise<void>
}

const initialState: RiskSnapshot = {
  metrics: {
    position: 0,
    liquidity: 0,
    volatility: 0,
    concentration: 0,
  },
  alerts: [],
  equityCurve: [],
}

export const useRiskStore = create<RiskState>((set) => ({
  ...initialState,
  loading: false,
  async fetchSnapshot() {
    set({ loading: true, error: undefined })
    try {
      const data = await api.fetchRiskSnapshot()
      set({ ...data, loading: false })
    } catch (error) {
      console.error('[RiskStore] fetchSnapshot failed', error)
      set({ loading: false, error: '风险数据获取失败' })
    }
  },
}))
