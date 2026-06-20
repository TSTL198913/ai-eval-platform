#!/bin/bash
# =====================================================================
# AI Eval Platform - 远程部署脚本
# 部署到 Ubuntu 虚拟机 (192.168.30.134)
# =====================================================================

set -e

# 配置
REMOTE_HOST="192.168.30.134"
REMOTE_USER="zs13"
REMOTE_PORT="22"
APP_DIR="/home/${REMOTE_USER}/ai-eval-platform"
SSH_KEY="${HOME}/.ssh/id_rsa"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# 检查SSH连接
check_ssh() {
    log_info "检查SSH连接..."
    if ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no ${REMOTE_USER}@${REMOTE_HOST} "echo 'SSH OK'" 2>/dev/null; then
        log_info "SSH连接成功"
        return 0
    else
        log_error "SSH连接失败"
        return 1
    fi
}

# 创建远程目录结构
create_dirs() {
    log_info "创建远程目录结构..."
    ssh ${REMOTE_USER}@${REMOTE_HOST} 'mkdir -p ~/ai-eval-platform/{src,tests,scripts,deploy,docs,data,logs} && mkdir -p ~/ai-eval-platform/.github/workflows && mkdir -p ~/ai-eval-platform/grafana/{dashboards,datasources} && mkdir -p ~/ai-eval-platform/deploy/{prometheus,monitoring} && echo "目录创建完成"'
}

# 同步代码到远程
sync_code() {
    log_info "同步代码到远程服务器..."
    rsync -avz --exclude='.git' --exclude='__pycache__' --exclude='.venv' \
        --exclude='node_modules' --exclude='.pytest_cache' \
        --exclude='*.log' --exclude='coverage.json' \
        -e "ssh -o StrictHostKeyChecking=no" \
        ./ ${REMOTE_USER}@${REMOTE_HOST}:${APP_DIR}/
    log_info "代码同步完成"
}

# 安装Docker（如果未安装）
install_docker() {
    log_info "检查Docker安装..."
    if ssh ${REMOTE_USER}@${REMOTE_HOST} "which docker" 2>/dev/null; then
        log_info "Docker已安装"
    else
        log_warn "Docker未安装，正在安装..."
        ssh ${REMOTE_USER}@${REMOTE_HOST} 'curl -fsSL https://get.docker.com | sh && sudo usermod -aG docker $USER && sudo systemctl enable docker && sudo systemctl start docker'
        log_info "Docker安装完成"
    fi
}

# 启动监控栈
start_monitoring() {
    log_info "启动监控栈..."
    ssh ${REMOTE_USER}@${REMOTE_HOST} 'cd ~/ai-eval-platform && docker-compose -f deploy/docker-compose.monitoring.yml up -d && echo "监控栈启动完成" && docker ps'
}

# 检查服务状态
check_services() {
    log_info "检查服务状态..."
    ssh ${REMOTE_USER}@${REMOTE_HOST} 'echo "=== Docker容器状态 ===" && docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" && echo "" && echo "=== Prometheus状态 ===" && curl -s http://localhost:9090/-/healthy || echo "Prometheus未就绪" && echo "" && echo "=== Pushgateway状态 ===" && curl -s http://localhost:9091/-/healthy || echo "Pushgateway未就绪" && echo "" && echo "=== Grafana状态 ===" && curl -s http://localhost:3000/api/health || echo "Grafana未就绪"'
}

# 部署主函数
deploy() {
    log_info "开始部署 AI Eval Platform 到 ${REMOTE_HOST}..."

    if ! check_ssh; then
        log_error "SSH连接检查失败，终止部署"
        exit 1
    fi

    create_dirs
    sync_code
    install_docker
    start_monitoring
    check_services

    log_info "=========================================="
    log_info "部署完成!"
    log_info "=========================================="
    log_info "Prometheus: http://${REMOTE_HOST}:9090"
    log_info "Grafana:    http://${REMOTE_HOST}:3000 (admin/admin)"
    log_info "Pushgateway: http://${REMOTE_HOST}:9091"
    log_info "=========================================="
}

# 查看日志
logs() {
    log_info "查看容器日志..."
    ssh ${REMOTE_USER}@${REMOTE_HOST} "docker logs -f ai-eval-prometheus"
}

# 停止服务
stop() {
    log_info "停止服务..."
    ssh ${REMOTE_USER}@${REMOTE_HOST} "cd ~/ai-eval-platform && docker-compose -f deploy/docker-compose.monitoring.yml down"
    log_info "服务已停止"
}

# 主入口
case "${1:-deploy}" in
    deploy)
        deploy
        ;;
    sync)
        sync_code
        ;;
    start)
        start_monitoring
        ;;
    stop)
        stop
        ;;
    status)
        check_services
        ;;
    logs)
        logs
        ;;
    *)
        echo "用法: $0 {deploy|sync|start|stop|status|logs}"
        exit 1
        ;;
esac
