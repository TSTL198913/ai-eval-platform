#!/bin/bash
# =====================================================================
# AI Evaluation Platform - 部署验证脚本
# =====================================================================
# 
# 功能：
# 1. 检查服务状态
# 2. 功能测试（API、任务队列）
# 3. 查看日志
# 4. 健康检查
#
# 使用方法：
#   chmod +x verify_deploy.sh
#   ./verify_deploy.sh [命令]
#
# 命令：
#   status    - 查看服务状态
#   api       - 测试 API 接口
#   task      - 测试任务队列
#   health    - 健康检查
#   logs      - 查看日志（最近 100 行）
#   logs-all  - 查看完整日志
#   test      - 完整功能测试
#   help      - 显示帮助
#
# =====================================================================

set -e

# 配置
API_URL="${API_URL:-http://localhost:8000}"
REDIS_URL="${REDIS_URL:-redis://localhost:6379}"
LOG_DIR="${LOG_DIR:-./logs}"
PROJECT_DIR="${PROJECT_DIR:-/opt/ai-eval-platform}"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 打印函数
print_header() {
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}========================================${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

# 检查 Docker 服务状态
check_docker_status() {
    print_header "Docker 服务状态"
    docker compose ps
}

# 检查容器健康状态
check_container_health() {
    print_header "容器健康检查"
    
    containers=$(docker compose ps -q)
    for container_id in $containers; do
        container_name=$(docker inspect --format='{{.Name}}' $container_id | sed 's/^\///')
        health=$(docker inspect --format='{{.State.Health.Status}}' $container_id 2>/dev/null || echo "none")
        status=$(docker inspect --format='{{.State.Status}}' $container_id)
        
        echo -n "容器: $container_name | 状态: $status"
        if [ "$health" != "none" ]; then
            echo -e " | 健康: $health"
        else
            echo ""
        fi
    done
}

# API 健康检查
check_api_health() {
    print_header "API 健康检查"
    
    echo "测试: GET /health"
    response=$(curl -s -w "\nHTTP_CODE:%{http_code}" $API_URL/health 2>/dev/null || echo "HTTP_CODE:000")
    
    if echo "$response" | grep -q "HTTP_CODE:200"; then
        print_success "API 服务正常"
        echo "$response" | grep -v "HTTP_CODE"
    else
        print_error "API 服务异常"
        echo "$response"
    fi
}

# API 功能测试
test_api() {
    print_header "API 功能测试"
    
    # 测试 1: 契约拦截
    echo ""
    echo "测试 1: 契约拦截（无效输入应返回 CONTRACT_ERROR）"
    echo "-------------------------------------------"
    response=$(curl -s -X POST $API_URL/api/v1/evaluate \
        -H "Content-Type: application/json" \
        -d '{"wrong": "data"}' 2>/dev/null)
    
    if echo "$response" | grep -q "CONTRACT_ERROR"; then
        print_success "契约拦截正常"
        echo "$response" | python3 -m json.tool 2>/dev/null || echo "$response"
    else
        print_error "契约拦截异常"
        echo "$response"
    fi
    
    # 测试 2: 业务路由
    echo ""
    echo "测试 2: 业务路由（finance 类型）"
    echo "-------------------------------------------"
    response=$(curl -s -X POST $API_URL/api/v1/evaluate \
        -H "Content-Type: application/json" \
        -d '{
            "id": "TEST_001",
            "type": "finance",
            "payload": {
                "case_id": "c1",
                "user_input": "10000元存一年定期，利率3%，利息多少？",
                "expected_output": "300元",
                "metadata": {"rate": 0.03}
            }
        }' 2>/dev/null)
    
    if echo "$response" | grep -q "evaluation_status"; then
        print_success "业务路由正常"
        echo "$response" | python3 -m json.tool 2>/dev/null || echo "$response"
    else
        print_warning "业务路由响应异常，请检查 LLM 配置"
        echo "$response"
    fi
    
    # 测试 3: 异步任务提交
    echo ""
    echo "测试 3: 异步任务提交"
    echo "-------------------------------------------"
    response=$(curl -s -X POST $API_URL/api/v1/evaluate/async \
        -H "Content-Type: application/json" \
        -d '{
            "id": "ASYNC_001",
            "type": "general",
            "payload": {
                "case_id": "c2",
                "user_input": "你好",
                "expected_output": "你好"
            }
        }' 2>/dev/null)
    
    if echo "$response" | grep -q "task_id"; then
        print_success "异步任务提交正常"
        echo "$response" | python3 -m json.tool 2>/dev/null || echo "$response"
    else
        print_warning "异步任务提交响应异常"
        echo "$response"
    fi
}

# 任务队列测试
test_task_queue() {
    print_header "任务队列测试"
    
    # 检查 Redis 连接
    echo ""
    echo "检查 Redis 连接..."
    if redis-cli -h localhost ping > /dev/null 2>&1; then
        print_success "Redis 连接正常"
        redis-cli info | grep -E "redis_version|connected_clients|used_memory_human"
    else
        print_error "Redis 连接失败"
    fi
    
    # 检查 Celery Worker
    echo ""
    echo "检查 Celery Worker..."
    if docker compose exec -T worker celery -A src.worker.celery_app inspect stats > /dev/null 2>&1; then
        print_success "Celery Worker 运行正常"
    else
        print_warning "Celery Worker 可能未运行或无法连接"
    fi
    
    # 检查任务队列
    echo ""
    echo "检查任务队列..."
    redis-cli llen celery 2>/dev/null || echo "无法获取队列长度"
    redis-cli llen celery 2>/dev/null || echo "无法获取结果队列长度"
}

# 查看日志
view_logs() {
    print_header "查看日志"
    
    # API 日志
    if [ -f "$LOG_DIR/api.log" ]; then
        echo ""
        echo -e "${YELLOW}API 日志 ($LOG_DIR/api.log):${NC}"
        echo "-------------------------------------------"
        tail -100 "$LOG_DIR/api.log"
    fi
    
    # Worker 日志
    if [ -f "$LOG_DIR/worker.log" ]; then
        echo ""
        echo -e "${YELLOW}Worker 日志 ($LOG_DIR/worker.log):${NC}"
        echo "-------------------------------------------"
        tail -100 "$LOG_DIR/worker.log"
    fi
    
    # Docker 日志
    echo ""
    echo -e "${YELLOW}Docker 容器日志 (API):${NC}"
    echo "-------------------------------------------"
    docker compose logs --tail=100 api 2>/dev/null || echo "无法获取 API 日志"
    
    echo ""
    echo -e "${YELLOW}Docker 容器日志 (Worker):${NC}"
    echo "-------------------------------------------"
    docker compose logs --tail=100 worker 2>/dev/null || echo "无法获取 Worker 日志"
}

# 完整功能测试
full_test() {
    print_header "完整功能测试"
    
    echo ""
    echo "开始全面测试..."
    echo ""
    
    # 1. 服务状态
    check_docker_status
    
    # 2. 健康检查
    check_container_health
    check_api_health
    
    # 3. API 测试
    test_api
    
    # 4. 任务队列测试
    test_task_queue
    
    # 5. 日志检查
    echo ""
    echo "最近日志:"
    docker compose logs --tail=20 2>/dev/null || echo "无法获取日志"
    
    print_header "测试完成"
}

# 帮助信息
show_help() {
    echo ""
    echo "AI Evaluation Platform - 部署验证脚本"
    echo ""
    echo "使用方法: $0 [命令]"
    echo ""
    echo "可用命令:"
    echo "  status     查看 Docker 服务状态"
    echo "  health     健康检查（容器 + API）"
    echo "  api        API 功能测试"
    echo "  task       任务队列测试"
    echo "  logs       查看日志（最近 100 行）"
    echo "  logs-all   查看完整日志"
    echo "  test       完整功能测试"
    echo "  help       显示帮助"
    echo ""
    echo "环境变量:"
    echo "  API_URL         API 地址 (默认: http://localhost:8000)"
    echo "  REDIS_URL       Redis 地址 (默认: redis://localhost:6379)"
    echo "  LOG_DIR         日志目录 (默认: ./logs)"
    echo "  PROJECT_DIR     项目目录 (默认: /opt/ai-eval-platform)"
    echo ""
    echo "示例:"
    echo "  API_URL=http://localhost:9000 $0 api"
    echo "  $0 test"
    echo ""
}

# 主程序
case "${1:-help}" in
    status)
        check_docker_status
        ;;
    health)
        check_container_health
        check_api_health
        ;;
    api)
        check_api_health
        test_api
        ;;
    task)
        test_task_queue
        ;;
    logs)
        docker compose logs --tail=100
        ;;
    logs-all)
        docker compose logs
        ;;
    test)
        full_test
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        print_error "未知命令: $1"
        echo "运行 '$0 help' 查看帮助"
        exit 1
        ;;
esac
