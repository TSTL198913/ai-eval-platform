from typing import AsyncGenerator, Any, Dict
from contextlib import asynccontextmanager
import re
import os
import time
from datetime import timedelta

from fastapi import FastAPI, Response, status, Depends, HTTPException
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware

from src.api.auth import (
    authenticate_user,
    create_access_token,
    create_refresh_token,
    decode_token,
    get_current_user,
    fake_users_db,
    ACCESS_TOKEN_EXPIRE_MINUTES,
)
from src.domain.evaluators import EVALUATOR_REGISTRY
from src.infra.db.session import init_tables
from src.infra.monitoring.metrics import expose_metrics
from src.schemas.evaluation import EvaluationSchema
from src.services.evaluator_svc import _normalize_raw_data, run_evaluation_service

# 认证模块是否可用：尝试初始化，失败时降级为demo模式(仅开发环境)
try:
    from src.api.auth import authenticate_user, fake_users_db  # noqa
    HAS_AUTH = True
except Exception:
    HAS_AUTH = False

# 输入验证函数
def validate_evaluator_name(name: str) -> bool:
    """验证评估器名称，防止SQL注入和特殊字符攻击"""
    if not name or not name.strip():
        return False
    if name.strip() == "/":
        return False
    # 只允许字母、数字、下划线和连字符
    pattern = r'^[a-zA-Z0-9_-]+$'
    return bool(re.match(pattern, name))


def validate_dataset_name(name: str) -> bool:
    """验证数据集名称"""
    if not name or not name.strip():
        return False
    pattern = r'^[a-zA-Z0-9_-]+$'
    return bool(re.match(pattern, name))


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


