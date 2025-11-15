# GLM Crypto Trading Platform - 策略意图架构升级报告

## 1. 文档概览

- 创建日期：2025-11-14
- 版本：v1.0
- 适用模块：
  - 后端：trading_service / strategy_service / sentiment_yyservice
  - 前端：Gamma 交易控制台（Options / Risk / Strategy 模块）
- 相关文档：
  - [`docs/gamma_scalping_architecture.md`](docs/gamma_scalping_architecture.md)
  - [`docs/architecture_decoupling.md`](docs/architecture_decoupling.md)

本报告总结了近期围绕 Gamma Scalping / P-Q 波动率交易框架所做的关键架构升级，包括：

1. 策略层从「被动信号 → 下单」升级为「状态 → 意图 → 执行」的三层结构。
2. 风控层引入组合杠杆与 FOMO/杀猪盘防御机制。
3. 宏观 Q（macro regime）与情绪引擎的接入设计。
4. 前端专业化看板（Options / Risk / Strategy）对这些改动的支撑方式。
5. 后续演进路线与迭代展望。

---

## 2. 原有架构与痛点

### 2.1 原有策略链路（简化）

- 核心策略：`PQVolTrader`  
  文件：[`services/trading_service/app/strategies/pq_vol_trader.py`](services/trading_service/app/strategies/pq_vol_trader.py:1)

原有链路大致为：

```text
行情 / 预测 → PQVolTrader._check_pq_spread() → StrategySignalEvent → RiskService → 执行层
```

主要特点：

1. **直接从条件判断到信号**

   - `_check_pq_spread()` 根据 `p_vol` / `q_vol` 差值直接返回 `StrategySignalEvent`（buy/sell）。
   - 逻辑集中在若干阈值判断上（如 `pq_spread > vol_threshold`）。

2. **状态分散**

   - 与决策相关的信息（P/Q、最近信号时间、仓位、情绪等）散落在多个成员变量，缺乏统一抽象。
   - 新增决策维度（如 FOMO、宏观 regime）需要在多处改动代码。

3. **缺乏语义化意图层**

   - 外界只看到 buy/sell 信号，无法表达「提高 Long Gamma 敞口」「从进攻转为防守」等高层意图。
   - 前端和风控难以直观展示策略真正的“意图”。

4. **Web3 场景下的局限**
   - 对杀猪盘/喊单类风险缺乏专门防御逻辑。
   - 宏观周期（牛/熊/恐慌）尚未系统整合到策略决策。
   - 杠杆与集中度风险更多在账户/下单层处理，策略自身缺少「自我约束」。

---

## 3. 本次关键改进总结

### 3.1 策略层：引入“状态 → 意图 → 信号”结构

在 `PQVolTrader` 内部完成了一轮不破坏外部接口的重构，核心改动包括：

1. 新增 `MarketState` 数据结构，统一聚合决策所需状态。
2. 新增 `_build_market_state()`：从内部字段构建 `MarketState`。
3. 新增 `_decide_intent(state)`：基于 `MarketState` 决定高层“意图”。
4. 重构 `_check_pq_spread()`：
   - 冷却检查 → 状态聚合 → 意图决策 → Intent → `StrategySignalEvent` 映射。
   - 对外仍然返回 `StrategySignalEvent`，保持兼容。

### 3.2 风控层：组合杠杆 & FOMO 防御

在 `RiskService` 中落地了组合杠杆与风险约束逻辑：

- 组合级 `gross_notional / portfolio_value` 控制整体杠杆。
- 结合 PnL、Delta、Gamma 限制极端加仓行为。
- 在 FOMO 极端场景下对订单进行 veto（拒绝或限额）。

同时，策略侧增加 FOMO 维度的意图防御层（在 `_decide_intent` 中）：  
当 `fomo_score` 超过阈值时，强制返回 `hold` 意图，避免“追涨杀跌”。

### 3.3 宏观 & 情绪：预留统一接入点

- 在 `PQVolTrader` 中为 `macro_regime` / `regime_score` / `latest_sentiment_score` 等字段预留通道。
- 未来可以从 `strategy_service` 的 GLM 模型输出、`sentiment_service` 的情绪模型直接填充进入 `MarketState`。
- 意图决策器 `_decide_intent` 已经预留宏观/情绪逻辑分支，方便逐步丰富。

