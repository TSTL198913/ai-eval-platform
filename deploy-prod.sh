#!/bin/bash
set -e

echo "=============================================="
echo "AI-Eval-Pro Production Deployment"
echo "=============================================="

APP_DIR="/opt/ai-eval-platform"
REPO_URL="https://github.com/TSTL198913/ai-eval-platform.git"
BRANCH="develop_06"

echo ""
echo "[1/6] 准备部署目录..."
mkdir -p $APP_DIR

echo ""
echo "[2/6] 克隆/更新代码..."
if [ -d "$APP_DIR/.git" ]; then
    cd $APP_DIR
    git fetch origin
    git checkout $BRANCH
    git pull origin $BRANCH
else
    git clone -b $BRANCH $REPO_URL $APP_DIR
    cd $APP_DIR
fi

echo ""
echo "[3/6] 配置环境变量..."
if [ ! -f ".env.prod" ]; then
    cp .env.prod.example .env.prod
    echo "DATABASE_URL=postgresql://eval:eval123@postgres:5432/ai_eval" > .env.prod
    echo "REDIS_URL=redis://redis:6379/0" >> .env.prod
    echo "RABBITMQ_URL=amqp://guest:guest@rabbitmq:5672//" >> .env.prod
    echo "CELERY_BROKER_URL=amqp://guest:guest@rabbitmq:5672//" >> .env.prod
    echo "CELERY_RESULT_BACKEND=redis://redis:6379/0" >> .env.prod
    echo "API_HOST=0.0.0.0" >> .env.prod
    echo "API_PORT=8000" >> .env.prod
    echo "DEBUG=false" >> .env.prod
    echo "LOG_LEVEL=INFO" >> .env.prod
    echo "LLM_PROVIDER=deepseek" >> .env.prod
    echo "DEEPSEEK_API_KEY=sk-999e073bd5204fb6893fa3255f520fd6" >> .env.prod
fi

echo ""
echo "[4/6] 停止旧服务..."
docker-compose -f docker-compose.prod.yml down 2>/dev/null || true

echo ""
echo "[5/6] 启动生产环境服务..."
docker-compose -f docker-compose.prod.yml up -d

echo ""
echo "[6/6] 等待服务启动并验证..."
echo "等待基础设施启动..."
sleep 30

echo ""
echo "检查容器状态..."
docker ps

echo ""
echo "等待API启动..."
sleep 20

echo ""
echo "健康检查..."
curl -s http://localhost:8000/health || echo "API健康检查失败"

echo ""
echo "=============================================="
echo "部署完成！"
echo "=============================================="
echo ""
echo "服务地址:"
echo "  API: http://192.168.30.134:8000"
echo "  前端: http://192.168.30.134"
echo "  RabbitMQ管理: http://192.168.30.134:15672"