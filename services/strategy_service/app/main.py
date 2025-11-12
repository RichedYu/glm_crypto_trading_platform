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
    sentiment_score_lag1: float
    volatility_lag1: float

class StrategyParameters(BaseModel):
    source: str
    predicted_volatility: float
    recommended_grid_size: float
    confidence_level: float

# --- API Endpoints ---
@app.get("/api/v1/health", tags=["通用"])
def health_check():
    return {"status": "ok", "service": "Strategy Service"}

@app.post("/api/v1/predict/dynamic-parameters", response_model=StrategyParameters, tags=["策略"])
def get_dynamic_parameters(input_data: PredictionInput):
    """
    接收最新的市场数据，返回GLM模型预测的动态交易参数。
    """
    if not model:
        # 如果模型未加载，返回一个安全的默认值
        raise HTTPException(status_code=503, detail="模型尚未加载")
    
    try:
        # 准备模型输入数据
        data_dict = {
            'const': 1.0, # 不要忘记常数项
            'sentiment_score_lag1': input_data.sentiment_score_lag1,
            'volatility_lag1': input_data.volatility_lag1
        }
        input_df = pd.DataFrame([data_dict])
        
        # 使用加载的模型进行预测
        predicted_volatility = model.predict(input_df)[0]
        
        # 【核心业务逻辑】将预测的波动率转换为网格大小
        # 这是一个简化的规则，你可以设计的更复杂
        if predicted_volatility > 0.8:
            grid_size = 3.5
        elif predicted_volatility > 0.6:
            grid_size = 2.5
        elif predicted_volatility > 0.4:
            grid_size = 2.0
        else:
            grid_size = 1.5
            
        # 获取预测的置信区间，可以用来调整风险
        prediction_ci = model.get_prediction(input_df).conf_int(alpha=0.05)[0]
        confidence_width = prediction_ci[1] - prediction_ci[0]
        
        return StrategyParameters(
            source="GLM_Gamma_Model",
            predicted_volatility=predicted_volatility,
            recommended_grid_size=grid_size,
            confidence_level=(1 - confidence_width) # 简单的置信度度量
        )

    except Exception as e:
        logging.error(f"策略参数预测失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))