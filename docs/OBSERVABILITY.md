# AI Eval Platform - 可观测性部署指南

## 一、已实现的监控组件

### 1. Prometheus 指标定义
位置: `src/infra/monitoring/metrics.py`

已定义的指标：
| 指标名 | 类型 | 说明 |
|--------|------|------|
| `evaluation_latency_seconds` | Histogram | 评估延迟分布 |
| `evaluation_total` | Counter | 评估请求总数 |
| `evaluation_errors_total` | Counter | 评估错误总数 |
| `task_queue_size` | Gauge | 任务队列大小 |
| `task_execution_seconds` | Histogram | 任务执行时间 |
| `buffer_size` | Gauge | 缓冲服务大小 |
| `db_connections` | Gauge | 数据库连接数 |
| `db_query_seconds` | Histogram | 数据库查询延迟 |
| `rate_limiter_tokens` | Gauge | 限流器令牌数 |
| `rate_limiter_blocked_total` | Counter | 被限流请求数 |

### 2. Prometheus 中间件
位置: `src/infra/monitoring/prometheus_middleware.py`

功能：
- 自动记录所有HTTP请求的延迟和状态码
- 按评估器类型统计调用次数
- 记录错误类型分布

### 3. LLM层指标
位置: `src/infra/monitoring/llm_metrics.py`

已定义的指标：
| 指标名 | 类型 | 说明 |
|--------|------|------|
| `llm_calls_total` | Counter | LLM调用总次数 |
| `llm_tokens_prompt_total` | Counter | Prompt Token消耗 |
| `llm_tokens_completion_total` | Counter | Completion Token消耗 |
| `llm_cost_usd` | Counter | LLM调用成本（美元） |
| `llm_latency_seconds` | Histogram | LLM API延迟分布 |
| `llm_errors_total` | Counter | LLM错误总数 |
| `llm_model_selection_total` | Counter | 模型选择分布 |

### 4. 全链路指标清单
位置: `src/infra/monitoring/metric_definitions.py`

定义8大类指标：
| 分类 | 指标数量 | 说明 |
|------|----------|------|
| API层 | 3 | 请求量、延迟、状态码 |
| 评估器层 | 5 | 调用量、延迟、分数分布、通过率、失败原因 |
| LLM层 | 6 | Token、成本、延迟、错误率、成功率、模型选择 |
| 业务层 | 6 | 日评估量、活跃用户、场景分布、高价值评估 |
| 模型性能 | 6 | 平均分数、通过率、Pareto前沿、性价比、稳定性、排名 |
| 成本治理 | 6 | 日/周/月成本、单位评估成本、预算使用率、Token效率 |
| 系统健康 | 6 | 可用性、错误率、P99延迟、队列、DB连接、内存 |

### 5. 指标端点
- `/metrics` - Prometheus格式指标
- `/api/v1/metrics` - API统一格式指标
- `/api/v1/cost-metrics` - 成本指标

### 6. Grafana Dashboard
位置: `grafana/dashboards/`

| Dashboard | 面板数 | 用途 |
|-----------|--------|------|
| `ai_eval_platform_ops.json` | 7 | 运营看板 - 延迟、QPS、错误分布 |
| `ai_eval_platform_insights.json` | 12 | 决策看板 - 模型质量趋势、Pareto前沿、成本分析 |

---

## 二、快速部署

### 步骤 1: 启动服务
```bash
# 启动 API 服务（会自动加载 Prometheus 中间件）
cd d:\workspace\ai-eval-platform-refactor
uvicorn src.api.server:app --host 0.0.0.0 --port 8000

# 验证指标端点
curl http://localhost:8000/metrics
```

### 步骤 2: 启动 Prometheus
```bash
# 使用 Docker 启动 Prometheus
docker run -d \
  --name prometheus \
  -p 9090:9090 \
  -v $(pwd)/deploy/prometheus/prometheus.yml:/etc/prometheus/prometheus.yml \
  prom/prometheus
```

