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

### Frontend Dashboard | 前端可视化

- Comprehensive UI/UX + API requirements for the React visualization cockpit are documented in `frontend/README.md`.  
- Includes tech stack, module breakdown (trading, sentiment, strategy, risk), performance guidelines, and phased roadmap for delivery.

### Security & Hygiene | 安全与规范

- `.gitignore` now strips `.env`, logs, and editor files — run `git status` to ensure secrets stay local.  
- Before pushing to GitHub, run the commands (see final section in Codex reply) to double-check no API keys remain.  
- Use `docker compose down` or `Ctrl+C` to stop containers; logs rotate automatically via `LogConfig`.
