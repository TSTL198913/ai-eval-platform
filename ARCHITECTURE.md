# AI-Eval-Pro: Enterprise-Grade Evaluation Platform - Architecture Design

## 1. System Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Frontend (React + Vite)                         │
│                    Dashboard / Evaluators / Models / Records                 │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │ HTTPS / JWT
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          Load Balancer (Nginx)                               │
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
            │  Task Queue   │   │  Task Queue   │   │   Redis       │
            │  (RabbitMQ)   │   │  (RabbitMQ)   │   │  (Cache/Lock) │
            │   Priority    │   │   Standard    │   │              │
            │   Queue       │   │   Queue       │   │              │
            └───────────────┘   └───────────────┘   └───────────────┘
                    │                   │
                    └───────────────────┼───────────────────┐
                                        ▼                   ▼
            ┌───────────────┐   ┌───────────────┐   ┌───────────────┐
            │   Worker #1   │   │   Worker #2   │   │ PostgreSQL    │
            │  (Evaluator)  │   │  (Evaluator)  │   │  (Results)    │
            └───────────────┘   └───────────────┘   └───────────────┘
                                        │
                                        ▼
                                ┌───────────────┐
                                │   DLQ Queue   │
                                │ (Dead Letter) │
                                └───────────────┘
```

## 2. Layered Architecture

### 2.1 Architecture Diagram (Detailed)

```
┌──────────────────────────────────────────────────────────────────┐
│                    Frontend (React + Vite + TS)                  │
│  Dashboard / Evaluators / Models / Records / Cost / Health      │
└──────────────────────────────────────────────────────────────────┘
                              │ HTTPS / JWT
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│                 API Layer (FastAPI Router)                      │
│  auth / evaluate / evaluators / models / records / reports     │
│  [CORS] [Security] [Prometheus] [RateLimit] Middlewares        │
│  v2 API Aggregation: evaluation / models / data / analytics    │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│             Service Layer (业务编排)                            │
│  evaluator_svc.run_evaluation_service()                        │
│  data_svc.search / get_recent / count                          │
│  annotation_svc.manage_annotations()                           │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│             Engine Layer (EvaluationEngine)                     │
│  异常分类捕获 / 状态映射 / 性能计时 / 持久化                     │
│  状态机: EvaluatorStatus → EvaluationRecordStatus               │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│            Domain Layer (核心业务逻辑)                          │
│  EvaluatorFactory + 15 Core Evaluators (BaseEvaluator)         │
│  ModelFactory + 5+ LLM Clients (BaseLLMClient)                 │
│  Domain Models / A/B Test / Calibration / GoldenDataset        │
│  safe_evaluate: 安全评估入口 + 结构化日志记录                     │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│        Distributed Layer (分布式原语)                           │
│  Lock / CircuitBreaker / RateLimiter / Queue / Idempotency     │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│        Infrastructure Layer (基础设施)                          │
│  DB (PostgreSQL/SQLite) / Cache (Redis) / MQ (RabbitMQ)        │
│  Security / Monitoring / Tracing / Logging / Plugins           │
└──────────────────────────────────────────────────────────────────┘
```

### 2.2 Layer Responsibilities

| 层级 | 目录 | 职责 | 依赖方向 |
|------|------|------|----------|
| **API** | `src/api/` | 路由分发、请求验证、响应格式化、v2聚合路由 | → Service |
| **Service** | `src/services/` | 业务编排、事务控制、跨域协作 | → Engine / Domain |
| **Engine** | `src/engine.py` | 异常捕获、状态映射（状态机）、性能计时 | → Domain |
| **Domain** | `src/domain/` | 核心业务规则、评估器实现、模型抽象、安全评估入口 | → Distributed / Infra |
| **Distributed** | `src/distributed/` | 分布式原语（锁、熔断、限流、队列、幂等） | → Infra |
| **Infra** | `src/infra/` | DB / Cache / MQ / 监控 / 安全 / RBAC | 外部资源 |

### 2.3 Dependency Rules

- ✅ 依赖单向流动：`API → Service → Engine → Domain → Distributed → Infra`
- ✅ 禁止跨层调用（如 API 直接调用 Repository）
- ✅ 新增评估器必须通过 `@EvaluatorFactory.register()` 注册
- ✅ 新增 LLM 客户端必须通过 `create_llm_client()` 创建
- ✅ 评估器黑名单机制：`_EVALUATOR_BLACKLIST` 控制评估器注册
- ✅ 评估器必须实现 `_do_evaluate()`，禁止直接重写 `evaluate()`

## 3. Core Components

### 3.1 API Layer (FastAPI)

**职责**: 接收评测请求，验证Schema，提交任务到队列

**特性**:
- 限流 (Rate Limiting)
- 请求验证 (Pydantic)
- 异步任务提交
- 任务状态查询
- v2 聚合路由（按功能域分组）
- RBAC 权限控制

**路由结构**:
```
src/api/routes/
├── v2/                    # v2 聚合路由
│   ├── evaluation.py      # 评估相关
│   ├── models.py          # 模型管理
│   ├── data.py            # 数据管理
│   ├── analytics.py       # 分析报表
│   └── config.py          # 配置管理
├── evaluation_routes.py   # v1 评估路由
├── auth_routes.py         # v1 认证路由
├── model_routes.py        # v1 模型路由
├── record_routes.py       # v1 记录路由
└── ... (27个v1路由)
```

### 3.2 Service Layer

**职责**: 业务编排、事务控制、跨域协作

**核心服务**:
- `EvaluatorService`: 评测执行服务
- `DataService`: 数据查询服务
- `AnnotationService`: 人工标注服务

**核心流程**:
```python
def run_evaluation_service(raw_data: dict, client=None) -> dict:
    # 1. 数据规范化
    # 2. Schema 验证
    # 3. 客户端选择（三级降级）
    # 4. 引擎执行
    # 5. 持久化（失败不影响返回）
    return {"status": ..., "record_id": ..., "latency_ms": ...}
