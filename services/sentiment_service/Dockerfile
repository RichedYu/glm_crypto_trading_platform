# /services/sentiment_service/Dockerfile
# /services/sentiment_service/Dockerfile
FROM python:3.10-slim

WORKDIR /app

# 1. 安装必要的系统依赖 (包括 curl 用于健康检查)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 2. 复制依赖文件并安装
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 3. 【你的绝佳方案】在构建镜像时就预先下载模型
#    这会将模型打包进最终的镜像里，实现秒级启动！
RUN python -c "from transformers import pipeline; \
    print('>>> 开始预下载 FinBERT 模型...'); \
    pipeline('sentiment-analysis', model='ProsusAI/finbert'); \
    print('>>> 模型已成功下载并缓存到镜像中！')"

# 4. 复制应用代码
COPY ./app /app/app

# 5. 定义服务启动命令
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]