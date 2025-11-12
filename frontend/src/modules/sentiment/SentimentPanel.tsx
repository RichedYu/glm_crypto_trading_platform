import { useEffect } from 'react'
import { Card, List, Space, Tag, Typography } from 'antd'
import {
  Area,
  AreaChart,
  CartesianGrid,
  Line,
  LineChart,
  RadialBar,
  RadialBarChart,
  ResponsiveContainer,
  Tooltip as RechartsTooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { useSentimentStore } from '../../stores/sentimentStore'
import { SectionHeader } from '../../components/SectionHeader'
import { COLORS, SENTIMENT_SCALE } from '../../utils/constants'

const sentimentColor = (value: number) => {
  if (value > 20) return COLORS.bull
  if (value < -20) return COLORS.bear
  return '#facc15'
}

export const SentimentPanel = () => {
  const { snapshot, loading, refresh } = useSentimentStore()

  useEffect(() => {
    refresh()
  }, [refresh])

  if (!snapshot) {
    return (
      <section id="sentiment">
        <SectionHeader title="市场情绪" description="实时情绪指数、热门话题、AI 摘要" onRefresh={refresh} />
        <Card loading={loading} className="bg-background-card border border-white/5 mt-4">
          数据加载中...
        </Card>
      </section>
    )
  }

  return (
    <section id="sentiment" className="space-y-6">
      <SectionHeader title="市场情绪" description="实时情绪指数、热门话题、AI 摘要" onRefresh={refresh} />

      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="bg-background-card border border-white/5" loading={loading}>
          <Typography.Title level={5} className="!text-gray-300">
            情绪指数
          </Typography.Title>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <RadialBarChart
                startAngle={180}
                endAngle={0}
                innerRadius="60%"
                outerRadius="100%"
                data={[
                  {
                    name: 'Sentiment',
                    value: snapshot.value - SENTIMENT_SCALE.min,
                    fill: sentimentColor(snapshot.value),
                  },
                ]}
              >
                <RadialBar
                  minAngle={15}
                  cornerRadius={30}
                  clockWise
                  dataKey="value"
                  fill={sentimentColor(snapshot.value)}
                />
                <RechartsTooltip />
              </RadialBarChart>
            </ResponsiveContainer>
            <div className="text-center mt-2">
              <p className="text-3xl font-semibold">{snapshot.value}</p>
              <p className="text-gray-400 text-sm">24h 变化 {snapshot.delta24h > 0 ? '+' : ''}{snapshot.delta24h}</p>
            </div>
          </div>
        </Card>

        <Card className="bg-background-card border border-white/5 lg:col-span-2" loading={loading}>
          <Typography.Title level={5} className="!text-gray-300">
            情绪趋势 vs BTC
          </Typography.Title>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedSentimentChart
                data={snapshot.trend}
                sentimentColor={sentimentColor(snapshot.value)}
              />
            </ResponsiveContainer>
          </div>
        </Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card className="bg-background-card border border-white/5" title="热门话题" loading={loading}>
          <List
            itemLayout="vertical"
            dataSource={snapshot.topics}
            renderItem={(topic) => (
              <List.Item>
                <List.Item.Meta
                  title={
                    <Space>
                      <span className="text-white">{topic.name}</span>
                      <Tag color={topic.sentiment === 'positive' ? 'green' : topic.sentiment === 'negative' ? 'red' : 'gold'}>
                        {topic.sentiment}
                      </Tag>
                    </Space>
                  }
                  description={
                    <div className="text-gray-400 text-sm">
                      热度 {topic.volume.toLocaleString()} · 关键词：{topic.keywords.join(', ')}
                    </div>
                  }
                />
                <p className="text-gray-300 text-sm">{topic.sampleTweet}</p>
              </List.Item>
            )}
          />
        </Card>

        <Card className="bg-background-card border border-white/5" title="AI 分析摘要" loading={loading}>
          <Typography.Paragraph className="text-gray-200 leading-relaxed">
            {snapshot.insight}
          </Typography.Paragraph>
          <Typography.Text type="secondary">更新时间：{snapshot.updatedAt}</Typography.Text>
        </Card>
      </div>
    </section>
  )
}

const ComposedSentimentChart = ({
  data,
  sentimentColor,
}: {
  data: Array<{ time: string; sentiment: number; price: number }>
  sentimentColor: string
}) => (
  <ResponsiveContainer width="100%" height="100%">
    <AreaChart data={data}>
      <defs>
        <linearGradient id="sentimentGradient" x1="0" y1="0" x2="0" y2="1">
          <stop offset="5%" stopColor={sentimentColor} stopOpacity={0.6} />
          <stop offset="95%" stopColor={sentimentColor} stopOpacity={0} />
        </linearGradient>
      </defs>
      <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
      <XAxis dataKey="time" stroke="#6b7280" />
      <YAxis yAxisId="sentiment" stroke="#6b7280" />
      <YAxis yAxisId="price" orientation="right" stroke="#6b7280" />
      <RechartsTooltip />
      <Area yAxisId="sentiment" type="monotone" dataKey="sentiment" stroke={sentimentColor} fill="url(#sentimentGradient)" />
      <Line yAxisId="price" type="monotone" dataKey="price" stroke="#38bdf8" strokeWidth={2} dot={false} />
    </AreaChart>
  </ResponsiveContainer>
)
