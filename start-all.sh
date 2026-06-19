#!/bin/bash
# =====================================================================
# 一键部署脚本 - 在虚拟机上执行
# =====================================================================

set -e

echo "=============================================="
echo "  AI Eval Platform - 一键部署"
echo "=============================================="

# 1. 启动监控栈
echo ""
echo "[1/2] 启动监控栈..."
docker-compose -f deploy/docker-compose.monitoring.yml up -d

# 2. 启动API服务
echo ""
echo "[2/2] 启动API服务..."
docker-compose -f docker-compose.prod.yml up -d

# 3. 等待服务启动
echo ""
echo "等待服务启动..."
sleep 15

# 4. 检查服务状态
echo ""
echo "=============================================="
echo "  服务状态"
echo "=============================================="
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

echo ""
echo "=============================================="
echo "  健康检查"
echo "=============================================="

# API健康检查
if curl -s -f http://localhost:8000/health > /dev/null 2>&1; then
    echo "✅ API: 健康"
else
    echo "⚠️ API: 未就绪（可能需要更多时间启动）"
fi

# Prometheus健康检查
if curl -s -f http://localhost:9090/-/healthy > /dev/null 2>&1; then
    echo "✅ Prometheus: 健康"
else
    echo "⚠️ Prometheus: 未就绪"
fi

# Grafana健康检查
if curl -s -f http://localhost:3000/api/health > /dev/null 2>&1; then
    echo "✅ Grafana: 健康"
else
    echo "⚠️ Grafana: 未就绪"
fi

echo ""
echo "=============================================="
echo "  访问地址"
echo "=============================================="
echo "  API:         http://192.168.30.134:8000"
echo "  Prometheus:  http://192.168.30.134:9090"
echo "  Grafana:     http://192.168.30.134:3000"
echo "  Pushgateway: http://192.168.30.134:9091"
echo "=============================================="