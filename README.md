# AI Eval Platform

分布式 AI 评测平台：FastAPI + Celery + Redis + PostgreSQL + RabbitMQ。

## 一键启动 (Docker Compose)

```bash
# 1. 复制配置
copy .env.example .env
# 编辑 .env 填入你的 LLM API Key

# 2. 启动所有服务
docker compose up -d --build

# 3. 初始化数据库
docker compose exec api python -c "from src.infra.db.session import init_tables; init_tables()"

# 4. 查看服务状态
docker compose ps
```

## 服务地址

| 服务 | 地址 | 说明 |
|------|------|------|
| API | http://localhost:8000 | FastAPI 服务 |
| API Docs | http://localhost:8000/docs | Swagger 文档 |
| RabbitMQ | http://localhost:15672 | Management UI (guest/guest) |
| Prometheus | http://localhost:9090 | 监控 (可选) |
| Grafana | http://localhost:3000 | 监控面板 (可选) |

## 便捷命令 (Makefile)

```bash
make up         # 启动所有服务
make down       # 停止所有服务
make logs       # 查看日志
make ps         # 查看状态
make test       # 运行测试
make monitoring # 启动监控组件
```

## 架构

```
┌─────────────────────────────────────────────────────────────┐
│                     Docker Compose                           │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│   ┌─────────┐    ┌─────────────┐    ┌─────────────────┐     │
│   │  API    │───▶│  RabbitMQ   │───▶│  Celery Worker  │     │
│   │ FastAPI │    │  消息队列    │    │  任务处理器     │     │
│   └─────────┘    └─────────────┘    └────────┬────────┘     │
│        │                                      │              │
│        ▼                                      ▼              │
│   ┌─────────┐                         ┌─────────────────┐     │
│   │ 限流器  │                         │  PostgreSQL     │     │
│   │ 熔断器  │                         │  结果持久化      │     │
│   └─────────┘                         └─────────────────┘     │
│        │                                      │              │
│        └──────────────┬───────────────────────┘              │
│                       ▼                                      │
│                  ┌─────────┐                                 │
│                  │  Redis  │                                 │
│                  │分布式锁  │                                 │
│                  └─────────┘                                 │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## 本地开发与测试

```bash
pip install -r requirements.txt
set TESTING=1

# 快速套件（跳过 slow / redis）
pytest tests/ -v

# 覆盖率报告（门禁 ≥70%）
pytest tests/ -m "not slow and not redis" --cov=src --cov-report=term-missing --cov-fail-under=70

# 全量压测
pytest tests/ --run-slow -v

# Redis 真异步集成（需 Redis + Worker）
set REDIS_URL=redis://localhost:6379/0
celery -A src.workers.celery_app worker --loglevel=warning &
pytest tests/integration/test_celery_redis.py -v -m redis
```

## CI

GitHub Actions 流水线（`.github/workflows/ci.yml`）：

- **lint-and-test**：Ruff + pytest + 覆盖率门禁（70%）
- **redis-integration**：Redis 服务 + Celery Worker + 真异步用例

本地等价检查：

```bash
ruff check src tests
pytest tests/ -m "not slow and not redis" --cov=src --cov-fail-under=70 -q
```

## API 示例

同步评测：

```bash
curl -X POST http://localhost:8000/api/v1/evaluate ^
  -H "Content-Type: application/json" ^
  -d "{\"id\":\"case_001\",\"type\":\"text\",\"payload\":{\"user_input\":\"什么是机器学习\",\"expected_output\":\"机器学习\"}}"
```

异步评测：

```bash
curl -X POST http://localhost:8000/api/v1/evaluate/async ^
  -H "Content-Type: application/json" ^
  -d "{\"id\":\"case_002\",\"type\":\"code\",\"payload\":{\"code\":\"def add(a,b): return a+b\",\"expected_output\":\"语法正确\"}}"
```

## 压测与报告

```bash
set STRESS_TOTAL_TASKS=200
python script/stress_test_launcher.py
```

报告输出：`reports/stress_report.json`

性能基准测试（pytest）：

```bash
pytest tests/e2e/test_performance_bench.py -v -s
```

报告输出：`reports/performance_report.json`

## 环境变量

| 变量 | 说明 |
|------|------|
| `DEEPSEEK_API_KEY` | DeepSeek API Key，未设置时使用 Stub 客户端 |
| `DEEPSEEK_MODEL` | 模型名，默认 `deepseek-chat` |
| `DATABASE_URL` | 数据库连接串 |
| `STRESS_TOTAL_TASKS` | 压测任务数，默认 100 |
| `TESTING=1` | 测试模式，使用 SQLite |

## 架构

```
Client -> FastAPI -> EvaluationEngine -> Evaluator -> LLM
                    -> Celery Worker  -> PostgreSQL
```

支持的评测类型：`finance` / `text` / `code` / `code_review` / `general`
