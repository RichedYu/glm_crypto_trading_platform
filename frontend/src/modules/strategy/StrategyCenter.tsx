import { useEffect } from 'react'
import { Button, Card, Col, Progress, Row, Space, Statistic } from 'antd'
import { Area, AreaChart, Legend, Radar, RadarChart, ResponsiveContainer, PolarGrid, PolarAngleAxis } from 'recharts'
import { SectionHeader } from '../../components/SectionHeader'
import { StrategyStatusTag } from '../../components/StatusTag'
import { useStrategyStore } from '../../stores/strategyStore'
import { formatPercent } from '../../utils/formatters'

export const StrategyCenter = () => {
  const { strategies, backtests, loading, fetchSnapshot } = useStrategyStore()

  useEffect(() => {
    fetchSnapshot()
  }, [fetchSnapshot])

  return (
    <section id="strategy" className="space-y-6">
      <SectionHeader title="策略管理中心" description="策略运行状态、参数配置与回测表现" onRefresh={fetchSnapshot} />

      <Row gutter={[16, 16]}>
        {strategies.map((strategy) => (
          <Col xs={24} md={8} key={strategy.id}>
            <Card className="bg-background-card border border-white/5 h-full" loading={loading}>
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-gray-400 text-sm">{strategy.name}</p>
                  <p className="text-white font-semibold">{strategy.description}</p>
                </div>
                <StrategyStatusTag status={strategy.status} />
              </div>
              <div className="mt-4 grid grid-cols-2 gap-4 text-sm">
                <Statistic title="今日收益" value={formatPercent(strategy.dailyReturn)} />
                <Statistic title="胜率" value={formatPercent(strategy.winRate * 100)} />
                <Statistic title="交易次数" value={strategy.tradesToday} />
                <Statistic title="Sharpe" value={strategy.sharpe} precision={2} />
              </div>
              <Space className="mt-4">
                <Button type="primary">启动</Button>
                <Button>配置</Button>
              </Space>
            </Card>
          </Col>
        ))}
      </Row>

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={16}>
          <Card className="bg-background-card border border-white/5" title="回测曲线" loading={loading}>
            <div className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={backtests[0]?.equityCurve ?? []}>
                  <defs>
                    <linearGradient id="equityGradient" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#1890FF" stopOpacity={0.6} />
                      <stop offset="95%" stopColor="#1890FF" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <Area dataKey="equity" stroke="#1890FF" fill="url(#equityGradient)" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </Card>
        </Col>
        <Col xs={24} lg={8}>
          <Card className="bg-background-card border border-white/5" title="策略评分雷达" loading={loading}>
            <div className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <RadarChart
                  data={[
                    { metric: '收益', value: 80 },
                    { metric: '风险', value: 60 },
                    { metric: '稳定性', value: 75 },
                    { metric: '适应性', value: 65 },
                    { metric: '效率', value: 72 },
                  ]}
                >
                  <PolarGrid />
                  <PolarAngleAxis dataKey="metric" stroke="#9ca3af" />
                  <Radar name="S1" dataKey="value" stroke="#38bdf8" fill="#38bdf8" fillOpacity={0.5} />
                </RadarChart>
              </ResponsiveContainer>
            </div>
          </Card>
        </Col>
      </Row>
    </section>
  )
}
