# GLM Crypto Trading Platform - 系统架构图

创建时间：2025-11-27 23:13:00

---

## 1. 总体架构图 (Overall Architecture)

```mermaid
graph TB
    subgraph "前端层 Frontend Layer"
        UI[React + TypeScript UI]
        WS[WebSocket Client]
        HTTP[HTTP Client / Axios]
    end

    subgraph "API 网关层 API Gateway (规划中)"
        GW[API Gateway / Load Balancer]
    end

    subgraph "微服务层 Microservices Layer"
        TS[Trading Service<br/>:8001]
        SENT[Sentiment Service<br/>:8002]
        STRAT[Strategy Service<br/>:8003]
    end

    subgraph "消息与状态层 Message & State Layer"
        REDIS[(Redis<br/>消息总线 + 状态存储)]
    end

    subgraph "外部系统 External Systems"
        BINANCE[Binance API<br/>交易所]
        TWITTER[Twitter API<br/>社交数据]
    end

    UI --> HTTP
    UI --> WS
    HTTP --> GW
    WS --> GW

    GW --> TS
    GW --> SENT
    GW --> STRAT

    TS --> REDIS
    SENT --> REDIS
    STRAT --> REDIS

    TS --> BINANCE
    SENT --> TWITTER

    style UI fill:#1890ff,color:#fff
    style REDIS fill:#dc3545,color:#fff
    style TS fill:#52c41a,color:#fff
    style SENT fill:#faad14,color:#fff
    style STRAT fill:#722ed1,color:#fff
```

---

## 2. Trading Service 内部架构

```mermaid
graph LR
    subgraph "Trading Service 内部"
        API[FastAPI<br/>REST API]

        subgraph "策略引擎层"
            ENGINE[Strategy Engine]
            GRID[Grid Strategy]
            PQ[PQ Vol Trader]
            DELTA[Delta Hedger]
        end

        subgraph "风控层"
            RISK[Risk Service]
            VETO[Veto Rules]
        end

        subgraph "执行层"
            EXEC[Execution Service]
            OPT_EXEC[Option Execution]
        end

        subgraph "适配器层"
            MARKET[Market Adapter]
            ORDER[Order Adapter]
        end

        subgraph "状态存储"
            PORT[Portfolio Store]
            STATE[State Store]
        end
    end

    BUS[(Redis Streams<br/>Message Bus)]

    API --> ENGINE
    ENGINE --> GRID
    ENGINE --> PQ
    ENGINE --> DELTA

    GRID --> BUS
    PQ --> BUS
    DELTA --> BUS

    BUS --> RISK
    RISK --> VETO
    VETO --> EXEC
    EXEC --> OPT_EXEC

    OPT_EXEC --> ORDER
    MARKET --> BUS

    ENGINE --> STATE
    RISK --> PORT

    style ENGINE fill:#1890ff,color:#fff
    style RISK fill:#ff4d4f,color:#fff
    style EXEC fill:#52c41a,color:#fff
```

---

## 3. 事件驱动架构 (Event-Driven Architecture)

```mermaid
sequenceDiagram
    participant Market as Market Adapter
    participant Bus as Redis Streams
    participant Strategy as Strategy Engine
    participant Risk as Risk Service
    participant Exec as Execution Service
    participant Exchange as Binance API

    Market->>Bus: publish(market.tick)
    Bus->>Strategy: consume(market.tick)

    Strategy->>Strategy: 状态聚合<br/>(MarketState)
    Strategy->>Strategy: 意图决策<br/>(_decide_intent)

    Strategy->>Bus: publish(strategy.signal)
    Bus->>Risk: consume(strategy.signal)

    Risk->>Risk: 组合模拟<br/>杠杆检查

    alt 风控通过
        Risk->>Bus: publish(execution.command)
        Bus->>Exec: consume(execution.command)
        Exec->>Exchange: place_order()
        Exchange-->>Exec: order_fill
        Exec->>Bus: publish(order.fill)
    else 风控拒绝
        Risk->>Bus: publish(risk.veto)
    end

    Bus->>Strategy: consume(order.fill)
    Strategy->>Strategy: 更新状态
```

---

