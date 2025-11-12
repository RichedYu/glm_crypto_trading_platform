export type PositionSide = 'long' | 'short'

export interface Position {
  id: string
  symbol: string
  side: PositionSide
  entryPrice: number
  currentPrice: number
  size: number
  pnlPercent: number
  openedAt: string
  stopLoss?: number
  takeProfit?: number
}

export type OrderStatus = 'filled' | 'open' | 'cancelled' | 'partial'

export interface Order {
  id: string
  timestamp: string
  symbol: string
  type: 'market' | 'limit'
  side: 'buy' | 'sell'
  price: number
  quantity: number
  fee: number
  status: OrderStatus
}

export interface AccountSummary {
  totalEquity: number
  available: number
  locked: number
  todaysPnl: number
  cumulativePnl: number
  winRate: number
  riskExposure: number
}

export interface TradingSnapshot {
  positions: Position[]
  orders: Order[]
  account: AccountSummary
  priceHistory: Array<{ time: number; price: number }>
}

export interface SentimentSnapshot {
  value: number // -100 ~ 100
  delta24h: number
  trend: Array<{ time: string; sentiment: number; price: number }>
  topics: SentimentTopic[]
  insight: string
  updatedAt: string
}

export interface SentimentTopic {
  name: string
  volume: number
  sentiment: 'positive' | 'negative' | 'neutral'
  keywords: string[]
  sampleTweet: string
}

export interface StrategyDescriptor {
  id: string
  name: string
  description: string
  status: 'running' | 'stopped' | 'pending'
  dailyReturn: number
  winRate: number
  tradesToday: number
  sharpe: number
  profile: 'conservative' | 'balanced' | 'aggressive'
}

export interface StrategyBacktest {
  id: string
  equityCurve: Array<{ date: string; equity: number; benchmark: number }>
  stats: {
    totalReturn: number
    annualReturn: number
    maxDrawdown: number
    sharpe: number
    winRate: number
    profitFactor: number
  }
}

export interface StrategySnapshot {
  strategies: StrategyDescriptor[]
  backtests: StrategyBacktest[]
}

export interface RiskMetrics {
  position: number
  liquidity: number
  volatility: number
  concentration: number
}

export interface RiskAlert {
  id: string
  timestamp: string
  category: 'stop_loss' | 'position' | 'system' | 'market'
  severity: 'low' | 'medium' | 'high'
  message: string
  status: 'new' | 'ack'
}

export interface RiskSnapshot {
  metrics: RiskMetrics
  alerts: RiskAlert[]
  equityCurve: Array<{ time: string; equity: number; drawdown: number }>
}
