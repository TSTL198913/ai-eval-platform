#!/usr/bin/env bash
# =====================================================================
# AI Evaluation Platform - Production Deployment Script
#
# 安全特性:
# - 原子回滚机制
# - 备份自动清理（保留最近7天）
# - 精确镜像清理（仅当前项目）
# - 健康检查超时保护
# =====================================================================

set -euo pipefail

# 配置
APP_DIR="/opt/ai-eval-platform"
HEALTH_ENDPOINT="${HEALTH_ENDPOINT:-http://localhost:8000/health}"
HEALTH_TIMEOUT="${HEALTH_TIMEOUT:-60}"
BACKUP_RETENTION_DAYS=7
DOCKER_IMAGE_LABEL="ai-eval-platform"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() { echo -e "${GREEN}[INFO]${NC} $*"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }

# 清理旧备份（保留最近N天）
cleanup_old_backups() {
    log_info "Cleaning up backups older than ${BACKUP_RETENTION_DAYS} days"
    find "${APP_DIR}" -maxdepth 1 -name "docker-compose.yml.backup.*" -mtime +${BACKUP_RETENTION_DAYS} -delete 2>/dev/null || true
}

# 获取当前运行的镜像ID
get_current_image() {
    local image_id=""
    local container_id
    container_id=$(docker compose ps -q app 2>/dev/null | head -1)
    if [ -n "$container_id" ]; then
        image_id=$(docker inspect --format='{{.Image}}' "$container_id" 2>/dev/null || echo "")
    fi
    echo "$image_id"
}

# 健康检查
health_check() {
    local timeout=$1
    local interval=5
    local elapsed=0

    while [ $elapsed -lt $timeout ]; do
        if curl -sf "$HEALTH_ENDPOINT" > /dev/null 2>&1; then
            return 0
        fi
        echo "Waiting for health... (${elapsed}s/${timeout}s)"
        sleep $interval
        elapsed=$((elapsed + interval))
    done
    return 1
}

# 执行回滚
perform_rollback() {
    local backup_file=$1
    local current_image=$2

    log_warn "Initiating rollback"
    docker compose down || true

    if [ -f "$backup_file" ]; then
        cp "$backup_file" docker-compose.yml
        log_info "Restored docker-compose.yml from backup"
    fi

    if [ -n "$current_image" ]; then
        if command -v yq >/dev/null 2>&1; then
            yq eval ".services.app.image = \"$current_image\"" -i docker-compose.yml
        else
            sed -i "/^services:/,/^[^ ]/ { /^  app:/,/^  / { s|image:.*|image: ${current_image}| } }" docker-compose.yml
        fi
        log_info "Restored previous image: ${current_image:0:20}..."
    fi

    docker compose up -d

    if health_check 30; then
        log_info "Rollback successful, service restored"
        return 0
    else
        log_error "Rollback also failed! Manual intervention required"
        return 1
    fi
}

# 主部署流程
main() {
    cd "$APP_DIR"

    # 1. 预处理
    cleanup_old_backups

    local current_image
    current_image=$(get_current_image)
    local timestamp
    timestamp=$(date +%Y%m%d_%H%M%S)
    local backup_file="docker-compose.yml.backup.${timestamp}"

    cp docker-compose.yml "$backup_file"
    log_info "Created backup: ${backup_file}"

    # 2. 同步代码
    log_info "Syncing code from origin/main"
    git fetch origin main
    git reset --hard origin/main

    # 3. 部署新镜像
    log_info "Pulling and starting new containers"
    docker compose pull
    docker compose up -d --remove-orphans

    # 4. 健康检查
    log_info "Running health check (timeout: ${HEALTH_TIMEOUT}s)"
    if health_check "$HEALTH_TIMEOUT"; then
        log_info "Deployment successful"
        # 只清理带当前项目标签的旧镜像，避免影响其他服务
        docker image prune -a --filter "label=${DOCKER_IMAGE_LABEL}" --filter "until=24h" -f || true
        # 清理当前备份（部署成功无需保留）
        rm -f "$backup_file"
        exit 0
    fi

    # 5. 回滚
    log_error "Health check failed, rolling back"
    if perform_rollback "$backup_file" "$current_image"; then
        # 回滚成功，但标记为失败
        exit 1
    else
        # 回滚失败，严重错误
        exit 2
    fi
}

main "$@"
