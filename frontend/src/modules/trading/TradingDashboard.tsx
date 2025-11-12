import { useEffect, useMemo, useRef } from 'react'
import { Card, Col, Row, Statistic, Table, Tag } from 'antd'
import { createChart, IChartApi, ISeriesApi, LineData } from 'lightweight-charts'
import dayjs from 'dayjs'
import { useTradingStore } from '../../stores/tradingStore'
import { formatCurrency, formatDateTime, formatDuration, formatPercent } from '../../utils/formatters'
import { SectionHeader } from '../../components/SectionHeader'
import { COLORS } from '../../utils/constants'
import { Position } from '../../services/types'

const PositionCard = ({ position }: { position: Position }) => (
  <Card className="bg-background-card border border-white/5" hoverable>
    <div className="flex items-center justify-between">
      <div>
        <p className="text-sm text-gray-400">{position.symbol}</p>
        <p className="text-xl font-semibold">{position.side === 'long' ? '多头' : '空头'}</p>
      </div>
      <Tag color={position.pnlPercent >= 0 ? 'green' : 'red'}>{formatPercent(position.pnlPercent)}</Tag>
    </div>
    <dl className="grid grid-cols-2 gap-2 mt-4 text-sm text-gray-300">
      <div>
        <dt>入场价</dt>
        <dd className="font-medium text-white">{formatCurrency(position.entryPrice)}</dd>
      </div>
      <div>
        <dt>现价</dt>
        <dd className="font-medium text-white">{formatCurrency(position.currentPrice)}</dd>
      </div>
      <div>
        <dt>数量</dt>
        <dd>{position.size.toFixed(4)}</dd>
      </div>
      <div>
        <dt>持仓时间</dt>
        <dd>{formatDuration(position.openedAt)}</dd>
      </div>
    </dl>
    <div className="mt-4 text-xs text-gray-500 flex justify-between">
      <span>止损: {position.stopLoss?.toFixed(2)}</span>
      <span>止盈: {position.takeProfit?.toFixed(2)}</span>
    </div>
  </Card>
)

const LivePriceChart = () => {
  const containerRef = useRef<HTMLDivElement>(null)
  const priceHistory = useTradingStore((state) => state.priceHistory)

  useEffect(() => {
    if (!containerRef.current) return
    const chart = createChart(containerRef.current, {
      layout: {
        background: { color: '#1F2329' },
        textColor: '#9ca3af',
      },
      grid: {
        horzLines: { color: '#1f2937' },
        vertLines: { color: '#1f2937' },
      },
      width: containerRef.current.clientWidth,
      height: 320,
    })
    const lineSeries = chart.addAreaSeries({
      lineColor: COLORS.primary,
      topColor: 'rgba(24, 144, 255, 0.4)',
      bottomColor: 'rgba(24, 144, 255, 0.05)',
    })
    if (priceHistory.length > 0) {
      const data: LineData[] = priceHistory.map((point) => ({
        time: point.time,
        value: point.price,
      }))
      lineSeries.setData(data)
    }

    const handleResize = () => {
      if (containerRef.current) {
        chart.applyOptions({ width: containerRef.current.clientWidth })
      }
    }
    window.addEventListener('resize', handleResize)

    return () => {
      window.removeEventListener('resize', handleResize)
      chart.remove()
    }
  }, [priceHistory])

  return <div ref={containerRef} className="w-full" />
}

export const TradingDashboard = () => {
  const { positions, orders, account, loading, fetchSnapshot } = useTradingStore()

  useEffect(() => {
    fetchSnapshot()
  }, [fetchSnapshot])

  const orderColumns = useMemo(
    () => [
      { title: '时间', dataIndex: 'timestamp', render: (value: string) => formatDateTime(value) },
      { title: '交易对', dataIndex: 'symbol' },
      { title: '类型', dataIndex: 'type', render: (value: string) => value.toUpperCase() },
      { title: '方向', dataIndex: 'side', render: (value: string) => value.toUpperCase() },
      {
        title: '数量',
        dataIndex: 'quantity',
        render: (value: number) => value.toFixed(4),
      },
      {
        title: '价格',
        dataIndex: 'price',
        render: (value: number) => formatCurrency(value),
      },
      {
        title: '手续费',
        dataIndex: 'fee',
        render: (value: number) => value.toFixed(4),
      },
      {
        title: '状态',
        dataIndex: 'status',
        render: (status: string) => (
          <Tag color={status === 'filled' ? 'green' : status === 'open' ? 'blue' : 'default'}>{status}</Tag>
        ),
      },
    ],
    [],
  )

  return (
    <section id="trading" className="space-y-6">
      <SectionHeader title="交易监控" description="持仓状态、订单流水、实时行情" onRefresh={fetchSnapshot} />

      <Row gutter={[16, 16]}>
        <Col xs={12} md={6}>
          <Card className="bg-background-card border border-white/5">
            <Statistic title="总资产" value={formatCurrency(account.totalEquity)} precision={2} />
            <Statistic title="可用资金" value={formatCurrency(account.available)} precision={2} />
          </Card>
        </Col>
        <Col xs={12} md={6}>
          <Card className="bg-background-card border border-white/5">
            <Statistic title="今日盈亏" value={account.todaysPnl} precision={2} valueStyle={{ color: COLORS.bull }} />
            <Statistic title="累计盈亏" value={account.cumulativePnl} precision={2} />
          </Card>
        </Col>
        <Col xs={12} md={6}>
          <Card className="bg-background-card border border-white/5">
            <Statistic title="胜率" value={account.winRate * 100} suffix="%" precision={2} />
            <Statistic title="风险暴露" value={account.riskExposure * 100} suffix="%" precision={2} />
          </Card>
        </Col>
      </Row>

      <Card className="bg-background-card border border-white/5" loading={loading}>
        <LivePriceChart />
      </Card>

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={10}>
          <SectionHeader title="实时持仓" />
          <div className="space-y-4">
            {positions.map((position) => (
              <PositionCard key={position.id} position={position} />
            ))}
          </div>
        </Col>
        <Col xs={24} lg={14}>
          <SectionHeader title="订单流水" />
          <Table
            columns={orderColumns}
            dataSource={orders}
            rowKey="id"
            size="small"
            pagination={{ pageSize: 6 }}
            scroll={{ x: true }}
            className="mt-4"
          />
        </Col>
      </Row>
    </section>
  )
}