### 3.4 前端：专业化 Gamma 控制台（规划中）

- Options Panel 将重构为“三层信息架构”：
  1. 组合级风险总览（Delta / Gamma / Vega / 杠杆 / 回撤）。
  2. Gamma 控制台：展示 P/Q、intent、macro regime、FOMO 等，并显示当前意图。
  3. 期权明细 & 执行细节：显示各合约与对应的执行结果。

当前已经完成与后端 API 的路径、字段对齐设计，下一步会在前端代码中落地。

---

## 4. 策略意图架构设计详解

### 4.1 MarketState：统一状态容器

位置：[`services/trading_service/app/strategies/pq_vol_trader.py`](services/trading_service/app/strategies/pq_vol_trader.py:1)

```python
from dataclasses import dataclass

@dataclass
class MarketState:
    """
    策略内部使用的聚合状态，统一把 P/Q、宏观 Q、情绪/FOMO 和风险信息放在一起。
    """
    underlying: str

    # 波动率相关（P vs Q 框架）
    p_vol: Optional[float]
    q_vol: Optional[float]
    pq_spread: Optional[float]

    # 宏观 regime（由 strategy_service 提供）
    macro_regime: Optional[str] = None
    regime_score: float = 0.0

    # 情绪/FOMO（由 sentiment_service 提供）
    sentiment_score: Optional[float] = None
    fomo_score: Optional[float] = None

    # 组合风险（由 RiskService / PortfolioStateStore 提供）
    total_delta: Optional[float] = None
    total_gamma: Optional[float] = None
    leverage: Optional[float] = None
    drawdown_pct: Optional[float] = None
```

设计要点：

- 所有与决策相关的维度统一放入 `MarketState`，避免逻辑散落。
- 各维度来源清晰：P/Q 来自价格与模型，宏观来自 `strategy_service`，情绪来自 `sentiment_service`，风险来自组合状态。
- 新增决策维度，只需扩展数据类与构建逻辑，不需大规模重构。

### 4.2 `_build_market_state()`：状态聚合入口

```python
def _build_market_state(self) -> Optional[MarketState]:
    """聚合当前已知的 P/Q、宏观信息、情绪和风险状态。"""
    if self.latest_p_vol is None or self.latest_q_vol is None:
        return None

    pq_spread = self.latest_q_vol - self.latest_p_vol

    state = MarketState(
        underlying=self.underlying,
        p_vol=self.latest_p_vol,
        q_vol=self.latest_q_vol,
        pq_spread=pq_spread,
        macro_regime=self.macro_regime,
        regime_score=self.regime_score,
        sentiment_score=self.latest_sentiment_score,
        fomo_score=self.latest_fomo_score,
        total_delta=None,   # 预留：后续接组合状态
        total_gamma=None,
        leverage=None,
        drawdown_pct=None,
    )
    return state
```

意义：

- **将“读状态”的责任集中**：所有状态读取、计算逻辑集中于此，降低耦合。
- **Explicit is better than implicit**：调用方不再直接访问一堆成员变量，而是使用一个显式的 `state` 对象。

### 4.3 `_decide_intent(state)`：意图决策器

