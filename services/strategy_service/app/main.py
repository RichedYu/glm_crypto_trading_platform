# /services/strategy_service/app/main.py
import logging
import pickle
import os
import pandas as pd
import numpy as np
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# --- FastAPI 应用和模型加载 ---
app = FastAPI(
    title="策略服务 (Strategy Service)",
    description="使用GLM模型进行市场预测，并提供动态交易参数。"
)

# 全局变量持有加载的模型
model = None
MODEL_PATH = "/app/artifacts/volatility_glm_model.pkl"

@app.on_event("startup")
def load_model():
    """服务启动时加载训练好的GLM模型"""
    global model
    if os.path.exists(MODEL_PATH):
        with open(MODEL_PATH, 'rb') as f:
            model = pickle.load(f)
        logging.info("✅ GLM波动率模型加载成功！")
    else:
        logging.warning("⚠️ 未找到模型文件。API将使用默认值。")

# --- API 输入输出模型 ---
class PredictionInput(BaseModel):
    """
    宏观 Q 模型输入特征

    - sentiment_score_lag1: 上一周期市场情绪得分（来自情绪服务）
    - volatility_lag1: 上一周期实现波动率
    - macro_regime: 当前宏观大环境（可选: bull/bear/sideways/high_vol/low_vol）
    """
    sentiment_score_lag1: float
    volatility_lag1: float
    macro_regime: str | None = None  # 允许调用方显式指定宏观 regime

class StrategyParameters(BaseModel):
    """
    GLM 波动率 + 宏观周期综合后的策略参数

    - predicted_volatility: GLM 预测的短期波动率
    - recommended_grid_size: 推荐网格大小（结合宏观 regime 调整）
    - confidence_level: 预测置信度（0~1）
    - macro_regime: 识别出的宏观周期标签
    - regime_score: 宏观 regime 得分，用于衡量趋势/风险强度
    """
    source: str
    predicted_volatility: float
    recommended_grid_size: float
    confidence_level: float
    macro_regime: str
    regime_score: float

def _infer_macro_regime(
    realized_vol: float,
    sentiment: float
) -> tuple[str, float]:
    """
    简单的宏观周期判别逻辑，使 Q 与业内常见「风险周期」对齐。

    业内常见视角：
    - 高波动 + 高情绪分化: risk-on 但不稳定，偏「高波动牛/熊」
    - 低波动 + 高乐观情绪: 典型慢牛/拥挤交易
    - 高波动 + 情绪极端悲观: 恐慌/去杠杆阶段
    - 低波动 + 情绪中性: 区间/震荡市

    这里输出:
    - regime: bull / bear / panic / chop / unknown
    - regime_score: 0~1，绝对值越大代表 regime 越明显
    """
    # 防御性处理
    vol = max(realized_vol, 1e-8)
    sent = sentiment

    # 归一化/分层阈值，可以根据历史分布再做精细化标定
    high_vol = vol > 0.8
    mid_vol = 0.4 < vol <= 0.8
    low_vol = vol <= 0.4

    very_bullish = sent > 0.7
    bullish = 0.3 < sent <= 0.7
    neutral = -0.3 <= sent <= 0.3
    bearish = -0.7 <= sent < -0.3
    very_bearish = sent < -0.7

    # 高波动 + 极端悲观 => panic / 去杠杆
    if high_vol and very_bearish:
        return "panic", min(1.0, (vol - 0.8) + abs(sent))

    # 高波动 + 极端乐观 => 高波动风险牛
    if high_vol and very_bullish:
        return "high_vol_bull", min(1.0, (vol - 0.8) + sent)

    # 低～中波动 + 乐观 => 慢牛/风险偏好上升
    if (low_vol or mid_vol) and bullish:
        return "bull", min(1.0, 0.5 * vol + sent)

    # 中～高波动 + 悲观 => 熊市/风险厌恶
    if (mid_vol or high_vol) and bearish:
        return "bear", min(1.0, vol + abs(sent))

    # 低波动 + 情绪中性 => 区间/震荡
    if low_vol and neutral:
        return "chop", min(1.0, 0.2 + vol)

    return "unknown", 0.1