```

### 3.3 Engine Layer

**职责**: 异常分类捕获、状态映射（状态机）、性能计时

**核心组件**: `EvaluationEngine`

**执行流程**:
```
EvaluationEngine.run()
    │
    ├─ 1. 从 EvaluatorFactory 获取评估器（受熔断器保护）
    │     └─ EvaluatorFactory.get(type, client)
    │
    ├─ 2. 调用 evaluator.safe_evaluate(request)
    │     └─ safe_evaluate() 内置熔断器 + 异常处理 + 日志记录
    │
    ├─ 3. 状态映射（状态机转换）
    │     ├─ EvaluatorStatus.SUCCESS        → PASSED
    │     ├─ EvaluatorStatus.PARTIAL        → PASSED（带标记）
    │     ├─ EvaluatorStatus.CANNOT_EVALUATE → ERROR
    │     └─ EvaluatorStatus.ERROR          → FAILED/ERROR（根据 error_code）
    │
    ├─ 4. 构建 EvaluationResult（case_id, status, model, adapter, latency, response）
    │
    └─ 5. 返回结果（由 Service 层负责持久化）
```

### 3.4 Domain Layer

**职责**: 核心业务规则、评估器实现、模型抽象、安全评估入口

#### 3.4.1 Evaluator Factory Pattern

```python
@EvaluatorFactory.register("security")
class SecurityEvaluator(BaseEvaluator):
    def _do_evaluate(self, request: EvaluationSchema) -> DomainResponse:
        ...

# 自动发现机制（pkgutil 扫描 + 黑名单过滤）
_EVALUATOR_BLACKLIST = {"text", "text_similarity_base", "sentiment", ...}

# 16个核心评估器（新增 llm_guard）
CORE_EVALUATORS = ["general", "code", "code_review", "security", "memory", 
                   "semantic", "qa", "factuality", "risk", "classification",
                   "composite", "function_call", "multi_agent", "llm_as_judge", "robustness", "llm_guard"]
```

#### 3.4.2 LLM Client Factory

```python
def create_llm_client(provider=None, client=None, config=None):
    # 三级降级: 客户端注入 → 自定义配置 → 环境变量配置
    # 缓存策略: _llm_client_cache (单例), _env_config_cache (配置缓存)
    # 双锁保护: RLock (线程安全)
