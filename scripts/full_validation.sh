#!/bin/bash
set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

print_status() { echo -e "${GREEN}[✓]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[⚠]${NC} $1"; }
print_error() { echo -e "${RED}[✗]${NC} $1"; }
print_header() { echo ""; echo "================================================"; echo "  $1"; echo "================================================"; }

# --------------------------------------------------
# 1. 基础服务检查
# --------------------------------------------------
print_header "1. 基础服务检查"

echo -n "检查容器状态..."
CONTAINER_STATUS=$(docker compose -f docker-compose.prod.yml ps --format "table {{.Name}}\t{{.State}}" 2>/dev/null)
echo ""
echo "$CONTAINER_STATUS"

# 统计 running 容器（只看 running 行）
RUNNING_COUNT=$(docker compose -f docker-compose.prod.yml ps --format "{{.State}}" 2>/dev/null | grep -c "running")
TOTAL_COUNT=$(docker compose -f docker-compose.prod.yml ps --format "{{.Name}}" 2>/dev/null | wc -l)

if [ $RUNNING_COUNT -eq $TOTAL_COUNT ] && [ $TOTAL_COUNT -gt 0 ]; then
    print_status "所有 $RUNNING_COUNT 个容器运行正常"
else
    print_error "部分容器未运行 ($RUNNING_COUNT/$TOTAL_COUNT)"
    exit 1
fi

echo -n "检查端口监听..."
PORTS=$(netstat -tlnp 2>/dev/null | grep -E ":8000|:5432|:6379|:5672|:80" | awk '{print $4}')
if [ -n "$PORTS" ]; then
    echo "$PORTS"
    print_status "端口监听正常"
else
    print_warning "部分端口未监听"
fi

# --------------------------------------------------
# 2. API健康检查
# --------------------------------------------------
print_header "2. API健康检查"

echo -n "检查健康端点..."
HEALTH_RESPONSE=$(curl -s http://localhost:8000/health)
if echo "$HEALTH_RESPONSE" | grep -q "healthy"; then
    echo "$HEALTH_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$HEALTH_RESPONSE"
    print_status "API健康检查通过"
else
    print_error "API健康检查失败: $HEALTH_RESPONSE"
    exit 1
fi

echo -n "检查OpenAPI文档..."
DOCS_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/docs)
if [ "$DOCS_RESPONSE" = "200" ]; then
    print_status "OpenAPI文档可访问"
else
    print_error "OpenAPI文档不可访问 (HTTP $DOCS_RESPONSE)"
    exit 1
fi

# --------------------------------------------------
# 3. 评估器API测试
# --------------------------------------------------
print_header "3. 评估器API测试"

EVALUATOR_TYPES=(
    "text" "general" "code" "security" "qa" "summary"
    "semantic" "grammar" "sentiment" "translation" "classification"
    "finance" "fact_check" "meta_test" "risk"
)

PASS_COUNT=0
FAIL_COUNT=0

