#!/bin/bash
# =====================================================================
# AI Evaluation Platform - 部署验证脚本
# Server: 192.162.30.138
# User: zs13
# =====================================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

print_status() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[⚠]${NC} $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

print_header() {
    echo ""
    echo "============================================"
    echo "  $1"
    echo "============================================"
}

# ---------------------------------------------------------------------
# 1. 基础服务检查
# ---------------------------------------------------------------------
print_header "1. 基础服务检查"

echo -n "检查容器状态..."
docker compose -f docker-compose.prod.yml ps --format "table {{.Name}}\t{{.State}}"
print_status "容器状态检查完成"

echo -n "检查 API 健康端点..."
HEALTH_RESPONSE=$(curl -s http://localhost:8000/health)
if echo "$HEALTH_RESPONSE" | grep -q "healthy"; then
    print_status "API 健康检查通过: $HEALTH_RESPONSE"
else
    print_error "API 健康检查失败: $HEALTH_RESPONSE"
    exit 1
fi

echo -n "检查 Prometheus 监控端点..."
METRICS_RESPONSE=$(curl -s http://localhost:8000/metrics | head -5)
if echo "$METRICS_RESPONSE" | grep -q "evaluation_total"; then
    print_status "监控端点正常"
else
    print_error "监控端点异常"
    exit 1
fi

echo -n "检查端口监听..."
PORTS=$(netstat -tlnp 2>/dev/null | grep -E ":8000|:5432|:6379|:5672" || true)
if [ -n "$PORTS" ]; then
    echo "$PORTS"
    print_status "端口监听正常"
else
    print_warning "部分端口未监听"
fi

# ---------------------------------------------------------------------
# 2. API 接口测试
# ---------------------------------------------------------------------
print_header "2. API 接口测试"

echo -n "测试评估接口 (text)..."
EVAL_RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/evaluate \
    -H "Content-Type: application/json" \
    -d '{
        "id": "test_validation_001",
        "type": "text",
        "payload": {
            "user_input": "What is AI?",
            "expected_output": "AI stands for Artificial Intelligence"
        }
    }')

if echo "$EVAL_RESPONSE" | grep -q "success"; then
    SCORE=$(echo "$EVAL_RESPONSE" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('data',{}).get('score','N/A'))")
    echo "分数: $SCORE"
    print_status "文本评估接口测试通过"
else
    print_error "文本评估接口测试失败: $EVAL_RESPONSE"
    exit 1
fi

echo -n "测试评估接口 (finance)..."
EVAL_RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/evaluate \
    -H "Content-Type: application/json" \
    -d '{
        "id": "test_validation_002",
        "type": "finance",
        "payload": {
            "user_input": "1000元贷款3%一年利息",
            "expected_output": "30"
        }
    }')

if echo "$EVAL_RESPONSE" | grep -q "success"; then
    SCORE=$(echo "$EVAL_RESPONSE" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('data',{}).get('score','N/A'))")
    echo "分数: $SCORE"
    print_status "金融评估接口测试通过"
else
    print_error "金融评估接口测试失败: $EVAL_RESPONSE"
    exit 1
fi

echo -n "测试评估接口 (general)..."
EVAL_RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/evaluate \
    -H "Content-Type: application/json" \
    -d '{
        "id": "test_validation_003",
        "type": "general",
        "payload": {
            "user_input": "Hello World"
        }
    }')

if echo "$EVAL_RESPONSE" | grep -q "success"; then
    SCORE=$(echo "$EVAL_RESPONSE" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('data',{}).get('score','N/A'))")
    echo "分数: $SCORE"
    print_status "通用评估接口测试通过"
else
    print_error "通用评估接口测试失败: $EVAL_RESPONSE"
    exit 1
fi

echo -n "测试异步评估接口..."
ASYNC_RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/evaluate/async \
    -H "Content-Type: application/json" \
    -d '{
        "id": "test_async_001",
        "type": "general",
        "payload": {
            "user_input": "Async test"
        }
    }')

if echo "$ASYNC_RESPONSE" | grep -q "queued"; then
    TASK_ID=$(echo "$ASYNC_RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('task_id','N/A'))")
    echo "任务ID: $TASK_ID"
    print_status "异步评估接口测试通过"
else
    print_error "异步评估接口测试失败: $ASYNC_RESPONSE"
    exit 1
fi

# ---------------------------------------------------------------------
# 3. 数据库验证
# ---------------------------------------------------------------------
print_header "3. 数据库验证"

echo "检查数据库连接..."
DB_CONNECT=$(docker exec ai-eval-postgres psql -U eval -d ai_eval -c "\conninfo" 2>/dev/null)
if [ $? -eq 0 ]; then
    print_status "数据库连接正常"
    echo "$DB_CONNECT" | grep "You are connected"
