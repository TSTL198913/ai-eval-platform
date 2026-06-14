# AI 评测平台运维手册

## 概述

本文档为 AI 评测平台的日常运维提供指导，包括监控、告警、故障处理、性能优化等。

## 日常运维

### 1. 健康检查

```bash
# API 健康检查
curl http://localhost:8000/health

# 分布式服务健康检查
curl http://localhost:8001/health

# Redis 健康检查
redis-cli ping

# Worker 健康检查
celery -A src.workers.celery_app inspect active
```

### 2. 日志管理

```bash
# 查看实时日志
tail -f logs/ai-eval.log

# 按级别过滤
grep "ERROR" logs/ai-eval.log | tail -100

# 日志轮转配置
# /etc/logrotate.d/ai-eval
/var/log/ai-eval/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 0640 ai_eval ai_eval
}
```

### 3. 指标监控

```bash
# Prometheus 指标
curl http://localhost:8000/metrics

# 关键指标
# - requests_total: 总请求数
# - request_duration_seconds: 请求延迟
# - cache_hits_total: 缓存命中数
# - circuit_breaker_state: 熔断器状态
```

## 告警处理

### 1. 告警规则

| 告警名称 | 条件 | 严重程度 | 处理建议 |
|----------|------|----------|----------|
| HighErrorRate | 错误率 > 5% | Critical | 检查服务状态 |
| HighLatency | P99 > 500ms | Warning | 性能优化 |
| CircuitBreakerOpen | 熔断器打开 | Critical | 检查下游服务 |
| QueueLengthHigh | 队列长度 > 1000 | Warning | 扩容 worker |
| RedisConnectionFailed | Redis 连接失败 | Critical | 检查 Redis |

### 2. 告警响应流程

```
告警触发
    ↓
确认告警（5分钟内）
    ↓
分析原因（15分钟内）
    ↓
采取行动（30分钟内）
    ↓
记录事件
    ↓
复盘总结
```

### 3. 常见告警处理

#### HighErrorRate 处理

```bash
# 1. 检查错误日志
grep "ERROR" logs/ai-eval.log | tail -50

# 2. 检查下游服务
curl -k https://downstream-service/health

# 3. 检查资源使用
top -u ai_eval

# 4. 如果是外部依赖问题，触发熔断
# 熔断器会自动处理
```

#### HighLatency 处理

```bash
# 1. 检查慢查询
grep "slow" logs/ai-eval.log

# 2. 检查 Redis 延迟
redis-cli --latency-history

# 3. 检查数据库连接
psql -c "SELECT * FROM pg_stat_activity"

# 4. 扩容或优化
kubectl scale deployment ai-eval-api --replicas=10
```

#### CircuitBreakerOpen 处理

```bash
# 1. 检查下游服务状态
curl -k https://downstream-service/health

# 2. 检查网络连通性
ping downstream-service

# 3. 查看熔断器状态
curl http://localhost:8000/circuit-breaker-status

# 4. 如果下游恢复，手动重置熔断器
curl -X POST http://localhost:8000/circuit-breaker/reset
```

## 故障恢复

### 1. 服务故障

```bash
# 1. 快速切换到备用节点
kubectl get pods -n ai-eval -o wide

# 2. 如果是 Deployment 问题，滚动重启
kubectl rollout restart deployment/ai-eval-api -n ai-eval

# 3. 回滚到上一版本
kubectl rollout undo deployment/ai-eval-api -n ai-eval

# 4. 扩缩容
kubectl scale deployment ai-eval-api --replicas=5 -n ai-eval
```

### 2. 数据库故障

```bash
# 1. 检查数据库连接
psql -c "SELECT 1"

# 2. 检查连接池
psql -c "SELECT count(*) FROM pg_stat_activity"

# 3. 重启数据库
sudo systemctl restart postgresql

# 4. 如果有只读副本，切换到只读
# 修改 DATABASE_URL 指向只读副本
```

### 3. Redis 故障

```bash
# 1. 检查 Redis 状态
redis-cli info

# 2. 检查持久化
redis-cli info persistence

# 3. 如果 AOF 损坏，修复
redis-cli debug fix-AOF

# 4. 如果需要，从备份恢复
redis-cli --pipe < backup-latest.rdb
```

### 4. 数据恢复

```bash
# 1. 从备份恢复数据库
pg_restore -U postgres -d ai_eval /backup/db-latest.sql

# 2. 从备份恢复 Redis
redis-cli -p 6379 < /backup/redis-latest.rdb

# 3. 验证数据完整性
psql -c "SELECT count(*) FROM evaluations;"
redis-cli DBSIZE
```

## 性能优化

### 1. 性能基线

| 指标 | 基线值 | 目标值 | 告警阈值 |
|------|--------|--------|----------|
| QPS | 500 | 1000 | >800 |
| P50 延迟 | 50ms | 30ms | >100ms |
| P95 延迟 | 150ms | 80ms | >300ms |
| P99 延迟 | 300ms | 100ms | >500ms |
| 错误率 | <0.1% | <0.01% | >1% |
| CPU 使用率 | 60% | 50% | >80% |
| 内存使用率 | 70% | 60% | >85% |

