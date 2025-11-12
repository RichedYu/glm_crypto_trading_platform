import axios from 'axios'
import {
  backtestsMock,
  riskSnapshotMock,
  sentimentSnapshotMock,
  strategiesMock,
  tradingSnapshotMock,
} from './mockData'
import {
  RiskSnapshot,
  SentimentSnapshot,
  StrategySnapshot,
  TradingSnapshot,
} from './types'

const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8001/api/v1'
const USE_MOCK = import.meta.env.VITE_USE_MOCK === 'true'

const client = axios.create({
  baseURL: API_BASE,
  timeout: 10000,
})

export const api = {
  async fetchTradingSnapshot(): Promise<TradingSnapshot> {
    if (USE_MOCK) return tradingSnapshotMock()
    const [positions, orders, account] = await Promise.all([
      client.get('/positions'),
      client.get('/orders', { params: { status: 'all' } }),
      client.get('/account/balance'),
    ])
    const priceHistory = await client.get('/market/history', { params: { limit: 240 } })
    return {
      positions: positions.data,
      orders: orders.data,
      account: account.data,
      priceHistory: priceHistory.data,
    }
  },

  async fetchSentimentSnapshot(): Promise<SentimentSnapshot> {
    if (USE_MOCK) return sentimentSnapshotMock()
    const [current, history, topics, insights] = await Promise.all([
      client.get('/sentiment/current'),
      client.get('/sentiment/history', { params: { days: 7 } }),
      client.get('/sentiment/topics/trending'),
      client.get('/sentiment/insights'),
    ])
    return {
      value: current.data.value,
      delta24h: current.data.delta24h,
      trend: history.data,
      topics: topics.data,
      insight: insights.data.summary,
      updatedAt: current.data.updatedAt,
    }
  },

  async fetchStrategySnapshot(): Promise<StrategySnapshot> {
    if (USE_MOCK) {
      return {
        strategies: strategiesMock(),
        backtests: backtestsMock(),
      }
    }
    const [strategies, backtests] = await Promise.all([
      client.get('/strategies'),
      client.get('/strategies/backtests'),
    ])
    return {
      strategies: strategies.data,
      backtests: backtests.data,
    }
  },

  async fetchRiskSnapshot(): Promise<RiskSnapshot> {
    if (USE_MOCK) return riskSnapshotMock()
    const [metrics, alerts, equity] = await Promise.all([
      client.get('/risk/metrics'),
      client.get('/risk/alerts', { params: { status: 'new' } }),
      client.get('/risk/equity-curve'),
    ])
    return {
      metrics: metrics.data,
      alerts: alerts.data,
      equityCurve: equity.data,
    }
  },
}

export const websocketBase =
  import.meta.env.VITE_WS_BASE ?? 'ws://localhost:8001/ws/market'
