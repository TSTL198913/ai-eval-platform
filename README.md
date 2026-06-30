# AI-Eval-Pro: Enterprise-Grade Evaluation Infrastructure

AI-Eval-Pro is a distributed evaluation framework designed for production-level AI quality assurance.

🚀 **Production-Ready**: Distributed architecture with high-availability circuit breakers and ACID storage.

🛡️ **Compliance-First**: Built-in security gates and RBAC governance for LLM outputs.

📊 **Actionable Insights**: Automated consistency alignment (Kappa ≥ 0.6) and auto-remediation loops.

📈 **Verified Quality**: 838+ test cases passed, CI/CD-integrated, and ready for K8s deployment.

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18-61dafb.svg)](https://react.dev)
[![License](https://img.shields.io/badge/License-Internal-orange.svg)]()

## 一、项目简介

AI-Eval-Pro 是一个面向大语言模型（LLM）的**企业级分布式评测基础设施**，提供从模型接入、评测执行、结果分析到质量门禁的完整链路。系统采用**六层分层架构**（API → Service → Engine → Domain → Distributed → Infra），支持 15+ 种核心评估器类型、5+ 种模型提供者，并具备企业级的分布式能力（锁、熔断、限流、幂等、队列）。

**核心价值**：
- 统一接口接入多种 LLM（DeepSeek / OpenAI / Anthropic / Ollama / Qwen）
- 覆盖安全、代码、事实性、规划、记忆等 15+ 维度的细粒度评估
- 集成业界标准指标（BLEU/ROUGE/METEOR/F1）与主流框架（RAGAS/DeepEval）
- 完整的人工标注工作流（双盲标注、Cohen's Kappa 一致性、黄金样本校准）
- 分布式任务调度，支持优先级队列与异步评估
- 完整的可观测性（Prometheus + Grafana + 结构化日志 + OpenTelemetry）
- 企业级 RBAC 权限控制与安全门禁

> 📘 **新增**：标准指标库、第三方框架适配、人工标注、可视化报告 — 详见 [docs/enhancement_features_guide.md](file:///d:/workspace/ai-eval-platform-refactor/docs/enhancement_features_guide.md)

---

## 二、核心功能

### 2.1 多模型统一接入

通过 `create_llm_client()` 工厂方法一键接入 5+ 种 LLM Provider，支持环境变量配置与单例缓存：

```python
from src.domain.models.llm_factory import create_llm_client

# 方式1：自动从环境变量读取
client = create_llm_client()

# 方式2：指定 Provider
client = create_llm_client(provider="openai")

# 方式3：注入 Mock 客户端（用于测试）
client = create_llm_client(client=MockClient())
```

**支持的 Provider**：`deepseek` / `openai` / `anthropic` / `ollama` / `qwen` / `dashscope` / `stub`

### 2.2 15+ 核心评估器体系

评估器通过 `@EvaluatorFactory.register()` 装饰器自动注册，支持插件化扩展与黑名单机制：

| 类别 | 评估器 | 用途 |
|------|--------|------|
| **安全** | `SecurityEvaluator` | 注入攻击 / 越狱检测 / 内容安全 |
| **代码** | `CodeEvaluator` / `CodeReviewEvaluator` | 代码生成与审查质量 |
| **事实性** | `FactCheckEvaluator` / `FactualityEvaluator` | 事实核查与真实性 |
| **语义** | `SemanticEvaluator` | 语义相似度与对齐评估 |
| **问答** | `QAEvaluator` | 问答质量与相关性 |
| **记忆** | `MemoryEvaluator` | 长短期记忆能力评估 |
| **鲁棒性** | `RobustnessEvaluator` | 提示词鲁棒性与稳定性 |
| **代理** | `MultiAgentEvaluator` | 多代理协作能力 |
| **工具** | `FunctionCallEvaluator` | 工具调用准确性 |
| **分类** | `ClassificationEvaluator` | 分类任务评估 |
| **风险** | `RiskEvaluator` | 业务风险检测 |
| **LLM裁判** | `LLMAJudgeEvaluator` | LLM-as-a-Judge 语义评估 |
| **综合** | `CompositeEvaluator` | 多维度综合评估 |
| **通用** | `GeneralEvaluator` | 通用能力评估 |

核心评估器列表见 [src/domain/evaluators/__init__.py](file:///d:/workspace/ai-eval-platform-refactor/src/domain/evaluators/__init__.py#L67-L70)。

### 2.3 分布式任务调度

支持同步与异步两种评测模式：
- **同步模式**：`POST /api/v1/evaluate` - 立即返回结果
- **异步模式**：`POST /api/v1/evaluate/async` - 提交到 Celery 任务队列
- **批量模式**：`POST /api/v1/evaluate/sync-batch` - 批量评估
- **状态查询**：`GET /api/v1/tasks/{task_id}` - 实时任务状态

### 2.4 分布式能力

- **分布式锁**（Redlock）— 防止任务重复执行
- **熔断器**（Circuit Breaker）— 防止级联失败
- **多维限流**（Token Bucket）— 按用户/API/Worker 维度
- **幂等性检查**（Idempotency）— 任务去重
- **优先级队列**（Priority Queue）— 重要任务优先处理

### 2.5 企业级安全与权限

- **RBAC 权限控制**：基于角色的访问控制（Role-Based Access Control），支持 API Key 认证与权限粒度控制
- **安全中间件**：注入检测、内容过滤、越狱防护
- **质量门禁**：自动评估质量阈值检查，阻止低质量模型上线
- **审计日志**：完整的操作记录与合规追溯

### 2.6 可观测性

- **Prometheus 指标**：`/metrics` 端点暴露评估次数、延迟、错误率
- **Grafana 仪表盘**：内置 `ai_eval_platform_ops.json` 与 `ai_eval_platform_insights.json`
- **结构化日志**：JSON 格式日志，支持链路追踪
- **OpenTelemetry**：分布式追踪（可选启用）

---

## 三、系统架构

### 3.1 整体架构图

```
┌──────────────────────────────────────────────────────────────────┐
│                    Frontend (React + Vite + TS)                  │
│  Dashboard / Evaluators / Models / Records / Cost / Health      │
└──────────────────────────────────────────────────────────────────┘
                              │ HTTPS / JWT
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│                  API Layer (FastAPI Router)                      │
│   auth / evaluate / evaluators / models / records / reports     │
│   [CORS] [Security] [Prometheus] [RateLimit] Middlewares        │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│              Service Layer (业务编排)                            │
│   evaluator_svc → run_evaluation_service()                      │
│   data_svc → search / get_recent / count                        │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│              Engine Layer (EvaluationEngine)                     │
│   异常分类捕获 → 状态映射 → 性能计时 → 持久化                    │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│             Domain Layer (核心业务逻辑)                          │
│   EvaluatorFactory → 15 Core Evaluators (BaseEvaluator)         │
│   ModelFactory → 5+ LLM Clients (BaseLLMClient)                 │
│   Domain Models / A/B Test / Calibration / GoldenDataset        │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│         Distributed Layer (分布式原语)                           │
│   Lock / CircuitBreaker / RateLimiter / Queue / Idempotency     │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│         Infrastructure Layer (基础设施)                          │
│   DB (PostgreSQL/SQLite) / Cache (Redis) / MQ (RabbitMQ)        │
│   Security / Monitoring / Tracing / Logging / Plugins           │
└──────────────────────────────────────────────────────────────────┘
```

### 3.2 分层职责

| 层级 | 目录 | 职责 | 依赖方向 |
|------|------|------|----------|
| **API** | `src/api/` | 路由分发、请求验证、响应格式化、v2 聚合路由 | → Service |
| **Service** | `src/services/` | 业务编排、事务控制、跨域协调 | → Engine / Domain |
| **Engine** | `src/engine.py` | 异常捕获、状态映射、性能计时 | → Domain |
| **Domain** | `src/domain/` | 核心业务规则、评估器实现、模型抽象 | → Distributed / Infra |
| **Distributed** | `src/distributed/` | 分布式原语（锁、熔断、限流、队列、幂等） | → Infra |
| **Infra** | `src/infra/` | DB / Cache / MQ / 监控 / 安全 / RBAC | 外部资源 |

**依赖规则**（参见 [.trae/rules/arch_review.md](file:///d:/workspace/ai-eval-platform-refactor/.trae/rules/arch_review.md)）：
- ✅ 依赖单向流动：`API → Service → Engine → Domain → Distributed → Infra`
- ❌ 禁止跨层调用（如 API 直接调用 Repository）
- ✅ 新增评估器必须通过 `@EvaluatorFactory.register()` 注册
- ✅ 新增 LLM 客户端必须通过 `create_llm_client()` 创建
- ✅ 评估器黑名单机制：`_EVALUATOR_BLACKLIST` 控制评估器注册

### 3.3 关键设计模式

| 模式 | 应用位置 | 说明 |
|------|----------|------|
| **工厂模式** | `EvaluatorFactory` / `ModelRegistry` | 评估器与模型客户端的统一创建入口 |
| **注册表模式** | `EvaluatorFactory._registry` | 运行时动态发现与注册 |
| **装饰器模式** | `@EvaluatorFactory.register()` | 解耦评估器定义与注册逻辑 |
| **策略模式** | `RegisterStrategy.OVERWRITE/SKIP/ERROR` | 处理重复注册的多种策略 |
| **上下文管理器** | `get_db_session()` / `DistributedLock` | 资源生命周期自动管理 |
| **熔断器** | `BaseEvaluator.safe_evaluate()` | 单个评估器的故障隔离 |

---

## 四、核心业务逻辑

### 4.1 评测执行流程

**核心代码**：[src/engine.py](file:///d:/workspace/ai-eval-platform-refactor/src/engine.py)

```
EvaluationEngine.run()
    │
    ├─ 1. 从 EvaluatorFactory 获取评估器（受熔断器保护）
    │      └─ EvaluatorFactory.get(type, client)
    │
    ├─ 2. 调用 evaluator.safe_evaluate(request)
    │      └─ safe_evaluate() 内置熔断器 + 异常处理
    │
    ├─ 3. 状态映射
    │      ├─ is_valid=True        → PASSED
    │      ├─ error含"_ERROR"        → ERROR
    │      └─ 其他                   → FAILED
    │
    ├─ 4. 构造 EvaluationResult（case_id, status, model, adapter, latency, response）
    │
    └─ 5. 返回结果（由 Service 层负责持久化）
```

**关键特性**：
- **异常分类**：`ContractValidationError` / `DomainLogicError` / `InfrastructureError` / `Exception` 四级异常分类
- **状态机**：`PENDING → PASSED / FAILED / ERROR` 三态终结
- **性能埋点**：`time.perf_counter()` 毫秒级延迟统计
- **熔断保护**：评估器创建与执行双层熔断

### 4.2 评估器发现与注册

**核心代码**：[src/domain/evaluators/__init__.py](file:///d:/workspace/ai-eval-platform-refactor/src/domain/evaluators/__init__.py)

```python
# 1. 通过装饰器注册（支持黑名单过滤）
@EvaluatorFactory.register("security")
class SecurityEvaluator(BaseEvaluator):
    def evaluate(self, request: EvaluationSchema) -> DomainResponse:
        ...

# 2. 自动发现机制（pkgutil 扫描 + 黑名单过滤）
_EVALUATOR_BLACKLIST = {
    "text", "text_similarity_base", "sentiment", "grammar", "summary",
    "translation", "multilingual", "fact_check", "finance", "drift",
    "prompt_sensitivity", "prompt_regression", "judge_robustness",
    "multi_judge_ensemble", "multi_metric", "standard_metric", "ragas",
    "deepeval", "meta_test", "planning", "trajectory", "runtime_agent", "tool_use"
}

def auto_discover(force: bool = False):
    for _, name, _is_pkg in pkgutil.iter_modules(__path__):
        if name not in _SKIP_MODULES and name not in _EVALUATOR_BLACKLIST:
            importlib.import_module(f".{name}", package=__name__)
    _EVALUATOR_REGISTRY = EvaluatorFactory._registry

# 3. 列出核心评估器
def list_core_evaluators() -> list[str]:
    return ["general", "code", "code_review", "security", "memory", 
            "semantic", "qa", "factuality", "risk", "classification",
            "composite", "function_call", "multi_agent", "llm_as_judge", "robustness"]
```

**注册流程**：
1. 模块导入时触发 `auto_discover()`
2. 扫描 `src/domain/evaluators/` 下所有非排除子模块
3. 黑名单模块被自动跳过，仅注册 15 个核心评估器
4. 每个子模块 import 时通过装饰器自动注册
5. 启动时 `lifespan` 预热已注册评估器列表

### 4.3 模型客户端管理

**核心代码**：[src/domain/models/llm_factory.py](file:///d:/workspace/ai-eval-platform-refactor/src/domain/models/llm_factory.py)

```
create_llm_client()
    │
    ├─ 1. 客户端注入优先（client=MockClient()）
    │
    ├─ 2. 自定义配置优先（config=ModelConfig(...)）
    │
    └─ 3. 缓存路径（默认）
         ├─ 双重检查锁（RLock）
         ├─ load_config() 加载环境变量（带缓存）
         ├─ _create_new_client() 实际创建
         └─ 缓存到 _llm_client_cache
```

**缓存策略**：
- `_llm_client_cache`：客户端单例，key = `provider:model_name`
- `_env_config_cache`：环境变量配置缓存，减少重复读取
- **双锁保护**：`_cache_lock`（客户端）+ `_env_cache_lock`（配置）

### 4.4 路由与业务编排

**核心代码**：[src/services/evaluator_svc.py](file:///d:/workspace/ai-eval-platform-refactor/src/services/evaluator_svc.py)

```python
def run_evaluation_service(raw_data: dict, client=None) -> dict:
    # 1. 数据规范化
    raw_data = _normalize_raw_data(raw_data)

    # 2. Schema 验证
    case = EvaluationSchema(**raw_data)

    # 3. 客户端选择（三级降级）
    if client is not None:           # 显式注入
        llm_client = client
    elif case.model_provider:         # 显式 Provider
        llm_client = create_llm_client(provider=case.model_provider, ...)
    else:                              # 智能路由
        llm_client, routing_decision = model_router.create_llm_client(case.type, case.payload)

    # 4. 引擎执行
    result = EvaluationEngine(llm_client).run(case)

    # 5. 持久化（失败不影响返回）
    db_id = _repository.save(result)

    return {"status": ..., "record_id": ..., "latency_ms": ..., ...}
```

### 4.5 异常处理体系

**核心代码**：[src/exceptions.py](file:///d:/workspace/ai-eval-platform-refactor/src/exceptions.py)

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

**全局异常处理器**（[src/api/server.py](file:///d:/workspace/ai-eval-platform-refactor/src/api/server.py#L144-L206)）：
- `BasePlatformError` → 400/422 + 标准化错误码
- `Pydantic ValidationError` → 400 + 字段级错误
- `HTTPException` → 透传状态码
- `Exception` → 500 + INTERNAL_ERROR

---

## 五、数据流向

### 5.1 同步评测数据流

```
┌─────────┐    HTTP/JSON    ┌─────────┐    dict     ┌─────────┐
│ Client  │ ───────────────▶│   API   │────────────▶│ Service │
└─────────┘                 │ Router  │             └────┬────┘
                            └────┬────┘                  │
                                 │ Schema Validate       │ Schema
                                 ▼                       ▼ Validate
                            ┌─────────┐             ┌─────────┐
                            │ Pydantic│             │Evaluation│
                            │  Check  │             │ Schema  │
                            └─────────┘             └────┬────┘
                                                         │
                                                         ▼
┌─────────┐   ┌──────────┐   ┌─────────┐   ┌────────────────────┐
│  Repo   │◀──│ Engine   │◀──│Evaluator│◀──│  LLM Client         │
│  Save   │   │   Run    │   │  .eval  │   │ (DeepSeek/OpenAI..)│
└────┬────┘   └──────────┘   └─────────┘   └────────────────────┘
     │
     ▼
┌──────────┐
│PostgreSQL│  eval_results table
│ / SQLite │
└──────────┘
```

### 5.2 异步评测数据流

```
Client ─POST /evaluate/async─▶ API Router
                                    │
                                    ▼
                            [validate + 序列化]
                                    │
                                    ▼
                         ┌─────────────────┐
                         │   RabbitMQ /    │  Priority Queue
                         │  Celery Broker  │
                         └────────┬────────┘
                                  │
                                  ▼
                         ┌─────────────────┐
                         │ Celery Worker   │  Distributed Lock
                         │  (Pool)         │  + Idempotency
                         └────────┬────────┘
                                  │
                                  ▼
                         ┌─────────────────┐
                         │ Worker tasks.py │  eval_case_task()
                         │  → evaluator_svc│
                         └────────┬────────┘
                                  │
                                  ▼
                         ┌─────────────────┐
                         │   Database +    │  Result + Trace
                         │   Redis Cache   │
                         └─────────────────┘
```

### 5.3 数据模型

**评估请求**（[src/schemas/evaluation.py](file:///d:/workspace/ai-eval-platform-refactor/src/schemas/evaluation.py#L27-L42)）：

```python
class EvaluationSchema(BaseModel):
    id: str                        # 唯一 case_id（自动生成 UUID）
    type: str                      # 评估器类型（必须已注册）
    payload: dict[str, Any]        # 业务数据（user_input / expected_output 等）
    metadata: dict | None          # 元数据
    model_provider: str | None     # 指定 LLM Provider
    model_name: str | None         # 指定模型名
```

**领域响应**：

```python
class DomainResponse(BaseModel):
    is_valid: bool = True          # 是否通过
    text: str | None               # 模型输出
    score: float | None            # 评分（0.0 ~ 1.0）
    error: str | None              # 错误信息
    metadata: dict | None          # 元信息
    data: Any | None               # 扩展数据
```

**评估结果**（[src/schemas/schemas.py](file:///d:/workspace/ai-eval-platform-refactor/src/schemas/schemas.py#L34-L41)）：

```python
class EvaluationResult(BaseModel):
    case_id: str                   # 评估用例 ID
    status: EvaluationStatus       # PENDING/PASSED/FAILED/ERROR
    model_name: str | None         # 使用的模型
    adapter_name: str              # 评估器类名
    response: DomainResponse       # 详细响应
    latency_ms: float              # 耗时
    error_message: str | None      # 错误描述
```

**数据库模型**（[src/infra/db/models.py](file:///d:/workspace/ai-eval-platform-refactor/src/infra/db/models.py)）：

| 表 | 关键字段 | 用途 |
|----|----------|------|
| `eval_results` | id, case_id, model_name, adapter_name, status, latency_ms, response_data, created_at | 评测结果持久化 |
| `trajectories` | id, case_id, steps, total_tokens, success | Agent 轨迹记录 |

### 5.4 关键链路示例

**完整链路**（以 `POST /api/v1/evaluate` 为例）：

```
1. 客户端发起 POST 请求
   ↓
2. FastAPI 中间件链
   - SecurityMiddleware: 注入检测
   - RateLimitMiddleware: 限流
   - PrometheusMiddleware: 指标埋点
   ↓
3. CORS / Auth 验证
   ↓
4. 路由到达 evaluation_router
   ↓
5. Pydantic 验证请求体（EvaluationSchema）
   ↓
6. 调用 run_evaluation_service(raw_data)
   ↓
7. 智能选择 LLM Client（三级降级）
   ↓
8. EvaluationEngine.run(case)
   - 获取评估器（熔断器保护）
   - 执行 safe_evaluate
   - 状态映射
   - 计时
   ↓
9. EvaluationRepository.save(result)
   - SQLAlchemy ORM 写入
   - 事务管理
   ↓
10. 构造统一响应 + 业务码
   ↓
11. 序列化返回 JSON
```

---

## 六、目录结构

```
ai-eval-platform-refactor/
├── src/                          # 后端核心代码
│   ├── api/                      # API 层
│   │   ├── routes/               # 路由模块（v1: 27 个 / v2: 5 个聚合路由）
│   │   │   └── v2/               # v2 聚合路由（evaluation/models/data/analytics/config）
│   │   ├── server.py             # FastAPI 应用入口
│   │   ├── security_middleware.py
│   │   └── versioning.py
│   ├── services/                 # 服务层
│   │   ├── evaluator_svc.py
│   │   └── data_svc.py
│   ├── domain/                   # 领域层
│   │   ├── evaluators/           # 15+ 核心评估器
│   │   ├── models/               # LLM 客户端工厂
│   │   ├── benchmarks/           # GSM8K / MMLU / HumanEval
│   │   ├── testing/              # 变异测试 / 红蓝测试
│   │   ├── online/               # 在线评估
│   │   ├── security/             # 安全测试
│   │   ├── ab_testing.py
│   │   ├── calibration_service.py
│   │   ├── golden_dataset.py
│   │   └── model_routing.py
│   ├── distributed/              # 分布式原语
│   │   ├── lock.py               # Redlock
│   │   ├── circuit_breaker.py
│   │   ├── rate_limiter.py
│   │   ├── queue.py
│   │   └── idempotency.py
│   ├── infra/                    # 基础设施层
│   │   ├── db/                   # SQLAlchemy
│   │   ├── monitoring/           # Prometheus
│   │   ├── security/             # 加密配置
│   │   ├── analytics/            # 分析报告
│   │   ├── cache.py              # Redis 缓存
│   │   ├── feature_flags.py
│   │   ├── high_availability.py
│   │   └── plugins.py
│   ├── workers/                  # Celery 异步任务
│   │   ├── celery_app.py
│   │   ├── tasks.py
│   │   └── monitor_queue.py
│   ├── schemas/                  # Pydantic Schema
│   ├── engine.py                 # 评测引擎核心
│   ├── config.py                 # 统一配置
│   └── exceptions.py             # 异常体系
├── frontend/                     # 前端 (React + TS + Vite)
│   ├── src/
│   │   ├── pages/                # 7 个业务页面
│   │   ├── components/           # 通用组件
│   │   ├── hooks/                # 自定义 Hooks
│   │   ├── services/             # API 客户端
│   │   └── stores/               # Zustand
│   └── package.json
├── tests/                        # 测试体系
│   ├── unit/                     # 单元测试
│   ├── integration/              # 集成测试
│   ├── e2e/                      # E2E（Playwright）
│   ├── reliability/              # 可靠性测试
│   ├── performance/              # 性能测试
│   ├── security/                 # OWASP 安全测试
│   ├── chaos/                    # 混沌测试
│   └── smoke/                    # 冒烟测试
├── deploy/                       # 部署配置
│   ├── prometheus/
│   └── alertmanager/
├── docker/                       # Docker & K8s
├── grafana/                      # Grafana 仪表盘
├── docs/                         # 详细文档
├── alembic/                      # 数据库迁移
├── scripts/                      # 运维脚本
└── sdk/python/                   # Python SDK
```

---

## 七、关键 API 端点

### v1 API（兼容模式）

| Method | Endpoint | 描述 |
|--------|----------|------|
| `POST` | `/api/v1/auth/login` | 用户登录 |
| `POST` | `/api/v1/auth/refresh` | 刷新 Token |
| `POST` | `/api/v1/evaluate` | 同步评测 |
| `POST` | `/api/v1/evaluate/async` | 异步评测 |
| `POST` | `/api/v1/evaluate/sync-batch` | 批量评测 |
| `GET` | `/api/v1/tasks/{task_id}` | 查询任务状态 |
| `GET` | `/api/v1/evaluators` | 列出评估器 |
| `GET` | `/api/v1/evaluators/{name}` | 评估器详情 |
| `GET` | `/api/v1/models` | 列出模型 |
| `POST` | `/api/v1/models/compare` | 模型对比 |
| `GET` | `/api/v1/records` | 评测记录列表 |
| `GET` | `/api/v1/records/{id}` | 记录详情 |
| `DELETE` | `/api/v1/records/{id}` | 删除记录 |
| `GET` | `/api/v1/dashboard/stats` | 仪表盘统计 |
| `POST` | `/api/v1/calibration/run` | 运行校准 |
| `POST` | `/api/v1/finetune/export` | 导出微调数据 |
| `GET` | `/api/v1/datasets` | 数据集列表 |
| `POST` | `/api/v1/reports/generate` | 生成报告 |
| `GET` | `/api/v1/health` | 健康检查 |
| `GET` | `/api/v1/health/detailed` | 详细健康检查 |
| `GET` | `/api/v1/metrics` | Prometheus 指标 |

### v2 API（聚合模式）

| Method | Endpoint | 描述 |
|--------|----------|------|
| `POST` | `/api/v2/evaluation/evaluate` | 统一评估入口（同步/异步/批量） |
| `GET` | `/api/v2/evaluation/tasks/{task_id}` | 任务状态查询 |
| `GET` | `/api/v2/evaluation/records` | 评估记录列表 |
| `GET` | `/api/v2/evaluation/records/{id}` | 记录详情 |
| `GET` | `/api/v2/models` | 模型列表与状态 |
| `POST` | `/api/v2/models/compare` | 模型对比分析 |
| `POST` | `/api/v2/models/switch` | 模型切换 |
| `GET` | `/api/v2/data/datasets` | 数据集管理 |
| `POST` | `/api/v2/data/upload` | 数据上传 |
| `GET` | `/api/v2/analytics/dashboard` | 仪表盘统计 |
| `GET` | `/api/v2/analytics/metrics` | 评估指标 |
| `POST` | `/api/v2/analytics/reports` | 生成报告 |
| `GET` | `/api/v2/config/evaluators` | 评估器配置 |
| `GET` | `/api/v2/config/system` | 系统配置 |
| `GET` | `/` | 根路径（API 信息） |
| `GET` | `/docs` | Swagger UI |

---

## 八、快速开始

### 8.1 环境要求

- Python 3.11+
- Node.js 18+
- PostgreSQL 14+（生产）/ SQLite（开发）
- Redis 6+
- RabbitMQ 3.10+

### 8.2 后端启动

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env 填入 API Keys

# 3. 数据库初始化
alembic upgrade head

# 4. 启动 API 服务
uvicorn src.api.server:app --host 0.0.0.0 --port 8000 --reload

# 5. 启动 Celery Worker（异步任务）
celery -A src.workers.celery_app worker --loglevel=info
```

### 8.3 前端启动

```bash
cd frontend
npm install
npm run dev
# 默认访问 http://localhost:5173
```

### 8.4 Docker 一键启动

```bash
docker-compose up -d
```

---

## 九、扩展开发

### 9.1 新增评估器

```python
# src/domain/evaluators/my_evaluator.py
from src.domain.evaluators.evaluator_factory import EvaluatorFactory
from src.domain.evaluators.base import BaseEvaluator
from src.schemas.evaluation import EvaluationSchema, DomainResponse

@EvaluatorFactory.register("my_type")
class MyEvaluator(BaseEvaluator):
    def evaluate(self, request: EvaluationSchema) -> DomainResponse:
        # 实现评测逻辑
        user_input = self.get_input_text(request)
        if not user_input:
            return self.create_error_response("输入不能为空")

        # 执行业务逻辑
        score = self._do_evaluate(user_input)

        return self.create_success_response(
            text="评估完成",
            score=score,
            data={"detail": "..."}
        )
```

评估器会在模块导入时自动注册，无需手动配置。

### 9.2 新增 LLM Provider

```python
# src/domain/models/my_provider.py
from src.domain.models.base import BaseLLMClient
from src.domain.models.llm_factory import ModelRegistry

@ModelRegistry.register("my_provider")
class MyProviderClient(BaseLLMClient):
    def chat(self, messages, **kwargs):
        # 实现 LLM 调用
        ...
```

### 9.3 新增 API 路由

```python
# src/api/routes/my_routes.py
from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/my", tags=["my"])

@router.get("/items")
async def list_items():
    return {"items": []}
```

然后在 [src/api/server.py](file:///d:/workspace/ai-eval-platform-refactor/src/api/server.py) 注册：

```python
from src.api.routes.my_routes import router as my_router
app.include_router(my_router)
```

---

## 十、测试

测试体系覆盖 8 个维度，**838+ 测试用例通过**，CI/CD 集成：

| 测试类型 | 目录 | 覆盖范围 |
|----------|------|----------|
| **单元测试** | `tests/unit/` | 核心组件、评估器、服务层（800+） |
| **集成测试** | `tests/integration/` | API、领域、基础设施（17+ external） |
| **E2E 测试** | `tests/e2e/` | 完整前后端工作流（Playwright） |
| **可靠性测试** | `tests/reliability/` | 分布式、并发、熔断、限流 |
| **性能测试** | `tests/performance/` | 基准测试、压力测试 |
| **安全测试** | `tests/security/` | OWASP 漏洞扫描 |
| **混沌测试** | `tests/chaos/` | 网络抖动、故障注入 |
| **冒烟测试** | `tests/smoke/` | 关键路径验证 |

```bash
# 运行所有单元测试
pytest tests/unit -v

# 并行运行（pytest-xdist）
pytest tests/unit -n auto

# 运行带覆盖率
pytest --cov=src --cov-report=html

# 运行冒烟测试
pytest tests/smoke/ -v

# E2E 测试
cd frontend && npx playwright test
```

---

## 十一、部署与可观测性

### 11.1 部署

- **Docker Compose**：单机快速部署（含 Prometheus / Grafana / Redis / RabbitMQ）
- **Kubernetes**：生产级编排（见 [docker/k8s/deployment.yaml](file:///d:/workspace/ai-eval-platform-refactor/docker/k8s/deployment.yaml)）— 支持水平扩展、健康检查、优雅降级
- **CI/CD**：GitHub Actions（[.github/workflows/](file:///d:/workspace/ai-eval-platform-refactor/.github/workflows)）— 自动化测试、构建、部署流水线
- **数据库**：PostgreSQL（生产）/ SQLite（开发），支持 ACID 事务与连接池

### 11.2 监控

- **Prometheus**：[deploy/prometheus/prometheus.yml](file:///d:/workspace/ai-eval-platform-refactor/deploy/prometheus/prometheus.yml)
- **Grafana 仪表盘**：[grafana/dashboards/](file:///d:/workspace/ai-eval-platform-refactor/grafana/dashboards)
- **告警规则**：[deploy/prometheus/alerts.yml](file:///d:/workspace/ai-eval-platform-refactor/deploy/prometheus/alerts.yml)

### 11.3 详细文档

- [ARCHITECTURE.md](file:///d:/workspace/ai-eval-platform-refactor/ARCHITECTURE.md) - 架构设计细节
- [PERFORMANCE_ANALYSIS.md](file:///d:/workspace/ai-eval-platform-refactor/PERFORMANCE_ANALYSIS.md) - 性能分析
- [docs/deployment_guide.md](file:///d:/workspace/ai-eval-platform-refactor/docs/deployment_guide.md) - 部署指南
- [docs/operations_manual.md](file:///d:/workspace/ai-eval-platform-refactor/docs/operations_manual.md) - 运维手册
- [docs/OBSERVABILITY.md](file:///d:/workspace/ai-eval-platform-refactor/docs/OBSERVABILITY.md) - 可观测性
- [docs/enhancement_features_guide.md](file:///d:/workspace/ai-eval-platform-refactor/docs/enhancement_features_guide.md) - 增强功能使用指南（标准指标 / RAGAS / DeepEval / 人工标注 / 可视化）
- [.trae/documents/SYSTEM_MAPPING.md](file:///d:/workspace/ai-eval-platform-refactor/.trae/documents/SYSTEM_MAPPING.md) - 系统功能完备性矩阵

---

## 十二、技术栈

| 组件 | 技术 | 用途 |
|------|------|------|
| **API 框架** | FastAPI 0.104+ | 高性能异步 API |
| **ASGI 服务器** | Uvicorn | 生产级 ASGI |
| **任务队列** | Celery + RabbitMQ | 分布式异步任务 |
| **缓存/锁** | Redis | 分布式锁、限流、缓存 |
| **数据库** | PostgreSQL / SQLite | 结果持久化 |
| **ORM** | SQLAlchemy 2 | 数据库访问 |
| **迁移** | Alembic | 数据库版本管理 |
| **认证** | JWT (python-jose + passlib) | 无状态认证 |
| **前端** | React 18 + TypeScript + Vite | SPA |
| **UI 库** | Ant Design 5 + Tailwind CSS | 组件与样式 |
| **状态管理** | Zustand | 轻量状态 |
| **HTTP 客户端** | Axios | API 调用 |
| **图表** | Recharts | 数据可视化 |
| **测试** | pytest + vitest + playwright | 单元/集成/E2E |
| **指标** | Prometheus + Grafana | 监控 |
| **追踪** | OpenTelemetry | 链路追踪 |
| **容器化** | Docker + Docker Compose | 容器部署 |
| **编排** | Kubernetes | 生产编排 |

---

## 十三、版本信息

- **当前版本**：v2.0.0 (Enterprise Edition)
- **最后更新**：2026-06-29
- **License**：Internal Use Only
- **测试状态**：✅ 838+ 测试用例通过

## 十四、贡献指南

提交代码前请遵循 [.trae/rules/arch_review.md](file:///d:/workspace/ai-eval-platform-refactor/.trae/rules/arch_review.md) 中的规则：

- ✅ 单次修改不超过 2 个核心模块
- ✅ 新增功能保持向后兼容
- ✅ 测试覆盖率 ≥ 80%
- ✅ 新增异常继承 `BasePlatformError`
- ✅ 依赖单向流动，禁止跨层调用
- ✅ 新增评估器通过工厂注册
- ✅ 外部输入经 Pydantic 验证

---

> 💡 **提示**：本 README 提供了项目的高层视角。深入实现请查阅相关模块源码及 [docs/](file:///d:/workspace/ai-eval-platform-refactor/docs) 目录下的专项文档。
