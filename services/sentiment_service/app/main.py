# /services/sentiment_service/app/main.py

import logging
from fastapi import FastAPI, HTTPException, status
from fastapi.concurrency import run_in_threadpool # 导入线程池工具
import tweepy

# 【修改】使用绝对路径导入，确保稳定性
from app.services.twitter_service import get_tweets_sync
from app.services.nlp_service import analyze_sentiment_for_tweets, get_sentiment_pipeline

# --- FastAPI 应用设置 ---
app = FastAPI(
    title="情感分析服务 (Sentiment Service)",
    description="负责从社交媒体抓取数据并进行情感分析。"
)

# --- 应用生命周期事件 ---
@app.on_event("startup")
def startup_event():
    """服务启动时，预加载昂贵的NLP模型，避免第一次请求过慢。"""
    logging.info("正在预加载情感分析模型...")
    get_sentiment_pipeline()
    logging.info("✅ 模型加载完毕，服务已就绪。")

# --- API Endpoints ---
@app.get("/api/v1/health", tags=["通用"])
def health_check():
    """健康检查接口，用于监控服务是否存活。"""
    return {"status": "ok", "service": "Sentiment Service"}

@app.get("/api/v1/sentiment/twitter", tags=["情感分析"])
async def get_twitter_sentiment(query: str = "BNB", max_results: int = 10):
    """
    根据查询词获取Twitter的情感分析结果。
    """
    try:
        # 【修改】在线程池中运行同步的 get_tweets_sync 函数
        # 这样可以避免阻塞FastAPI的异步事件循环，提升服务性能
        tweets_df = await run_in_threadpool(get_tweets_sync, query, max_results)
        
        if tweets_df.empty:
            logging.warning(f"未能为查询 '{query}' 找到任何推文。")
            return {"query": query, "overall_sentiment": "neutral", "weighted_score": 0.0, "tweets_analyzed": 0}

        # NLP分析是CPU密集型任务，也可以在线程池中运行
        sentiment_result = await run_in_threadpool(analyze_sentiment_for_tweets, tweets_df)
        
        return sentiment_result

    # 【修改】更精确的错误处理
    except tweepy.errors.TooManyRequests:
        logging.warning("触发Twitter API速率限制！")
        # 返回 429 错误码，让调用方（如 train.py）知道是速率问题
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Twitter API rate limit exceeded. Please wait.",
        )
    except Exception as e:
        logging.error(f"处理情感分析请求时发生未知错误: {e}", exc_info=True)
        # 对于所有其他内部错误，返回标准的 500 错误码
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"An internal error occurred: {e}"
        )