```

**支持的 Provider**: `deepseek` / `openai` / `anthropic` / `ollama` / `qwen` / `dashscope` / `stub`

#### 3.4.3 Domain Models

| 模型 | 用途 | 位置 |
|------|------|------|
| `GoldenDataset` | 黄金样本管理、校准 | `src/domain/golden_dataset.py` |
| `AdaptiveCalibrator` | 自适应校准器（偏差监控、自动校准） | `src/domain/calibration/adaptive_calibrator.py` |
| `ABTesting` | A/B 测试管理 | `src/domain/ab_testing.py` |
| `ModelRouting` | 智能模型路由 | `src/domain/model_routing.py` |
| `MetaEvaluator` | 元评估器 | `src/domain/meta_evaluator.py` |
| `LLMGuardEvaluator` | LLM 安全扫描（OWASP Top 10） | `src/domain/evaluators/llm_guard_evaluator.py` |

#### 3.4.4 安全评估入口 (Safe Evaluate)

**职责**: 统一评估入口，确保日志记录和异常捕获

**异常分层处理**:
- 业务异常（`BasePlatformError` 及其子类）→ 向上传播到 engine 层处理
- 非业务异常（`RuntimeError`, `ValueError` 等）→ 捕获并转换为 `DomainResponse(evaluation_status=ERROR, error_code=SYSTEM_ERROR)`

**日志记录**: 每次评估必须记录结构化日志，包含评估器类型、输入输出、分数、状态、置信度等信息

### 3.5 Distributed Layer

**职责**: 分布式原语（锁、熔断、限流、队列、幂等）

| 组件 | 实现 | 用途 |
|------|------|------|
| **DistributedLock** | Redlock | 防止任务重复执行 |
| **CircuitBreaker** | 状态机 + Redis | 防止级联失败 |
| **RateLimiter** | Token Bucket + Redis | 多维度限流 |
| **PriorityQueue** | RabbitMQ + Celery | 优先级任务调度 |
| **Idempotency** | Redis + Hash | 任务去重 |

### 3.6 Infrastructure Layer

**职责**: DB / Cache / MQ / 监控 / 安全 / RBAC

#### 3.6.1 Database (SQLAlchemy)

**数据库模型**:
| 表 | 关键字段 | 用途 |
|----|----------|------|
| `eval_results` | id, case_id, model_name, adapter_name, status, latency_ms, response_data, created_at | 评测结果持久化 |
| `trajectories` | id, case_id, steps, total_tokens, success | Agent 轨迹记录 |

**连接池**: QueuePool（避免 SQLite StaticPool 死锁问题）

#### 3.6.2 Security (RBAC)

```python
class Role(Enum):
    GUEST = "guest"
    USER = "user"
    ADMIN = "admin"
    SUPER_ADMIN = "super_admin"
    # ... 扩展角色

class Permission(Enum):
    CREATE_AB_TEST = "create_ab_test"
    RUN_BENCHMARK = "run_benchmark"
    MANAGE_GOLDEN_DATASET = "manage_golden_dataset"
    # ... 扩展权限
```

#### 3.6.3 Monitoring

- **Prometheus**: `/metrics` 端点暴露评估次数、延迟、错误率
- **Grafana**: 内置 `ai_eval_platform_ops.json` 和 `ai_eval_platform_insights.json`
- **OpenTelemetry**: 分布式追踪（可选启用）
- **Structured Logging**: JSON 格式日志，支持链路追踪

## 4. Key Distributed Features

### 4.1 分布式锁 (Distributed Lock)

```
Key: eval:lock:{case_id}
Value: {worker_id}:{timestamp}
TTL: 30s (自动续期)
```

防止同一任务被多个worker重复执行。

### 4.2 消息可靠性

- Publisher Confirms: 确保消息到达broker
- Consumer Acknowledgements: 确保消息被处理
- Dead Letter Queue: 处理失败消息

### 4.3 熔断器 (Circuit Breaker)

```
States: CLOSED → OPEN → HALF_OPEN → CLOSED
触发条件: 连续失败次数 > threshold
恢复机制: 探测请求成功
```

### 4.4 限流 (Rate Limiting)

- 令牌桶算法
- Redis 原子操作
- 多维度限流（用户/API/Worker）

### 4.5 幂等性 (Idempotency)

```
Key: eval:idempotency:{case_id}:{timestamp}
Value: {task_id}
TTL: 24h
```

## 5. Data Models

### 5.1 Evaluation Schema

```python
class EvaluationSchema(BaseModel):
    id: str                        # 唯一 case_id（自动生成UUID）
    type: str                      # 评估器类型（必须已注册）
    payload: dict[str, Any]        # 业务数据（user_input / expected_output 等）
    metadata: dict | None          # 元数据
    model_provider: str | None     # 指定 LLM Provider
    model_name: str | None         # 指定模型名
    
    model_config = ConfigDict(frozen=True)  # 不可变模型，必须通过 model_copy 修改