## 4. 策略意图架构 (Intent-Oriented Architecture)

```mermaid
graph TD
    START[市场数据输入] --> STATE[状态聚合<br/>MarketState]

    STATE --> P[P-Vol<br/>市场隐含波动率]
    STATE --> Q[Q-Vol<br/>模型预测波动率]
    STATE --> MACRO[Macro Regime<br/>宏观周期]
    STATE --> FOMO[FOMO Score<br/>情绪指标]
    STATE --> RISK_M[Risk Metrics<br/>组合风险]

    P --> INTENT{意图决策器<br/>_decide_intent}
    Q --> INTENT
    MACRO --> INTENT
    FOMO --> INTENT
    RISK_M --> INTENT

    INTENT -->|Q > P| LONG[increase_long_gamma<br/>做多波动率]
    INTENT -->|Q < P| SHORT[increase_short_gamma<br/>做空波动率]
    INTENT -->|FOMO > 阈值| HOLD[hold<br/>防御模式]
    INTENT -->|其他| MONITOR[hold<br/>观望]

    LONG --> SIGNAL[Strategy Signal Event]
    SHORT --> SIGNAL
    HOLD --> SIGNAL
    MONITOR --> SIGNAL

    SIGNAL --> RISK_CHECK[Risk Service<br/>风控校验]

    RISK_CHECK -->|通过| EXEC[Execution Command]
    RISK_CHECK -->|拒绝| VETO[Risk Veto]

    EXEC --> ORDER[Order Placement]

    style INTENT fill:#1890ff,color:#fff
    style RISK_CHECK fill:#ff4d4f,color:#fff
    style ORDER fill:#52c41a,color:#fff
```

---

## 5. 前端模块架构

```mermaid
graph TB
    subgraph "前端模块 Frontend Modules"
        LAYOUT[App Layout<br/>顶栏 + 侧边栏]

        subgraph "核心面板"
            TRADE[Trading Dashboard<br/>交易监控]
            OPTIONS[Options Panel<br/>Gamma 控制台]
            RISK[Risk Panel<br/>风险看板]
            STRATEGY[Strategy Center<br/>策略中心]
            SENTIMENT[Sentiment Panel<br/>情绪分析]
        end

        subgraph "状态管理 State Management"
            TRADE_STORE[Trading Store<br/>Zustand]
            RISK_STORE[Risk Store<br/>Zustand]
            STRATEGY_STORE[Strategy Store<br/>Zustand]
            SENTIMENT_STORE[Sentiment Store<br/>Zustand]
        end

        subgraph "数据服务 Data Services"
            API[API Service<br/>Axios]
            WS_SERVICE[WebSocket Service<br/>实时数据流]
            OPTIONS_API[Options API<br/>期权专用]
        end
    end

    LAYOUT --> TRADE
    LAYOUT --> OPTIONS
    LAYOUT --> RISK
    LAYOUT --> STRATEGY
    LAYOUT --> SENTIMENT

    TRADE --> TRADE_STORE
    OPTIONS --> RISK_STORE
    RISK --> RISK_STORE
    STRATEGY --> STRATEGY_STORE
    SENTIMENT --> SENTIMENT_STORE

    TRADE_STORE --> API
    TRADE_STORE --> WS_SERVICE
    RISK_STORE --> OPTIONS_API
    STRATEGY_STORE --> API
    SENTIMENT_STORE --> API

    API --> BACKEND[Backend APIs]
    WS_SERVICE --> BACKEND
    OPTIONS_API --> BACKEND

    style OPTIONS fill:#722ed1,color:#fff
    style RISK fill:#ff4d4f,color:#fff
    style STRATEGY fill:#1890ff,color:#fff
```

---

## 6. 数据流图 (Data Flow Diagram)

