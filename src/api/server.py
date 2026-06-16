from fastapi import FastAPI, Response, status
from fastapi.responses import HTMLResponse, PlainTextResponse

from src.domain.evaluators import EVALUATOR_REGISTRY
from src.infra.db.repository import EvaluationRepository
from src.infra.db.session import init_tables
from src.infra.monitoring.metrics import expose_metrics
from src.schemas.evaluation import EvaluationSchema
from src.services.evaluator_svc import _normalize_raw_data, run_evaluation_service
from src.workers.celery_app import celery_app
from src.workers.tasks import eval_case_task

app = FastAPI(
    title="AI Eval Platform",
    description="""
# AI 评估平台 API 文档

## 概述

AI 评估平台是一个通用的 AI 模型评估服务，支持多种评估类型，包括文本相似度、金融计算、代码审查、情感分析、分类、翻译等。

## 功能特性

- **同步评估**: 实时获取评估结果
- **异步评估**: 高并发场景下的异步任务处理
- **多评估类型**: 支持 13+ 种评估器类型
- **分布式能力**: Redis 分布式锁、令牌桶限流、熔断器
- **数据持久化**: PostgreSQL 存储所有评估记录
- **监控 Dashboard**: 可视化管理界面

## 评估类型

| 类型 | 描述 |
|------|------|
| text | 文本相似度评估 |
| finance | 金融计算评估 |
| code | 代码质量评估 |
| code_review | 代码审查评估 |
| general | 通用评估 |
| semantic | 语义相似度评估 |
| sentiment | 情感分析评估 |
| classification | 文本分类评估 |
| translation | 翻译质量评估 |
| grammar | 语法检查评估 |
| summary | 摘要质量评估 |
| fact_check | 事实核查评估 |
| qa | 问答质量评估 |

## 快速开始

### 同步评估

```bash
curl -X POST http://localhost:8000/api/v1/evaluate \\
  -H "Content-Type: application/json" \\
  -d '{
    "id": "test_case_001",
    "type": "text",
    "payload": {
      "user_input": "什么是人工智能？",
      "expected_output": "人工智能是模拟人类智能的计算机系统"
    }
  }'
```

### 异步评估

```bash
curl -X POST http://localhost:8000/api/v1/evaluate/async \\
  -H "Content-Type: application/json" \\
  -d '{
    "id": "async_case_001",
    "type": "general",
    "payload": {"user_input": "请分析以下内容"}
  }'
```

### 查询任务状态

```bash
curl http://localhost:8000/api/v1/tasks/{task_id}
```
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# 通过 Repository 访问数据库，保持架构一致性
_repository = EvaluationRepository()


@app.on_event("startup")
async def startup_event():
    init_tables()


@app.get("/health")
async def health_check():
    """健康检查端点"""
    return {"status": "healthy", "service": "ai-eval-platform"}


@app.get("/metrics", response_class=PlainTextResponse)
async def metrics():
    """Prometheus metrics endpoint"""
    return expose_metrics()


@app.post("/api/v1/evaluate")
async def evaluate_endpoint(raw_data: dict, response: Response):
    result = run_evaluation_service(raw_data)

    if result["status"] == "error":
        if result["code"] == "CONTRACT_ERROR":
            response.status_code = status.HTTP_400_BAD_REQUEST
        else:
            response.status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    else:
        response.status_code = status.HTTP_200_OK

    return result


@app.post("/api/v1/evaluate/async")
async def evaluate_async_endpoint(raw_data: dict, response: Response):
    try:
        normalized = _normalize_raw_data(raw_data)
        case = EvaluationSchema(**normalized)
    except Exception as e:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return {"status": "error", "code": "CONTRACT_ERROR", "message": str(e)}

    task = eval_case_task.delay(case.model_dump())
    return {
        "status": "queued",
        "task_id": task.id,
        "case_id": case.id,
    }


@app.get("/api/v1/tasks/{task_id}")
async def get_task_status(task_id: str):
    result = celery_app.AsyncResult(task_id)
    payload = {
        "task_id": task_id,
        "state": result.state,
    }
    if result.ready():
        payload["result"] = result.result
    return payload


# ============================================================================
# 测试接口
# ============================================================================


@app.get("/api/v1/test/echo")
async def test_echo():
    """回显测试 - 验证 API 服务正常运行"""
    return {
        "status": "ok",
        "message": "API 服务运行正常",
        "timestamp": "2024-01-01T00:00:00Z",
    }


@app.get("/api/v1/test/db")
async def test_database():
    """数据库连接测试 - 通过 Repository 访问"""
    try:
        count = _repository.count()
        return {
            "status": "ok",
            "message": "数据库连接正常",
            "record_count": count,
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"数据库连接失败: {str(e)}",
        }


@app.get("/api/v1/records")
async def get_recent_records(limit: int = 10):
    """获取最近的评估记录 - 通过 Repository 访问"""
    try:
        records = _repository.get_recent(limit=limit)
        return {
            "status": "ok",
            "count": len(records),
            "records": records,
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"获取记录失败: {str(e)}",
        }


@app.get("/api/v1/dashboard/stats")
async def get_dashboard_stats():
    """获取 Dashboard 统计数据"""
    try:
        record_count = _repository.count()
        recent_records = _repository.get_recent(limit=5)
        evaluator_types = list(EVALUATOR_REGISTRY.keys())

        status_counts = {}
        for record in recent_records:
            status = record.get("status", "unknown")
            status_counts[status] = status_counts.get(status, 0) + 1

        return {
            "status": "ok",
            "data": {
                "total_records": record_count,
                "evaluator_types": len(evaluator_types),
                "recent_records": recent_records,
                "status_distribution": status_counts,
            },
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"获取统计数据失败: {str(e)}",
        }


@app.get("/", response_class=HTMLResponse)
async def dashboard():
    """监控 Dashboard 界面"""
    stats = await get_dashboard_stats()
    data = stats.get("data", {})

    html = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Eval Platform Dashboard</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; padding: 20px; }}
        .container {{ max-width: 1400px; margin: 0 auto; }}
        .header {{ text-align: center; color: white; margin-bottom: 30px; }}
        .header h1 {{ font-size: 2.5rem; margin-bottom: 10px; }}
        .header p {{ opacity: 0.9; }}
        .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin-bottom: 30px; }}
        .card {{ background: white; border-radius: 12px; padding: 24px; box-shadow: 0 10px 40px rgba(0,0,0,0.1); transition: transform 0.3s; }}
        .card:hover {{ transform: translateY(-5px); }}
        .card-icon {{ font-size: 2.5rem; margin-bottom: 12px; }}
        .card-value {{ font-size: 2rem; font-weight: bold; color: #333; }}
        .card-label {{ color: #666; margin-top: 4px; }}
        .section {{ background: white; border-radius: 12px; padding: 24px; box-shadow: 0 10px 40px rgba(0,0,0,0.1); margin-bottom: 20px; }}
        .section h2 {{ color: #333; margin-bottom: 20px; font-size: 1.3rem; }}
        .table {{ width: 100%; border-collapse: collapse; }}
        .table th, .table td {{ padding: 12px; text-align: left; border-bottom: 1px solid #eee; }}
        .table th {{ background: #f8f9fa; color: #666; font-weight: 600; }}
        .table tr:hover {{ background: #f8f9fa; }}
        .status-badge {{ padding: 4px 12px; border-radius: 20px; font-size: 0.8rem; font-weight: 600; }}
        .status-passed {{ background: #d4edda; color: #155724; }}
        .status-failed {{ background: #f8d7da; color: #721c24; }}
        .status-pending {{ background: #fff3cd; color: #856404; }}
        .status-success {{ background: #d1ecf1; color: #0c5460; }}
        .chart {{ display: flex; gap: 10px; flex-wrap: wrap; }}
        .chart-bar {{ flex: 1; min-width: 80px; background: linear-gradient(180deg, #667eea 0%, #764ba2 100%); border-radius: 8px; padding: 12px; text-align: center; color: white; }}
        .chart-bar-value {{ font-size: 1.5rem; font-weight: bold; }}
        .chart-bar-label {{ font-size: 0.85rem; opacity: 0.9; }}
        .evaluator-tags {{ display: flex; flex-wrap: wrap; gap: 8px; }}
        .evaluator-tag {{ background: #e9ecef; padding: 6px 14px; border-radius: 20px; font-size: 0.85rem; color: #495057; }}
        .evaluator-tag::before {{ content: '✓ '; color: #667eea; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>AI Eval Platform</h1>
            <p>AI 评估平台监控 Dashboard</p>
        </div>

        <div class="cards">
            <div class="card">
                <div class="card-icon">📊</div>
                <div class="card-value">{data.get("total_records", 0)}</div>
                <div class="card-label">总评估记录</div>
            </div>
            <div class="card">
                <div class="card-icon">🧠</div>
                <div class="card-value">{data.get("evaluator_types", 0)}</div>
                <div class="card-label">评估器类型</div>
            </div>
            <div class="card">
                <div class="card-icon">✅</div>
                <div class="card-value">{data.get("status_distribution", {}).get("passed", 0)}</div>
                <div class="card-label">通过记录</div>
            </div>
            <div class="card">
                <div class="card-icon">⏱️</div>
                <div class="card-value">API 运行中</div>
                <div class="card-label">服务状态</div>
            </div>
        </div>

        <div class="section">
            <h2>状态分布</h2>
            <div class="chart">
                {
        "".join(
            f'<div class="chart-bar"><div class="chart-bar-value">{count}</div><div class="chart-bar-label">{status}</div></div>'
            for status, count in data.get("status_distribution", {}).items()
        )
    }
            </div>
        </div>

        <div class="section">
            <h2>已注册评估器</h2>
            <div class="evaluator-tags">
                {
        "".join(f'<span class="evaluator-tag">{e}</span>' for e in EVALUATOR_REGISTRY.keys())
    }
            </div>
        </div>

        <div class="section">
            <h2>最近评估记录</h2>
            <table class="table">
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>Case ID</th>
                        <th>评估器</th>
                        <th>模型</th>
                        <th>状态</th>
                        <th>延迟(ms)</th>
                        <th>时间</th>
                    </tr>
                </thead>
                <tbody>
                    {
        "".join(
            f'''
                    <tr>
                        <td>{r.get('id', '-')}</td>
                        <td>{r.get('case_id', '-')}</td>
                        <td>{r.get('adapter_name', '-')}</td>
                        <td>{r.get('model_name', '-')}</td>
                        <td><span class="status-badge status-{r.get('status', 'unknown').lower()}">{r.get('status', '-')}</span></td>
                        <td>{r.get('latency_ms', '-')}</td>
                        <td>{r.get('created_at', '-')}</td>
                    </tr>
                    '''
            for r in data.get("recent_records", [])
        )
    }
                </tbody>
            </table>
        </div>
    </div>
</body>
</html>
    """
    return HTMLResponse(content=html)