```

### 5.2 Domain Response

```python
class DomainResponse(BaseModel):
    is_valid: bool = True                              # 是否通过
    text: str | None = None                            # 模型输出
    score: float | None = None                         # 评分（0.0 ~ 1.0）
    evaluation_status: EvaluatorStatus = SUCCESS       # 评估器状态（状态机）
    confidence: float | None = None                    # 评估置信度（0.0-1.0）
    confidence_level: ConfidenceLevel | None = None    # 置信度等级（自动计算）
    error: str | None = None                           # 错误信息
    metadata: dict | None = None                       # 元信息
    data: Any | None = None                            # 扩展数据
    
    @model_validator(mode="after")
    def compute_confidence_level(cls, values):
        # 根据 confidence 自动计算 confidence_level
        ...
```

### 5.3 Evaluator Status Machine

**评估器状态枚举**:
| 状态 | 值 | 含义 | 转换目标 |
|------|-----|------|----------|
| `SUCCESS` | "success" | 评估正常完成，返回有效分数 | → PASSED |
| `CANNOT_EVALUATE` | "cannot_evaluate" | 无法评估（如缺少必要输入） | → ERROR |
| `PARTIAL` | "partial" | 部分评估（如降级评估） | → PASSED（带标记） |
| `ERROR` | "error" | 评估失败（业务规则不满足或系统错误） | → FAILED/ERROR |

**状态转换规则**:
```
EvaluatorStatus.SUCCESS        → EvaluationRecordStatus.PASSED
EvaluatorStatus.PARTIAL        → EvaluationRecordStatus.PASSED
EvaluatorStatus.CANNOT_EVALUATE → EvaluationRecordStatus.ERROR
EvaluatorStatus.ERROR          → EvaluationRecordStatus.FAILED（无 error_code）
                                → EvaluationRecordStatus.ERROR（有 error_code）
```

### 5.4 Confidence System

**置信度等级枚举**:
| 等级 | 值 | 阈值 | 说明 |
|------|-----|------|------|
| `HIGH` | "high" | >= 0.9 | 完整数据 + LLM评估 |
| `MEDIUM` | "medium" | >= 0.7 | 部分数据 + LLM评估 或 完整数据 + Embedding |
| `LOW` | "low" | >= 0.5 | 部分数据 + Embedding |
| `VERY_LOW` | "very_low" | < 0.5 | 仅语法检查 或 数据严重缺失 |

### 5.5 Evaluation Result

```python
class EvaluationResult(BaseModel):
    case_id: str                   # 评估用例 ID
    status: EvaluationStatus       # PENDING/PASSED/FAILED/ERROR
    model_name: str | None         # 使用的模型
    adapter_name: str              # 评估器类型
    response: DomainResponse       # 详细响应（包含置信度）
    latency_ms: float              # 耗时
    error_message: str | None      # 错误描述
