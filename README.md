## GLM Crypto Trading Platform · 加密量化平台

### Overview | 项目概述

- **English**: Modular research-to-production stack for running grid-based trading on Binance, enriched with sentiment and strategy microservices.  
- **中文**：一个模块化的量化平台，可在币安运行网格策略，并通过策略/情绪微服务提供智能推理。

### Services & Ports | 服务与端口

| Service | Port Mapping | Description | 描述 |
|---------|--------------|-------------|------|
| `trading_service` | `8001 -> 8000` | Async grid trader, risk engine, API proxy pool entry | 异步网格交易 + 风控 + API 代理入口 |
| `sentiment_service` | `8002 -> 8000` | Twitter ingestion + FinBERT scoring | 推特抓取与 FinBERT 情绪打分 |
| `strategy_service` | `8003 -> 8000` | Volatility GLM + parameter recommendation API | 波动率 GLM 与参数推荐接口 |

All ports are now centrally managed through the new API proxy configuration (see `services/trading_service/app/core/config.py`).  
所有端口可通过 `config.py` 中的 API 代理配置统一维护。

### API Proxy Pool | API 代理池

- **What**: `ApiProxyPool` (in `app/core/api_proxy_pool.py`) rotates through multiple base URLs, tracks failures, cools down unhealthy endpoints, and exposes a `health_snapshot()` for monitoring.  
- **Benefit**: Keeps strategy/sentiment APIs reachable even when one container/port is flaky; ready for future gateway expansion.  
- **Usage**: `GridTrader` calls `strategy_service` via the pool. Configure fail threshold/cooldown/endpoints through `STRATEGY_SERVICE_ENDPOINTS`, `API_PROXY_FAIL_THRESHOLD`, etc.

### Quick Start | 快速开始

1. **Prepare secrets | 配置密钥**  
   - Duplicate each `.env.example` (or create `.env`) under `services/*` and fill Binance keys, PushPlus token, proxies, etc.  
   - NEVER commit real keys; `.gitignore` blocks all `.env` files by default.
2. **Build services | 构建服务**  
   ```bash
   docker compose up --build
   ```
3. **Monitor logs | 观察日志**  
   - Trading: `docker compose logs -f trading_service`  
   - Strategy: `docker compose logs -f strategy_service`  
   - Sentiment: `docker compose logs -f sentiment_service`

### Configuration | 配置说明

- `STRATEGY_SERVICE_ENDPOINTS` / `SENTIMENT_SERVICE_ENDPOINTS`: list of fallback URLs (container DNS + localhost ports).  
- `API_PROXY_FAIL_THRESHOLD`: maximum sequential failures before cooling an endpoint.  
- `API_PROXY_COOLDOWN_SECONDS`: cooldown duration for unhealthy endpoints.  
- `S1_*` parameters: S1 controller lookback and buy/sell trigger percentages.  
- `API_TIMEOUT` (ms) automatically converts to seconds for the proxy timeout.

### Prospect & Research | 发展路线

- Detailed roadmap for optimization algorithms and emotion signals lives in `docs/prospect.md` (bilingual).  
- Notebook experiments are under `notebooks/` (`01_data_exploration.ipynb`, `02_glm_volatility_model.ipynb`); remember to align library versions with service requirements.

### Intent Pipeline Upgrade | 策略意图升级

- **New intent → risk → execution bus**: strategies output `StrategyIntentEvent`, `StrategyEngine` runs Pre-Order Veto, and vetted intents reach `execution.command` for multi-leg conversion.  
- **Real-time macro & risk feeds**: `RiskService` now broadcasts `market.macro_state`（宏观/FOMO）和 `portfolio.risk`（Greeks/杠杆），`DeltaHedger`、前端与运维共享同一视图。  
- **Frontend alignment**: `/api/v1/options/pq-spread` 返回意图、宏观与 FOMO 字段，`OptionsPanel` 展示 Gamma 策略语义。  
- 📄 详见 `docs/intent_pipeline_upgrade_report.md` 与 `docs/strategy_intent_architecture_upgrade.md`，用于交付说明与培训。

### Tech Stack & Tooling | 技术栈

| Layer | Primary Tech | Notes |
| ----- | ------------ | ----- |
| Trading / Risk Services | Python 3.11, FastAPI, asyncio, Redis Streams, CCXT | 事件驱动策略引擎、风控、执行适配器 |
| Strategy Service | Python, StatsModels, scikit-learn | GLM 波动率预测 + 参数推荐 |
| Sentiment Service | Python, Tweepy, HuggingFace Transformers (FinBERT) | 推特抓取与情绪打分，提供 REST API |
| Frontend | React 18, TypeScript, Ant Design, Vite | Gamma 控制台 & 风控看板 |
| Data / Infra | Redis, Docker Compose, GitHub Actions（可选） | 状态中心、消息总线、容器化部署 |

**Certifications / Compliance**  
- 内部凭证管理：所有 `.env` 通过 `.gitignore` 保护，PushPlus & Binance API Key 仅存储于本地/密钥管家。  
- 网络安全：镜像无 root 运行、Redis 需在 VPC 内部署；如需上云可结合 HashiCorp Vault / AWS Secrets Manager。  
- 代码扫描：推荐结合 `pre-commit` + `ruff`/`black` + `npm audit`，并在 CI 中运行依赖漏洞扫描。

### Project History | 历程回顾

| 时间 | 里程碑 |
| ---- | ------- |
| 2023 Q4 | 初版 GridTrader 单体上线，支持基本网格/风控逻辑 |
| 2024 Q2 | 架构解耦：消息总线、插件化策略、独立 sentiment/strategy 服务（详见 `docs/architecture_decoupling.md`）|
| 2024 Q4 | Gamma/PQ 策略研发，完成 `docs/gamma_scalping_architecture.md` 方案、前端风控面板雏形 |
| 2025 Q1 | 完成本次策略意图 & 风控升级，串行 Intent Bus + OptionExecutionService，发布《策略意图架构升级报告》|

### Roadmap & Outlook | 未来展望

1. **Intent Persistence & Replay**：将 `StrategyIntentEvent`/`ExecutionCommandEvent` 写入审计表，支持历史回放与 explainability。  
2. **策略覆盖度**：逐步让 Grid、S1、Predictive 策略也输出 Intent，从而复用统一风控与前端语义。  
3. **宏观信号扩展**：引入链上指标、资金费率、资金流量等多因子，统一在 `market.macro_state` 广播。  
4. **自动化运维**：完善 GitHub Actions / Argo Workflows，进行镜像构建、联测与 Canary 部署。  
5. **安全与合规**：引入 API key rotation、访问审计、合约交易限额策略，满足更高等级的托管要求。

### Frontend Dashboard | 前端可视化

- Comprehensive UI/UX + API requirements for the React visualization cockpit are documented in `frontend/README.md`.  
- Includes tech stack, module breakdown (trading, sentiment, strategy, risk), performance guidelines, and phased roadmap for delivery.

### Security & Hygiene | 安全与规范

- `.gitignore` now strips `.env`, logs, and editor files — run `git status` to ensure secrets stay local.  
- Before pushing to GitHub, run the commands (see final section in Codex reply) to double-check no API keys remain.  
- Use `docker compose down` or `Ctrl+C` to stop containers; logs rotate automatically via `LogConfig`.
