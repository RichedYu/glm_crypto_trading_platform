# 前后端 API 映射验证文档

## 文档概述

本文档验证前端可视化组件与后端 API 的字段映射关系，确保数据流的正确性。

创建时间：2025-11-27 23:12:00

---

## 1. Options Panel - P-Q 波动率面板

### 前端接口定义

**文件**: [`frontend/src/services/optionsApi.ts`](../frontend/src/services/optionsApi.ts:6-19)

```typescript
export interface PQSpreadData {
  underlying: string;
  p_vol: number;
  q_vol: number;
  spread: number;
  signal: string;
  confidence: number;
  intent_type?: string; // ✅ 策略意图类型
  intent_reason?: string; // ✅ 意图原因
  macro_regime?: string; // ✅ 宏观周期
  regime_score?: number; // ✅ 周期强度
  fomo_score?: number; // ✅ FOMO 指标
  timestamp: string;
}
```

### 后端 API 实现

**文件**: [`services/trading_service/app/api/options_api.py`](../services/trading_service/app/api/options_api.py:48-76)

**端点**: `GET /api/v1/options/pq-spread/{underlying}`

**返回字段**:

```python
{
    "underlying": underlying,
    "p_vol": 0.65,
    "q_vol": 0.72,
    "spread": 0.07,
    "signal": "buy_volatility",
    "confidence": 0.85,
    "intent_type": intent_type,        # ✅ 对应前端
    "intent_reason": intent_reason,    # ✅ 对应前端
    "macro_regime": macro_regime,      # ✅ 对应前端
    "regime_score": regime_score,      # ✅ 对应前端
    "fomo_score": fomo_score,          # ✅ 对应前端
    "timestamp": datetime.utcnow().isoformat()
}
```

### 前端展示逻辑

**文件**: [`frontend/src/modules/options/OptionsPanel.tsx`](../frontend/src/modules/options/OptionsPanel.tsx:322-344)

```tsx
<Card size="small" title="策略意图">
  <div>
    <strong>{pqSpread.intent_type || "保持观望"}</strong>
  </div>
  <div style={{ color: "#8c8c8c", marginTop: 4 }}>
    {pqSpread.intent_reason || "暂无原因"}
  </div>
</Card>

<Card size="small" title="宏观 / FOMO 状态">
  <div>
    宏观: {pqSpread.macro_regime || "unknown"} ·
    强度 {(pqSpread.regime_score ?? 0).toFixed(2)}
  </div>
  <div style={{ marginTop: 4 }}>
    FOMO 指标: {(pqSpread.fomo_score ?? 0).toFixed(2)}
  </div>
</Card>
```

**验证结果**: ✅ **完全对应，字段一致**

---

## 2. Portfolio Greeks - 组合风险指标

### 前端接口定义

**文件**: [`frontend/src/services/optionsApi.ts`](../frontend/src/services/optionsApi.ts:21-29)

```typescript
export interface PortfolioGreeks {
  total_delta: number;
  total_gamma: number;
  total_vega: number;
  total_theta: number;
  total_rho: number;
  timestamp: string;
  hedge_status: string;
}
```

### 后端 API 实现

**文件**: [`services/trading_service/app/api/options_api.py`](../services/trading_service/app/api/options_api.py:79-102)

**端点**: `GET /api/v1/options/greeks/portfolio`

**返回字段**:

```python
{
    "total_delta": risk_metrics.get("total_delta", 0.0),   # ✅
    "total_gamma": risk_metrics.get("total_gamma", 0.0),   # ✅
    "total_vega": risk_metrics.get("total_vega", 0.0),     # ✅
    "total_theta": risk_metrics.get("total_theta", 0.0),   # ✅
    "total_rho": risk_metrics.get("total_rho", 0.0),       # ✅
    "timestamp": risk_metrics.get("updated_at"),           # ✅
    "hedge_status": "neutral" if ... else "needs_hedge"    # ✅
}
```

### 前端展示逻辑

**文件**: [`frontend/src/modules/options/OptionsPanel.tsx`](../frontend/src/modules/options/OptionsPanel.tsx:160-207)

```tsx
<Card title="组合风险总览 (Portfolio Risk Overview)">
  <Statistic title="Delta (总敞口)" value={riskOverview.total_delta} />
  <Statistic title="Gamma" value={riskOverview.total_gamma} />
  <Statistic title="Vega" value={riskOverview.total_vega} />
  <Statistic title="Theta" value={riskOverview.total_theta} />
  <Statistic title="Rho" value={riskOverview.total_rho} />
</Card>
```

**验证结果**: ✅ **完全对应，字段一致**

---

## 3. Hedge Status - Delta 对冲状态

### 前端接口定义

**文件**: [`frontend/src/services/optionsApi.ts`](../frontend/src/services/optionsApi.ts:46-52)

```typescript
export interface HedgeStatus {
  total_delta: number;
  status: string;
  recommended_action: string;
  hedge_quantity: number;
  timestamp: string;
}
```

### 后端 API 实现

**文件**: [`services/trading_service/app/api/options_api.py`](../services/trading_service/app/api/options_api.py:135-171)

