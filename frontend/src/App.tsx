import { ConfigProvider, theme } from 'antd'
import './App.css'
import { TradingDashboard } from './modules/trading/TradingDashboard'
import { SentimentPanel } from './modules/sentiment/SentimentPanel'
import { StrategyCenter } from './modules/strategy/StrategyCenter'
import { RiskPanel } from './modules/risk/RiskPanel'
import { AppLayout } from './components/layout/AppLayout'
import { useSentimentStore } from './stores/sentimentStore'

function App() {
  const lastUpdated = useSentimentStore((state) => state.snapshot?.updatedAt)

  return (
    <ConfigProvider
      theme={{
        algorithm: theme.darkAlgorithm,
        token: {
          colorBgBase: '#0b0e11',
          colorTextBase: '#f3f4f6',
          colorBorder: '#1f2937',
        },
      }}
    >
      <AppLayout lastUpdated={lastUpdated}>
        <TradingDashboard />
        <SentimentPanel />
        <StrategyCenter />
        <RiskPanel />
      </AppLayout>
    </ConfigProvider>
  )
}

export default App
