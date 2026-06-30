# =====================================================================
# AI Evaluation Platform - Dockerfile
# =====================================================================

FROM python:3.10-slim

# 设置工作目录
WORKDIR /app

# 配置 pip 使用国内镜像源加速下载
RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple \
    && pip config set global.trusted-host pypi.tuna.tsinghua.edu.cn

# 安装系统依赖
RUN sed -i 's/deb.debian.org/mirrors.tuna.tsinghua.edu.cn/g' /etc/apt/sources.list.d/debian.sources \
    && apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制源代码
COPY src/ ./src/
COPY tests/ ./tests/
COPY pyproject.toml .
COPY pytest.ini .

# 设置环境变量
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# 暴露端口
EXPOSE 8000

# 默认命令 - 启动 API 服务器
CMD ["uvicorn", "src.api.server:app", "--host", "0.0.0.0", "--port", "8000"]
