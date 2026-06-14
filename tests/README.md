# 测试说明

## 分层

| 目录 | 职责 |
|------|------|
| `tests/unit/` | 单模块，Mock 外部依赖 |
| `tests/domain/` | Evaluator 领域逻辑 |
| `tests/integration/` | Engine / Worker / Repository |
| `tests/contract/` | OpenAPI + Pydantic 契约 |
| `tests/e2e/` | 全链路服务级 |

## 运行

```bash
set TESTING=1

# 默认：跳过 slow
pytest tests/ -v

# 覆盖率（与 CI 一致）
pytest tests/ -m "not slow and not redis" --cov=src --cov-report=html:reports/coverage_html --cov-fail-under=70

# 全量 prod 压测
pytest tests/ --run-slow -v

# 契约测试
pytest tests/contract/ -v -m contract

# Redis 真异步（需 REDIS_URL + Worker）
set REDIS_URL=redis://localhost:6379/0
pytest tests/integration/test_celery_redis.py -m redis -v
```

## 标记

| 标记 | 含义 |
|------|------|
| `slow` | 全量 prod 数据集，默认跳过 |
| `redis` | 真 Celery broker，本地需 Redis |
| `contract` | API/Schema 契约 |

## 约定

- 使用 `conftest.mock_llm`，禁止依赖真实 LLM API
- 持久化测试使用全局 `SessionLocal`（SQLite StaticPool）
- 断言业务语义，禁止仅 `assert is not None`