```

## 6. API Endpoints

### 6.1 v1 API（兼容模式）

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /api/v1/auth/login | 用户登录 |
| POST | /api/v1/auth/refresh | 刷新 Token |
| POST | /api/v1/evaluate | 同步评测 |
| POST | /api/v1/evaluate/async | 异步评测 |
| POST | /api/v1/evaluate/sync-batch | 批量评测 |
| GET | /api/v1/tasks/{task_id} | 查询任务状态 |
| GET | /api/v1/evaluators | 列出评估器 |
| GET | /api/v1/evaluators/{name} | 评估器详情 |
| GET | /api/v1/models | 列出模型 |
| POST | /api/v1/models/compare | 模型对比 |
| GET | /api/v1/records | 评测记录列表 |
| GET | /api/v1/records/{id} | 记录详情 |
| DELETE | /api/v1/records/{id} | 删除记录 |
| GET | /api/v1/dashboard/stats | 仪表盘统计 |
| POST | /api/v1/calibration/run | 运行校准 |
| POST | /api/v1/finetune/export | 导出微调数据 |
| GET | /api/v1/datasets | 数据集列表 |
| POST | /api/v1/reports/generate | 生成报告 |
| GET | /api/v1/health | 健康检查 |
| GET | /api/v1/health/detailed | 详细健康检查 |
| GET | /api/v1/metrics | Prometheus 指标 |

### 6.2 v2 API（聚合模式）

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /api/v2/evaluation/evaluate | 统一评估入口（同步/异步/批量） |
| GET | /api/v2/evaluation/tasks/{task_id} | 任务状态查询 |
| GET | /api/v2/evaluation/records | 评估记录列表 |
| GET | /api/v2/evaluation/records/{id} | 记录详情 |
| GET | /api/v2/models | 模型列表与状态 |
| POST | /api/v2/models/compare | 模型对比分析 |
| POST | /api/v2/models/switch | 模型切换 |
| GET | /api/v2/data/datasets | 数据集管理 |
| POST | /api/v2/data/upload | 数据上传 |
| GET | /api/v2/analytics/dashboard | 仪表盘统计 |
| GET | /api/v2/analytics/metrics | 评估指标 |
| POST | /api/v2/analytics/reports | 生成报告 |
| GET | /api/v2/config/evaluators | 评估器配置 |
| GET | /api/v2/config/system | 系统配置 |

## 7. Error Handling System

### 7.1 Exception Hierarchy

```
BasePlatformError
├─ ContractValidationError     [E1xxx] 输入契约违反
│   └─ EmptyInputError
├─ DomainLogicError            [E2xxx] 业务逻辑错误
│   ├─ EvaluatorNotFoundError
│   ├─ UnsupportedActionError
│   └─ SecurityError
│       ├─ InjectionDetectedError   [E3001]
│       └─ JailbreakDetectedError   [E3002]
├─ InfrastructureError         [E4xxx] 基础设施故障
│   ├─ LLMTimeoutError             [E4003]
│   └─ ConnectionPoolExhaustedError [E4005]
└─ IdempotencyError            [E5002] 幂等冲突
```

### 7.2 Global Exception Handling

| 异常类型 | HTTP状态码 | 处理方式 |
|----------|-----------|----------|
| `BasePlatformError` | 400/422 | 标准化错误码 + 详细错误信息 |
| `Pydantic ValidationError` | 400 | 字段级错误详情 |
| `HTTPException` | 透传 | 保持原有状态码 |
| `Exception` | 500 | INTERNAL_ERROR + 内部日志 |

### 7.3 异常分层处理策略

```
业务异常 (BasePlatformError)
    │
    ├─ ContractValidationError → 向上传播 → engine.py → ERROR状态 + contract_validator
    ├─ DomainLogicError        → 向上传播 → engine.py → ERROR状态 + domain_handler
    └─ InfrastructureError     → 向上传播 → engine.py → ERROR状态 + infra_handler

非业务异常 (RuntimeError, ValueError, etc.)
    │
    ├─ safe_evaluate 捕获 → create_error_response(error_code="SYSTEM_ERROR")
    └─ engine.py 检测 error_code → ERROR状态
