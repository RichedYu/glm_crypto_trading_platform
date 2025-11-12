import { create } from 'zustand'
import { api } from '../services/api'
import { SentimentSnapshot } from '../services/types'

type SentimentState = {
  snapshot?: SentimentSnapshot
  loading: boolean
  error?: string
  refresh: () => Promise<void>
}

export const useSentimentStore = create<SentimentState>((set) => ({
  loading: false,
  async refresh() {
    set({ loading: true, error: undefined })
    try {
      const snapshot = await api.fetchSentimentSnapshot()
      set({ snapshot, loading: false })
    } catch (error) {
      console.error('[SentimentStore] refresh failed', error)
      set({ loading: false, error: '无法获取情绪数据' })
    }
  },
}))