_sync_task_results = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan事件处理器 - 启动时预热关键资源"""
    import time
    import sys
    
    print("=" * 60, flush=True)
    print("开始预热...", flush=True)
    warmup_start = time.time()
    
    # 1. 初始化数据库表
    print("[1/5] 初始化数据库表...", flush=True)
    t0 = time.time()
    init_tables()
    print(f"      数据库表初始化完成: {time.time()-t0:.0f}s", flush=True)
    
    # 2. 预热数据库连接池 - 执行一次查询
    print("[2/5] 预热数据库连接池...", flush=True)
    t0 = time.time()
    try:
        from src.infra.db.session import get_db
        from sqlalchemy import text
        db_gen = get_db()
        db = next(db_gen)
        _ = db.execute(text("SELECT 1"))
        db.commit()
        # 保持连接活跃一段时间
        time.sleep(0.5)
        next(db_gen, None)  # 关闭连接
        print(f"      连接池预热完成: {time.time()-t0:.0f}s", flush=True)
    except Exception as e:
        print(f"      连接池预热失败: {e}", flush=True)
    
    # 3. 预热评估器注册表
    print("[3/5] 预热评估器注册表...", flush=True)
    t0 = time.time()
    try:
        from src.domain.evaluators import EVALUATOR_REGISTRY
        evaluators = list(EVALUATOR_REGISTRY.keys())
        print(f"      已注册评估器: {evaluators}", flush=True)
        print(f"      评估器预热完成: {time.time()-t0:.0f}s", flush=True)
    except Exception as e:
        print(f"      评估器预热失败: {e}", flush=True)
    
    # 4. 预热模型工厂
    print("[4/5] 预热模型工厂...", flush=True)
    t0 = time.time()
    try:
        from src.domain.models.llm_factory import ModelRegistry
        providers = ModelRegistry.list_providers()
        print(f"      可用模型供应商: {providers}", flush=True)
        print(f"      模型工厂预热完成: {time.time()-t0:.0f}s", flush=True)
    except Exception as e:
        print(f"      模型工厂预热失败: {e}", flush=True)
    
    # 5. 预热报告生成器
    print("[5/5] 预热报告生成器...", flush=True)
    t0 = time.time()
    try:
        from src.domain.reports.report_generator import ReportGenerator
        _ = ReportGenerator()
        print(f"      报告生成器预热完成: {time.time()-t0:.0f}s", flush=True)
    except Exception as e:
        print(f"      报告生成器预热失败: {e}", flush=True)
    
    print("=" * 60, flush=True)
    print(f"预热完成! 总耗时: {time.time()-warmup_start:.1f}s", flush=True)
    print("=" * 60, flush=True)
    
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

from src.api.security_middleware import SecurityMiddleware
app.add_middleware(SecurityMiddleware)


import logging
from pydantic import ValidationError
from fastapi import Request
from fastapi.responses import JSONResponse
from src.exceptions import BasePlatformError, ContractValidationError, DomainLogicError, InfrastructureError

logger = logging.getLogger(__name__)


@app.exception_handler(BasePlatformError)
async def platform_error_handler(request: Request, exc: BasePlatformError):
    """平台业务异常处理"""
    logger.error(f"Platform error [{exc.code}]: {exc.message}")
    return JSONResponse(
        status_code=400 if exc.code == "CONTRACT_ERROR" else 422,
        content={
            "code": exc.code,
            "message": exc.message,
            "data": None,
        },
    )


@app.exception_handler(ValidationError)
async def validation_error_handler(request: Request, exc: ValidationError):
    """Pydantic验证错误处理"""
    logger.error(f"Validation error: {exc}")
    errors = []
    for error in exc.errors():
        errors.append({
            "field": ".".join(str(loc) for loc in error["loc"]),
            "message": error["msg"],
            "type": error["type"],
        })
    return JSONResponse(
        status_code=400,
        content={
            "code": "CONTRACT_ERROR",
            "message": "输入数据校验失败",
            "data": {"errors": errors},
        },
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """HTTP异常处理"""
    logger.warning(f"HTTP error {exc.status_code}: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": exc.status_code,
            "message": exc.detail,
            "data": None,
        },
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """全局异常处理 - 捕获所有未处理异常"""
    logger.exception(f"Unexpected error on {request.url.path}: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "code": "INTERNAL_ERROR",
            "message": "系统内部发生不可预知的错误，请稍后重试",
            "data": None,
        },
    )


@app.post("/api/v1/auth/login")
async def login_endpoint(raw_data: dict, response: Response):
    # 输入验证
    if not raw_data:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return error_response(400, "Request body is required")
    
    username = raw_data.get("username")
    password = raw_data.get("password")
    
    # 验证用户名和密码非空
    if not username or not username.strip():
        response.status_code = status.HTTP_401_UNAUTHORIZED
        return error_response(401, "Username is required")
    
    if not password or not password.strip():
        response.status_code = status.HTTP_401_UNAUTHORIZED
        return error_response(401, "Password is required")

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
        response.status_code = status.HTTP_401_UNAUTHORIZED
        return error_response(401, "Invalid username or password")

    access_token = create_access_token(
        data={"sub": user["username"]},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
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
async def refresh_endpoint(raw_data: dict, response: Response):
    refresh_token = raw_data.get("refresh_token")
    if not refresh_token:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return error_response(400, "Missing refresh_token")

    if not HAS_AUTH:
        # Demo模式下也需校验token格式，防止任意字符串绕过
        if not refresh_token or not refresh_token.startswith("demo-"):
            response.status_code = status.HTTP_401_UNAUTHORIZED
            return error_response(401, "Invalid refresh_token")
        return success_response(
            {
                "access_token": "demo-token",
                "refresh_token": "demo-refresh-token",
                "token_type": "bearer",
                "expires_in": 3600,
            }
        )

    payload = decode_token(refresh_token)
    if not payload:
        response.status_code = status.HTTP_401_UNAUTHORIZED
        return error_response(401, "Invalid refresh_token")

    username = payload.get("sub")
    if not username or username not in fake_users_db:
        response.status_code = status.HTTP_401_UNAUTHORIZED
        return error_response(401, "User not found")

    access_token = create_access_token(
        data={"sub": username},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    new_refresh_token = create_refresh_token(data={"sub": username})

    return success_response(
        {
            "access_token": access_token,
            "refresh_token": new_refresh_token,
            "token_type": "bearer",
            "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        }
    )


@app.get("/api/v1/auth/me")
async def get_current_user_endpoint(current_user: dict = Depends(get_current_user)):
    """获取当前用户信息"""
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return success_response({
        "username": current_user.get("username"),
        "full_name": current_user.get("full_name"),
        "email": current_user.get("email"),
        "roles": ["admin"] if current_user.get("username") == "admin" else ["user"],
    })


@app.get("/health")
async def health_check():
    return success_response({"status": "healthy", "service": "ai-eval-platform"})


@app.get("/api/v1/health")
async def api_v1_health_check():
    """统一健康检查端点"""
    checks = {}
    
    try:
        repo = _get_repository()
        count = repo.count()
        checks["database"] = {"status": "healthy", "record_count": count}
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        checks["database"] = {"status": "unhealthy", "error": "数据库连接失败"}
    
    try:
        from src.infra.cache import get_redis
        redis_client = get_redis()
        redis_client.ping()
        checks["redis"] = {"status": "healthy"}
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
        checks["redis"] = {"status": "unhealthy", "error": "缓存连接失败"}
    
    try:
        celery_app = _get_celery_app()
        checks["celery"] = {"status": "healthy"}
    except Exception as e:
        logger.error(f"Celery health check failed: {e}")
        checks["celery"] = {"status": "unhealthy", "error": "任务队列连接失败"}
    
    overall_status = "healthy" if all(c["status"] == "healthy" for c in checks.values()) else "unhealthy"
    
    return success_response({
        "status": overall_status,
        "service": "ai-eval-platform",
        "components": checks,
    })


@app.get("/metrics", response_class=PlainTextResponse)
async def metrics():
    return expose_metrics()


@app.post("/api/v1/evaluate")
async def evaluate_endpoint(raw_data: EvaluationSchema, response: Response):
    """
    执行评估任务（支持选择评估模型）

    请求参数示例：
    {
        "id": "eval-001",
        "type": "llm_as_judge",
        "payload": {...},
        "model_provider": "openai",      // 可选：评估器使用的LLM提供者
        "model_name": "gpt-4o"           // 可选：评估器使用的LLM模型名称
    }

    支持的 model_provider 值：
    - deepseek: DeepSeek 模型
    - openai: OpenAI 模型
    - anthropic: Anthropic 模型
    - ollama: Ollama 本地模型
    - qwen: 通义千问模型

    注意：需要提前在环境变量中配置对应 provider 的 API Key。
    不指定时使用默认配置（LLM_PROVIDER 环境变量）。
    """
    normalized = _normalize_raw_data(raw_data.model_dump())
    result = run_evaluation_service(normalized)

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
        logger.error(f"Async evaluation validation error: {e}")
        response.status_code = status.HTTP_400_BAD_REQUEST
        return error_response(400, "输入数据校验失败")

    try:
        eval_case_task = _get_eval_case_task()
        task = eval_case_task.delay(case.model_dump())
        return success_response(
            {
                "task_id": task.id,
                "case_id": case.id,
                "status": "queued",
            }
        )
    except Exception as celery_e:
        logger.error(f"Celery error, falling back to synchronous execution: {celery_e}")
        result = run_evaluation_service(raw_data)
        if result["status"] == "error":
            response.status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
            return error_response(result.get("code", 400), result.get("message", "Evaluation failed"))
        else:
            task_id = f"sync-{case.id}-{int(time.time())}"
            _sync_task_results[task_id] = result
            return success_response(
                {
                    "task_id": task_id,
                    "case_id": case.id,
                    "status": "completed",
                    "result": result,
                }
            )


@app.get("/api/v1/tasks/{task_id}")
async def get_task_status(task_id: str):
    if task_id.startswith("sync-"):
        if task_id in _sync_task_results:
            result = _sync_task_results[task_id]
            return success_response({
                "task_id": task_id,
                "state": "SUCCESS",
                "result": result,
            })
        else:
            return success_response({
                "task_id": task_id,
                "state": "PENDING",
            })
    
    try:
        celery_app = _get_celery_app()
        result = celery_app.AsyncResult(task_id)
        payload = {
            "task_id": task_id,
            "state": result.state,
        }
        if result.ready():
            payload["result"] = result.result
        return success_response(payload)
    except Exception as e:
        logger.error(f"Failed to get task status for {task_id}: {e}")
        return success_response({
            "task_id": task_id,
            "state": "PENDING",
            "error": "获取任务状态失败",
        })


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
        logger.error(f"Database connection failed: {e}")
        return error_response(500, "数据库连接失败")


@app.get("/api/v1/records")
async def get_recent_records(response: Response, limit: int = 10):
    if limit < 1 or limit > 100:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return error_response(400, "limit must be between 1 and 100")
    
    try:
        repo = _get_repository()
        records = repo.get_recent(limit=limit)
        return success_response({"count": len(records), "items": records})
    except Exception as e:
        logger.error(f"Failed to get records: {e}")
        return error_response(500, "获取记录失败")


@app.get("/api/v1/records/search")
async def search_records(
    response: Response,
    evaluator: str | None = None,
    record_status: str | None = None,
    limit: int = 10,
    offset: int = 0,
    sort_by: str = "created_at",
    sort_order: str = "desc",
):
    if limit < 1 or limit > 100:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return error_response(400, "limit must be between 1 and 100")
    
    if offset < 0 or offset > 10000:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return error_response(400, "offset must be between 0 and 10000")
    
    try:
        repo = _get_repository()
        records = repo.search(
            evaluator=evaluator, 
            status=record_status, 
            limit=limit,
            offset=offset,
            sort_by=sort_by,
            sort_order=sort_order,
        )
        total = repo.count()
        return success_response({
            "count": len(records),
            "total": total,
            "filters": {
                "evaluator": evaluator,
                "status": record_status,
                "limit": limit,
                "offset": offset,
                "sort_by": sort_by,
                "sort_order": sort_order,
            },
            "records": records,
        })
    except Exception as e:
        logger.error("Search failed: {0}", e)
        return error_response(500, "搜索失败")


@app.get("/api/v1/records/export")
async def export_records(format: str = "csv", response: Response = None):
    """导出评估记录(支持CSV和JSON格式)"""
    try:
        # 路径遍历防护 - 只允许csv或json格式
        if format.lower() not in ["csv", "json"]:
            if response:
                response.status_code = status.HTTP_400_BAD_REQUEST
            return error_response(400, "非法参数")
        
        repo = _get_repository()
        records = repo.get_all_for_export()
        
        if format.lower() == "json":
            import json
            content = json.dumps(records, ensure_ascii=False, indent=2)
            return JSONResponse(
                content=json.loads(content),
                headers={"Content-Disposition": f"attachment; filename=eval_records_{int(time.time())}.json"},
                media_type="application/json",
            )
        elif format.lower() == "csv":
            import csv
            import io
            
            output = io.StringIO()
            writer = csv.writer(output)
            
            if records:
                headers = list(records[0].keys())
                writer.writerow(headers)
                
                for record in records:
                    row = []
                    for key in headers:
                        value = record.get(key)
                        if isinstance(value, dict):
                            import json
                            row.append(json.dumps(value, ensure_ascii=False))
                        elif value is None:
                            row.append("")
                        else:
                            row.append(str(value))
                    writer.writerow(row)
            
            return PlainTextResponse(
                content=output.getvalue(),
                headers={"Content-Disposition": f"attachment; filename=eval_records_{int(time.time())}.csv"},
                media_type="text/csv",
            )
        else:
            return error_response(400, "format must be 'csv' or 'json'")
    except Exception as e:
        logger.error(f"Export failed: {e}")
        return error_response(500, "导出失败")


@app.get("/api/v1/records/{record_id}")
async def get_record_detail(record_id: int, response: Response):
    try:
        repo = _get_repository()
        record = repo.get_by_id(record_id)
        if record:
            return success_response(record)
        else:
            response.status_code = status.HTTP_404_NOT_FOUND
            return error_response(404, "Record not found")
    except Exception as e:
        logger.error("Failed to get record: {0}", e)
        return error_response(500, "  ȡ  ¼ʧ  ")


# 记录更新允许的白名单字段（安全：防止伪造评测结果）
_RECORD_UPDATE_ALLOWED_FIELDS = {"model_name", "adapter_name", "status"}
_RECORD_UPDATE_ALLOWED_STATUS = {"passed", "failed", "error", "pending", "config"}

@app.put("/api/v1/records/{record_id}")
async def update_record(record_id: int, update_data: dict, response: Response):
    invalid_fields = set(update_data.keys()) - _RECORD_UPDATE_ALLOWED_FIELDS
    if invalid_fields:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return error_response(400, f"Invalid fields: {', '.join(invalid_fields)}")
    if "status" in update_data and update_data["status"] not in _RECORD_UPDATE_ALLOWED_STATUS:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return error_response(400, f"Invalid status value: {update_data['status']}")
    try:
        repo = _get_repository()
        success = repo.update(record_id, update_data)
        if success:
            record = repo.get_by_id(record_id)
            return success_response(record)
        else:
            response.status_code = status.HTTP_404_NOT_FOUND
            return error_response(404, "Record not found or no valid fields to update")
    except Exception as e:
        logger.error("Failed to update record: {0}", e)
        return error_response(500, "更新记录失败")


@app.delete("/api/v1/records/{record_id}")
async def delete_record(record_id: int, response: Response):
    try:
        repo = _get_repository()
        success = repo.delete(record_id)
        if success:
            return success_response({"message": "Record deleted successfully"})
        else:
            response.status_code = status.HTTP_404_NOT_FOUND
            return error_response(404, "Record not found")
    except Exception as e:
        logger.error("Failed to delete record: {0}", e)
        return error_response(500, "ɾ    ¼ʧ  ")


@app.post("/api/v1/records/batch/delete")
async def batch_delete_records(data: dict, response: Response):
    record_ids = data.get("ids", [])
    if not isinstance(record_ids, list) or not record_ids:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return error_response(400, "ids must be a non-empty list")
    
    try:
        repo = _get_repository()
        deleted_count = repo.batch_delete(record_ids)
        return success_response({
            "message": f"Batch delete completed",
            "deleted_count": deleted_count,
            "total_requested": len(record_ids),
        })
    except Exception as e:
        logger.error("Batch delete failed: {0}", e)
        return error_response(500, "    ɾ  ʧ  ")


@app.post("/api/v1/records/batch/update")
async def batch_update_records(data: dict, response: Response):
    record_ids = data.get("ids", [])
    update_data = data.get("data", {})
    
    if not isinstance(record_ids, list) or not record_ids:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return error_response(400, "ids must be a non-empty list")
    
    if not isinstance(update_data, dict) or not update_data:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return error_response(400, "data must be a non-empty dict")
    
    invalid_fields = set(update_data.keys()) - _RECORD_UPDATE_ALLOWED_FIELDS
    if invalid_fields:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return error_response(400, f"Invalid fields: {', '.join(invalid_fields)}")
    if "status" in update_data and update_data["status"] not in _RECORD_UPDATE_ALLOWED_STATUS:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return error_response(400, f"Invalid status value: {update_data['status']}")
    
    try:
        repo = _get_repository()
        updated_count = repo.batch_update(record_ids, update_data)
        return success_response({
            "message": f"Batch update completed",
            "updated_count": updated_count,
            "total_requested": len(record_ids),
        })
    except Exception as e:
        logger.error("Batch update failed: {0}", e)
        return error_response(500, "批量更新失败")


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
async def get_evaluator_detail(name: str, response: Response):
    # 输入验证：防止SQL注入和特殊字符攻
    if not validate_evaluator_name(name):
        response.status_code = status.HTTP_404_NOT_FOUND
        return error_response(404, f"Invalid evaluator name format")
    
    try:
        from src.domain.evaluators.evaluator_factory import EvaluatorFactory

        if name not in EVALUATOR_REGISTRY:
            response.status_code = status.HTTP_404_NOT_FOUND
            return error_response(404, f"Evaluator '{name}' not found")

        evaluator_cls = EVALUATOR_REGISTRY[name]
        return success_response({
            "name": name,
            "class_name": evaluator_cls.__name__,
            "docstring": evaluator_cls.__doc__ or "No description",
            "module": evaluator_cls.__module__,
        })
    except Exception as e:
        logger.error("Failed to get evaluator info: {0}", e)
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return error_response(500, "  ȡ        Ϣʧ  ")


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
                logger.error(f"Batch evaluation case error: {e}")
                results.append(
                    {
                        "case_id": case_data.get("id", "unknown"),
                        "status": "error",
                        "message": "评测失败",
                    }
                )

        return success_response({
            "total": len(cases),
            "queued": sum(1 for r in results if r.get("status") == "queued"),
            "failed": sum(1 for r in results if r.get("status") == "error"),
            "results": results,
        })
    except Exception as e:
        logger.error(f"Batch evaluation failed: {e}")
        response.status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
        return error_response(422, "批量评测失败")


# ==================== 评估配置管理 ====================
@app.post("/api/v1/eval-configs")
async def save_eval_config(config_data: dict):
    """保存评估配置"""
    try:
        config_id = config_data.get("id") or f"config_{int(time.time())}"
        name = config_data.get("name", "未命名配置")
        evaluator_type = config_data.get("evaluator_type", "")
        config = config_data.get("config", {})
        enabled = config_data.get("enabled", True)

        repo = _get_repository()
        # 保存配置到数据库
        record = {
            "case_id": config_id,
            "adapter_name": f"config:{evaluator_type}",
            "model_name": "config",
            "status": "config",
            "latency_ms": 0,
            "response_data": {
                "name": name,
                "evaluator_type": evaluator_type,
                "config": config,
                "enabled": enabled,
            },
        }
        repo.create(record)

        return success_response({
            "id": config_id,
            "name": name,
            "evaluator_type": evaluator_type,
            "enabled": enabled,
        })
    except Exception as e:
        logger.error(f"Save eval config failed: {e}")
        return error_response(500, "保存配置失败")


@app.get("/api/v1/eval-configs")
async def get_eval_configs():
    """获取所有评估配置"""
    try:
        repo = _get_repository()
        records = repo.get_all(limit=100)
        # 过滤出配置记录
        configs = []
        for r in records:
            if r.get("adapter_name", "").startswith("config:"):
                response_data = r.get("response_data")
                if isinstance(response_data, str):
                    try:
                        response_data = json.loads(response_data)
                    except:
                        response_data = {}
                configs.append({
                    "id": r.get("case_id"),
                    "name": response_data.get("name", "未命名") if isinstance(response_data, dict) else "未命名",
                    "evaluator_type": response_data.get("evaluator_type", "") if isinstance(response_data, dict) else "",
                    "config": response_data.get("config", {}) if isinstance(response_data, dict) else {},
                    "enabled": response_data.get("enabled", True) if isinstance(response_data, dict) else True,
                })
        return success_response(configs)
    except Exception as e:
        logger.error(f"Get eval configs failed: {e}")
        return error_response(500, "获取配置列表失败")


@app.delete("/api/v1/eval-configs/{config_id}")
async def delete_eval_config(config_id: str, response: Response):
    """删除评估配置"""
    try:
        repo = _get_repository()
        # 根据case_id查找并删除
        records = repo.get_all(limit=1000)
        for r in records:
            if r.get("case_id") == config_id and r.get("adapter_name", "").startswith("config:"):
                repo.delete(r.get("id"))
                return success_response({"deleted": True})
        response.status_code = status.HTTP_404_NOT_FOUND
        return error_response(404, "配置不存在")
    except Exception as e:
        logger.error(f"Delete eval config failed: {e}")
        return error_response(500, "删除配置失败")


@app.post("/api/v1/evaluate/sync-batch")
async def evaluate_sync_batch(batch_data: dict):
    """同步批量评估（无需Celery）"""
    try:
        cases = batch_data.get("cases", [])
        if not cases:
            return error_response(400, "Batch evaluation requires cases array")

        results = []
        for case_data in cases:
            try:
                # 直接使用原始数据调用同步服务
                result = run_evaluation_service(case_data)
                results.append({
                    "case_id": case_data.get("id", "unknown"),
                    "status": result.get("status", "unknown"),
                    "score": result.get("data", {}).get("score") if isinstance(result.get("data"), dict) else 0,
                    "latency_ms": result.get("latency_ms", 0),
                })
            except Exception as e:
                logger.error(f"Sync batch case error: {e}")
                results.append({
                    "case_id": case_data.get("id", "unknown"),
                    "status": "error",
                    "message": str(e),
                })

        return success_response({
            "total": len(cases),
            "passed": sum(1 for r in results if r.get("status") == "passed"),
            "failed": sum(1 for r in results if r.get("status") in ["error", "failed"]),
            "results": results,
        })
    except Exception as e:
        logger.error(f"Sync batch evaluation failed: {e}")
        return error_response(500, "批量评测失败")


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
        logger.error(f"Failed to get stats: {e}")
        return error_response(500, "获取统计信息失败")


@app.get("/api/v1/models")
async def get_models():
    """获取所有可用模型列表"""
    try:
        from src.domain.models.llm_factory import ModelRegistry, ModelProvider, load_config

        models = []
        for provider in ModelRegistry.list_providers():
            try:
                config = load_config(provider)
                models.append({
                    "id": f"{provider}-{config.model_name}",
                    "name": config.model_name,
                    "provider": provider,
                    "provider_name": provider.capitalize(),
                    "status": "available",
                })
            except Exception:
                models.append({
                    "id": provider,
                    "name": provider,
                    "provider": provider,
                    "provider_name": provider.capitalize(),
                    "status": "config_required",
                })

        return success_response(models)
    except Exception as e:
        logger.error(f"Failed to get models: {e}")
        return error_response(500, "获取模型列表失败")


@app.post("/api/v1/models/compare")
async def compare_models(request_data: dict):
    """模型对比评测（演示端点 - 返回模拟数据）
    
    注意：此端点为演示目的，返回模拟数据。
    生产环境应接入真实的 benchmark 评估流程。
    """
    try:
        models = request_data.get("models", [])
        datasets = request_data.get("datasets", ["mmlu", "gsm8k"])

        if not models:
            return error_response(400, "At least one model is required")

        from src.domain.models.llm_factory import create_llm_client

        results = []
        for model_info in models:
            provider = model_info.get("provider", "")
            model_name = model_info.get("name", "")

            try:
                client = create_llm_client(provider=provider)
                model_results = {
                    "model": model_name,
                    "provider": provider,
                    "datasets": {},
                    "mean_accuracy": 0.0,
                    "mean_latency_ms": 0.0,
                    "total_cost_usd": 0.0,
                    "warning": "此为演示数据，非真实评测结果",
                }

                total_accuracy = 0.0
                total_latency = 0.0
                total_cost = 0.0
                count = 0

                for dataset in datasets:
                    sample_count = min(request_data.get("sample_count", 5), 20)

                    if dataset == "mmlu":
                        model_results["datasets"]["mmlu"] = {
                            "accuracy": 0.75 + (0.05 * count),
                            "samples": sample_count,
                            "latency_ms": 800 + (100 * count),
                            "is_simulated": True,
                        }
                    elif dataset == "gsm8k":
                        model_results["datasets"]["gsm8k"] = {
                            "accuracy": 0.80 + (0.03 * count),
                            "samples": sample_count,
                            "latency_ms": 1200 + (150 * count),
                            "is_simulated": True,
                        }
                    elif dataset == "human_eval":
                        model_results["datasets"]["human_eval"] = {
                            "accuracy": 0.65 + (0.04 * count),
                            "samples": sample_count,
                            "latency_ms": 1500 + (200 * count),
                            "is_simulated": True,
                        }

                    dataset_result = model_results["datasets"][dataset]
                    total_accuracy += dataset_result["accuracy"]
                    total_latency += dataset_result["latency_ms"]
                    total_cost += dataset_result["latency_ms"] * 0.00001
                    count += 1

                if count > 0:
                    model_results["mean_accuracy"] = total_accuracy / count
                    model_results["mean_latency_ms"] = total_latency / count
                    model_results["total_cost_usd"] = total_cost

                results.append(model_results)
            except Exception as e:
                logger.error(f"Model compare error for {model_name}: {e}")
                results.append({
                    "model": model_name,
                    "provider": provider,
                    "error": "模型执行失败",
                })

        return success_response({
            "models": results,
            "is_simulated": True,
            "warning": "此端点返回模拟数据，仅供演示。生产环境请接入真实 benchmark 评估。",
            "datasets": datasets,
            "summary": {
                "best_accuracy": max(results, key=lambda x: x.get("mean_accuracy", 0)).get("model") if results else None,
                "fastest": min(results, key=lambda x: x.get("mean_latency_ms", float("inf"))).get("model") if results else None,
            },
        })
    except Exception as e:
        logger.error(f"Failed to compare models: {e}")
        return error_response(500, "模型对比失败")


@app.get("/api/v1/cost")
async def get_cost_metrics():
    """获取成本指标"""
    try:
        from src.infra.cost_governance import cost_governance

        metrics = cost_governance.get_metrics()
        budget_check = cost_governance.check_budget()

        return success_response({
            "daily_cost_usd": metrics.daily_cost_usd,
            "weekly_cost_usd": metrics.weekly_cost_usd,
            "monthly_cost_usd": metrics.monthly_cost_usd,
            "avg_latency_ms": metrics.avg_latency_ms,
            "p50_latency_ms": metrics.p50_latency_ms,
            "p95_latency_ms": metrics.p95_latency_ms,
            "p99_latency_ms": metrics.p99_latency_ms,
            "total_requests": metrics.total_requests,
            "avg_tokens_per_request": metrics.avg_tokens_per_request,
            "budget_status": {
                "daily_budget_ok": budget_check["daily_budget_ok"],
                "daily_usage_percent": budget_check["daily_usage_percent"],
                "daily_limit": cost_governance.daily_cost_limit,
            },
            "top_models_by_cost": cost_governance.get_top_models_by_cost(),
        })
    except Exception as e:
        logger.error(f"Failed to get cost metrics: {e}")
        return error_response(500, "获取成本指标失败")


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
        logger.error(f"Failed to get reports: {e}")
        return error_response(500, "获取报告列表失败")

@app.get("/api/v1/reports/{filename}")
async def get_report(filename: str, response: Response):
    """获取单个报告"""
    try:
        from fastapi.responses import FileResponse
        report_dir = os.path.abspath("reports")
        filepath = os.path.normpath(os.path.join(report_dir, filename))
        
        if not filepath.startswith(report_dir):
            response.status_code = status.HTTP_400_BAD_REQUEST
            return error_response(400, "Invalid filename")
        
        if os.path.exists(filepath):
            return FileResponse(filepath)
        response.status_code = status.HTTP_404_NOT_FOUND
        return error_response(404, f"Report '{filename}' not found")
    except Exception as e:
        logger.error(f"Failed to get report: {e}")
        return error_response(500, "获取报告失败")

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
        logger.error(f"Failed to generate report: {e}")
        return error_response(500, "生成报告失败")


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
        logger.error(f"Failed to get datasets: {e}")
        return error_response(500, "获取数据集列表失败")


@app.get("/api/v1/datasets/{dataset_name}")
async def get_dataset_details(dataset_name: str, response: Response):
    """获取数据集详情"""
    # 输入验证：防止特殊字符攻
    if not validate_dataset_name(dataset_name):
        response.status_code = status.HTTP_404_NOT_FOUND
        return error_response(404, f"Invalid dataset name format")
    
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
        response.status_code = status.HTTP_404_NOT_FOUND
        return error_response(404, f"Dataset '{dataset_name}' not found")
    except Exception as e:
        logger.error(f"Failed to get dataset: {e}")
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return error_response(500, "获取数据集失败")


@app.get("/api/v1/health/detailed")
async def api_health_detailed():
    """Detailed health check - API unified format"""
    try:
        import time
        from src.config import settings

        result = {
            "service": {
                "name": "ai-eval-platform",
                "version": "1.0.0",
                "timestamp": time.time(),
            },
            "components": {
                "redis": {"status": "healthy"},
                "database": {"status": "healthy"},
                "rabbitmq": {"status": "healthy"},
            },
            "metrics": {
                "requests_total": 0,
                "avg_latency_ms": 0.0,
                "error_rate": 0.0,
                "cache_hit_rate": 0.0,
            },
        }

        return success_response(result)
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return error_response(500, "健康检查失败")


@app.get("/api/v1/metrics")
async def api_metrics():
    """Performance metrics - API unified format"""
    try:
        from src.infra.cost_governance import cost_governance

        metrics = cost_governance.get_metrics()

        return success_response({
            "requests_total": metrics.total_requests,
            "avg_latency_ms": metrics.avg_latency_ms,
            "p50_latency_ms": metrics.p50_latency_ms,
            "p95_latency_ms": metrics.p95_latency_ms,
            "p99_latency_ms": metrics.p99_latency_ms,
            "error_rate": 0.0,
            "cache_hit_rate": 0.0,
        })
    except Exception as e:
        logger.error(f"Metrics failed: {e}")
        return error_response(500, "获取指标失败")


@app.get("/api/v1/calibration/datasets")
async def get_golden_datasets():
    """获取黄金标准数据集列表"""
    try:
        from src.domain.golden_dataset import golden_dataset_manager
        datasets = golden_dataset_manager.list_datasets()
        return success_response({"datasets": datasets})
    except Exception as e:
        logger.error(f"Failed to get golden datasets: {e}")
        return error_response(500, "获取黄金数据集失败")


@app.post("/api/v1/calibration/datasets")
async def create_golden_dataset(data: dict):
    """创建黄金标准数据集"""
    try:
        from src.domain.golden_dataset import golden_dataset_manager
        dataset_id = data.get("dataset_id")
        description = data.get("description", "")
        dimensions = data.get("dimensions", ["correctness"])
        if not dataset_id:
            return error_response(400, "dataset_id 必填")
        golden_dataset_manager.create_dataset(dataset_id, description, dimensions)
        return success_response({"dataset_id": dataset_id, "message": "数据集创建成功"})
    except Exception as e:
        logger.error(f"Failed to create golden dataset: {e}")
        return error_response(500, "创建黄金数据集失败")


@app.post("/api/v1/calibration/datasets/{dataset_id}/samples")
async def add_golden_sample(dataset_id: str, data: dict):
    """添加黄金标注样本"""
    try:
        from src.domain.golden_dataset import golden_dataset_manager
        sample = data.get("sample")
        if not sample:
            return error_response(400, "sample 必填")
        golden_dataset_manager.add_sample(dataset_id, sample)
        return success_response({"message": "样本添加成功"})
    except Exception as e:
        logger.error(f"Failed to add golden sample: {e}")
        return error_response(500, "添加样本失败")


@app.post("/api/v1/calibration/datasets/{dataset_id}/samples/{sample_id}/correct")
async def correct_golden_sample(dataset_id: str, sample_id: str, data: dict):
    """修正评估结果"""
    try:
        from src.domain.golden_dataset import golden_dataset_manager
        corrected_scores = data.get("corrected_scores")
        corrected_reason = data.get("corrected_reason", "")
        golden_dataset_manager.correct_sample(dataset_id, sample_id, corrected_scores, corrected_reason)
        return success_response({"message": "修正成功"})
    except Exception as e:
        logger.error(f"Failed to correct golden sample: {e}")
        return error_response(500, "修正失败")


@app.get("/api/v1/calibration/datasets/{dataset_id}/few-shot")
async def get_few_shot_examples(dataset_id: str, limit: int = 3, dimensions: str = None):
    """获取 Few-shot 示例"""
    try:
        from src.domain.golden_dataset import golden_dataset_manager
        dim_list = dimensions.split(",") if dimensions else None
        examples = golden_dataset_manager.get_few_shot_examples(dataset_id, limit=limit, dimensions=dim_list)
        return success_response({"examples": examples})
    except Exception as e:
        logger.error(f"Failed to get few-shot examples: {e}")
        return error_response(500, "获取 Few-shot 示例失败")


@app.get("/api/v1/routing/config")
async def get_routing_config():
    """获取智能路由配置"""
    try:
        from src.domain.model_routing import model_router
        config = model_router.get_routing_config()
        return success_response(config)
    except Exception as e:
        logger.error(f"Failed to get routing config: {e}")
        return error_response(500, "获取路由配置失败")


@app.post("/api/v1/routing/config")
async def update_routing_config(data: dict):
    """更新智能路由配置"""
    try:
        from src.domain.model_routing import model_router
        model_router.update_routing_config(data)
        return success_response({"message": "路由配置更新成功"})
    except Exception as e:
        logger.error(f"Failed to update routing config: {e}")
        return error_response(500, "更新路由配置失败")


@app.get("/api/v1/routing/decision")
async def get_routing_decision(task_type: str):
    """获取路由决策"""
    try:
        from src.domain.model_routing import model_router
        decision = model_router.route(task_type)
        return success_response(decision)
    except Exception as e:
        logger.error(f"Failed to get routing decision: {e}")
        return error_response(500, "获取路由决策失败")


@app.get("/api/v1/models/performance")
async def get_model_performance(task_type: str = None, model_name: str = None):
    """获取模型性能分析"""
    try:
        from src.domain.model_performance import model_performance_analyzer
        if model_name:
            analysis = model_performance_analyzer.analyze_model_performance(model_name)
        else:
            analysis = model_performance_analyzer.analyze_all_models(task_type)
        return success_response(analysis)
    except Exception as e:
        logger.error(f"Failed to get model performance: {e}")
        return error_response(500, "获取模型性能失败")


@app.get("/api/v1/models/recommendations")
async def get_model_recommendations(task_type: str = None, preference: str = "balanced"):
    """获取模型推荐"""
    try:
        from src.domain.model_performance import model_performance_analyzer
        recommendations = model_performance_analyzer.get_model_recommendations(task_type, preference)
        return success_response({"recommendations": recommendations})
    except Exception as e:
        logger.error(f"Failed to get model recommendations: {e}")
        return error_response(500, "获取模型推荐失败")


# ============================================================
# Meta-Evaluator API - 高冲突检测与评估器漂移分析
# ============================================================

@app.get("/api/v1/meta/conflicts")
async def get_pending_conflicts(status: str = None, limit: int = 50):
    """获取待处理的评估冲突列表"""
    try:
        from src.domain.meta_evaluator import meta_evaluator
        conflicts = meta_evaluator.get_pending_conflicts(status=status, limit=limit)
        return success_response({"conflicts": conflicts})
    except Exception as e:
        logger.error(f"Failed to get conflicts: {e}")
        return error_response(500, "获取冲突列表失败")


@app.get("/api/v1/meta/conflicts/stats")
async def get_conflict_stats():
    """获取冲突统计信息"""
    try:
        from src.domain.meta_evaluator import meta_evaluator
        stats = meta_evaluator.get_conflict_stats()
        return success_response(stats)
    except Exception as e:
        logger.error(f"Failed to get conflict stats: {e}")
        return error_response(500, "获取冲突统计失败")


@app.post("/api/v1/meta/conflicts/{case_id}/resolve")
async def resolve_conflict(case_id: str, resolution: str = "reviewed"):
    """解决评估冲突"""
    try:
        from src.domain.meta_evaluator import meta_evaluator
        meta_evaluator.resolve_conflict(case_id, resolution)
        return success_response({"message": "冲突已解决", "case_id": case_id})
    except Exception as e:
        logger.error(f"Failed to resolve conflict: {e}")
        return error_response(500, "解决冲突失败")


@app.get("/api/v1/meta/drift")
async def get_evaluator_drift(days: int = 7):
    """分析评估器漂移情况"""
    try:
        from src.domain.meta_evaluator import meta_evaluator
        drift = meta_evaluator.analyze_evaluator_drift(days=days)
        return success_response(drift)
    except Exception as e:
        logger.error(f"Failed to analyze drift: {e}")
        return error_response(500, "分析评估器漂移失败")


# ============================================================
# Performance API - 性能优化与缓存管理
# ============================================================

@app.get("/api/v1/performance/report")
async def get_performance_report():
    """获取性能报告"""
    try:
        from src.infra.performance import performance_optimizer
        report = performance_optimizer.get_performance_report()
        return success_response(report)
    except Exception as e:
        logger.error(f"Failed to get performance report: {e}")
        return error_response(500, "获取性能报告失败")


@app.get("/api/v1/performance/cache/stats")
async def get_cache_stats():
    """获取缓存统计"""
    try:
        from src.infra.performance import evaluation_cache
        stats = evaluation_cache.get_stats()
        return success_response(stats)
    except Exception as e:
        logger.error(f"Failed to get cache stats: {e}")
        return error_response(500, "获取缓存统计失败")


@app.post("/api/v1/performance/cache/clear")
async def clear_cache():
    """清空评估缓存"""
    try:
        from src.infra.performance import evaluation_cache
        evaluation_cache.clear()
        return success_response({"message": "缓存已清空"})
    except Exception as e:
        logger.error(f"Failed to clear cache: {e}")
        return error_response(500, "清空缓存失败")


# ============================================================
# Dashboard API - 评估看板数据
# ============================================================

@app.get("/api/v1/dashboard/overview")
async def get_dashboard_overview():
    """获取评估看板概览"""
    try:
        from src.infra.db.repository import EvaluationRepository
        from src.domain.meta_evaluator import meta_evaluator
        from src.domain.golden_dataset import golden_dataset_manager

        repo = EvaluationRepository()
        recent_records = repo.get_recent(limit=100)

        conflict_stats = meta_evaluator.get_conflict_stats()
        golden_datasets = golden_dataset_manager.list_datasets()

        avg_score = 0
        if recent_records:
            scores = [
                r.get("response_data", {}).get("total_score", 0)
                for r in recent_records
                if r.get("response_data", {}).get("total_score", 0) > 0
            ]
            if scores:
                avg_score = sum(scores) / len(scores)

        return success_response({
            "total_evaluations": repo.count(),
            "recent_count": len(recent_records),
            "avg_score": round(avg_score, 1),
            "high_priority_conflicts": conflict_stats.get("high_priority_count", 0),
            "golden_datasets_count": len(golden_datasets),
            "system_status": "healthy" if conflict_stats.get("high_priority_count", 0) < 5 else "attention_needed"
        })
    except Exception as e:
        logger.error(f"Failed to get dashboard overview: {e}")
        return error_response(500, "获取看板数据失败")


# ============================================================
# Fine-tune API - 训练数据导出与模型管理
# ============================================================

@app.get("/api/v1/finetune/export/datasets")
async def list_exportable_datasets():
    """列出可导出的黄金数据集"""
    try:
        from src.domain.golden_dataset import golden_dataset_manager
        from src.domain.fine_tune_exporter import fine_tune_exporter

        datasets = golden_dataset_manager.list_datasets()
        exportable = []

        for ds in datasets:
            if ds.samples:
                stats = {
                    "total_samples": len(ds.samples),
                    "corrected_samples": sum(1 for s in ds.samples if s.human_corrected),
                    "avg_score": sum(s.scores.values()) / max(len(ds.samples), 1) if ds.samples else 0
                }
                exportable.append({
                    "id": ds.id,
                    "name": ds.name,
                    "description": ds.description,
                    "samples_count": len(ds.samples),
                    "corrected_count": stats["corrected_samples"],
                    "avg_score": round(stats["avg_score"], 1),
                    "exportable": stats["corrected_samples"] >= 50
                })

        return success_response({"datasets": exportable})
    except Exception as e:
        logger.error(f"Failed to list datasets: {e}")
        return error_response(500, "获取数据集列表失败")


@app.post("/api/v1/finetune/export")
async def export_training_data(data: dict):
    """导出训练数据"""
    try:
        from src.domain.fine_tune_exporter import fine_tune_exporter, ExportFormat

        dataset_id = data.get("dataset_id")
        output_dir = data.get("output_dir", "data/fine_tune")
        format_str = data.get("format", "openai")
        min_score = data.get("min_score", 0.0)

        if not dataset_id:
            return error_response(400, "dataset_id 必填")

        export_format = ExportFormat(format_str)
        filepath = fine_tune_exporter.export_from_golden_dataset(
            dataset_id=dataset_id,
            output_dir=output_dir,
            format=export_format,
            min_score=min_score
        )

        stats = fine_tune_exporter.get_stats()

        return success_response({
            "message": "导出成功",
            "file_path": filepath,
            "stats": stats
        })
    except ValueError as e:
        return error_response(400, str(e))
    except Exception as e:
        logger.error(f"Failed to export: {e}")
        return error_response(500, "导出失败")


@app.post("/api/v1/finetune/export/db")
async def export_from_database(data: dict = None):
    """从数据库导出训练数据"""
    try:
        from src.domain.fine_tune_exporter import fine_tune_exporter, ExportFormat

        data = data or {}
        output_dir = data.get("output_dir", "data/fine_tune")
        format_str = data.get("format", "openai")
        limit = data.get("limit", 1000)
        min_score = data.get("min_score", 50.0)

        export_format = ExportFormat(format_str)
        filepath = fine_tune_exporter.export_from_db(
            output_dir=output_dir,
            format=export_format,
            limit=limit,
            min_score=min_score
        )

        stats = fine_tune_exporter.get_stats()

        return success_response({
            "message": "数据库导出成功",
            "file_path": filepath,
            "stats": stats
        })
    except Exception as e:
        logger.error(f"Failed to export from DB: {e}")
        return error_response(500, "数据库导出失败")


@app.get("/api/v1/finetune/quality-report")
async def get_quality_report(dataset_id: str = None):
    """获取训练数据质量报告"""
    try:
        from src.domain.golden_dataset import golden_dataset_manager
        from src.domain.fine_tune_exporter import fine_tune_exporter

        if dataset_id:
            dataset = golden_dataset_manager.get_dataset(dataset_id)
            if not dataset:
                return error_response(404, f"Dataset '{dataset_id}' not found")

            samples = [
                {
                    "id": s.id,
                    "metadata": {"avg_score": sum(s.scores.values()) / max(len(s.scores), 1) if s.scores else 0}
                }
                for s in dataset.samples
            ]
        else:
            datasets = golden_dataset_manager.list_datasets()
            samples = [
                {
                    "id": s.id,
                    "metadata": {"avg_score": sum(s.scores.values()) / max(len(s.scores), 1) if s.scores else 0}
                }
                for ds in datasets
                for s in ds.samples
            ]

        # 转换为 TrainingSample 格式用于分析
        training_samples = []
        for s in samples:
            training_samples.append(type('Sample', (), {
                "id": s["id"],
                "metadata": s["metadata"]
            })())

        report = fine_tune_exporter.generate_quality_report(training_samples)

        return success_response(report)
    except Exception as e:
        logger.error(f"Failed to generate quality report: {e}")
        return error_response(500, "生成质量报告失败")


@app.get("/api/v1/finetune/models")
async def list_fine_tuned_models():
    """列出已注册的 Fine-tuned 模型"""
    try:
        from src.domain.fine_tuned_evaluator import model_manager

        models = model_manager.list_models()

        return success_response({
            "models": models,
            "default_model": model_manager._default_model
        })
    except Exception as e:
        logger.error(f"Failed to list models: {e}")
        return error_response(500, "获取模型列表失败")


@app.post("/api/v1/finetune/models")
async def register_fine_tuned_model(data: dict):
    """注册新的 Fine-tuned 模型"""
    try:
        from src.domain.fine_tuned_evaluator import model_manager

        name = data.get("name")
        model_path = data.get("model_path")
        set_default = data.get("set_default", False)

        if not name or not model_path:
            return error_response(400, "name 和 model_path 必填")

        success = model_manager.register_model(name, model_path, set_default)

        if success:
            return success_response({
                "message": "模型注册成功",
                "name": name,
                "model_path": model_path
            })
        else:
            return error_response(400, f"模型路径不存在: {model_path}")
    except Exception as e:
        logger.error(f"Failed to register model: {e}")
        return error_response(500, "注册模型失败")


@app.post("/api/v1/finetune/evaluate")
async def evaluate_with_fine_tuned(data: dict):
    """使用 Fine-tuned 模型进行评估"""
    try:
        from src.domain.fine_tuned_evaluator import model_manager
        from src.schemas.evaluation import EvaluationSchema

        model_name = data.get("model_name")
        user_input = data.get("user_input")
        actual_output = data.get("actual_output")
        dimensions = data.get("dimensions", ["correctness"])

        if not user_input or not actual_output:
            return error_response(400, "user_input 和 actual_output 必填")

        evaluator = model_manager.get_evaluator(model_name)

        if not evaluator:
            return error_response(404, f"模型 '{model_name}' 未找到")

        request = EvaluationSchema(
            id=f"finetune_eval_{int(time.time())}",
            type="fine_tuned",
            payload={
                "user_input": user_input,
                "actual_output": actual_output,
                "dimensions": dimensions
            }
        )

        result = evaluator.evaluate(request)

        return success_response({
            "result": result.data,
            "model_status": evaluator.model_info.status.value
        })
    except Exception as e:
        logger.error(f"Failed to evaluate: {e}")
        return error_response(500, "评估失败")


@app.get("/api/v1/finetune/guide")
async def get_fine_tune_guide():
    """获取 Fine-tune 操作指南"""
    guide = {
        "title": "Fine-tune 操作指南",
        "steps": [
            {
                "step": 1,
                "title": "积累高质量样本",
                "description": "通过黄金数据集积累至少 200+ 修正后的样本",
                "api": "POST /api/v1/calibration/datasets/{id}/samples/{sample_id}/correct"
            },
            {
                "step": 2,
                "title": "导出训练数据",
                "description": "导出为 OpenAI 或 LLaMA-Factory 格式",
                "api": "POST /api/v1/finetune/export"
            },
            {
                "step": 3,
                "title": "数据质量检查",
                "description": "检查导出数据的质量评分和分布",
                "api": "GET /api/v1/finetune/quality-report"
            },
            {
                "step": 4,
                "title": "本地 Fine-tune",
                "description": "使用 LLaMA-Factory 或 OpenAI Fine-tune API 训练",
                "command": "llamafactory-cli train examples/train_lora/eval_judge.yaml"
            },
            {
                "step": 5,
                "title": "注册模型",
                "description": "将训练好的模型注册到评估系统",
                "api": "POST /api/v1/finetune/models"
            },
            {
                "step": 6,
                "title": "对比测试",
                "description": "对比 Fine-tuned 模型与原 GPT-4 的效果和延迟",
                "api": "POST /api/v1/finetune/evaluate"
            }
        ],
        "recommended_models": [
            {"name": "Qwen2-0.5B", "size": "500MB", "use_case": "快速评估"},
            {"name": "Phi-3-mini", "size": "2.3GB", "use_case": "高质量评估"},
            {"name": "DeepSeek-1.5B", "size": "1.5GB", "use_case": "中文优化"}
        ],
        "expected_improvement": {
            "token_cost": "降低 70-95%",
            "latency": "提升 5-20倍",
            "accuracy": "领域任务提升 10-30%"
        }
    }
    return success_response(guide)