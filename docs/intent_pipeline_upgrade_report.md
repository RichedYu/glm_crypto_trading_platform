# GLM Crypto Trading Platform — 策略意图与风控一体化升级报告

> 版本：v1.0（2025-02-15）

本报告梳理本轮「策略意图架构」落地时完成的关键升级，帮助研发、量化与运维团队快速理解改动范围、收益与后续动作。

## 1. 升级目标概览

1. **修复运行时缺陷**：补足 `StrategyEngine` 的 P/Q 事件消费链路及消息模型缺失，避免 `PQVolTrader` 无法收敛数据或进程直接崩溃。
2. **引入「意图→风控→执行」串行管线**：确保所有策略动作都能通过风控审核运转，并且可被前端/监控语义化展示。
3. **实时风险闭环**：让 DeltaHedger、PQ 策略与 RiskService 建立事件化数据通路（组合 Greeks、宏观/FOMO 指标）。
4. **前后端对齐**：API 与前端面板同步展示意图、宏观、FOMO 等新维度，便于操作与复盘。

## 2. 核心技术改动

### 2.1 消息模型与基础设施

- 在 `services/trading_service/app/messaging/messages.py` 中新增：
  - `StrategyIntentEvent`：描述策略输出的高阶意图（动作、方向、数量、原因、metadata）。
  - `ExecutionCommandEvent`：风控审批后的执行任务，供期权执行器消费。
  - `MacroStateEvent` / `PortfolioRiskEvent`：宏观情绪及组合风险广播事件。
- `StrategyEngine` 现有 `_consume_volatility_surfaces` / `_consume_volatility_forecasts` 实现补齐，确保 PQ 能接收 P/Q 世界数据。

### 2.2 策略层意图化

- `PQVolTraderStrategy`：
  - `on_volatility_surface/on_volatility_forecast` 直接返回 `StrategyIntentEvent`，不再自行发信号。
  - 新增 `on_macro_state` 吸收 `MacroStateEvent`，FOMO 与宏观 regime 可实时影响 `_decide_intent`。
  - `intent_base_size` / 仓位约束控制单次意图数量，metadata 附带 `pq_spread`、宏观、FOMO 等信息。
- `DeltaHedgerStrategy`：
  - 移除轮询逻辑，改为消费 `portfolio.risk`，在 `total_delta` 越界时发布 `delta_hedge` 意图。

### 2.3 StrategyEngine 串行管线

- Engine 只订阅 `strategy.intent`：
  - 调用 `RiskService.check_pre_order()` 完成 veto。
  - 期权类动作（`buy_straddle` 等）转发至 `execution.command`，由 OptionExecutionService 翻译为多腿订单。
  - 其他资产动作直接生成 `order.command`，同样附带 `intent_id` 以便追踪。
- 兼容旧版 `StrategySignalEvent`：仍可发布，Engine 会走同样的风控与下单流程。

### 2.4 风控与宏观数据源

- RiskService 新增：
  - `PortfolioRiskEvent` 广播（Greeks、杠杆、position_ratio）供 DeltaHedger/前端共享。
  - `_macro_state_broadcast_loop()` 周期性调用 sentiment_service + 组合 PnL 估算 realized vol，推送 `market.macro_state`。
- 风控配置新增 `macro_broadcast_interval`、`sentiment_api_urls` 等，可在 `.env`/配置中调整。

### 2.5 执行 & 前端

- OptionExecutionService：改为订阅 `execution.command`，只执行已通过风控的意图。
- `options_api` / `optionsApi.ts` / `OptionsPanel.tsx`：
  - `/api/v1/options/pq-spread` 返回 `intent_type/intent_reason/macro_regime/regime_score/fomo_score`。
  - 前端 Gamma 控制台新增卡片展示意图、宏观及 FOMO 指标，便于人工监控。

## 3. 落地收益

| 维度 | 改进前 | 改进后 |
| --- | --- | --- |
| 风控路径 | 策略 signal 可能绕过 RiskService，被 OptionExecutionService 直接下单 | 所有策略必须输出 Intent，Engine 串行风控，OptionExecutionService 仅执行 vetted intent |
| 数据一致性 | PQ 缺少 P/Q 消费通道、宏观/FOMO 无法实时注入 | `_consume_volatility_*` 补齐，`market.macro_state`/`portfolio.risk` 提供统一来源 |
| Delta 管理 | DeltaHedger 轮询旧状态且量化不可控 | 通过事件驱动的 total_delta，超限即意图对冲，响应更快、可追踪 |
| 可观测性 | API/UI 无法呈现意图语义 | 前端展示 intent、宏观、FOMO，便于运营/研究回放 |

## 4. 部署与操作注意

1. **消息总线**：Redis Streams 需要新增 `strategy.intent`、`execution.command`、`portfolio.risk`、`market.macro_state` 等 stream 与消费组（引擎、执行器各自独立 consumer）。
2. **服务依赖**：
   - RiskService 需具备访问 sentiment_service 的网络权限。
   - OptionExecutionService 必须与 `market.vol_surface` 同步，以便执行意图时找到最新曲面。
3. **配置**：
   - `intent_base_size`、`macro_broadcast_interval` 等可在策略/风控配置中调优。
   - 若 sentiment_service 不可用，可临时关闭宏观广播（配置项置空）。
4. **回放/监控**：建议在监控面板新增 `strategy.intent`/`execution.command` 的消费延迟与失败统计，确保串行流程稳定。

## 5. 后续规划（建议）

1. **Intent 持久化**：将 `StrategyIntentEvent` 与 `ExecutionCommandEvent` 写入时序数据库/审计日志，方便回测复盘。
2. **多策略协同**：为其他策略（Grid、S1 等）逐步改造为 Intent 输出，统一风控走廊。
3. **指标推送**：在 `market.macro_state` 中加上更多可选指标（链上活跃度、资金费率等）。
4. **前端 Explainability**：结合 intent 流构建“意图→信号→订单→成交”的可视化链路。

---

如需进一步了解实现细节，可参考 `docs/strategy_intent_architecture_upgrade.md` 以及相关模块源码。