```python
def _decide_intent(self, state: MarketState) -> Optional[Dict[str, Any]]:
    """
    意图决策器：根据 MarketState 决定当前应该采取的高层动作。
    返回：
      - intent_type: "increase_long_gamma" / "increase_short_gamma" / "hold" / ...
      - direction: "buy" / "sell" / None
      - reason: 字符串，便于日志与回测
      - metadata: 附加上下文
    """

    if state.p_vol is None or state.q_vol is None or state.pq_spread is None:
        return None

    pq_spread = state.pq_spread

    # 日志：完整打印当前状态
    self.logger.info(
        "状态评估 | P: %.2f%% | Q: %.2f%% | PQ差: %+0.2f%% | macro_regime=%s | "
        "regime_score=%.2f | fomo_score=%s",
        state.p_vol * 100,
        state.q_vol * 100,
        pq_spread * 100,
        state.macro_regime or "unknown",
        state.regime_score,
        f"{state.fomo_score:.3f}" if state.fomo_score is not None else "None",
    )

    # ① FOMO 防御：极端情绪下强制 HOLD
    if (
        state.fomo_score is not None
        and self.max_fomo_score is not None
        and state.fomo_score > self.max_fomo_score
    ):
        return {
            "intent_type": "hold",
            "direction": None,
            "reason": "high_fomo_risk",
            "metadata": {"fomo_score": state.fomo_score},
        }

    # ② P/Q 主逻辑：Q > P → 做多波动率
    if pq_spread > self.vol_threshold and self.current_position < self.max_position_size:
        return {
            "intent_type": "increase_long_gamma",
            "direction": "buy",
            "reason": "market_underpricing_volatility",
            "metadata": {
                "pq_spread": pq_spread,
                "macro_regime": state.macro_regime,
                "regime_score": state.regime_score,
            },
        }

    # Q < P → 做空波动率
    if pq_spread < -self.vol_threshold and self.current_position > -self.max_position_size:
        return {
            "intent_type": "increase_short_gamma",
            "direction": "sell",
            "reason": "market_overpricing_volatility",
            "metadata": {
                "pq_spread": pq_spread,
                "macro_regime": state.macro_regime,
                "regime_score": state.regime_score,
            },
        }

    # ③ 默认观望
    return {
        "intent_type": "hold",
        "direction": None,
        "reason": "threshold_not_met",
        "metadata": {"pq_spread": pq_spread},
    }
```

这个意图层，实际上就是给策略一个“可以自然进化”的位置：

- 未来想引入宏观 regime、杠杆、回撤等更多条件时，都可以在这里做组合判断。
- 前端可以直接展示 `intent_type` 与 `reason`，帮助人类理解策略行为。

### 4.4 `_check_pq_spread()`：兼容层（Intent → Signal）

```python
async def _check_pq_spread(self) -> Optional[StrategySignalEvent]:
    """
    检查 P-Q 价差并生成信号：
      冷却检查 → 状态构建 → 意图决策 → Intent → StrategySignalEvent。
    """

    # 冷却时间检查
    if self.last_signal_time:
        elapsed = (datetime.utcnow() - self.last_signal_time).total_seconds()
        if elapsed < self.signal_cooldown_seconds:
            return None

    # 构建状态
    state = self._build_market_state()
    if not state:
        return None

    # 意图决策
    intent = self._decide_intent(state)
    if not intent or intent.get("direction") is None:
        return None  # HOLD 或无动作意图

    direction = intent["direction"]
    reason = intent.get("reason", "")
    metadata = intent.get("metadata", {})

    # Intent → StrategySignalEvent 映射（兼容旧接口）
    if direction == "buy":
        signal = StrategySignalEvent(
            strategy_id=self.strategy_id,
            signal_type="buy",
            symbol=self.underlying,
            confidence=min(abs(state.pq_spread or 0.0) / self.vol_threshold, 1.0),
            metadata={
                "strategy_type": "pq_vol_trader",
                "action": "buy_straddle",
                "p_vol": state.p_vol,
                "q_vol": state.q_vol,
                "pq_spread": state.pq_spread,
                "reason": reason,
                "fomo_score": state.fomo_score,
                "macro_regime": state.macro_regime,
                "regime_score": state.regime_score,
                **metadata,
            },
        )
    elif direction == "sell":
        signal = StrategySignalEvent(
            strategy_id=self.strategy_id,
            signal_type="sell",
            symbol=self.underlying,
            confidence=min(abs(state.pq_spread or 0.0) / self.vol_threshold, 1.0),
            metadata={
                "strategy_type": "pq_vol_trader",
                "action": "sell_straddle",
                "p_vol": state.p_vol,
                "q_vol": state.q_vol,
                "pq_spread": state.pq_spread,
                "reason": reason,
                "fomo_score": state.fomo_score,
                "macro_regime": state.macro_regime,
                "regime_score": state.regime_score,
                **metadata,
            },
        )
    else:
        return None

    self.last_signal_time = datetime.utcnow()
    return signal
```

这里是 Phase 1 的关键：