### 步骤 3: 导入 Grafana Dashboard
1. 访问 http://localhost:3000 (Grafana)
2. 添加 Prometheus 数据源: Settings → Data Sources → Prometheus → URL: http://prometheus:9090
3. 导入 Dashboard:
   - 运营看板: Dashboards → Import → 上传 `ai_eval_platform_ops.json`
   - 决策看板: Dashboards → Import → 上传 `ai_eval_platform_insights.json`

---

## 三、全链路指标详解

### 3.1 API层指标

```promql
# 请求QPS（按端点）
sum(rate(api_requests_total[5m])) by (endpoint)

# P95延迟（按端点）
histogram_quantile(0.95, sum(rate(api_request_duration_seconds_bucket[5m])) by (le, endpoint))
```

### 3.2 评估器层指标

```promql
# 评估器调用分布
sum(rate(evaluator_calls_total[5m])) by (evaluator_type)

# P99评估延迟
histogram_quantile(0.99, sum(rate(evaluator_latency_seconds_bucket[5m])) by (le, evaluator_type))

# 评估通过率
sum(rate(evaluator_calls_total{status="pass"}[5m])) by (evaluator_type) /
sum(rate(evaluator_calls_total[5m])) by (evaluator_type)
```

### 3.3 LLM层指标

```promql
# Token消耗（按模型）
sum(rate(llm_tokens_total[5m])) by (model, token_type)

# LLM调用成本
sum(rate(llm_cost_usd[5m])) by (model)

# 模型选择分布
sum(rate(llm_model_selection_total[5m])) by (model, selection_reason)
```

### 3.4 业务层指标

```promql
# 每日活跃用户数
count(count(evaluation_requests{user_id!=""}) by (user_id, date))

# 高价值评估占比
sum(rate(high_value_evaluations[5m])) by (evaluator_type) /
sum(rate(evaluator_calls_total[5m])) by (evaluator_type)
```

### 3.5 模型性能指标

```promql
# 模型平均分数
avg(evaluation_score) by (model, evaluator_type)

# 模型性价比指数
avg(evaluation_score) by (model) /
(sum(llm_cost_usd) by (model) / sum(evaluator_calls_total) by (model))
```

### 3.6 成本治理指标

```promql
# 日/周/月成本
sum(increase(llm_cost_usd[1d]))
sum(increase(llm_cost_usd[7d]))
sum(increase(llm_cost_usd[30d]))

# 单位评估成本
sum(llm_cost_usd) / sum(evaluator_calls_total)
```

---

## 四、关键指标解读

### 延迟指标
| 指标 | P50 | P95 | P99 | 建议阈值 |
|------|-----|-----|-----|----------|
| API延迟 | <500ms | <1000ms | <2000ms | >3000ms告警 |
| 评估延迟 | <1000ms | <3000ms | <5000ms | >8000ms告警 |
| LLM延迟 | <1000ms | <3000ms | <5000ms | >10000ms告警 |

### 业务指标
| 指标 | 正常范围 | 告警阈值 |
|------|----------|----------|
| 错误率 | <1% | >5% |
| QPS | 取决于硬件 | >1000告警 |
| 队列堆积 | <100 | >500告警 |

### 模型性能指标
| 指标 | 优秀 | 良好 | 较差 |
|------|------|------|------|
| 平均分数 | >0.85 | >0.70 | <0.70 |
| 通过率 | >90% | >75% | <75% |
| 性价比指数 | >1000 | >500 | <500 |

---

## 五、Pareto前沿分析

### 质量 vs 延迟
- X轴: LLM延迟 (P95)
- Y轴: 评估分数
- 目标: 找到"低延迟+高质量"的模型

### 质量 vs 成本
- X轴: 单位评估成本
- Y轴: 评估分数
- 目标: 找到"低成本+高质量"的模型

### 智能路由建议
| 场景 | 推荐模型 | 理由 |
|------|----------|------|
| 快速过滤 | DeepSeek-Mini | 低延迟、低成本 |
| 精确评估 | GPT-4o | 高质量 |
| 平衡之选 | DeepSeek-V3 | 中等成本、可接受质量 |

