# GLM 加密货币交易平台 · 前端可视化系统需求

> 构建一个专业级、实时交互的 Web 控制台，为 GLM 量化平台提供交易监控、市场情绪、策略管理与风控洞察。

---

## 🎯 项目概述

- **目标**：打造实时、模块化、可扩展的前端，使量化团队和运营能在一个界面中查看行情、策略、风控与情绪。
- **数据来源**：交易服务（/api/v1/…）、策略服务、情绪服务以及 WebSocket 市场流。
- **交付形式**：React + TypeScript + Vite SPA，配套 Storybook、API 对接文档和部署指南。

---

## 📋 技术栈

| 类别 | 选型 |
|------|------|
| 前端框架 | React 18+、TypeScript |
| 状态管理 | Zustand 或 Redux Toolkit（根据团队偏好） |
| UI 组件 | Ant Design 或 shadcn/ui（需支持暗色主题） |
| 样式系统 | Tailwind CSS（统一主题、快速开发） |
| 图表库 | TradingView Lightweight Charts、Recharts/ECharts |
| 数据层 | React Query（API + WebSocket 同步）、Axios |
| 实时通信 | Native WebSocket + 自定义 hooks |
| 构建工具 | Vite |
| 工具链 | ESLint、Prettier、Husky（Conventional Commits）、Storybook |

---

## 🧱 架构原则

1. **模块化**：按业务域组织（交易/情绪/策略/风控），每个模块自带 store、services、components。
2. **插件式扩展**：策略模块支持后续新增策略卡片、指标、回测视图。
3. **体验优先**：响应式布局、深色默认主题，可切换亮色；所有表格具备筛选/排序/导出。
4. **性能**：路由懒加载、虚拟列表、Web Worker 处理重计算、React Query 缓存。
5. **专业度**：遵守金融数据精度（价格 8 位、数量 4 位），指标链路清晰。

---

## 🎨 UI/UX 规范

- **主题色**：涨 `#00C087`、跌 `#FF4D4F`、主色 `#1890FF`、背景 `#0B0E11`/`#141414`。
- **布局**：1920×1080 桌面为主，平板 1024×768 自适应；顶栏 + 侧边导航 + 模块化网格。
- **组件规范**：
  - Loading/Skeleton 覆盖所有异步区域，空状态展示 friendly 文案。
  - 错误提示具备“重试/回退”操作。
  - 数据导出按钮支持 CSV/JSON。
- **关键指标**：PnL、Sharpe、Win Rate、Max Drawdown、风险暴露、情绪指数。

---

## 📊 功能模块

### 1. 交易监控仪表盘

- **实时持仓卡片**：交易对、方向、入场/当前价、未实现盈亏%、持仓时间；支持平仓、改止盈止损。
- **订单流水表**：时间、类型、方向、数量、价格、手续费、状态；筛选/排序/分页/导出。
- **实时 K 线图**：TradingView 图层，指标 (MA/MACD/RSI/BBands)、多周期、标注入场和止盈止损。
- **账户概览**：总资产、可用/冻结、今日/累计盈亏、胜率、风险暴露。
- **核心接口**：
  - `GET /api/v1/positions`
  - `GET /api/v1/orders?status=all`
  - `GET /api/v1/account/balance`
  - `POST /api/v1/orders/close`
  - `WS /ws/market/{symbol}`

### 2. 市场情绪分析

- **情绪指数仪表**：-100 ~ +100，显示当前值和 24h 变化。
- **情绪趋势图**：情绪 vs BTC 价格，关键事件标注。
- **热门话题榜**：话题、热度、倾向；点击展开 keywords/tweets。
- **AI 分析摘要**：GLM 生成 150 字总结 + 信号提示。
- **核心接口**：
  - `GET /api/v1/sentiment/current`
  - `GET /api/v1/sentiment/history?days=7`
  - `GET /api/v1/sentiment/topics/trending`
  - `GET /api/v1/sentiment/insights`

### 3. 策略管理中心

- **策略卡片**：展示 S1/S2… 状态、收益、胜率、交易次数；操作启停、编辑、详情。
- **参数配置面板**：动态表单（交易对、周期、风险比例等），含预设模板与实时校验。
- **回测结果**：净值曲线 vs 基准、Performance 表、时间轴交易明细。
- **策略对比**：收益曲线、雷达评分。
- **核心接口**：
  - `GET /api/v1/strategies`
  - `POST /api/v1/strategies/{id}/start|stop`
  - `PUT /api/v1/strategies/{id}/config`
  - `GET /api/v1/strategies/{id}/backtest`

### 4. 风险控制面板

