from typing import AsyncGenerator, Any, Dict
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response, status, Depends
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware

from src.api.auth import (
    authenticate_user,
    create_access_token,
    create_refresh_token,
    get_current_user,
    fake_users_db,
    ACCESS_TOKEN_EXPIRE_MINUTES,
)
from src.domain.evaluators import EVALUATOR_REGISTRY
from src.infra.db.session import init_tables
from src.infra.monitoring.metrics import expose_metrics
from src.schemas.evaluation import EvaluationSchema
from src.services.evaluator_svc import _normalize_raw_data, run_evaluation_service

HAS_AUTH = False


def success_response(data: Any = None, message: str = "success") -> Dict[str, Any]:
    return {"code": 0, "message": message, "data": data}


def error_response(code: int, message: str) -> Dict[str, Any]:
    return {"code": code, "message": message, "data": None}


_repository = None


def _get_repository():
    global _repository
    if _repository is None:
        from src.infra.db.repository import EvaluationRepository
        _repository = EvaluationRepository()
    return _repository


def _get_eval_case_task():
    from src.workers.tasks import eval_case_task
    return eval_case_task


def _get_celery_app():
    from src.workers.celery_app import celery_app
    return celery_app


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_tables()
    yield


app = FastAPI(
    title="AI Eval Platform",
    description="AI Evaluation Platform API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/api/v1/auth/login")
