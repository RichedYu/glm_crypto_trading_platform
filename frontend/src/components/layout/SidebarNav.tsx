import { Menu } from 'antd'
import {
  AppstoreOutlined,
  FundProjectionScreenOutlined,
  RadarChartOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons'

const menuItems = [
  { key: 'trading', label: '交易监控', icon: <AppstoreOutlined /> },
  { key: 'sentiment', label: '市场情绪', icon: <ThunderboltOutlined /> },
  { key: 'strategy', label: '策略管理', icon: <FundProjectionScreenOutlined /> },
  { key: 'risk', label: '风险控制', icon: <RadarChartOutlined /> },
]

type Props = {
  onNavigate: (id: string) => void
}

export const SidebarNav = ({ onNavigate }: Props) => (
  <aside className="hidden lg:flex lg:flex-col w-64 bg-[#11151a]/95 border-r border-white/5">
    <div className="px-6 py-6 border-b border-white/5">
      <p className="text-xs text-gray-500 uppercase tracking-widest">GLM Trading</p>
      <p className="text-2xl font-semibold text-white mt-2">Mission Control</p>
    </div>
    <Menu
      theme="dark"
      mode="inline"
      selectable={false}
      items={menuItems}
      className="flex-1 bg-transparent border-0 [&_.ant-menu-item]:!my-1"
      onClick={({ key }) => onNavigate(key as string)}
    />
  </aside>
)