```

## 8. Technology Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| API | FastAPI 0.104+ | 高性能异步API |
| ASGI Server | Uvicorn | 生产级ASGI |
| Task Queue | RabbitMQ + Celery | 分布式任务队列 |
| Cache/Lock | Redis 6+ | 分布式锁、限流、缓存 |
| Database | PostgreSQL 14+ / SQLite | 结果持久化 |
| ORM | SQLAlchemy 2 | 数据库访问 |
| Migration | Alembic | 数据库版本管理 |
| Authentication | JWT (python-jose + passlib) | 无状态认证 |
| Frontend | React 18 + TypeScript + Vite | SPA |
| UI Framework | Ant Design 5 + Tailwind CSS | 组件与样式 |
| State Management | Zustand | 轻量状态管理 |
| HTTP Client | Axios | API调用 |
| Charts | Recharts | 数据可视化 |
| Testing | pytest + vitest + playwright | 单元/集成/E2E |
| Metrics | Prometheus + Grafana | 监控 |
| Tracing | OpenTelemetry | 链路追踪 |
| Container | Docker + Docker Compose | 容器部署 |
| Orchestration | Kubernetes | 生产编排 |

## 9. Reliability Features

1. **At-Least-Once Delivery**: 消息确认机制
2. **Idempotency**: 任务去重 (case_id + timestamp)
3. **Graceful Degradation**: 熔断器保护 + 降级策略(PARTIAL状态)
4. **Circuit Breaker**: 防止级联失败
5. **Rate Limiting**: 防止系统过载
6. **Dead Letter Queue**: 失败消息收集
7. **Retry with Backoff**: 自动重试 + 指数退避
8. **Distributed Lock**: 防止任务重复执行
9. **安全评估入口**: safe_evaluate 统一异常处理和日志记录

## 10. Scalability

- **水平扩展**: 增加Worker节点即可
- **优先级队列**: 重要任务优先处理
- **负载均衡**: RabbitMQ round-robin + Nginx
- **自动扩缩容**: K8s HPA 支持 (基于CPU/队列长度)
- **Connection Pool**: SQLAlchemy QueuePool 支持高并发

## 11. Observability

### 11.1 Metrics (Prometheus)

| 指标名 | 类型 | 描述 |
|--------|------|------|
| `evaluation_counter` | Counter | 评估总次数 |
| `evaluation_errors` | Counter | 评估错误次数 |
| `evaluation_latency` | Histogram | 评估延迟分布 |
| `circuit_breaker_state` | Gauge | 熔断器状态 |
| `queue_length` | Gauge | 队列长度 |

### 11.2 Tracing (OpenTelemetry)

- Trace ID 贯穿整个评估流程
- Span 覆盖：API → Service → Engine → Evaluator → LLM Client
- 支持 Jaeger / Zipkin / OTLP

### 11.3 Structured Logging

**评估结果日志格式**:
```json
{
    "timestamp": "2026-07-01T12:00:00",
    "evaluator_type": "SecurityEvaluator",
    "request_id": "case_123",
    "evaluation_type": "security",
    "input_text": "...",
    "actual_output": "...",
    "expected_output": "...",
    "score": 0.85,
    "evaluation_status": "success",
    "confidence": 0.92,
    "confidence_level": "high",
    "is_valid": true,
    "error": null,
    "metadata_keys": ["language", "model"],
    "dimensions_evaluated": ["injection", "jailbreak"],
    "dimensions_skipped": []
}
```

**关键特性**:
- JSON 结构化日志
- 包含 trace_id, span_id, case_id
- 分级日志：DEBUG / INFO / WARNING / ERROR
- Phase 1.5 诊断期要求：记录原始输入、输出、评估维度覆盖情况

## 12. Testing Architecture

### 12.1 Test Coverage Matrix

| 测试类型 | 目录 | 覆盖范围 |
|----------|------|----------|
| **单元测试** | `tests/unit/` | 核心组件、评估器、服务层（400+） |
| **集成测试** | `tests/integration/` | API、领域、基础设施（57+） |
| **E2E 测试** | `tests/e2e/` | 完整前后端工作流（Playwright） |
| **可靠性测试** | `tests/reliability/` | 分布式、并发、熔断、限流 |
| **性能测试** | `tests/performance/` | 基准测试、压力测试 |
| **安全测试** | `tests/security/` | OWASP 漏洞扫描 |
| **混沌测试** | `tests/chaos/` | 网络抖动、故障注入 |
| **冒烟测试** | `tests/smoke/` | 关键路径验证 |

### 12.2 Meta-Testing Framework

系统内置元测试框架，用于验证评估器自身的准确性：

```
MetaEvaluator
    │
    ├─ 一致性检验：评估器对相同输入的结果一致性
    ├─ 对抗性检验：对抗样本检测能力
    ├─ 边界检验：边界条件处理能力
    └─ 校准检验：与人工标注的一致性
```

## 13. Configuration Management

### 13.1 Environment Variables

| 变量 | 用途 | 默认值 |
|------|------|--------|
| `AI_EVAL_SECRET_KEY` | JWT 密钥 | 必须配置 |
| `AI_EVAL_DB_URL` | 数据库连接 | `sqlite:///test.db` |
| `AI_EVAL_REDIS_URL` | Redis 连接 | `redis://localhost:6379` |
| `AI_EVAL_RABBITMQ_URL` | RabbitMQ 连接 | `amqp://guest:guest@localhost` |
| `AI_EVAL_ADMIN_PASSWORD` | 管理员密码 | `admin123` |
| `TESTING` | 测试模式 | `False` |

