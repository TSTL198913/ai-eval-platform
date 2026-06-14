#!/bin/bash
# =====================================================================
# AI Evaluation Platform - 生产环境部署脚本
# 架构师最佳实践：
# 1. 不在服务器上构建镜像，只拉取预构建镜像
# 2. 使用 docker compose 无缝替换实现零停机更新
# 3. 配置滚动更新策略
# =====================================================================

set -e

# 配置变量
DOCKER_REGISTRY="${DOCKER_REGISTRY:-ghcr.io/tstl198913}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
COMPOSE_FILE="docker-compose.prod.yml"
ENV_FILE=".env.prod"

echo "=============================================="
echo "  AI Evaluation Platform - 生产部署"
echo "=============================================="

# 1. 检查环境变量文件
if [ -f "$ENV_FILE" ]; then
    echo "✅ 加载环境变量文件: $ENV_FILE"
    export $(cat "$ENV_FILE" | grep -v '^#' | xargs)
else
    echo "⚠️ 未找到环境变量文件: $ENV_FILE，使用默认配置"
fi

# 2. 拉取最新镜像（不在服务器构建）
echo ""
echo "[步骤 1/3] 拉取预构建镜像..."
echo "  镜像: ${DOCKER_REGISTRY}/ai-eval-platform:${IMAGE_TAG}"
docker compose -f "$COMPOSE_FILE" pull

# 3. 备份当前配置（用于回滚）
echo ""
echo "[步骤 2/3] 备份当前配置..."
mkdir -p deploy_backups
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
cp "$COMPOSE_FILE" "deploy_backups/docker-compose.backup.${TIMESTAMP}.yml"
echo "  备份文件: deploy_backups/docker-compose.backup.${TIMESTAMP}.yml"

# 4. 零停机更新（使用 --remove-orphans 清理旧容器）
echo ""
echo "[步骤 3/3] 执行零停机部署更新..."
docker compose -f "$COMPOSE_FILE" up -d --remove-orphans

# 5. 验证部署状态
echo ""
echo "=============================================="
echo "  部署状态验证"
echo "=============================================="

echo ""
echo "📋 容器状态:"
docker compose -f "$COMPOSE_FILE" ps

echo ""
echo "⏳ 等待服务启动..."
sleep 10

echo ""
echo "🔍 健康检查:"
if curl -s -f http://localhost:8000/health > /dev/null; then
    echo "✅ API 服务健康检查通过"
else
    echo "❌ API 服务健康检查失败"
    echo "📝 查看日志: docker compose -f $COMPOSE_FILE logs api"
    exit 1
fi

echo ""
echo "🎉 部署完成！"
echo ""
echo "📊 服务访问地址:"
echo "  - API: http://localhost:8000"
echo "  - Prometheus: http://localhost:9090 (如果启用监控)"
echo "  - Grafana: http://localhost:3000 (如果启用监控)"
echo ""
echo "🔄 回滚命令:"
echo "  docker compose -f $COMPOSE_FILE down"
echo "  docker compose -f deploy_backups/docker-compose.backup.${TIMESTAMP}.yml up -d"
