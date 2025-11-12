import { useEffect } from 'react'
import { Card, Col, List, Progress, Row } from 'antd'
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip as RechartsTooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { SectionHeader } from '../../components/SectionHeader'
import { SeverityTag } from '../../components/StatusTag'
import { useRiskStore } from '../../stores/riskStore'

export const RiskPanel = () => {
  const { metrics, alerts, equityCurve, loading, fetchSnapshot } = useRiskStore()

  useEffect(() => {
    fetchSnapshot()
  }, [fetchSnapshot])

  const riskEntries = [
    { key: 'position', label: '仓位风险', value: metrics.position },
    { key: 'liquidity', label: '流动性风险', value: metrics.liquidity },
    { key: 'volatility', label: '波动率风险', value: metrics.volatility },
    { key: 'concentration', label: '集中度风险', value: metrics.concentration },
  ]

  return (
    <section id="risk" className="space-y-6">
      <SectionHeader title="风险控制面板" description="风险雷达、告警流、资金曲线与压力测试" onRefresh={fetchSnapshot} />

      <Row gutter={[16, 16]}>
        {riskEntries.map((entry) => (
          <Col xs={24} md={6} key={entry.key}>
            <Card className="bg-background-card border border-white/5" loading={loading}>
              <p className="text-gray-400 text-sm mb-2">{entry.label}</p>
              <Progress percent={Math.round(entry.value * 100)} strokeColor="#ff4d4f" showInfo />
            </Card>
          </Col>
        ))}
      </Row>

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={14}>
          <Card className="bg-background-card border border-white/5" title="资金曲线" loading={loading}>
            <div className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={equityCurve}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
                  <XAxis dataKey="time" stroke="#9ca3af" />
                  <YAxis stroke="#9ca3af" />
                  <RechartsTooltip />
                  <Area type="monotone" dataKey="equity" stroke="#10b981" fill="#10b98155" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </Card>
        </Col>
        <Col xs={24} lg={10}>
          <Card className="bg-background-card border border-white/5" title="实时告警" loading={loading}>
            <List
              dataSource={alerts}
              renderItem={(alert) => (
                <List.Item actions={[<SeverityTag key="severity" severity={alert.severity} />]}>
                  <List.Item.Meta
                    title={<span className="text-white">{alert.message}</span>}
                    description={
                      <div className="text-gray-400 text-sm">
                        {alert.category} · {alert.timestamp}
                      </div>
                    }
                  />
                </List.Item>
              )}
            />
          </Card>
        </Col>
      </Row>
    </section>
  )
}