### 2. 性能分析

```bash
# 1. 生成火焰图
py-spy record -o profile.svg --pid $(pgrep -f uvicorn)

# 2. 检查慢请求
grep "slow" logs/ai-eval.log

# 3. 数据库查询分析
psql -c "SELECT * FROM pg_stat_statements ORDER BY total_time DESC LIMIT 10;"

# 4. Redis 分析
redis-cli --bigkeys
redis-cli --latency-history
```

### 3. 缓存优化

```bash
# 1. 检查缓存命中率
curl http://localhost:8000/metrics | grep cache_hit

# 2. 清理过期缓存
redis-cli KEYS "expired:*" | xargs redis-cli DEL

# 3. 调整缓存大小
# 编辑 src/infra/performance.py
# MAX_CACHE_SIZE = 5000

# 4. 预热缓存
curl -X POST http://localhost:8000/cache/warm-up
```

### 4. 数据库优化

```sql
-- 1. 创建必要索引
CREATE INDEX idx_evaluations_model ON evaluations(model_id);
CREATE INDEX idx_evaluations_created ON evaluations(created_at);
CREATE INDEX idx_evaluations_status ON evaluations(status);

-- 2. 分析查询
EXPLAIN ANALYZE SELECT * FROM evaluations WHERE model_id = 'gpt-4';

-- 3. 连接池调整
ALTER SYSTEM SET max_connections = 200;
ALTER SYSTEM SET shared_buffers = '2GB';
```

## 扩缩容

### 1. 水平扩缩容

```bash
# API 服务扩缩容
kubectl scale deployment ai-eval-api --replicas=10 -n ai-eval

# Worker 扩缩容
kubectl scale deployment ai-eval-worker --replicas=5 -n ai-eval

# HPA 自动扩缩容
kubectl autoscale deployment ai-eval-api \
  --min=2 --max=20 --cpu-percent=60 \
  -n ai-eval
```

### 2. 垂直扩缩容

```bash
# 更新资源限制
kubectl patch deployment ai-eval-api \
  -p '{"spec":{"template":{"spec":{"containers":[{"name":"api","resources":{"limits":{"cpu":"2","memory":"4Gi"}}}]}}}}' \
  -n ai-eval
```

## 安全运维

### 1. 密钥管理

```bash
# 轮换 API 密钥
curl -X POST http://localhost:8000/api-keys/rotate

# 审计密钥使用
curl http://localhost:8000/api-keys/usage
```

### 2. 访问控制

```bash
# 检查未授权访问
grep "401\|403" logs/ai-eval.log | tail -50

# 更新防火墙规则
ufw allow from 10.0.0.0/8 to any port 8000
```

### 3. 安全更新

```bash
# 检查依赖漏洞
pip-audit

# 更新依赖
pip install -U -r requirements.txt

# 重启服务应用更新
kubectl rollout restart deployment/ai-eval-api -n ai-eval
```

## 运维工具

### 1. 管理脚本

```bash
#!/bin/bash
# scripts/ops/health-check.sh

echo "=== AI Eval Health Check ==="

# API 健康
curl -sf http://localhost:8000/health > /dev/null && echo "API: OK" || echo "API: FAIL"

# Redis 健康
redis-cli ping > /dev/null 2>&1 && echo "Redis: OK" || echo "Redis: FAIL"

# Worker 健康
celery -A src.workers.celery_app inspect active > /dev/null 2>&1 && echo "Worker: OK" || echo "Worker: FAIL"

# 队列状态
echo "Queue length: $(redis-cli llen celery)"
```

### 2. 自动化任务

```bash
# crontab 配置
# 每日健康检查
0 * * * * /opt/ai-eval/scripts/ops/health-check.sh

# 每周备份
0 2 * * 0 /opt/ai-eval/scripts/ops/backup.sh

# 每日报告
0 9 * * * /opt/ai-eval/scripts/ops/daily-report.sh
```

## 值班制度

### 1. 值班安排

| 周次 | 值班人 | 联系电话 |
|------|--------|----------|
| 第一周 | 张三 | 138xxxx |
| 第二周 | 李四 | 139xxxx |
| 第三周 | 王五 | 137xxxx |
| 第四周 | 赵六 | 136xxxx |

### 2. 值班职责

- 监控告警平台状态
- 处理紧急故障
- 响应客户问题
- 记录运维事件

### 3. 交接事项

- 当前告警列表
- 进行中的变更
- 待处理的问题
- 注意事项

## 复盘总结

每次重大故障后，进行复盘：

1. **时间线**：故障发生到恢复的全过程
2. **根因**：故障的根本原因
3. **影响**：故障造成的影响
4. **处理**：采取的应急措施
5. **改进**：防止再次发生的措施
6. **行动项**：具体改进任务和负责人

---

**文档版本**: v1.0
**最后更新**: 2024-01-15
**维护人**: 运维团队
