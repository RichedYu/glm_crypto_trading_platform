# /services/trading_service/Dockerfile

# 使用一个稳定、轻量的Python版本作为基础镜像
FROM python:3.10-slim

# 在容器内创建一个工作目录
WORKDIR /app

# 将依赖文件复制到容器中
COPY requirements.txt .

# 安装所有Python库
RUN pip install --no-cache-dir -r requirements.txt

# 将你的应用代码复制到容器的工作目录中
# 注意：我们将整个 /app 目录复制过去
COPY ./app /app/app

# 定义当容器启动时要执行的默认命令
# 它会用uvicorn来运行你的FastAPI应用
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]