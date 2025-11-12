import { Button, Space } from 'antd'
import { BulbOutlined, CloudSyncOutlined } from '@ant-design/icons'
import dayjs from 'dayjs'

type Props = {
  onToggleTheme: () => void
  lastUpdated?: string
}

export const TopBar = ({ onToggleTheme, lastUpdated }: Props) => (
  <header className="sticky top-0 z-30 backdrop-blur bg-[#0b0e11]/80 border-b border-white/5 px-4 md:px-8 py-4 flex items-center justify-between">
    <Space direction="vertical" size={0}>
      <span className="text-xs uppercase tracking-[0.3em] text-gray-500">Realtime Crypto Cockpit</span>
      <span className="text-xl font-semibold text-white">GLM 量化控制台</span>
    </Space>
    <Space size="middle">
      <span className="hidden md:flex items-center gap-2 text-gray-400 text-sm">
        <CloudSyncOutlined />
        {lastUpdated ? dayjs(lastUpdated).format('YYYY-MM-DD HH:mm') : '未同步'}
      </span>
      <Button icon={<BulbOutlined />} onClick={onToggleTheme}>
        切换主题
      </Button>
    </Space>
  </header>
)
