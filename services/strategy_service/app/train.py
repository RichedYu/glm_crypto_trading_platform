# /services/strategy_service/app/train.py
import pandas as pd
import numpy as np
import ccxt
import requests
import time
from datetime import datetime, timedelta, timezone
import statsmodels.api as sm
import pickle
import os
import logging

# 配置日志，以便在容器中看到更清晰的输出
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_data(hours=72, query="BNB", max_tweets_per_hour=20):
    """从行情API和情感服务API获取并整合数据，带有智能重试机制。"""
    logging.info("开始获取数据...")
    
    # 1. 获取行情数据 (这部分不变)
    exchange = ccxt.binance()
    since = exchange.parse8601((datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat())
    ohlcv = exchange.fetch_ohlcv('BNB/USDT', '1h', since=since, limit=hours)
    price_df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    price_df['datetime'] = pd.to_datetime(price_df['timestamp'], unit='ms', utc=True)
    price_df = price_df.set_index('datetime')
    logging.info(f"成功获取了 {len(price_df)} 条K线数据。")

    # 2. 获取情感数据
    sentiment_data = []
    api_url = "http://sentiment_service:8000/api/v1/sentiment/twitter"
    logging.info(f"正在从情感服务 ({api_url}) 获取数据...")
    
    for dt in price_df.index:
        retries = 3
        while retries > 0:
            try:
                response = requests.get(api_url, params={"query": query, "max_results": max_tweets_per_hour}, timeout=30)
                
                # 【新增】智能处理API响应
                if response.status_code == 200:
                    data = response.json()
                    sentiment_score = data.get('weighted_score', 0)
                    sentiment_data.append({"datetime": dt, "sentiment_score": sentiment_score})
                    logging.info(f"成功获取 {dt.strftime('%Y-%m-%d %H:%M')} 的情感数据, 分数: {sentiment_score:.4f}")
                    time.sleep(1) # 成功后短暂等待，避免触发自己的服务速率限制
                    break # 成功了，跳出重试循环

                elif response.status_code == 429:
                    # 如果遇到速率限制，就耐心等待15分钟
                    wait_time = 15 * 60 + 5 # 等待15分钟多一点
                    logging.warning(f"遇到Twitter API速率限制 (429)，将暂停 {wait_time // 60} 分钟...")
                    time.sleep(wait_time)
                    logging.info("已恢复，重新尝试获取数据...")
                    # 这次重试不消耗重试次数
                    continue 
                
                else:
                    # 其他服务器错误，记录并进行常规重试
                    logging.error(f"调用情感服务API失败: {response.status_code} {response.text}")
                    retries -= 1
                    time.sleep(5) # 等待5秒后重试
            
            except requests.exceptions.RequestException as e:
                logging.error(f"网络连接错误: {e}，将进行重试...")
                retries -= 1
                time.sleep(10) # 网络问题，等待更长时间
        
        # 如果所有重试都失败了
        if retries == 0:
            logging.error(f"在多次重试后仍无法获取 {dt} 的情感数据，将使用默认值0。")
            sentiment_data.append({"datetime": dt, "sentiment_score": 0})
            
    sentiment_df = pd.DataFrame(sentiment_data).set_index('datetime')


    # 3. 合并与特征工程
    df = price_df.join(sentiment_df, how='inner')
    df['log_return'] = np.log(df['close'] / df['close'].shift(1))
    df['realized_volatility_1hr'] = df['log_return'].rolling(window=1).std() * np.sqrt(24*365)
    df['target_volatility_3hr'] = df['realized_volatility_1hr'].shift(-3)
    df['sentiment_score_lag1'] = df['sentiment_score'].shift(1)
    df['volatility_lag1'] = df['realized_volatility_1hr'].shift(1)
    df.dropna(inplace=True)
    logging.info("数据准备与特征工程完成。")
    return df # 假设你最后返回的是这个DataFrame

def train_volatility_model(df: pd.DataFrame):
    """使用准备好的数据训练GLM模型并保存"""
    logging.info("开始训练GLM波动率模型...")
    
    # 准备建模数据
    df_model = df.copy()
    df_model['target_volatility_3hr'] += 1e-8
    
    y = df_model['target_volatility_3hr']
    X = df_model[['sentiment_score_lag1', 'volatility_lag1']]
    X = sm.add_constant(X)
    
    # 训练伽马回归模型
    gamma_glm = sm.GLM(y, X, family=sm.families.Gamma(link=sm.families.links.log()))
    results = gamma_glm.fit()
    
    logging.info("模型训练完成！")
    print(results.summary())
    
    # 保存模型
    artifacts_path = "/app/artifacts"
    os.makedirs(artifacts_path, exist_ok=True)
    model_path = os.path.join(artifacts_path, "volatility_glm_model.pkl")
    
    with open(model_path, 'wb') as f:
        pickle.dump(results, f)
        
    logging.info(f"✅ 模型已成功保存到: {model_path}")
    
    return results

if __name__ == "__main__":
    training_data = get_data()
    if not training_data.empty:
        train_volatility_model(training_data)
    else:
        logging.error("没有获取到足够的数据来训练模型，请检查服务是否正常运行。")