# Distributed AI Evaluation Platform - Architecture Design

## 1. System Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Load Balancer (Nginx)                            │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
                    ┌───────────────────┼───────────────────┐
                    ▼                   ▼                   ▼
            ┌───────────────┐   ┌───────────────┐   ┌───────────────┐
            │   FastAPI #1  │   │   FastAPI #2  │   │   FastAPI #3  │
            │  (API Worker) │   │  (API Worker) │   │  (API Worker) │
            └───────────────┘   └───────────────┘   └───────────────┘
                    │                   │                   │
                    └───────────────────┼───────────────────┘
                                        │
                    ┌───────────────────┼───────────────────┐
                    ▼                   ▼                   ▼
            ┌───────────────┐   ┌───────────────┐   ┌───────────────┐
            │  Task Queue   │   │  Task Queue   │   │  Task Queue   │
            │  (RabbitMQ)   │   │  (RabbitMQ)   │   │  (RabbitMQ)   │
            │   Priority    │   │   Standard    │   │   Low         │
            │   Queue       │   │   Queue       │   │   Queue       │
            └───────────────┘   └───────────────┘   └───────────────┘
                    │                   │                   │
                    └───────────────────┼───────────────────┘
                                        │
                    ┌───────────────────┼───────────────────┐
                    ▼                   ▼                   ▼
            ┌───────────────┐   ┌───────────────┐   ┌───────────────┐
            │   Worker #1   │   │   Worker #2   │   │   Worker #N   │
            │  (Evaluator)  │   │  (Evaluator)  │   │  (Evaluator)  │
            └───────────────┘   └───────────────┘   └───────────────┘
                    │                   │                   │
                    └───────────────────┼───────────────────┘
                                        │
                    ┌───────────────────┼───────────────────┐
                    ▼                   ▼                   ▼
            ┌───────────────┐   ┌───────────────┐   ┌───────────────┐
            │  Redis Cache  │   │ PostgreSQL    │   │  DLQ Queue   │
            │  (Distributed │   │ (Results)     │   │ (Dead Letter)│
            │   Lock+State) │   │              │   │              │
            └───────────────┘   └───────────────┘   └───────────────┘
```

## 2. Core Components

### 2.1 API Layer (FastAPI)
- **职责**: 接收评测请求，验证Schema，提交任务到队列
- **特性**:
  - 限流 (Rate Limiting)
  - 请求验证 (Pydantic)
  - 异步任务提交
  - 任务状态查询

### 2.2 Message Queue Layer (RabbitMQ)
- **职责**: 任务分发、负载均衡、优先级调度
- **特性**:
  - 优先级队列 (priority queue)
  - 消息持久化 (durable)
  - 消费者负载均衡 (round-robin)
  - Dead Letter Exchange (DLX) 处理失败消息

### 2.3 Worker Layer (Celery + Custom)
- **职责**: 执行评测任务
- **特性**:
  - 分布式锁防止重复执行
  - 自动重试 + 退避
  - 熔断器保护
  - 指标采集

### 2.4 Cache Layer (Redis)
- **职责**: 分布式锁、结果缓存、限流计数
- **特性**:
  - Redlock 分布式锁
  - TTL 缓存
  - 限流令牌桶

### 2.5 Persistence Layer (PostgreSQL)
- **职责**: 评测结果持久化
- **特性**:
  - 连接池
  - 批量写入
  - 读写分离支持

## 3. Key Distributed Features

### 3.1 分布式锁 (Distributed Lock)
```
Key: eval:lock:{case_id}
Value: {worker_id}:{timestamp}
TTL: 30s (自动续期)
```
防止同一任务被多个worker重复执行。

### 3.2 消息可靠性
- Publisher Confirms: 确保消息到达broker
- Consumer Acknowledgements: 确保消息被处理
- Dead Letter Queue: 处理失败消息

### 3.3 熔断器 (Circuit Breaker)
```
States: CLOSED → OPEN → HALF_OPEN → CLOSED
触发条件: 连续失败次数 > threshold
恢复机制: 探测请求成功
```

### 3.4 限流 (Rate Limiting)
- 令牌桶算法
- Redis 原子操作
- 多维度限流 (用户/API/Worker)

## 4. Data Models

### 4.1 Evaluation Task
```python
class EvaluationTask:
    task_id: str (UUID)
    case_id: str
    domain: str (finance/text/code)
    payload: Dict
    priority: int (1-10)
    retry_count: int
    created_at: datetime
    deadline: datetime (可选)
```

### 4.2 Evaluation Result
```python
class EvaluationResult:
    task_id: str
    case_id: str
    status: Enum (PENDING/PASSED/FAILED/ERROR)
    model_name: str
    adapter_name: str
    score: float
    latency_ms: float
    trace_id: str (OpenTelemetry)
    error: Optional[str]
    created_at: datetime
```

## 5. API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /api/v1/evaluate | 同步评测 |
| POST | /api/v1/evaluate/async | 异步评测 |
| GET | /api/v1/tasks/{task_id} | 查询任务状态 |
| GET | /api/v1/health | 健康检查 |
| GET | /api/v1/metrics | Prometheus指标 |

## 6. Technology Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| API | FastAPI | 高性能异步API |
| Task Queue | RabbitMQ + Celery | 分布式任务队列 |
| Cache/Lock | Redis | 分布式锁、限流 |
| Database | PostgreSQL | 结果持久化 |
| Tracing | OpenTelemetry | 分布式追踪 |
| Metrics | Prometheus | 指标采集 |
| Container | Docker + K8s | 容器化编排 |

## 7. Reliability Features

1. **At-Least-Once Delivery**: 消息确认机制
2. **Idempotency**: 任务去重 (case_id + timestamp)
3. **Graceful Degradation**: 熔断器保护
4. **Circuit Breaker**: 防止级联失败
5. **Rate Limiting**: 防止系统过载
6. **Dead Letter Queue**: 失败消息收集

## 8. Scalability

- **水平扩展**: 增加Worker节点即可
- **优先级队列**: 重要任务优先处理
- **负载均衡**: RabbitMQ round-robin
- **自动扩缩容**: K8s HPA 支持 (基于CPU/队列长度)
