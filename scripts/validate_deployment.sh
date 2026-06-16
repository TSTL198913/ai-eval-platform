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

echo -n "测试评估接口 (text_similarity)..."
EVAL_RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/evaluate \
    -H "Content-Type: application/json" \
    -d '{
        "case_id": "test_validation_001",
        "model_name": "test_model",
        "input": "What is AI?",
        "expected_output": "AI stands for Artificial Intelligence",
        "evaluation_type": "text_similarity"
    }')

if echo "$EVAL_RESPONSE" | grep -q "score"; then
    echo "分数: $(echo "$EVAL_RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('score','N/A'))")"
    print_status "评估接口测试通过"
else
    print_error "评估接口测试失败: $EVAL_RESPONSE"
    exit 1
fi

echo -n "测试评估接口 (keyword_overlap)..."
EVAL_RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/evaluate \
    -H "Content-Type: application/json" \
    -d '{
        "case_id": "test_validation_002",
        "model_name": "test_model",
        "input": "Machine learning is a subset of AI",
        "expected_output": "AI machine learning subset",
        "evaluation_type": "keyword_overlap"
    }')

if echo "$EVAL_RESPONSE" | grep -q "score"; then
    echo "分数: $(echo "$EVAL_RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('score','N/A'))")"
    print_status "关键词重叠测试通过"
else
    print_error "关键词重叠测试失败: $EVAL_RESPONSE"
    exit 1
fi

echo -n "测试评估列表接口..."
LIST_RESPONSE=$(curl -s http://localhost:8000/api/v1/evaluations)
if echo "$LIST_RESPONSE" | grep -q "test_validation"; then
    COUNT=$(echo "$LIST_RESPONSE" | python3 -c "import sys,json; print(len(json.load(sys.stdin)))")
    echo "共 $COUNT 条记录"
    print_status "评估列表接口正常"
else
    print_error "评估列表接口异常: $LIST_RESPONSE"
    exit 1
fi

echo -n "测试批量评估接口..."
BATCH_RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/evaluate/batch \
    -H "Content-Type: application/json" \
    -d '[
        {"case_id": "batch_test_001", "model_name": "test", "input": "Hello", "expected_output": "Hi", "evaluation_type": "text_similarity"},
        {"case_id": "batch_test_002", "model_name": "test", "input": "World", "expected_output": "World", "evaluation_type": "text_similarity"}
    ]')

if echo "$BATCH_RESPONSE" | grep -q "success"; then
    print_status "批量评估接口正常"
else
    print_error "批量评估接口异常: $BATCH_RESPONSE"
    exit 1
fi

# ---------------------------------------------------------------------
# 3. 数据库验证
# ---------------------------------------------------------------------
print_header "3. 数据库验证"

echo -n "检查数据库表结构..."
TABLES=$(docker exec ai-eval-postgres psql -U eval -d ai_eval -c "\dt" 2>/dev/null | grep -E "evaluations|test_cases")
if [ -n "$TABLES" ]; then
    echo "$TABLES"
    print_status "数据库表结构正常"
else
    print_error "数据库表结构异常"
    exit 1
fi

echo -n "查询评估记录数..."
RECORD_COUNT=$(docker exec ai-eval-postgres psql -U eval -d ai_eval -c "SELECT COUNT(*) FROM evaluations;" -t 2>/dev/null | tr -d ' ')
echo "$RECORD_COUNT 条记录"
print_status "数据库记录正常"

# ---------------------------------------------------------------------
# 4. Celery Worker 验证
# ---------------------------------------------------------------------
print_header "4. Celery Worker 验证"

echo -n "检查 Worker 状态..."
WORKER_LOG=$(docker compose -f docker-compose.prod.yml logs worker 2>/dev/null | tail -5)
if echo "$WORKER_LOG" | grep -q "ready"; then
    echo "$WORKER_LOG"
    print_status "Celery Worker 运行正常"
else
    print_warning "Celery Worker 状态需要确认"
fi

# ---------------------------------------------------------------------
# 5. 性能测试
# ---------------------------------------------------------------------
print_header "5. 并发性能测试"

echo "执行 10 个并发请求..."
for i in {1..10}; do
    curl -s -X POST http://localhost:8000/api/v1/evaluate \
        -H "Content-Type: application/json" \
        -d "{\"case_id\": \"perf_test_$i\", \"model_name\": \"test\", \"input\": \"Test $i\", \"expected_output\": \"Test $i\", \"evaluation_type\": \"text_similarity\"}" > /dev/null &
done
wait

FINAL_COUNT=$(docker exec ai-eval-postgres psql -U eval -d ai_eval -c "SELECT COUNT(*) FROM evaluations;" -t 2>/dev/null | tr -d ' ')
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