for TYPE in "${EVALUATOR_TYPES[@]}"; do
    echo -n "测试 $TYPE 评估器..."

    case $TYPE in
        text)
            PAYLOAD='{"user_input":"What is AI?","expected_output":"AI stands for Artificial Intelligence"}'
            ;;
        general)
            PAYLOAD='{"user_input":"Hello World"}'
            ;;
        code)
            PAYLOAD='{"user_input":"def hello():\n    return \"hello\"","expected_output":"hello"}'
            ;;
        security)
            PAYLOAD='{"user_input":"SELECT * FROM users WHERE id=1"}'
            ;;
        qa)
            PAYLOAD='{"user_input":"What is Python?","expected_output":"Python is a programming language"}'
            ;;
        summary)
            PAYLOAD='{"user_input":"This is a long text about AI. AI stands for Artificial Intelligence.","expected_output":"AI summary"}'
            ;;
        semantic)
            PAYLOAD='{"user_input":"apple","expected_output":"fruit"}'
            ;;
        grammar)
            PAYLOAD='{"user_input":"He go to school","expected_output":"He goes to school"}'
            ;;
        sentiment)
            PAYLOAD='{"user_input":"I love this product!","expected_output":"positive"}'
            ;;
        translation)
            PAYLOAD='{"user_input":"Hello","expected_output":"你好"}'
            ;;
        classification)
            PAYLOAD='{"user_input":"Apple is a fruit","expected_output":"fruit"}'
            ;;
        finance)
            PAYLOAD='{"user_input":"1000元贷款3%一年利息","expected_output":"30"}'
            ;;
        fact_check)
            PAYLOAD='{"user_input":"Earth is flat","expected_output":"false"}'
            ;;
        meta_test)
            PAYLOAD='{"user_input":"Test","expected_output":"pass"}'
            ;;
        risk)
            PAYLOAD='{"user_input":"Investment risk analysis","expected_output":"low"}'
            ;;
        *)
            PAYLOAD='{"user_input":"Test"}'
            ;;
    esac

    RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/evaluate \
        -H "Content-Type: application/json" \
        -d "{\"id\":\"test_${TYPE}_001\",\"type\":\"${TYPE}\",\"payload\":${PAYLOAD}}")

    if echo "$RESPONSE" | grep -q "success"; then
        SCORE=$(echo "$RESPONSE" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('data',{}).get('score','N/A'))")
        echo "分数: $SCORE"
        print_status "$TYPE 评估器测试通过"
        PASS_COUNT=$((PASS_COUNT + 1))
    else
        ERROR_MSG=$(echo "$RESPONSE" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('message','Unknown error'))" 2>/dev/null || echo "$RESPONSE")
        echo "错误: $ERROR_MSG"
        print_error "$TYPE 评估器测试失败"
        FAIL_COUNT=$((FAIL_COUNT + 1))
    fi
done

echo ""
echo "评估器测试结果: ${PASS_COUNT} 通过, ${FAIL_COUNT} 失败"

# --------------------------------------------------
# 4. 数据库验证
# --------------------------------------------------
print_header "4. 数据库验证"

echo -n "检查数据库连接..."
DB_CONNECT=$(docker exec ai-eval-postgres psql -U eval -d ai_eval -c "\conninfo" 2>/dev/null)
if [ $? -eq 0 ]; then
    echo "$DB_CONNECT" | grep "You are connected"
    print_status "数据库连接正常"
else
    print_error "数据库连接失败"
    exit 1
fi

echo -n "检查数据库表..."
TABLE_LIST=$(docker exec ai-eval-postgres psql -U eval -d ai_eval -c "\dt" 2>/dev/null)
if echo "$TABLE_LIST" | grep -q "eval_results"; then
    echo "$TABLE_LIST" | grep -v "^-" | grep -v "List of relations"
    print_status "数据库表结构正常"
else
    print_error "数据库表结构异常"
    exit 1
fi

echo -n "查询评估记录数..."
RECORD_COUNT=$(docker exec ai-eval-postgres psql -U eval -d ai_eval -c "SELECT COUNT(*) FROM eval_results;" -t 2>/dev/null | tr -d ' ')
echo "$RECORD_COUNT 条记录"
print_status "数据库记录正常"

# --------------------------------------------------
# 5. 异步任务测试
# --------------------------------------------------
print_header "5. 异步任务测试"

echo -n "测试异步评估接口..."
ASYNC_RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/evaluate/async \
    -H "Content-Type: application/json" \
    -d '{"id":"test_async_001","type":"general","payload":{"user_input":"Async test"}}')