- **风险雷达**：仓位/流动性/波动/集中度风险，颜色分级。
- **实时告警列表**：止损触发、仓位超限、系统异常、市场异动；支持标记/处理。
- **资金曲线**：净值面积图+回撤阴影，关键事件标记。
- **压力测试**：输入场景、输出损失/保证金/强平风险。
- **核心接口**：
  - `GET /api/v1/risk/metrics`
  - `GET /api/v1/risk/alerts?status=new`
  - `GET /api/v1/risk/equity-curve`
  - `POST /api/v1/risk/stress-test`

---

## 🗂 项目结构

```
frontend/
├── src/
│   ├── components/          # 通用组件 (charts/forms/layouts)
│   ├── modules/
│   │   ├── trading/
│   │   ├── sentiment/
│   │   ├── strategy/
│   │   └── risk/
│   ├── services/            # api.ts / websocket.ts / types.ts
│   ├── stores/              # Zustand/Redux slices
│   ├── hooks/               # useWebSocket/useRealTimeData/useChartData...
│   ├── utils/               # formatters/validators/calculations
│   └── App.tsx
├── public/
├── package.json
├── tsconfig.json
└── vite.config.ts
```

---

## 🧠 状态管理示例

```ts
// stores/trading.ts
import create from 'zustand'
import { api } from '@/services/api'

interface TradingState {
  positions: Position[]
  orders: Order[]
  balance: AccountBalance | null
  fetchPositions: () => Promise<void>
  closePosition: (id: string) => Promise<void>
}

export const useTradingStore = create<TradingState>((set) => ({
  positions: [],
  orders: [],
  balance: null,
  fetchPositions: async () => {
    const data = await api.get('/positions')
    set({ positions: data })
  },
  closePosition: async (id) => {
    await api.post('/orders/close', { position_id: id })
    await Promise.all([/* refresh positions/orders */])
  },
}))
```

---

## 🔌 WebSocket Hook

```ts
import { useEffect, useState } from 'react'

export const useMarketData = (symbol: string) => {
  const [price, setPrice] = useState<number>(0)

  useEffect(() => {
    const ws = new WebSocket(`${import.meta.env.VITE_WS_BASE}/ws/market/${symbol}`)
    ws.onmessage = (event) => {
      const payload = JSON.parse(event.data)
      setPrice(payload.price)
    }
    return () => ws.close()
  }, [symbol])

  return { price }
}
```

---

## 🪟 TradingView 图表配置

```ts
export const chartOptions = {
  layout: {
    background: { color: '#0B0E11' },
    textColor: '#D9D9D9',
  },
  grid: {
    vertLines: { color: '#1f2937' },
    horzLines: { color: '#1f2937' },
  },
  crosshair: { mode: CrosshairMode.Normal },
  timeScale: { timeVisible: true, secondsVisible: false },
}
```

---

## 🚀 开发阶段

| Phase | 内容 |
|-------|------|
| **MVP** | 交易仪表盘（持仓/订单/K 线）、基础布局、WebSocket 实时行情 |
| **Phase 2** | 情绪分析、策略管理、回测展示 |
| **Phase 3** | 风控面板、多策略对比、数据导出 |
| **Phase 4** | 性能优化、移动端适配、国际化 |

---

## ⚙️ 性能策略

- 路由懒加载，首屏 < 2s。
- `react-window` 虚拟列表。
- React Query 智能缓存与失效策略。
- 输入/滚动防抖节流。
- 重型技术指标搬到 WebWorker。

---

## 🔐 安全要求

1. JWT 存储于 HttpOnly Cookie，配套刷新策略。
2. 角色隔离：管理员 / 交易员 / 观察者。
3. API Key 永不下发到前端，只暴露必要数据。
4. XSS 防护，所有用户输入 sanitize。
5. 全站 HTTPS，严格 CSP。

---

## 📦 交付物

1. React + TS 源码（含 Lint/Format 配置）。
2. Storybook 组件文档。
3. API 调用示例与错误码说明。
4. 部署指南（Docker + Nginx）。
5. 用户手册与操作流程。

---

## 📋 注意事项

- 使用 `decimal.js` 处理金额。
- 时间统一 UTC，展示层再转换本地。
- 错误降级策略 & 重试提示。
- Skeleton/Empty 组件覆盖所有异步场景。
- 命名遵循驼峰（变量）/kebab-case（文件夹），提交遵循 Conventional Commits。

---

## 🎨 设计参考

- TradingView（图表与指标）
- Binance（订单面板）
- 3Commas（策略配置/回测）
- Grafana（实时仪表盘）

---

## 🤝 协作要求

- ESLint + Prettier + Husky 在提交前自动执行。
- 核心 Hooks/组件提供 JSDoc 注释。
- Jest + React Testing Library 覆盖关键逻辑。
- PR 需附截图或 Loom 视频展示交互。

---

> 期望效果：一个美观、专业、可靠的可视化 cockpit，为交易决策提供实时、可操作的数据洞察。
