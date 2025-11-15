# Gamma Scalping 架构完整指南

## 概述

本文档描述 GLM 加密货币交易平台的 Gamma Scalping 实现,包括 P-Q 量化框架、Delta 对冲机制和前后端集成。

## 核心概念

### P-World vs Q-World

- **P-World (市场在想什么)**: 从期权市场价格反算的隐含波动率(Implied Volatility)
- **Q-World (模型认为会发生什么)**: GLM 模型基于宏观/情绪数据预测的未来波动率
- **交易逻辑**: 当 Q > P + 阈值时,市场低估波动率,买入期权;反之卖出

### Gamma Scalping

Gamma Scalping 是通过 Delta 对冲实现的波动率套利策略:

1. **持有 Long Gamma 仓位**(如买入跨式期权)
2. **价格上涨** → Gamma 使 Delta 变正 → **卖出期货对冲** → 高位卖出
3. **价格下跌** → Delta 变负 → **买入期货对冲** → 低位买入
4. **自动"高卖低买"** → 赚取波动率利润

## 系统架构

```
┌─────────────────────────────────────────────────────────────────┐
│                    Message Bus (Redis Streams)                   │
│  market.tick | market.vol_surface | strategy.signal |           │
│  strategy.forecast.volatility | order.command | order.fill |    │
│  risk.alert | position.update                                   │
└─────────────────────────────────────────────────────────────────┘
         ▲              ▲                    ▲
         │              │                    │
    ┌────┴────┐   ┌─────┴──────┐      ┌─────┴──────┐
    │ Market  │   │  Options   │      │ Strategy   │
    │ Adapter │   │  Adapter   │      │ Service    │
    │         │   │ (P-World)  │      │ (Q-World)  │
    └─────────┘   └────────────┘      └────────────┘
                                             │
         ┌───────────────────────────────────┘
         │
    ┌────▼─────────────────────────────────────────┐
    │         Strategy Engine                      │
    │  ┌──────────┐  ┌──────────┐  ┌───────────┐ │
    │  │ PQ Vol   │  │  Delta   │  │   Grid    │ │
    │  │ Trader   │  │  Hedger  │  │ Strategy  │ │
    │  └──────────┘  └──────────┘  └───────────┘ │
    └───────────────────┬──────────────────────────┘
                        │
                   ┌────▼────┐
                   │  Risk   │ ◄── Pre-Order Veto
                   │ Service │ ◄── Greeks计算
                   └────┬────┘
                        │
                   ┌────▼────────────┐
                   │ Portfolio Store │
                   │  (Redis State)  │
                   │  - Positions    │
                   │  - Greeks       │
                   │  - total_delta  │
                   └─────────────────┘
                        │
                   ┌────▼────────────┐
                   │   Frontend      │
                   │ OptionsPanel    │
                   │  - P-Q价差      │
                   │  - Delta状态    │
                   │  - Greeks仪表盘 │
                   └─────────────────┘
```

## 完整工作流程

### 1. 市场数据采集

**OptionsChainAdapter** (P-World):

```python
# services/trading_service/app/adapters/options_adapter.py
- 拉取期权合约价格
- Black-Scholes反算IV
- 计算Greeks (Delta, Gamma, Vega, Theta, Rho)
- 构建波动率曲面
- 发布到 market.vol_surface
```

**StrategyService** (Q-World):

```python
# services/strategy_service/ (待实现)
- 订阅sentiment_service情绪数据
- 订阅宏观经济数据
- GLM模型预测未来波动率
- 发布到 strategy.forecast.volatility
```

### 2. P vs Q 策略决策

**PQVolTraderStrategy**:

```python
# services/trading_service/app/strategies/pq_vol_trader.py

async def on_volatility_surface(vol_surface):
    self.latest_p_vol = vol_surface.atm_iv  # 更新P值

async def on_volatility_forecast(forecast):
    self.latest_q_vol = forecast.predicted_volatility  # 更新Q值

async def _check_pq_spread():
    pq_spread = self.latest_q_vol - self.latest_p_vol

    if pq_spread > self.vol_threshold:
        # 市场低估波动率,买入跨式
        return StrategySignalEvent(
            signal_type="buy",
            metadata={"action": "buy_straddle"}
        )
```

### 3. 期权执行转换

**OptionExecutionService**:

```python
# services/trading_service/app/execution/option_execution_service.py

async def _execute_straddle(signal, side):
    # 从波动率曲面找ATM期权
    atm_options = self._find_atm_options(vol_surface)

    # 生成Call和Put订单
    for option in atm_options:  # [Call, Put]
        order_command = OrderCommand(
            symbol=self._format_option_symbol(option),
            side=side,
            quantity=0.1
        )
        await self.message_bus.publish("order.command", order_command)
```

### 4. 风控检查

**RiskService Pre-Order Veto**:

```python
# services/trading_service/app/risk/risk_service.py

async def check_pre_order(strategy_id, symbol, side, quantity, price):
    # 1. 检查回撤
    drawdown_check = await self._check_drawdown()
    if not drawdown_check.approved:
        return drawdown_check

    # 2. 检查仓位限制
    position_check = await self._check_position_limits()

    # 3. 模拟订单影响
    simulated_check = await self._simulate_order_impact(...)

    return RiskCheckResult(approved=True)
```

### 5. 订单执行与 Greeks 更新

**订单成交后**:

```python
# RiskService._process_fill()

async def _process_fill(fill):
    # 更新持仓
    await self.portfolio_store.update_position(...)

    # 计算Greeks
    greeks = await self._calculate_position_greeks(symbol, position)

    # 更新风险指标(包括total_delta)
    await self._update_risk_metrics()
    # → total_delta = sum(所有持仓的delta)
```