---

## 六、Celery任务监控（选项C）

### 6.1 监控架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                      Celery Worker 分布式架构                         │
│                                                                     │
│   ┌──────────┐      ┌──────────┐      ┌──────────┐                │
│   │ Worker 1 │      │ Worker 2 │      │ Worker 3 │                │
│   │ (CPU)    │      │ (IO)     │      │ (Mixed)  │                │
│   └────┬─────┘      └────┬─────┘      └────┬─────┘                │
│        │                 │                 │                        │
│        └────────────┬────┴────────────────┘                        │
│                     │                                              │
│              ┌─────▼─────┐                                        │
│              │  RabbitMQ │  (Broker)                              │
│              └─────┬─────┘                                        │
│                    │                                               │
│         ┌──────────▼──────────┐                                   │
│         │   Pushgateway       │  (指标推送)                        │
│         │   :9091             │                                   │
│         └──────────┬──────────┘                                   │
│                    │                                              │
└────────────────────│──────────────────────────────────────────────┘
                     │
         ┌──────────▼──────────┐
         │     Prometheus       │
         │   (指标聚合存储)       │
         └──────────┬──────────┘
                    │
         ┌──────────▼──────────┐
         │      Grafana         │
         │   (可视化仪表盘)      │
         └─────────────────────┘
```

### 6.2 Celery监控组件

位置: `src/infra/monitoring/celery_metrics.py`

已定义的指标：
| 指标名 | 类型 | 说明 |
|--------|------|------|
| `celery_task_state_transitions_total` | Counter | 任务状态转换次数 |
| `celery_task_execution_seconds` | Histogram | 任务执行时间分布 |
| `celery_task_retries_total` | Counter | 任务重试总次数 |
| `celery_task_failures_total` | Counter | 任务失败总次数 |
| `celery_queue_depth` | Gauge | 队列深度 |
| `celery_worker_count` | Gauge | Worker数量 |
| `celery_task_delay_seconds` | Histogram | 任务提交到开始执行的延迟 |
| `celery_running_tasks` | Gauge | 正在执行的任务数 |

### 6.3 监控脚本

位置: `src/infra/monitoring/monitor_celery.py`

功能：
- 定期检查队列深度
- 监控Worker状态
- 推送指标到Pushgateway

### 6.4 快速启动

```bash
# 启动完整监控栈（Prometheus + Pushgateway + Grafana）
docker-compose -f deploy/docker-compose.monitoring.yml up -d

# 单独启动Celery监控脚本
python -m src.infra.monitoring.monitor_celery --interval=10

# 单次检查（非守护模式）
python -m src.infra.monitoring.monitor_celery --once
```

### 6.5 关键Celery指标解读

| 指标 | 正常范围 | 告警阈值 | 说明 |
|------|----------|----------|------|
| `celery_running_tasks` | < Worker并发数 | > Worker并发数 | 任务积压 |
| `celery_queue_depth` | < 100 | > 500 | 队列堆积 |
| `celery_task_execution_seconds` | < 60s | > 120s | 任务执行过慢 |
| `celery_task_retries_total` | < 5% | > 20% | 任务不稳定 |
| `celery_task_failures_total` | < 1% | > 5% | 系统故障 |

### 6.6 故障排查

#### 队列堆积
```bash
# 检查队列状态
celery -A src.workers.celery_app inspect stats

# 查看活跃任务
celery -A src.workers.celery_app inspect active

# 强制终止长时间运行的任务
celery -A src.workers.celery_app control revoke <task_id>
```

#### Worker无响应
```bash
# 检查Worker日志
docker logs ai-eval-celery-worker

# 重启Worker
docker-compose -f deploy/docker-compose.monitoring.yml restart celery-worker
```

#### 指标未采集
1. 确认Pushgateway运行正常: `curl http://localhost:9091/metrics`
2. 确认Celery任务使用了指标: 检查任务日志
3. 确认Prometheus抓取Pushgateway: 检查 http://localhost:9090/targets