- 对外接口保持为 `StrategySignalEvent`，不破坏原有系统。
- 对内已经完成向「状态/意图」结构的升级，为未来 Phase 2（引入 `StrategyIntentEvent`）做了铺垫。

---

## 5. 风控与 Web3 风险防御的改进

### 5.1 RiskService：组合杠杆控制

文件：[`services/trading_service/app/risk/risk_service.py`](services/trading_service/app/risk/risk_service.py:1)

主要新增逻辑（伪代码）：

```python
def _simulate_order_impact(...):
    # 1. 计算当前组合名义敞口
    current_gross_notional = sum(abs(pos.qty * pos.price) for pos in portfolio.positions)

    # 2. 计算本次订单名义敞口
    order_notional = abs(order.quantity * order.price)

    # 3. 估算新组合杠杆
    new_gross_notional = current_gross_notional + order_notional
    new_leverage = new_gross_notional / max(portfolio.total_equity, epsilon)

    if new_leverage > self.max_leverage:
        return RiskCheckResult(
            approved=False,
            reason="组合杠杆超限",
            details={"new_leverage": new_leverage},
        )

    ...
```

效果：

- 在账户层严格限制总杠杆，避免策略在高 FOMO/高波动期间无限加仓。
- 与策略侧的意图防御（FOMO → HOLD）形成双保险。

### 5.2 杀猪盘/喊单场景下的防御

防御手段来自三层：

1. **Sentiment/FOMO 层**：
   - `sentiment_service` 提供情绪 & FOMO 指标。
   - 策略侧在 `_decide_intent` 中使用 `fomo_score` 做“硬刹车”。
2. **RiskService 引擎层**：
   - 限制日内净买入、单笔最大名义金额、组合杠杆等约束。
3. **宏观 regime 层（规划中）**：
   - 在 `macro_regime == "panic"` 时，即便 P/Q 给出正向信号，也可以通过意图层降低仓位或强制 HOLD。

---

## 6. 前后端对齐与前端展望

### 6.1 后端接口对齐

- Options / Gamma 相关 API 均按 `/api/v1/options/...` 规范暴露。
- 返回字段中，已对齐：
  - vol 相关：`p_vol`, `q_vol`, `pq_spread`
  - 策略元信息：`strategy_type`, `action`, `reason`, `macro_regime`, `regime_score`, `fomo_score`
- 文档原先提到的 `action` 与实际实现 `recommended_action` 差异已在设计上统一，后端可保持一个字段，前端做 alias 映射。

### 6.2 前端 Options/Risk/Strategy 面板规划

文件（计划改造中）：

- [`frontend/src/modules/options/OptionsPanel.tsx`](frontend/src/modules/options/OptionsPanel.tsx:1)
- [`frontend/src/modules/risk/RiskPanel.tsx`](frontend/src/modules/risk/RiskPanel.tsx:1)
- [`frontend/src/modules/strategy/StrategyCenter.tsx`](frontend/src/modules/strategy/StrategyCenter.tsx:1)

目标 UI 结构：

1. **组合风险总览（顶层）**

   - 显示：Delta / Gamma / Vega / 杠杆 / 回撤。
   - 直接消费 RiskService & PortfolioStateStore 的聚合数据。

2. **Gamma 控制台（中层）**

   - 显示：当前 `MarketState` 的关键字段：
     - P/Q、`pq_spread`
     - `macro_regime` / `regime_score`
     - `fomo_score`
   - 显示：当前意图（`intent_type` + `reason`）与实际信号（buy/sell/hold）。

3. **期权明细 & 执行细节（底层）**
   - 各合约的持仓、价格、Greeks。
   - 最近执行的订单与对应意图、状态快照。

---

## 7. 与现有文档的关系

### 7.1 与 `gamma_scalping_architecture.md` 的一致性

- 现有文档中关于 Gamma Scalping / P vs Q 框架的描述，在逻辑上与当前代码保持一致：

  - 使用 P/Q 差值驱动波动率交易；
  - Delta 通过永续合约进行对冲；
  - 策略以模块化方式挂载在策略引擎上。