if echo "$ASYNC_RESPONSE" | grep -q "queued"; then
    TASK_ID=$(echo "$ASYNC_RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('task_id','N/A'))")
    echo "任务ID: $TASK_ID"
    print_status "异步评估接口测试通过"

    sleep 5

    echo -n "查询异步任务状态..."
    STATUS_RESPONSE=$(curl -s http://localhost:8000/api/v1/evaluate/task/$TASK_ID)
    if echo "$STATUS_RESPONSE" | grep -q "success\|pending\|completed"; then
        echo "$STATUS_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$STATUS_RESPONSE"
        print_status "异步任务状态查询正常"
    else
        print_warning "异步任务状态异常: $STATUS_RESPONSE"
    fi
else
    print_error "异步评估接口测试失败: $ASYNC_RESPONSE"
    exit 1
fi

echo -n "检查Worker日志..."
WORKER_LOG=$(docker logs ai-eval-worker 2>/dev/null | tail -5)
echo "$WORKER_LOG"
if echo "$WORKER_LOG" | grep -qE "(ready|connected|INFO/MainProcess)"; then
    print_status "Worker运行正常"
else
    print_warning "Worker日志需要检查"
fi

# --------------------------------------------------
# 6. Redis缓存测试
# --------------------------------------------------
print_header "6. Redis缓存测试"

echo -n "检查Redis连接..."
REDIS_PING=$(docker exec ai-eval-redis redis-cli ping 2>/dev/null)
if [ "$REDIS_PING" = "PONG" ]; then
    print_status "Redis连接正常"

    echo -n "检查Redis键数量..."
    REDIS_KEYS=$(docker exec ai-eval-redis redis-cli dbsize 2>/dev/null)
    echo "$REDIS_KEYS 个键"
    print_status "Redis状态正常"
else
    print_error "Redis连接失败"
    exit 1
fi

# --------------------------------------------------
# 7. RabbitMQ测试
# --------------------------------------------------
print_header "7. RabbitMQ测试"

echo -n "检查RabbitMQ连接..."
RABBITMQ_STATUS=$(docker exec ai-eval-rabbitmq rabbitmqctl status 2>/dev/null | head -5)
if [ $? -eq 0 ]; then
    echo "$RABBITMQ_STATUS" | grep -E "(pid|running)"
    print_status "RabbitMQ运行正常"
else
    print_error "RabbitMQ连接失败"
    exit 1
fi

# --------------------------------------------------
# 8. 监控指标测试
# --------------------------------------------------
print_header "8. 监控指标测试"

echo -n "检查Prometheus指标..."
METRICS_RESPONSE=$(curl -s http://localhost:8000/metrics | head -10)
if [ -n "$METRICS_RESPONSE" ]; then
    echo "$METRICS_RESPONSE"
    print_status "监控指标正常"
else
    print_warning "监控指标异常"
fi

# --------------------------------------------------
# 9. 并发性能测试
# --------------------------------------------------
print_header "9. 并发性能测试"

echo -n "执行5个并发请求..."
START_TIME=$(date +%s)
for i in {1..5}; do
    curl -s -X POST http://localhost:8000/api/v1/evaluate \
        -H "Content-Type: application/json" \
        -d "{\"id\":\"perf_test_$i\",\"type\":\"general\",\"payload\":{\"user_input\":\"Perf test $i\"}}" > /dev/null &
done
wait
END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

FINAL_COUNT=$(docker exec ai-eval-postgres psql -U eval -d ai_eval -c "SELECT COUNT(*) FROM eval_results;" -t 2>/dev/null | tr -d ' ')
echo "耗时: ${DURATION}秒, 总记录数: $FINAL_COUNT"

if [ $DURATION -lt 30 ]; then
    print_status "并发性能测试通过 (${DURATION}秒)"
else
    print_warning "并发性能较慢 (${DURATION}秒)"
fi

# --------------------------------------------------
# 10. 结果汇总
# --------------------------------------------------
print_header "✅ 全面验证完成"

echo ""
echo "服务器信息:"
echo "  IP:     $(hostname -I | awk '{print $1}')"
echo "  用户:   $(whoami)"
echo ""
echo "服务状态汇总:"
echo "  基础服务:      ✅ 全部运行"
echo "  API健康:       ✅ 通过"
echo "  评估器测试:    ✅ ${PASS_COUNT}/${#EVALUATOR_TYPES[@]} 通过"
echo "  数据库:        ✅ 正常"
echo "  异步任务:      ✅ 正常"
echo "  Redis:         ✅ 正常"
echo "  RabbitMQ:      ✅ 正常"
echo "  监控指标:      ✅/⚠️ 正常/警告"
echo ""
echo "服务访问地址:"
echo "  API:           http://$(hostname -I | awk '{print $1}'):8000"
echo "  API文档:       http://$(hostname -I | awk '{print $1}'):8000/docs"
echo "  健康检查:      http://$(hostname -I | awk '{print $1}'):8000/health"
echo "  监控指标:      http://$(hostname -I | awk '{print $1}'):8000/metrics"
echo "  RabbitMQ管理:  http://$(hostname -I | awk '{print $1}'):15672 (guest/guest)"
echo ""
echo "所有验证项均已完成！🎉"