**端点**: `GET /api/v1/options/hedge/status`

**返回字段**:

```python
{
    "total_delta": total_delta,                    # ✅
    "status": status,                              # ✅
    "recommended_action": action,                  # ✅
    "hedge_quantity": abs(total_delta) if ...,     # ✅
    "timestamp": datetime.utcnow().isoformat()     # ✅
}
```

### 前端展示逻辑

**文件**: [`frontend/src/modules/options/OptionsPanel.tsx`](../frontend/src/modules/options/OptionsPanel.tsx:209-257)

```tsx
<Alert
  message={`对冲状态: ${hedgeStatus.status}`}
  description={`建议操作: ${hedgeStatus.recommended_action}`}
  type={getHedgeStatusColor(hedgeStatus.status)}
/>
<Statistic
  title="总Delta敞口"
  value={hedgeStatus.total_delta}
/>
```

**验证结果**: ✅ **完全对应，字段一致**

---

## 4. Option Positions - 期权持仓明细

### 前端接口定义

**文件**: [`frontend/src/services/optionsApi.ts`](../frontend/src/services/optionsApi.ts:31-44)

```typescript
export interface OptionPosition {
  symbol: string;
  quantity: number;
  avg_price: number;
  unrealized_pnl: number;
  greeks: {
    delta?: number;
    gamma?: number;
    theta?: number;
    vega?: number;
    rho?: number;
  };
  strategy_id: string;
}
```

### 后端 API 实现

**文件**: [`services/trading_service/app/api/options_api.py`](../services/trading_service/app/api/options_api.py:105-132)

**端点**: `GET /api/v1/options/positions/options`

**返回字段**:

```python
{
    "symbol": symbol,                              # ✅
    "quantity": pos["quantity"],                   # ✅
    "avg_price": pos["avg_price"],                 # ✅
    "unrealized_pnl": pos.get("unrealized_pnl"),   # ✅
    "greeks": pos.get("greeks", {}),               # ✅
    "strategy_id": pos.get("strategy_id")          # ✅
}
```

### 前端展示逻辑

**文件**: [`frontend/src/modules/options/OptionsPanel.tsx`](../frontend/src/modules/options/OptionsPanel.tsx:97-151)

表格列定义完全对应后端返回字段。

**验证结果**: ✅ **完全对应，字段一致**

---

## 5. Risk Panel - 风险控制面板

### 前端 Store

**文件**: [`frontend/src/stores/riskStore.ts`](../frontend/src/stores/riskStore.ts)

风险指标通过 `useRiskStore` 管理：

- `metrics.position` (仓位风险)
- `metrics.liquidity` (流动性风险)
- `metrics.volatility` (波动率风险)
- `metrics.concentration` (集中度风险)

### 后端对应

风险指标来自 [`RiskService`](../services/trading_service/app/risk/risk_service.py) 与 [`PortfolioStateStore`](../services/trading_service/app/state/portfolio_store.py)

**验证结果**: ✅ **架构支持，需确保 RiskService 实时广播风险指标到 Redis**

---

## 6. Strategy Center - 策略管理中心

### 前端 Store

**文件**: [`frontend/src/stores/strategyStore.ts`](../frontend/src/stores/strategyStore.ts)

策略状态包含：

- `strategies[]` (策略列表)
- `backtests[]` (回测结果)

### 后端对应

策略状态通过 [`StrategyEngine`](../services/trading_service/app/strategies/engine.py) 管理，可通过以下端点获取：

- `GET /api/v1/options/strategies/pq-trader/state`
- `GET /api/v1/options/strategies/delta-hedger/state`

**验证结果**: ✅ **端点已定义，需完善策略状态序列化逻辑**

---

## 总结

### ✅ 已验证对应的组件

1. **OptionsPanel** - P-Q 波动率面板

   - 所有字段完全对应
   - Intent、macro_regime、fomo_score 正确展示

2. **Portfolio Greeks** - 组合风险指标

   - total_delta/gamma/vega/theta/rho 完全对应

3. **Hedge Status** - Delta 对冲状态

   - status、recommended_action、hedge_quantity 完全对应

4. **Option Positions** - 期权持仓明细
   - 表格展示与后端字段完全一致

### ⚠️ 需要完善的部分

1. **RiskPanel** - 风险指标实时更新

   - 后端需确保 RiskService 通过 Redis Streams 广播 `portfolio.risk` 事件
   - 前端需订阅该事件流实时更新

2. **StrategyCenter** - 策略状态同步
   - 后端策略状态序列化逻辑需完善
   - 考虑通过 WebSocket 推送策略状态变更

### 📋 建议改进

1. **统一事件格式**：确保所有事件（market.tick, strategy.signal, portfolio.risk）使用统一的时间戳格式
2. **WebSocket 推送**：对于高频更新的数据（Greeks、Delta），建议使用 WebSocket 而非轮询
3. **错误处理**：前端需增加对 API 失败的降级处理

---

2025-11-27 23:12:00 - 前后端 API 映射验证完成，核心字段完全对应