- 本次改进做了以下 **增强而非推翻**：
  1. 在原有 P vs Q 框架上，引入了状态聚合与语义化意图层。
  2. 使得文档中“宏观 Q + 情绪 + 风险”三类信号可以更自然地注入策略层。
  3. 保持文档中描述的 event-driven / message-bus / Redis 状态中心化模式不变。

### 7.2 与 `architecture_decoupling.md` 的关系

- 当前改造是对「策略/风控/执行解耦」设计的一次落地：
  - 策略负责“意图决策”；
  - 风控负责“约束 & veto”；
  - 执行负责“最优下单路径”；
- 未来可以在该文档中增加“Intent Bus & Intent Executor”的专节，描述下一阶段的解耦方案（见下文 Phase 2）。

---

## 8. 后续迭代与展望

### 8.1 Phase 2：Intent Event 化 & 执行解耦

**目标**：

- 将当前内部使用的 `intent dict` 抽象成正式事件类型 `StrategyIntentEvent`，与 `StrategySignalEvent` 并行存在。
- StrategyEngine 改为：
  - 先消费 `StrategyIntentEvent`；
  - 再由 Intent Executor 将其翻译成一个或多个具体订单（包括现货/期权/永续合约组合）。

**关键步骤**：

1. 在 `services/trading_service/app/messaging/messages.py` 中定义 `StrategyIntentEvent`。
2. 在 `PQVolTrader` 中新增一个输出渠道：可以选择发 IntentEvent（同时保持兼容 SignalEvent 一段时间）。
3. 新建一个 `IntentExecutionService`，专门负责：
   - 解析意图：如 `increase_long_gamma`；
   - 根据组合当前状态与 RiskService 限制决定具体头寸调整；
   - 生成并提交订单任务给执行层。

### 8.2 Phase 3：宏观/情绪/风险深度融入决策

1. **宏观 Q**：

   - `strategy_service` 输出 `macro_regime` & `regime_score`，推送到 trading_service。
   - 在 `_decide_intent` 中为各 regime 定义策略模式：
     - `bull`：允许更高 Gamma 敞口，较宽阈值。
     - `bear`：降低仓位，缩短持仓时间。
     - `panic`：原则上以防守/减仓为主。

2. **情绪/FOMO**：

   - 重构 FOMO 计算，结合价格动量、社交媒体情绪、成交量分布等。
   - 在策略与 RiskService 中统一这个指标，用作强限制条件。

3. **风险指标**：
   - 从 PortfolioStateStore / RiskService 获取 `total_delta` / `total_gamma` / `leverage` / `drawdown_pct`。
   - 把这些字段填入 `MarketState`，在 `_decide_intent` 中做例如：
     - 高杠杆 + 高 FOMO + 高 `pq_spread` 时，只允许部分减仓而非继续加仓。
     - 大回撤阶段禁止开启新的方向性仓位。

### 8.3 Phase 4：前端策略可视化与 Explainability

- 在前端 StrategyCenter 中：

  - 展示最新 `MarketState` 快照；
  - 展示每次意图决策的 inputs → intent → signal & order 链路；
  - 支持“回放模式”：对历史一段时间内的意图演化进行可视化。

- 为回测/研究提供基础：
  - 定期将 `MarketState` 与 `intent` / `signal` / `order` 记录到数据表中。
  - 允许对任意区间进行「重跑决策，但不重放下单」，用于调参/验证。

---

## 9. 小结

本次改造在 **不破坏现有接口** 的前提下，为 GLM Crypto Trading Platform 的 Gamma/PQ 策略引入了一个更接近「专业自营盘」的结构：

- 从“条件触发的信号”升级为“多维状态驱动的意图决策”；
- 在策略与风控之间形成互补：策略侧主动防御（FOMO / 宏观），风控侧被动约束（杠杆 / 头寸）；
- 为将来引入 Intent 事件总线、独立执行器、可解释型前端可视化提供了清晰的架构路径。

后续只要沿着本文档的 Phase 2/3/4 路线向前推进，就可以逐步把这个系统演化为一个：

- 能理解宏观周期、情绪周期；
- 能主动调整进攻/防守节奏；
- 能清晰展示「为什么做这个交易」；
  的专业级 Web3 Gamma 交易框架。
