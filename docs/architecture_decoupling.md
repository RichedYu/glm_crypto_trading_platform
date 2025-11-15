# 架构解耦文档

## 概述

本文档描述了 GLM 加密货币交易平台的架构解耦实现,从单体架构演进为事件驱动的微服务架构。

## 架构演进

### 原有架构痛点

1. **单体耦合**: [`GridTrader`](../services/trading_service/app/trader/trader.py:19-182) 在一个协程中编排交易所 IO、策略逻辑和风险控制,每个进程只能运行一个交易对/策略
2. **状态共享**: [`AdvancedRiskManager`](../services/trading_service/app/trader/risk_manager.py:4-78) 等模块直接读写 trader 状态,真实状态存在进程内存中
3. **同步调用**: 策略服务通过同步 HTTP 调用,无法支持并行执行或衍生品

### 新架构设计

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│ Message Bus     │────▶│ Plugin Strategy  │────▶│ State Store     │
│ (Redis Streams) │     │ Layer            │     │ (Redis + PG)    │
└─────────────────┘     └──────────────────┘     └─────────────────┘
    事件驱动              策略解耦                状态中心化
```

## 核心组件

### 1. 消息总线 (Message Bus)

**位置**: [`services/trading_service/app/messaging/`](../services/trading_service/app/messaging/)

#### 事件分类

- **market.tick**: 市场行情 tick
- **strategy.signal**: 策略信号
- **order.command**: 订单命令
- **order.fill**: 订单成交
- **risk.alert**: 风险告警
- **position.update**: 持仓更新
- **state.snapshot**: 状态快照

#### 实现

- **抽象接口**: [`MessageBus`](../services/trading_service/app/messaging/message_bus.py)
- **Redis 实现**: [`RedisStreamBus`](../services/trading_service/app/messaging/redis_bus.py)

### 2. 插件化策略层

**位置**: [`services/trading_service/app/strategies/`](../services/trading_service/app/strategies/)

- **策略基类**: [`BaseStrategy`](../services/trading_service/app/strategies/base.py)
- **策略引擎**: [`StrategyEngine`](../services/trading_service/app/strategies/engine.py)
- **网格策略**: [`GridStrategy`](../services/trading_service/app/strategies/grid_strategy.py)

### 3. 中心化状态存储

**位置**: [`services/trading_service/app/state/`](../services/trading_service/app/state/)

- **状态接口**: [`StateStore`](../services/trading_service/app/state/base.py)
- **Redis 实现**: [`RedisStateStore`](../services/trading_service/app/state/redis_store.py)

### 4. 市场数据适配器

**位置**: [`services/trading_service/app/adapters/market_adapter.py`](../services/trading_service/app/adapters/market_adapter.py)

## 使用示例

```python
from app.messaging import RedisStreamBus
from app.state import RedisStateStore
from app.strategies import StrategyEngine, GridStrategy
from app.adapters import MarketDataAdapter

# 初始化
redis_url = "redis://localhost:6379/0"
message_bus = RedisStreamBus.from_url(redis_url)
state_store = RedisStateStore.from_url(redis_url)

# 创建策略引擎
engine = StrategyEngine(message_bus, state_store, exchange)
engine.register_strategy_class("GridStrategy", GridStrategy)

# 加载策略
await engine.load_strategy(
    strategy_id="grid_bnb_1",
    strategy_name="GridStrategy",
    config={"symbol": "BNB/USDT", "base_price": 600.0, "grid_size": 2.0}
)

# 启动
await engine.start()
```

## 扩展性

### 支持衍生品

1. 创建期货/期权策略插件
2. 实现对应的交易工具类型
3. 扩展状态存储支持保证金

### 多进程部署

- 每个策略实例可独立进程
- 通过 Redis 消息总线通信
- 状态共享无需进程间通信

## 迁移路径

### Phase 1: 基础设施 (已完成)

- ✅ Redis Streams 消息总线
- ✅ 插件化策略层
- ✅ Redis 状态存储
- ✅ 市场数据适配器

### Phase 2: 策略迁移 (进行中)

- ✅ GridStrategy 插件化
- ⏳ S1 策略插件化
- ⏳ 风险管理解耦

### Phase 3: 生产就绪

- ⏳ PostgreSQL 持久化
- ⏳ 监控和告警
- ⏳ 性能优化

## 总结

新架构实现了:

1. **事件驱动**: 通过 Redis Streams 解耦组件通信
2. **策略解耦**: 插件化架构支持多策略并行
3. **状态中心化**: Redis 统一管理状态,支持多进程
4. **可扩展性**: 轻松添加新策略和交易工具类型
