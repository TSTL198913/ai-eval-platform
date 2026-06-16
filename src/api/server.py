from fastapi import FastAPI, Response, status
from fastapi.responses import PlainTextResponse

from src.infra.db.session import init_tables
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
