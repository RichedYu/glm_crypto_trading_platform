from datetime import datetime, timezone

def now_utc_iso() -> str:
    """返回当前UTC时间的ISO 8601格式字符串 (带Z后缀)"""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

def to_utc_iso(dt: datetime) -> str:
    """将datetime对象转换为UTC时间的ISO 8601格式字符串 (带Z后缀)"""
    if dt.tzinfo is None:
        # 如果是naive time，假定为UTC
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