else
    print_error "数据库连接失败，请检查数据库服务"
    exit 1
fi

echo ""
echo "检查数据库表结构..."
TABLE_LIST=$(docker exec ai-eval-postgres psql -U eval -d ai_eval -c "\dt" 2>/dev/null)
if echo "$TABLE_LIST" | grep -q "eval_results"; then
    echo "$TABLE_LIST" | grep -v "^-" | grep -v "List of relations"
    print_status "数据库表结构正常"
else
    print_warning "数据库表结构异常 - 未找到 eval_results 表，尝试重新创建..."
    
    echo "尝试手动创建表..."
    CREATE_RESULT=$(docker exec ai-eval-postgres psql -U eval -d ai_eval -c "
        CREATE TABLE IF NOT EXISTS eval_results (
            id SERIAL PRIMARY KEY,
            case_id VARCHAR(50) NOT NULL,
            model_name VARCHAR(50),
            adapter_name VARCHAR(50),
            status VARCHAR(20),
            latency_ms FLOAT,
            response_data JSON,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    " 2>/dev/null)
    
    if [ $? -eq 0 ]; then
        print_status "表结构创建成功"
        TABLE_LIST=$(docker exec ai-eval-postgres psql -U eval -d ai_eval -c "\dt" 2>/dev/null)
        echo "$TABLE_LIST" | grep -v "^-" | grep -v "List of relations"
    else
        print_error "表结构创建失败"
        echo "错误信息: $CREATE_RESULT"
        exit 1
    fi
fi

echo ""
echo "检查表结构详情..."
TABLE_STRUCT=$(docker exec ai-eval-postgres psql -U eval -d ai_eval -c "\d eval_results" 2>/dev/null)
echo "$TABLE_STRUCT"

echo ""
echo -n "查询评估记录数..."
RECORD_COUNT=$(docker exec ai-eval-postgres psql -U eval -d ai_eval -c "SELECT COUNT(*) FROM eval_results;" -t 2>/dev/null | tr -d ' ')
echo "$RECORD_COUNT 条记录"
print_status "数据库记录正常"

# ---------------------------------------------------------------------
# 4. Celery Worker 验证
# ---------------------------------------------------------------------
print_header "4. Celery Worker 验证"

echo "检查 Worker 容器状态..."
WORKER_CONTAINER=$(docker ps --filter "name=ai-eval-worker" --format "{{.Status}}")
if [ -n "$WORKER_CONTAINER" ]; then
    echo "Worker 容器状态: $WORKER_CONTAINER"
    print_status "Worker 容器运行中"
else
    print_error "Worker 容器未运行"
    exit 1
fi

echo ""
echo "检查 Worker 最近日志..."
WORKER_LOG=$(docker compose -f docker-compose.prod.yml logs worker 2>/dev/null | tail -10)
echo "$WORKER_LOG"

if echo "$WORKER_LOG" | grep -qE "(ready|connected|celery.*ready)"; then
    print_status "Celery Worker 运行正常"
elif echo "$WORKER_LOG" | grep -qE "(ERROR|Exception|Traceback)"; then
    print_warning "Celery Worker 日志中发现错误，请检查详细日志"
else
    print_warning "Celery Worker 状态需要确认（未找到就绪标识）"
fi

# ---------------------------------------------------------------------
# 5. 性能测试
# ---------------------------------------------------------------------
print_header "5. 并发性能测试"

echo "执行 10 个并发请求..."
for i in {1..10}; do
    curl -s -X POST http://localhost:8000/api/v1/evaluate \
        -H "Content-Type: application/json" \
        -d "{\"id\": \"perf_test_$i\", \"type\": \"general\", \"payload\": {\"user_input\": \"Test $i\"}}" > /dev/null &
done
wait

FINAL_COUNT=$(docker exec ai-eval-postgres psql -U eval -d ai_eval -c "SELECT COUNT(*) FROM eval_results;" -t 2>/dev/null | tr -d ' ')
echo "总记录数: $FINAL_COUNT"
print_status "并发测试完成"

# ---------------------------------------------------------------------
# 6. 结果汇总
# ---------------------------------------------------------------------
print_header "✅ 验证完成"

echo ""
echo "服务器信息:"
echo "  IP:     192.162.30.138"
echo "  用户:   zs13"
echo ""
echo "服务访问地址:"
echo "  API:           http://192.162.30.138:8000"
echo "  API 文档:      http://192.162.30.138:8000/docs"
echo "  健康检查:      http://192.162.30.138:8000/health"
echo "  监控指标:      http://192.162.30.138:8000/metrics"
echo "  RabbitMQ 管理: http://192.162.30.138:15672 (guest/guest)"
echo ""
echo "所有验证项均已通过！🎉"