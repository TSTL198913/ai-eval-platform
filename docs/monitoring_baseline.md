# AI Evaluation Platform - Grafana 监控基线配置

## 性能基线

### API 响应时间基线

| 指标 | 目标值 (P50) | 告警阈值 (P95) | 严重阈值 (P99) |
|------|-------------|---------------|---------------|
| 健康检查 | < 50ms | < 200ms | < 500ms |
| 评估器列表 | < 100ms | < 500ms | < 1000ms |
| 评测执行 | < 3000ms | < 8000ms | < 15000ms |
| 记录查询 | < 200ms | < 1000ms | < 2000ms |
| 报告生成 | < 2000ms | < 5000ms | < 10000ms |

### 吞吐量基线

| 场景 | 基准 TPS | 告警阈值 | 严重阈值 |
|------|----------|----------|----------|
| 静态资源 | > 1000 req/s | > 800 req/s | > 500 req/s |
| API 请求 | > 100 req/s | > 80 req/s | > 50 req/s |
| 评测任务 | > 20 req/s | > 15 req/s | > 10 req/s |

### 错误率基线

| 错误类型 | 目标值 | 告警阈值 | 严重阈值 |
|----------|--------|----------|----------|
| HTTP 5xx | < 0.1% | < 1% | < 5% |
| HTTP 4xx | < 5% | < 10% | < 20% |
| 评测失败 | < 1% | < 5% | < 10% |

### 资源使用基线

| 资源 | 正常范围 | 告警阈值 | 严重阈值 |
|------|----------|----------|----------|
| CPU 使用率 | 0-50% | 50-70% | > 70% |
| 内存使用率 | 0-60% | 60-80% | > 80% |
| 数据库连接 | < 50% | 50-70% | > 70% |
| Redis 连接 | < 50% | 50-70% | > 70% |

---

## 告警规则

### Critical 告警 (立即响应)

```yaml
# 评测服务完全不可用
- alert: EvaluationServiceDown
  expr: up{job="ai-eval-api"} == 0
  for: 1m
  labels:
    severity: critical
  annotations:
    summary: "评测服务不可用"
    description: "评测服务已经宕机超过1分钟"

# 错误率超过 5%
- alert: HighErrorRate
  expr: rate(http_requests_total{status=~"5.."}[5m]) / rate(http_requests_total[5m]) > 0.05
  for: 5m
  labels:
    severity: critical
  annotations:
    summary: "错误率过高"
    description: "5分钟内错误率超过5%"

# P99 延迟超过 10 秒
- alert: HighLatencyP99
  expr: histogram_quantile(0.99, rate(http_request_duration_seconds_bucket[5m])) > 10
  for: 5m
  labels:
    severity: critical
  annotations:
    summary: "P99延迟过高"
    description: "P99延迟已超过10秒"
```

### Warning 告警 (需要关注)

```yaml
# P95 延迟超过 5 秒
- alert: MediumLatencyP95
  expr: histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m])) > 5
  for: 5m
  labels:
    severity: warning
  annotations:
    summary: "P95延迟较高"
    description: "P95延迟已超过5秒"

# 队列积压超过 1000
- alert: QueueBacklog
  expr: queue_size > 1000
  for: 10m
  labels:
    severity: warning
  annotations:
    summary: "任务队列积压"
    description: "等待处理的任务数量过多"

# 成本接近日预算
- alert: DailyBudgetApproaching
  expr: daily_cost_total / daily_cost_limit > 0.8
  for: 5m
  labels:
    severity: warning
  annotations:
    summary: "日成本接近预算"
    description: "日成本已达到预算的80%"
```

---

## Grafana 仪表盘配置

### 关键面板

1. **概览面板**
   - 服务状态 (UP/DOWN)
   - 总请求数
   - 平均响应时间
   - 错误率

2. **性能面板**
   - 延迟分布 (P50, P75, P95, P99)
   - 请求率
   - 并发连接数

3. **资源面板**
   - CPU 使用率
   - 内存使用率
   - 数据库连接池
   - Redis 连接

4. **业务面板**
   - 评测任务数
   - 评测成功率
   - 成本消耗
   - 评估器使用分布

---

## 监控指标定义

### Prometheus 指标

```prometheus
# 请求指标
http_requests_total{job, method, endpoint, status}
http_request_duration_seconds_bucket{job, method, endpoint, le}
http_request_duration_seconds_sum{job, method, endpoint}
http_request_duration_seconds_count{job, method, endpoint}

# 评测指标
evaluation_total{job, domain, status}
evaluation_duration_seconds_bucket{job, domain, le}
evaluation_errors_total{job, domain, error_type}

# 业务指标
evaluation_cost_total{job, domain}
evaluation_tokens_total{job, domain, model}

# 资源指标
process_cpu_seconds_total{job}
process_resident_memory_bytes{job}
db_pool_connections{job, state}
redis_connections{job, state}
```

---

## 基线更新流程

1. **每周基线审查**
   - 回顾上周性能数据
   - 调整基线以反映实际增长
   - 记录异常事件

2. **季度基线评估**
   - 全面评估系统容量
   - 预测未来负载
   - 规划扩容

3. **事件驱动更新**
   - 重大功能发布后更新基线
   - 架构变更后更新基线
   - 性能优化后更新基线

---

## 阈值配置模板

```json
{
  "dashboard": {
    "panels": [
      {
        "title": "API 响应时间基线",
        "targets": [
          {
            "expr": "histogram_quantile(0.50, rate(http_request_duration_seconds_bucket[5m]))",
            "legendFormat": "P50"
          },
          {
            "expr": "histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))",
            "legendFormat": "P95"
          },
          {
            "expr": "histogram_quantile(0.99, rate(http_request_duration_seconds_bucket[5m]))",
            "legendFormat": "P99"
          }
        ],
        "thresholds": {
          "p50": {"value": 0.1, "color": "green"},
          "p95": {"value": 1.0, "color": "yellow"},
          "p99": {"value": 5.0, "color": "red"}
        }
      }
    ]
  }
}
```
