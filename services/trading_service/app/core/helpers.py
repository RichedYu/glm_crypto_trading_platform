from datetime import datetime, timezone
import requests
import logging
import os

logger = logging.getLogger(__name__)

def now_utc_iso() -> str:
    """返回当前UTC时间的ISO 8601格式字符串 (带Z后缀)"""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

def to_utc_iso(dt: datetime) -> str:
    """将datetime对象转换为UTC时间的ISO 8601格式字符串 (带Z后缀)"""
    if dt.tzinfo is None:
        # 如果是naive time，假定为UTC
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def send_pushplus_message(content: str, title: str = "交易通知") -> bool:
    """
    发送PushPlus消息通知
    
    Args:
        content: 消息内容
        title: 消息标题
        
    Returns:
        bool: 发送是否成功
    """
    token = os.getenv("PUSHPLUS_TOKEN", "")
    if not token:
        logger.warning("PUSHPLUS_TOKEN 未配置，跳过消息推送")
        return False
    
    try:
        url = "http://www.pushplus.plus/send"
        data = {
            "token": token,
            "title": title,
            "content": content,
            "template": "txt"
        }
        response = requests.post(url, json=data, timeout=10)
        result = response.json()
        
        if result.get("code") == 200:
            logger.info(f"PushPlus消息发送成功: {title}")
            return True
        else:
            logger.warning(f"PushPlus消息发送失败: {result}")
            return False
    except Exception as e:
        logger.error(f"PushPlus消息发送异常: {e}")
        return False


def format_trade_message(
    side: str,
    symbol: str,
    price: float,
    amount: float,
    total: float,
    grid_size: float,
    retry_count: tuple = None
) -> str:
    """
    格式化交易消息
    
    Args:
        side: 交易方向 ('buy' 或 'sell')
        symbol: 交易对
        price: 成交价格
        amount: 成交数量
        total: 成交总额
        grid_size: 当前网格大小
        retry_count: 重试次数元组 (当前次数, 最大次数)
        
    Returns:
        str: 格式化后的消息字符串
    """
    side_emoji = "🟢" if side == "buy" else "🔴"
    side_text = "买入" if side == "buy" else "卖出"
    
    message = f"""
{side_emoji} {side_text}成功
━━━━━━━━━━━━━━━━━━━━
📊 交易对: {symbol}
💰 价格: {price:.2f} USDT
📦 数量: {amount:.8f}
💵 总额: {total:.2f} USDT
📐 网格: {grid_size:.2f}%
⏰ 时间: {now_utc_iso()}
"""
    
    if retry_count:
        message += f"🔄 重试: {retry_count[0]}/{retry_count[1]}\n"
    
    return message.strip()
