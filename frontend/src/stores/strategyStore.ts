import { create } from 'zustand'
import { api } from '../services/api'
import { StrategySnapshot } from '../services/types'

type StrategyState = StrategySnapshot & {
  loading: boolean
  error?: string
  fetchSnapshot: () => Promise<void>
}

const initialState: StrategySnapshot = {
  strategies: [],
  backtests: [],
}

export const useStrategyStore = create<StrategyState>((set) => ({
  ...initialState,
  loading: false,
  async fetchSnapshot() {
    set({ loading: true, error: undefined })
    try {
      const data = await api.fetchStrategySnapshot()
      set({ ...data, loading: false })
    } catch (error) {
      console.error('[StrategyStore] fetchSnapshot failed', error)
      set({ loading: false, error: '获取策略数据失败' })
    }
  },
}))
