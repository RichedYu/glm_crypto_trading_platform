    # /services/strategy_service/Dockerfile
    FROM python:3.10-slim

    WORKDIR /app

    # 安装必要的系统依赖
    RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        && rm -rf /var/lib/apt/lists/*

    COPY requirements.txt .
    RUN pip install --no-cache-dir -r requirements.txt

    COPY ./app /app/app
    COPY ./artifacts /app/artifacts

    CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
    