### 6. Delta 对冲触发

**DeltaHedgerStrategy**:

```python
# services/trading_service/app/strategies/delta_hedger.py

async def _poll_delta():
    while self._running:
        # 从portfolio_store获取total_delta
        total_delta = await self.portfolio_store.get_total_delta()

        # 检查是否需要对冲
        if abs(total_delta) > self.delta_threshold:
            # Delta为正 → 卖出期货
            # Delta为负 → 买入期货
            hedge_quantity = -total_delta

            signal = StrategySignalEvent(
                signal_type="buy" if hedge_quantity > 0 else "sell",
                symbol=self.hedge_instrument,  # BTC/USDT:USDT永续
                metadata={"action": "delta_hedge"}
            )

        await asyncio.sleep(self.rebalance_interval)
```

### 7. 前端实时监控

**OptionsPanel 组件**:

```typescript
// frontend/src/modules/options/OptionsPanel.tsx

useEffect(() => {
  const fetchData = async () => {
    // 获取P-Q价差
    const pqData = await optionsApi.getPQSpread("BTC/USDT");

    // 获取Greeks
    const greeksData = await optionsApi.getPortfolioGreeks();

    // 获取对冲状态
    const hedgeData = await optionsApi.getHedgeStatus();

    // 更新UI
    setPQSpread(pqData);
    setGreeks(greeksData);
    setHedgeStatus(hedgeData);
  };

  fetchData();
  const interval = setInterval(fetchData, 5000); // 5秒刷新
  return () => clearInterval(interval);
}, []);
```

## API 端点详解

### 后端 API

| 端点                                              | 方法 | 描述            | 返回数据                          |
| ------------------------------------------------- | ---- | --------------- | --------------------------------- |
| `/api/v1/options/pq-spread/{underlying}`          | GET  | P-Q 价差        | `{p_vol, q_vol, spread, signal}`  |
| `/api/v1/options/greeks/portfolio`                | GET  | 投资组合 Greeks | `{total_delta, total_gamma, ...}` |
| `/api/v1/options/hedge/status`                    | GET  | Delta 对冲状态  | `{total_delta, status, action}`   |
| `/api/v1/options/positions/options`               | GET  | 期权持仓        | `{positions: [...]}`              |
| `/api/v1/options/volatility-surface/{underlying}` | GET  | 波动率曲面      | `{atm_iv, surface_data}`          |

### 前端服务

```typescript
// frontend/src/services/optionsApi.ts

class OptionsApiService {
  async getPQSpread(underlying: string): Promise<PQSpreadData>;
  async getPortfolioGreeks(): Promise<PortfolioGreeks>;
  async getHedgeStatus(): Promise<HedgeStatus>;
  async getOptionPositions(): Promise<{ positions: OptionPosition[] }>;
  async getVolatilitySurface(underlying: string): Promise<VolatilitySurface>;
}
```

## 关键配置

### DeltaHedger 配置

```python
{
    "underlying": "BTC/USDT",
    "hedge_instrument": "BTC/USDT:USDT",  # 永续合约
    "delta_threshold": 0.05,  # Delta阈值
    "rebalance_interval": 60  # 重新平衡间隔(秒)
}
```

### PQVolTrader 配置

```python
{
    "underlying": "BTC/USDT",
    "vol_threshold": 0.05,  # 5%波动率差异阈值
    "forecast_horizon": "24h",
    "max_position_size": 1.0
}
```

### RiskService 配置

```python
{
    "max_drawdown_pct": 0.20,  # 最大回撤20%
    "max_position_ratio": 0.80,  # 最大仓位80%
    "min_position_ratio": 0.10,  # 最小底仓10%
    "max_single_position_pct": 0.30  # 单个持仓最大30%
}
```

## 监控指标

### 关键指标

1. **P-Q 价差**: 市场 IV vs 预测波动率的差异
2. **total_delta**: 投资组合总 Delta 敞口
3. **对冲频率**: 每日 Delta 对冲次数
4. **Gamma PnL**: Gamma Scalping 产生的盈亏
5. **Greeks**: Delta, Gamma, Vega, Theta, Rho

### 告警阈值

- `|total_delta| > 0.10`: 需要立即对冲
- `drawdown > 15%`: 风险告警
- `position_ratio > 75%`: 仓位告警

## 性能优化

1. **Redis 缓存**: 波动率曲面缓存 60 秒
2. **Greeks 计算**: 仅在持仓变化时重新计算
3. **批量更新**: 多个持仓 Greeks 一次性更新
4. **异步处理**: 所有 IO 操作异步化

## 故障处理

### 常见问题

1. **total_delta 计算不准确**

   - 检查期权 Greeks 是否正确计算
   - 验证持仓数据是否同步

2. **对冲延迟**

   - 检查 DeltaHedger 轮询间隔
   - 验证消息总线连接

3. **前端数据不更新**
   - 检查 API 端点是否正常
   - 验证 WebSocket 连接(如使用)

## 下一步扩展

1. **实时 Greeks 更新**: 订阅市场数据实时重算
2. **多标的支持**: 同时交易 BTC/ETH 等多个标的
3. **高级策略**: Butterfly, Iron Condor 等
4. **机器学习优化**: 动态调整对冲阈值
5. **回测框架**: 历史数据验证策略有效性

## 总结

本系统实现了完整的 Gamma Scalping 基础设施:

- ✅ P-Q 量化框架
- ✅ 自动 Delta 对冲
- ✅ 实时 Greeks 计算
- ✅ Pre-Order 风控
- ✅ 前后端监控

可以开始实盘测试和策略优化!
