# /services/sentiment_service/app/services/nlp_service.py
import pandas as pd
from transformers import pipeline
from functools import lru_cache

@lru_cache(maxsize=1) # 使用缓存确保模型只被加载一次
def get_sentiment_pipeline():
    """
    加载并返回一个预训练的金融情感分析模型 (FinBERT)。
    第一次调用时会下载模型，可能需要一些时间。
    """
    # 使用专门为金融领域微调的BERT模型
    sentiment_task = pipeline("sentiment-analysis", model="ProsusAI/finbert")
    return sentiment_task

def analyze_sentiment_for_tweets(df: pd.DataFrame) -> dict:
    """
    对一个包含推文文本的DataFrame进行情感分析。
    """
    sentiment_pipeline = get_sentiment_pipeline()
    
    # transformers的pipeline可以直接处理文本列表
    texts = df['text'].tolist()
    sentiments = sentiment_pipeline(texts)
    
    df['sentiment_label'] = [s['label'] for s in sentiments]
    df['sentiment_score'] = [s['score'] for s in sentiments]
    
    # 将 "positive", "negative", "neutral" 转换为数值以便计算
    # positive: 1, neutral: 0, negative: -1
    def label_to_value(label):
        if label == 'positive':
            return 1
        elif label == 'negative':
            return -1
        else:
            return 0
            
    df['sentiment_value'] = df['sentiment_label'].apply(label_to_value)
    
    # 计算加权平均情感分数（用点赞数作为权重）
    weighted_sentiment_score = (df['sentiment_value'] * df['sentiment_score'] * (df['like_count'] + 1)).sum() / (df['like_count'] + 1).sum()
    
    # 确定整体情感
    overall_sentiment_label = "neutral"
    if weighted_sentiment_score > 0.1:
        overall_sentiment_label = "positive"
    elif weighted_sentiment_score < -0.1:
        overall_sentiment_label = "negative"
        
    return {
        "overall_sentiment": overall_sentiment_label,
        "weighted_score": round(weighted_sentiment_score, 4),
        "tweets_analyzed": len(df),
        "tweets_details": df.to_dict('records')
    }
