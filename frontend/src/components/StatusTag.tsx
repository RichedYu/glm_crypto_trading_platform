import { Tag } from 'antd'

export const StrategyStatusTag = ({ status }: { status: 'running' | 'stopped' | 'pending' }) => {
  switch (status) {
    case 'running':
      return <Tag color="green">运行中</Tag>
    case 'pending':
      return <Tag color="gold">待配置</Tag>
    default:
      return <Tag color="red">已停止</Tag>
  }
}

export const SeverityTag = ({ severity }: { severity: 'low' | 'medium' | 'high' }) => {
  const colors: Record<string, string> = {
    low: 'blue',
    medium: 'orange',
    high: 'red',
  }
  const labels: Record<string, string> = {
    low: '提醒',
    medium: '预警',
    high: '危险',
  }
  return <Tag color={colors[severity]}>{labels[severity]}</Tag>
}
