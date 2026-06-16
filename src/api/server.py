from fastapi import FastAPI, Response, status
from fastapi.responses import PlainTextResponse

from src.infra.db.repository import EvaluationRepository
from src.infra.db.session import get_db_session, init_tables
from src.infra.monitoring.metrics import expose_metrics
from src.schemas.evaluation import EvaluationSchema
from src.services.evaluator_svc import _normalize_raw_data, run_evaluation_service
from src.workers.celery_app import celery_app
from src.workers.tasks import eval_case_task

app = FastAPI(title="AI Eval Platform")


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
    """数据库连接测试"""
    try:
        with get_db_session() as session:
            result = session.execute(
                "SELECT COUNT(*) as count FROM eval_results"
            ).fetchone()
            return {
                "status": "ok",
                "message": "数据库连接正常",
                "record_count": result[0] if result else 0,
            }
    except Exception as e:
        return {
            "status": "error",
            "message": f"数据库连接失败: {str(e)}",
        }


@app.get("/api/v1/records")
async def get_recent_records(limit: int = 10):
    """获取最近的评估记录"""
    try:
        with get_db_session() as session:
            result = session.execute(
                f"SELECT id, case_id, model_name, adapter_name, status, "
                f"latency_ms, created_at FROM eval_results "
                f"ORDER BY created_at DESC LIMIT {limit}"
            ).fetchall()

            records = [
                {
                    "id": row[0],
                    "case_id": row[1],
                    "model_name": row[2],
                    "adapter_name": row[3],
                    "status": row[4],
                    "latency_ms": row[5],
                    "created_at": row[6].isoformat() if row[6] else None,
                }
                for row in result
            ]

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
