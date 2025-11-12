import { faker } from '@faker-js/faker'
import dayjs from 'dayjs'
import {
  AccountSummary,
  Order,
  Position,
  RiskAlert,
  RiskSnapshot,
  SentimentSnapshot,
  StrategyBacktest,
  StrategyDescriptor,
  TradingSnapshot,
} from './types'

const symbols = ['BNB/USDT', 'BTC/USDT', 'ETH/USDT', 'SOL/USDT']

const randomPositions = (): Position[] =>
  symbols.slice(0, 3).map((symbol, idx) => {
    const entry = faker.number.float({ min: 200, max: 620 })
    const current = entry * faker.number.float({ min: 0.92, max: 1.08 })
    return {
      id: `pos-${idx + 1}`,
      symbol,
      side: idx % 2 === 0 ? 'long' : 'short',
      entryPrice: Number(entry.toFixed(2)),
      currentPrice: Number(current.toFixed(2)),
      size: Number(faker.number.float({ min: 2, max: 15 }).toFixed(4)),
      pnlPercent: Number(((current - entry) / entry * 100).toFixed(2)),
      openedAt: dayjs().subtract(idx * 3, 'hour').toISOString(),
      stopLoss: Number((entry * 0.95).toFixed(2)),
      takeProfit: Number((entry * 1.05).toFixed(2)),
    }
  })

const randomOrders = (): Order[] =>
  Array.from({ length: 12 }).map((_, idx) => ({
    id: `ord-${idx}`,
    timestamp: dayjs().subtract(idx * 15, 'minute').toISOString(),
    symbol: faker.helpers.arrayElement(symbols),
    type: faker.helpers.arrayElement(['market', 'limit']),
    side: faker.helpers.arrayElement(['buy', 'sell']),
    price: Number(faker.number.float({ min: 200, max: 650 }).toFixed(2)),
    quantity: Number(faker.number.float({ min: 0.5, max: 8 }).toFixed(4)),
    fee: Number(faker.number.float({ min: 0.01, max: 0.2 }).toFixed(4)),
    status: faker.helpers.arrayElement(['filled', 'open', 'cancelled']),
  }))

const account: AccountSummary = {
  totalEquity: 152430,
  available: 68750,
  locked: 2360,
  todaysPnl: 1280,
  cumulativePnl: 18230,
  winRate: 0.68,
  riskExposure: 0.42,
}

const priceHistory = (): Array<{ time: number; price: number }> => {
  const start = dayjs().subtract(4, 'hour')
  const entries: Array<{ time: number; price: number }> = []
  let price = 520
  for (let i = 0; i < 240; i += 1) {
    price += faker.number.float({ min: -2.5, max: 2.5 })
    entries.push({
      time: start.add(i, 'minute').unix(),
      price: Number(price.toFixed(2)),
    })
  }
  return entries
}

export const tradingSnapshotMock = (): TradingSnapshot => ({
  positions: randomPositions(),
  orders: randomOrders(),
  account,
  priceHistory: priceHistory(),
})

export const sentimentSnapshotMock = (): SentimentSnapshot => {
  const base = dayjs()
  const trend = Array.from({ length: 7 }).map((_, idx) => ({
    time: base.subtract(7 - idx, 'day').format('MM-DD'),
    sentiment: faker.number.int({ min: -40, max: 70 }),
    price: faker.number.int({ min: 350, max: 650 }),
  }))

  return {
    value: 35,
    delta24h: 8,
    trend,
    topics: [
      {
        name: 'BNB Chain',
        volume: 4200,
        sentiment: 'positive',
        keywords: ['#airdrop', 'staking', 'new-chain'],
        sampleTweet: 'BNB ecosystem rotations heating up, watching liquidity...',
      },
      {
        name: 'BTC ETF',
        volume: 3900,
        sentiment: 'neutral',
        keywords: ['ETF flows', 'macro', 'institutions'],
        sampleTweet: 'ETF inflows slowing but still net positive week over week.',
      },
      {
        name: 'SOL DeFi',
        volume: 2600,
        sentiment: 'negative',
        keywords: ['DDOS', 'liquidations', 'solana'],
        sampleTweet: 'Congestion persists on Solana, watch liquidation cascades.',
      },
    ],
    insight:
      'Market leaning mildly bullish; DeFi narratives rotating to BNB while macro remains supportive. Watch SOL congestion risk.',
    updatedAt: dayjs().toISOString(),
  }
}

export const strategiesMock = (): StrategyDescriptor[] => [
  {
    id: 's1',
    name: 'S1 · Trend Grid',
    description: 'Volatility-aware grid with adaptive position sizing',
    status: 'running',
    dailyReturn: 0.85,
    winRate: 0.62,
    tradesToday: 18,
    sharpe: 2.1,
    profile: 'balanced',
  },
  {
    id: 's2',
    name: 'S2 · Mean Revert',
    description: 'Pairs trading and liquidity capture',
    status: 'running',
    dailyReturn: 0.34,
    winRate: 0.58,
    tradesToday: 9,
    sharpe: 1.5,
    profile: 'conservative',
  },
  {
    id: 's3',
    name: 'S3 · Momentum Burst',
    description: 'Captures short-lived breakouts with tight risk',
    status: 'stopped',
    dailyReturn: -0.12,
    winRate: 0.47,
    tradesToday: 0,
    sharpe: 0.8,
    profile: 'aggressive',
  },
]

export const backtestsMock = (): StrategyBacktest[] => [
  {
    id: 's1',
    equityCurve: Array.from({ length: 12 }).map((_, idx) => ({
      date: dayjs().subtract(12 - idx, 'month').format('YYYY-MM'),
      equity: 100 + idx * 4 + faker.number.float({ min: -1, max: 2 }),
      benchmark: 100 + idx * 2.5,
    })),
    stats: {
      totalReturn: 0.48,
      annualReturn: 0.32,
      maxDrawdown: 0.11,
      sharpe: 1.9,
      winRate: 0.61,
      profitFactor: 1.8,
    },
  },
  {
    id: 's2',
    equityCurve: Array.from({ length: 12 }).map((_, idx) => ({
      date: dayjs().subtract(12 - idx, 'month').format('YYYY-MM'),
      equity: 100 + idx * 2.2 + faker.number.float({ min: -1, max: 1 }),
      benchmark: 100 + idx * 2.5,
    })),
    stats: {
      totalReturn: 0.27,
      annualReturn: 0.19,
      maxDrawdown: 0.07,
      sharpe: 1.4,
      winRate: 0.58,
      profitFactor: 1.5,
    },
  },
]

export const riskSnapshotMock = (): RiskSnapshot => ({
  metrics: {
    position: 0.55,
    liquidity: 0.32,
    volatility: 0.62,
    concentration: 0.45,
  },
  alerts: Array.from({ length: 5 }).map((_, idx) => ({
    id: `alert-${idx}`,
    timestamp: dayjs().subtract(idx * 12, 'minute').toISOString(),
    category: faker.helpers.arrayElement(['stop_loss', 'position', 'system', 'market']),
    severity: faker.helpers.arrayElement(['low', 'medium', 'high']),
    message: faker.hacker.phrase(),
    status: idx === 0 ? 'new' : 'ack',
  })) as RiskAlert[],
  equityCurve: Array.from({ length: 14 }).map((_, idx) => ({
    time: dayjs().subtract(14 - idx, 'day').format('MM-DD'),
    equity: 100 + idx * 1.5 + faker.number.float({ min: -0.5, max: 1.5 }),
    drawdown: faker.number.float({ min: 0, max: 0.12 }),
  })),
})