# --- API Endpoints ---
@app.get("/api/v1/health", tags=["通用"])
def health_check():
    return {"status": "ok", "service": "Strategy Service"}

@app.post(
    "/api/v1/predict/dynamic-parameters",
    response_model=StrategyParameters,
    tags=["策略"],
)
def get_dynamic_parameters(input_data: PredictionInput):
    """
    接收最新的市场与宏观情绪数据，返回「对齐业内」的 Q（宏观波动率视角）和策略参数。

    优化点：
    1. 使用 GLM 模型预测短期波动率 (Q)
    2. 结合 realized_vol + 情绪 推断宏观 regime（牛/熊/震荡/恐慌等）
    3. 根据宏观 regime 调整网格间距（高风险期放大网格、低风险期收紧）
    """
    if not model:
        # 如果模型未加载，返回一个安全的默认值
        raise HTTPException(status_code=503, detail="模型尚未加载")
    
    try:
        # 准备模型输入数据（与训练保持一致）
        data_dict = {
            "const": 1.0,  # 不要忘记常数项
            "sentiment_score_lag1": input_data.sentiment_score_lag1,
            "volatility_lag1": input_data.volatility_lag1,
        }
        input_df = pd.DataFrame([data_dict])
        
        # 使用加载的 GLM 模型进行波动率预测 (Q)
        predicted_volatility = float(model.predict(input_df)[0])

        # 计算预测区间，估计不确定性
        prediction_ci = model.get_prediction(input_df).conf_int(alpha=0.05)[0]
        confidence_width = float(prediction_ci[1] - prediction_ci[0])
        confidence_level = float(max(0.0, min(1.0, 1.0 - confidence_width)))

        # 宏观 regime 识别：如果调用方未显式给 macro_regime，就用 vol + sentiment 自动推断
        if input_data.macro_regime:
            macro_regime = input_data.macro_regime
            regime_score = 0.5  # 由调用方指定时，我们认为强度中等
        else:
            macro_regime, regime_score = _infer_macro_regime(
                realized_vol=input_data.volatility_lag1,
                sentiment=input_data.sentiment_score_lag1,
            )

        # 【核心业务逻辑】将预测的波动率 + 宏观 regime 转为网格大小
        # 业界常见直觉：
        # - 高波动 & panic: 放大网格，降频率，避免在极端行情中过度交易
        # - 慢牛: 稍微放宽网格，允许趋势持仓
        # - 震荡: 收紧网格，吃波动
        base_grid_size: float
        if predicted_volatility > 0.8:
            base_grid_size = 3.0
        elif predicted_volatility > 0.6:
            base_grid_size = 2.4
        elif predicted_volatility > 0.4:
            base_grid_size = 1.8
        else:
            base_grid_size = 1.2

        # 根据宏观 regime 做二次调整
        regime_adjustment = 1.0
        if macro_regime in ("panic", "high_vol_bull"):
            # 极端行情：网格扩大，减少撮合次数
            regime_adjustment = 1.0 + 0.5 * regime_score
        elif macro_regime == "bull":
            # 慢牛：略微放宽网格
            regime_adjustment = 1.0 + 0.2 * regime_score
        elif macro_regime == "bear":
            # 熊市：保持略宽网格，避免频繁逆势交易
            regime_adjustment = 1.0 + 0.3 * regime_score
        elif macro_regime == "chop":
            # 震荡市：收紧网格，更积极做市
            regime_adjustment = max(0.7, 1.0 - 0.3 * regime_score)

        recommended_grid_size = round(base_grid_size * regime_adjustment, 2)

        return StrategyParameters(
            source="GLM_Macro_Q_Model",
            predicted_volatility=predicted_volatility,
            recommended_grid_size=recommended_grid_size,
            confidence_level=confidence_level,
            macro_regime=macro_regime,
            regime_score=regime_score,
        )

    except Exception as e:
        logging.error(f"策略参数预测失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))