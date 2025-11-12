import { ReactNode } from 'react'
import { Button, Space, Typography } from 'antd'
import { ReloadOutlined } from '@ant-design/icons'

type SectionHeaderProps = {
  title: string
  description?: string
  onRefresh?: () => void
  extra?: ReactNode
}

export const SectionHeader = ({ title, description, onRefresh, extra }: SectionHeaderProps) => (
  <div className="flex flex-wrap items-center justify-between gap-4">
    <div>
      <Typography.Title level={4} className="!text-white mb-0">
        {title}
      </Typography.Title>
      {description && <Typography.Text className="!text-gray-400">{description}</Typography.Text>}
    </div>
    <Space>
      {extra}
      {onRefresh && (
        <Button type="default" icon={<ReloadOutlined />} ghost onClick={onRefresh}>
          刷新
        </Button>
      )}
    </Space>
  </div>
)