```mermaid
graph LR
    subgraph "数据源 Data Sources"
        MARKET_DATA[市场行情<br/>Binance]
        SOCIAL_DATA[社交数据<br/>Twitter]
    end

    subgraph "数据处理 Processing"
        MARKET_ADAPTER[Market Adapter]
        SENTIMENT_ENGINE[Sentiment Engine<br/>FinBERT]
        STRATEGY_MODEL[Strategy Model<br/>GLM]
    end

    subgraph "状态中心 State Center"
        REDIS_STATE[(Redis State Store)]
    end

    subgraph "决策引擎 Decision Engine"
        MARKET_STATE[MarketState<br/>状态聚合]
        INTENT_DECISION[Intent Decision<br/>意图决策]
        RISK_ENGINE[Risk Engine<br/>风控引擎]
    end

    subgraph "执行层 Execution"
        ORDER_EXEC[Order Execution]
        POSITION_MGR[Position Manager]
    end

    MARKET_DATA --> MARKET_ADAPTER
    SOCIAL_DATA --> SENTIMENT_ENGINE

    MARKET_ADAPTER --> REDIS_STATE
    SENTIMENT_ENGINE --> REDIS_STATE
    STRATEGY_MODEL --> REDIS_STATE

    REDIS_STATE --> MARKET_STATE
    MARKET_STATE --> INTENT_DECISION
    INTENT_DECISION --> RISK_ENGINE

    RISK_ENGINE -->|通过| ORDER_EXEC
    RISK_ENGINE -->|拒绝| VETO[Veto Log]

    ORDER_EXEC --> POSITION_MGR
    POSITION_MGR --> REDIS_STATE

    style MARKET_STATE fill:#1890ff,color:#fff
    style INTENT_DECISION fill:#722ed1,color:#fff
    style RISK_ENGINE fill:#ff4d4f,color:#fff
    style ORDER_EXEC fill:#52c41a,color:#fff
```

---

## 7. 部署架构 (Deployment Architecture)

```mermaid
graph TB
    subgraph "Docker Compose 环境"
        subgraph "应用容器 Application Containers"
            TS_CONTAINER[trading_service<br/>:8001]
            SENT_CONTAINER[sentiment_service<br/>:8002]
            STRAT_CONTAINER[strategy_service<br/>:8003]
        end

        subgraph "数据容器 Data Containers"
            REDIS_CONTAINER[Redis<br/>:6379]
        end

        subgraph "前端容器 Frontend (开发)"
            FRONTEND[Vite Dev Server<br/>:5173]
        end
    end

    subgraph "外部依赖 External Dependencies"
        BINANCE_API[Binance API]
        TWITTER_API[Twitter API]
    end

    subgraph "持久化存储 Persistent Storage"
        REDIS_VOL[(redis_data<br/>volume)]
        TRADING_VOL[(trading_data<br/>volume)]
        SENTIMENT_VOL[(sentiment_data<br/>volume)]
    end

    TS_CONTAINER --> REDIS_CONTAINER
    SENT_CONTAINER --> REDIS_CONTAINER
    STRAT_CONTAINER --> REDIS_CONTAINER

    FRONTEND --> TS_CONTAINER
    FRONTEND --> SENT_CONTAINER
    FRONTEND --> STRAT_CONTAINER

    TS_CONTAINER --> BINANCE_API
    SENT_CONTAINER --> TWITTER_API

    REDIS_CONTAINER --> REDIS_VOL
    TS_CONTAINER --> TRADING_VOL
    SENT_CONTAINER --> SENTIMENT_VOL

    style TS_CONTAINER fill:#52c41a,color:#fff
    style SENT_CONTAINER fill:#faad14,color:#fff
    style STRAT_CONTAINER fill:#722ed1,color:#fff
    style REDIS_CONTAINER fill:#dc3545,color:#fff
```

---

## 8. 技术栈总览

```mermaid
mindmap
  root((GLM Crypto<br/>Trading Platform))
    前端 Frontend
      React 18
      TypeScript
      Ant Design
      Zustand
      TanStack Query
      Vite
    后端 Backend
      Python 3.11
      FastAPI
      asyncio
      CCXT
      Redis Streams
    机器学习 ML
      StatsModels GLM
      scikit-learn
      HuggingFace Transformers
      FinBERT
    数据存储 Storage
      Redis
        消息总线
        状态存储
      PostgreSQL 规划中
        持久化
    DevOps
      Docker Compose
      GitHub Actions
      Pre-commit Hooks
```

---

2025-11-27 23:13:00 - 系统架构图创建完成，包含 8 个核心视图
