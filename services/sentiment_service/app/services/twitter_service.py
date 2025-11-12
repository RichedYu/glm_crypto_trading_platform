# /services/sentiment_service/app/services/twitter_service.py

import tweepy
import pandas as pd
from app.core.config import get_settings
import itertools
import logging
import threading
from typing import List

# --- 1. API密钥池 (API Key Pool) ---
# 这是一个线程安全的类，用于管理和轮换你的多个Twitter API密钥
class ApiKeyPool:
    def __init__(self):
        settings = get_settings()
        self.tokens: List[str] = settings.twitter_token_list
        
        # 检查.env中是否配置了有效的token
        if not self.tokens or not all(self.tokens):
            raise ValueError("未在.env文件中配置任何有效的TWITTER_BEARER_TOKENS")
            
        # 创建一个可以无限循环的迭代器，这让我们可以不断地轮换密钥
        self._client_pool = itertools.cycle([tweepy.Client(token) for token in self.tokens])
        # 创建一个线程锁，确保在多线程环境下安全地获取下一个客户端
        self._lock = threading.Lock()
        
        logging.info(f"✅ API密钥池初始化成功，共加载 {len(self.tokens)} 个密钥。")

    def get_next_client(self) -> tweepy.Client:
        """
        线程安全地从池中获取下一个tweepy客户端实例。
        每次调用，它都会返回使用下一个密钥初始化的客户端。
        """
        with self._lock:
            client = next(self._client_pool)
            logging.info(f"正在使用密钥池中的下一个密钥 (Token ending with '...{client.bearer_token[-4:]}')")
            return client

# 在模块级别创建一个全局的密钥池实例，供整个服务共享
# 这样可以避免每次请求都重新创建对象
api_key_pool = ApiKeyPool()


# --- 2. 数据获取函数 (Data Fetching Function) ---
def get_tweets_sync(query: str, max_results: int = 10) -> pd.DataFrame:
    """
    这是一个【同步】函数，负责执行实际的Twitter API请求。
    它将被FastAPI的线程池调用，以避免阻塞。
    """
    try:
        # 从全局池中获取一个客户端实例来进行本次请求
        client = api_key_pool.get_next_client()
        
        # 构建查询：搜索关键词，排除转推，只看英文推文以保证模型效果
        search_query = f"{query} -is:retweet lang:en"
        
        # 执行同步的API调用
        response = client.search_recent_tweets(
            query=search_query,
            max_results=max_results,
            tweet_fields=["created_at", "text", "public_metrics"]
        )
        
        # 检查是否有返回数据
        if not response.data:
            return pd.DataFrame()
            
        # 将返回的数据整理成易于处理的DataFrame格式
        tweet_list = []
        for tweet in response.data:
            metrics = tweet.public_metrics or {}
            tweet_list.append({
                'created_at': tweet.created_at,
                'text': tweet.text,
                'retweet_count': metrics.get('retweet_count', 0),
                'reply_count': metrics.get('reply_count', 0),
                'like_count': metrics.get('like_count', 0),
                'impression_count': metrics.get('impression_count', 0)
            })
            
        return pd.DataFrame(tweet_list)
        
    # 将tweepy的特定异常转换为我们可以处理的通用异常
    except tweepy.errors.TooManyRequests:
        # 这个异常会被捕获并重新抛出，以便上层API可以返回429状态码
        raise
    except Exception as e:
        logging.error(f"从Twitter获取数据时发生未知错误: {e}", exc_info=True)
        # 对于其他所有错误，也向上抛出，由API层统一处理为500错误
        raise