async def login_endpoint(raw_data: dict):
    username = raw_data.get("username")
    password = raw_data.get("password")

    if not HAS_AUTH:
        return success_response(
            {
                "access_token": "demo-token",
                "refresh_token": "demo-refresh-token",
                "token_type": "bearer",
                "expires_in": 3600,
            }
        )

    user = authenticate_user(fake_users_db, username, password)
    if not user:
        return error_response(401, "Invalid username or password")

    access_token = create_access_token(
        data={"sub": user["username"]},
        expires_delta=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
    refresh_token = create_refresh_token(data={"sub": user["username"]})

    return success_response(
        {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        }
    )


@app.post("/api/v1/auth/refresh")
async def refresh_endpoint(raw_data: dict):
    refresh_token = raw_data.get("refresh_token")
    if not refresh_token:
        return error_response(400, "Missing refresh_token")

    if not HAS_AUTH:
        return success_response(
            {
                "access_token": "demo-token",
                "refresh_token": "demo-refresh-token",
                "token_type": "bearer",
                "expires_in": 3600,
            }
        )

    return success_response(
        {
            "access_token": "demo-token",
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": 3600,
        }
    )


@app.get("/health")
async def health_check():
    return success_response({"status": "healthy", "service": "ai-eval-platform"})


@app.get("/metrics", response_class=PlainTextResponse)
async def metrics():
    return expose_metrics()


@app.post("/api/v1/evaluate")
async def evaluate_endpoint(raw_data: dict, response: Response):
    result = run_evaluation_service(raw_data)

    if result["status"] == "error":
        if result["code"] == "CONTRACT_ERROR":
            response.status_code = status.HTTP_400_BAD_REQUEST
        else:
            response.status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
        return error_response(result.get("code", 400), result.get("message", "Evaluation failed"))
    else:
        response.status_code = status.HTTP_200_OK
        return success_response(result)


@app.post("/api/v1/evaluate/async")
async def evaluate_async_endpoint(raw_data: dict, response: Response):
    try:
        normalized = _normalize_raw_data(raw_data)
        case = EvaluationSchema(**normalized)
    except Exception as e:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return error_response(400, str(e))

    eval_case_task = _get_eval_case_task()
    task = eval_case_task.delay(case.model_dump())
    return success_response(
        {
            "task_id": task.id,
            "case_id": case.id,
            "status": "queued",
        }
    )


@app.get("/api/v1/tasks/{task_id}")
async def get_task_status(task_id: str):
    celery_app = _get_celery_app()
    result = celery_app.AsyncResult(task_id)
    payload = {
        "task_id": task_id,
        "state": result.state,
    }
    if result.ready():
        payload["result"] = result.result
    return success_response(payload)


@app.get("/api/v1/test/echo")
async def test_echo():
    return success_response({"message": "API service running", "timestamp": "2024-01-01T00:00:00Z"})


@app.get("/api/v1/test/db")
async def test_database():
    try:
        repo = _get_repository()
        count = repo.count()
        return success_response({"message": "Database connection OK", "record_count": count})
    except Exception as e:
        return error_response(500, f"Database connection failed: {str(e)}")


@app.get("/api/v1/records")
async def get_recent_records(limit: int = 10):
    try:
        repo = _get_repository()
        records = repo.get_recent(limit=limit)
        return success_response({"count": len(records), "records": records})
    except Exception as e:
        return error_response(500, f"Failed to get records: {str(e)}")


@app.get("/api/v1/records/search")
async def search_records(
    evaluator: str | None = None,
    status: str | None = None,
    limit: int = 10,
):
    try:
        repo = _get_repository()
        records = repo.search(evaluator=evaluator, status=status, limit=limit)
        return success_response({
            "count": len(records),
            "filters": {
                "evaluator": evaluator,
                "status": status,
                "limit": limit,
            },
            "records": records,
        })
    except Exception as e:
        return error_response(500, f"Search failed: {str(e)}")


@app.get("/api/v1/evaluators")
async def get_all_evaluators():
    evaluators = []
    for name, cls in EVALUATOR_REGISTRY.items():
        evaluators.append({
            "name": name,
            "class_name": cls.__name__,
            "docstring": cls.__doc__ or "No description",
            "module": cls.__module__,
        })
    return success_response(evaluators)


@app.get("/api/v1/evaluators/{name}")
async def get_evaluator_detail(name: str):
    try:
        from src.domain.evaluators.evaluator_factory import EvaluatorFactory

        if name not in EVALUATOR_REGISTRY:
            return error_response(404, f"Evaluator '{name}' not found")

        evaluator_cls = EVALUATOR_REGISTRY[name]
        return success_response({
            "name": name,
            "class_name": evaluator_cls.__name__,
            "docstring": evaluator_cls.__doc__ or "No description",
            "module": evaluator_cls.__module__,
        })
    except Exception as e:
        return error_response(500, f"Failed to get evaluator info: {str(e)}")


@app.post("/api/v1/evaluate/batch")
async def evaluate_batch_endpoint(batch_data: dict, response: Response):
    try:
        cases = batch_data.get("cases", [])
        if not cases:
            response.status_code = status.HTTP_400_BAD_REQUEST
            return error_response(400, "Batch evaluation requires cases array")

        results = []
        eval_case_task = _get_eval_case_task()

        for case_data in cases:
            try:
                normalized = _normalize_raw_data(case_data)
                case = EvaluationSchema(**normalized)
                task = eval_case_task.delay(case.model_dump())
                results.append(
                    {
                        "case_id": case.id,
                        "task_id": task.id,
                        "status": "queued",
                    }
                )
            except Exception as e:
                results.append(
                    {
                        "case_id": case_data.get("id", "unknown"),
                        "status": "error",
                        "message": str(e),
                    }
                )

        return success_response({
            "total": len(cases),
            "queued": sum(1 for r in results if r.get("status") == "queued"),
            "failed": sum(1 for r in results if r.get("status") == "error"),
            "results": results,
        })
    except Exception as e:
        response.status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
        return error_response(422, f"Batch evaluation failed: {str(e)}")


@app.get("/api/v1/dashboard/stats")
async def get_dashboard_stats():
    try:
        repo = _get_repository()
        record_count = repo.count()
        recent_records = repo.get_recent(limit=5)
        evaluator_types = list(EVALUATOR_REGISTRY.keys())

        status_counts = {}
        for record in recent_records:
            status = record.get("status", "unknown")
            status_counts[status] = status_counts.get(status, 0) + 1

        return success_response({
            "total_records": record_count,
            "evaluator_types": len(evaluator_types),
            "recent_records": recent_records,
            "status_distribution": status_counts,
        })
    except Exception as e:
        return error_response(500, f"Failed to get stats: {str(e)}")


@app.get("/")
async def root():
    return success_response({"message": "AI Eval Platform API", "version": "1.0.0"})


@app.get("/api/v1/reports")
async def get_reports():
    """获取报告列表"""
    try:
        import os
        report_dir = "reports"
        if os.path.exists(report_dir):
            reports = []
            for filename in sorted(os.listdir(report_dir)):
                if filename.endswith(".html"):
                    filepath = os.path.join(report_dir, filename)
                    reports.append({
                        "filename": filename,
                        "path": f"/api/v1/reports/{filename}",
                        "size": os.path.getsize(filepath),
                        "created_at": os.path.getmtime(filepath),
                    })
            return success_response({"reports": reports})
        return success_response({"reports": []})
    except Exception as e:
        return error_response(500, f"Failed to get reports: {str(e)}")


@app.get("/api/v1/reports/{filename}")
async def get_report(filename: str):
    """获取单个报告"""
    try:
        import os
        from fastapi.responses import FileResponse
        filepath = os.path.join("reports", filename)
        if os.path.exists(filepath):
            return FileResponse(filepath)
        return error_response(404, f"Report '{filename}' not found")
    except Exception as e:
        return error_response(500, f"Failed to get report: {str(e)}")


@app.post("/api/v1/reports/generate")
async def generate_report_endpoint(filter_params: dict = None):
    """生成评测报告"""
    try:
        from src.domain.reports.report_generator import generate_report_from_records

        repo = _get_repository()
        if filter_params:
            records = repo.search(**filter_params)
        else:
            records = repo.get_recent(limit=100)

        report_path = generate_report_from_records(records)
        return success_response({
            "message": "Report generated successfully",
            "path": report_path,
            "url": f"/api/v1/reports/{os.path.basename(report_path)}",
        })
    except Exception as e:
        return error_response(500, f"Failed to generate report: {str(e)}")


@app.get("/api/v1/datasets")
async def get_datasets():
    """获取可用的评测数据集"""
    try:
        from src.domain.benchmarks.standard_datasets import DatasetManager

        datasets = DatasetManager.list_datasets()
        stats = DatasetManager.get_all_stats()
        return success_response({
            "datasets": datasets,
            "stats": stats,
        })
    except Exception as e:
        return error_response(500, f"Failed to get datasets: {str(e)}")


@app.get("/api/v1/datasets/{dataset_name}")
async def get_dataset_details(dataset_name: str):
    """获取数据集详情"""
    try:
        from src.domain.benchmarks.standard_datasets import DatasetManager, BenchmarkDataset

        ds_type = BenchmarkDataset(dataset_name)
        ds = DatasetManager.get_dataset(ds_type)
        data = ds.load()
        stats = ds.get_stats()

        return success_response({
            "name": dataset_name,
            "stats": stats,
            "sample_count": len(data),
            "sample": data[0] if data else None,
        })
    except ValueError:
        return error_response(404, f"Dataset '{dataset_name}' not found")
    except Exception as e:
        return error_response(500, f"Failed to get dataset: {str(e)}")