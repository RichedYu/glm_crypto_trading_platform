# /services/trading_service/app/main.py

import asyncio
import logging
from fastapi import FastAPI, HTTPException

# --- 导入我们重构好的核心模块 ---
from app.core.config import get_settings
from app.core.exchange_client import ExchangeClient
from app.trader.trader import GridTrader

# --- FastAPI 应用设置 ---
# 1. 获取配置实例
settings = get_settings()

# 2. 创建 FastAPI 应用
app = FastAPI(
    title="交易执行服务 (Trading Service)",
    description="负责执行网格交易和S1策略，并提供状态查询接口。",
    version="1.0.0"
)

# 3. 创建一个全局变量来持有交易机器人实例
#    这确保了整个服务生命周期中只有一个机器人实例
trader_instance: GridTrader = None

# --- 应用生命周期事件 ---
@app.on_event("startup")
async def startup_event():
    """
    【核心】应用启动时执行的异步函数。
    负责初始化所有必要的对象，让服务进入“准备就绪”状态。
    """
    global trader_instance
    logging.info("交易服务正在启动...")
    try:
        # 1. 创建交易所客户端
        exchange = ExchangeClient()
        # 2. 创建交易机器人实例 (注意：不再传入config)
        trader_instance = GridTrader(exchange)
        # 3. 异步初始化机器人 (加载市场数据、同步资金等)
        await trader_instance.initialize()
        
        logging.info("✅ 交易服务启动成功，机器人已初始化并待命！")
    except Exception as e:
        logging.critical(f"❌ 关键错误：服务启动时初始化机器人失败: {e}", exc_info=True)
        # 在生产环境中，可以考虑让服务启动失败
        # raise e

# --- API Endpoints ---
@app.get("/api/v1/health", tags=["通用"])
def health_check():
    """健康检查接口，用于监控服务是否存活。"""
    return {"status": "ok", "service": "Trading Service"}

@app.get("/api/v1/status", tags=["交易员状态"])
async def get_trader_status():
    """获取机器人当前的详细状态。"""
    if trader_instance and trader_instance.initialized:
        # 这里可以调用一个专门的方法来获取状态字典
        # 假设 trader.py 中有一个 get_current_status 方法
        # status = await trader_instance.get_current_status()
        # 为简化，我们先直接访问属性
        return {
            "symbol": trader_instance.symbol,
            "base_price": trader_instance.base_price,
            "current_price": trader_instance.current_price,
            "grid_size": trader_instance.grid_size,
            "total_assets_usd": trader_instance.total_assets
        }
    raise HTTPException(status_code=503, detail="机器人尚未初始化或初始化失败。")

@app.post("/api/v1/actions/trigger-cycle", tags=["交易员动作"])
async def trigger_trading_cycle():
    """
    【核心API】
    触发机器人执行一次完整的“感知-决策-行动”周期。
    这个接口将由定时任务（如Cron Job）或我们的策略服务调用。
    """
    if trader_instance and trader_instance.initialized:
        logging.info("接收到API请求，开始执行交易周期...")
        result = await trader_instance.run_one_cycle()
        return result
    raise HTTPException(status_code=503, detail="机器人尚未初始化或初始化失败。")

