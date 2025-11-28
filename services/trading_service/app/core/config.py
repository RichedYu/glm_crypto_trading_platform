# /services/trading_service/app/core/config.py

import os
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Dict, Any, List
from functools import lru_cache

class Settings(BaseSettings):
    """
    使用 Pydantic 管理服务的所有配置。
    它会自动从 .env 文件中加载环境变量。
    """

    # --- 1. 账户与API配置 (从 .env 文件加载) ---
    BINANCE_API_KEY: str
    BINANCE_API_SECRET: str
    PUSHPLUS_TOKEN: str | None = None  # 可选，可以为None
    HTTP_PROXY: str | None = None  # 可选的代理设置

    # --- 2. 核心交易参数 ---
    SYMBOL: str = 'BNB/USDT'
    INITIAL_GRID: float = 2.0  # 初始网格大小 (%)
    MIN_TRADE_AMOUNT: float = 20.0  # 单次最小交易金额 (USDT)
    INITIAL_PRINCIPAL: float = 1000.0  # 初始本金，用于统计盈亏
    INITIAL_BASE_PRICE: float = 0.0 # 初始基准价, 0表示动态获取
    AUTO_ADJUST_BASE_PRICE: bool = False # 是否自动调整基准价
    
    # --- 3. 仓位与风险管理 ---
    MAX_POSITION_RATIO: float = 0.9  # 最大仓位比例
    MIN_POSITION_RATIO: float = 0.1  # 最小仓位(底仓)比例
    MAX_DRAWDOWN: float = -0.15 # 允许的最大回撤
    DAILY_LOSS_LIMIT: float = -0.05 # 每日最大亏损限制
    RISK_FACTOR: float = 0.1 # 风险暴露系数

    # --- 4. 策略微调参数 ---
    FLIP_THRESHOLD_FACTOR: float = 0.2 # 触发价格反转的阈值因子 (原为网格大小的1/5)
    VOLATILITY_WINDOW: int = 24  # 波动率计算周期（小时）
    COOLDOWN: int = 60 # 交易冷却时间(秒)
    SAFETY_MARGIN: float = 0.95 # 可用余额的安全边际

    # 动态网格参数 (保持为字典结构，便于后续由策略服务动态提供)
    GRID_PARAMS: Dict[str, Any] = {
        'min': 1.0,
        'max': 4.0,
        'volatility_threshold': {
            'ranges': [
                {'range': [0, 0.20], 'grid': 1.0},
                {'range': [0.20, 0.40], 'grid': 1.5},
                {'range': [0.40, 0.60], 'grid': 2.0},
                {'range': [0.60, 0.80], 'grid': 2.5},
                {'range': [0.80, 1.00], 'grid': 3.0},
                {'range': [1.00, 1.20], 'grid': 3.5},
                {'range': [1.20, 999], 'grid': 4.0}
            ]
        }
    }

    # --- 5. 策略与外部服务配置 ---
    S1_LOOKBACK: int = 52
    S1_SELL_TARGET_PCT: float = 0.50
    S1_BUY_TARGET_PCT: float = 0.70
    STRATEGY_SERVICE_ENDPOINTS: List[str] = Field(default_factory=lambda: [
        "http://strategy_service:8000",
        "http://localhost:8003",
        "http://127.0.0.1:8003"
    ])
    SENTIMENT_SERVICE_ENDPOINTS: List[str] = Field(default_factory=lambda: [
        "http://sentiment_service:8000",
        "http://localhost:8002",
        "http://127.0.0.1:8002"
    ])
    API_PROXY_FAIL_THRESHOLD: int = 2
    API_PROXY_COOLDOWN_SECONDS: int = 120

    # --- 6. 系统与网络配置 ---
    API_TIMEOUT: int = 10000  # API超时时间(ms)
    RECV_WINDOW: int = 5000 # 币安接收窗口(ms)
    MAX_RETRIES: int = 5 # API请求最大重试次数
    RISK_CHECK_INTERVAL: int = 300 # 风控检查间隔(秒)
    DEBUG_MODE: bool = False
    
    # --- 7. Redis 配置 ---
    REDIS_HOST: str = "glm_redis"  # Docker 网络中的 Redis 主机名
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    
    @property
    def redis_url(self) -> str:
        """构建 Redis 连接 URL"""
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    class Config:
        # Pydantic的内部配置类，告诉它去哪里找配置文件
        env_file = ".env"
        env_file_encoding = 'utf-8'

@lru_cache() # 这个装饰器确保 get_settings() 只会执行一次，配置只被加载一次
def get_settings() -> Settings:
    """
    获取并返回配置实例。
    通过 lru_cache 实现单例模式，确保整个应用共享同一个配置对象。
    """
    return Settings()