### 13.2 Configuration Files

| 文件 | 用途 |
|------|------|
| `src/config/__init__.py` | 统一配置入口（Settings类 + get_settings） |
| `src/config/thresholds.py` | 评估阈值配置 |
| `src/config.py` | 兼容性导入层 |
| `config/evaluation_thresholds.yaml` | YAML 阈值配置 |
| `.env` | 环境变量（开发） |
| `.env.prod` | 环境变量（生产） |

### 13.3 配置管理规范

- **避免循环导入**: 配置类（`Settings`）和配置实例（`settings`）必须放在 `src/config/__init__.py` 中
- **延迟初始化**: `get_settings()` 使用 `@lru_cache` 实现单例模式
- **环境变量**: 敏感配置必须通过环境变量设置，默认值仅用于开发环境

## 14. Deployment Architecture

### 14.1 Docker Compose (Development)

```
docker-compose.yml
    │
    ├─ api: FastAPI + Uvicorn
    ├─ worker: Celery Worker
    ├─ redis: Redis
    ├─ rabbitmq: RabbitMQ
    ├─ postgres: PostgreSQL
    ├─ prometheus: Prometheus
    ├─ grafana: Grafana
    └─ frontend: React + Vite
```

### 14.2 Kubernetes (Production)

```
deploy/k8s/deployment.yaml
    │
    ├─ Deployment: ai-eval-api (replicas: 3)
    ├─ Deployment: ai-eval-worker (replicas: 5)
    ├─ Service: ai-eval-api (ClusterIP)
    ├─ Service: ai-eval-api-external (NodePort/LoadBalancer)
    ├─ HPA: ai-eval-worker (基于队列长度)
    ├─ Secret: ai-eval-secrets
    └─ ConfigMap: ai-eval-config
```

## 15. Key Design Patterns

| 模式 | 应用位置 | 说明 |
|------|----------|------|
| **工厂模式** | `EvaluatorFactory` / `ModelRegistry` | 评估器与模型客户端的统一创建入口 |
| **注册表模式** | `EvaluatorFactory._registry` | 运行时动态发现与注册 |
| **装饰器模式** | `@EvaluatorFactory.register()` | 解耦评估器定义与注册逻辑 |
| **策略模式** | `RegisterStrategy.OVERWRITE/SKIP/ERROR` | 处理重复注册的多种策略 |
| **上下文管理器** | `get_db_session()` / `DistributedLock` | 资源生命周期自动管理 |
| **熔断器模式** | `BaseEvaluator.evaluate()` | 单个评估器的故障隔离 |
| **模板方法模式** | `BaseEvaluator.evaluate()` | 定义评估流程骨架 |
| **状态机模式** | `EvaluatorStatus` | 明确区分评估结果状态 |

## 16. Security Architecture

### 16.1 Authentication

- JWT 无状态认证
- API Key 认证
- 双因素认证（可选）

### 16.2 Authorization (RBAC)

- 角色定义：GUEST / USER / ADMIN / SUPER_ADMIN
- 权限定义：基于资源的细粒度权限
- 权限装饰器：`@require_permission`, `@require_role`

### 16.3 Data Protection

- bcrypt 密码哈希
- 敏感配置加密存储
- HTTPS 传输加密
- 输入验证（Pydantic）

### 16.4 Security Evaluator

- 注入攻击检测
- 越狱检测
- 数据泄露检测
- 工具滥用检测

## 17. Version History

| 版本 | 日期 | 主要变更 |
|------|------|----------|
| v1.0.0 | 2026-06-20 | 基础评估器框架、37个评估器、27个API路由、SQLite数据库 |
| v2.0.0 | 2026-06-29 | 评估器精简（37→15）、API路由聚合（27→5）、数据库迁移（SQLite→PostgreSQL）、RBAC安全增强 |
| v2.1.0 | 2026-07-01 | 评估器状态机（EvaluatorStatus）、置信度系统（ConfidenceLevel）、安全评估入口（safe_evaluate）、结构化日志记录、Pydantic模型规范 |