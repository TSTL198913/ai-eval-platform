"""
AI Eval Platform - 主应用入口（路由聚合器）
所有API端点已拆分到独立的路由模块中
"""

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from src.api.common import success_response
from src.domain.evaluators import EVALUATOR_REGISTRY
from src.exceptions import BasePlatformError
from src.infra.db.session import init_tables

logger = logging.getLogger(__name__)

# =====================================================================
# Lifespan事件处理器 - 启动预热
# =====================================================================


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan事件处理器 - 启动时预热关键资源"""
    print("=" * 60, flush=True)
    print("开始预热...", flush=True)
    warmup_start = time.time()

    # 1. 初始化数据库表
    print("[1/5] 初始化数据库表...", flush=True)
    t0 = time.time()
    init_tables()
    print(f"      数据库表初始化完成: {time.time()-t0:.0f}s", flush=True)

    # 2. 预热数据库连接池
    print("[2/5] 预热数据库连接池...", flush=True)
    t0 = time.time()
    try:
        from sqlalchemy import text

        from src.infra.db.session import get_db

        db_gen = get_db()
        db = next(db_gen)
        _ = db.execute(text("SELECT 1"))
        db.commit()
        time.sleep(0.5)
        next(db_gen, None)
        print(f"      连接池预热完成: {time.time()-t0:.0f}s", flush=True)
    except Exception as e:
        print(f"      连接池预热失败: {e}", flush=True)

    # 3. 预热评估器注册表
    print("[3/5] 预热评估器注册表...", flush=True)
    t0 = time.time()
    try:
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


# =====================================================================
# 创建FastAPI应用
# =====================================================================

app = FastAPI(
    title="AI Eval Platform",
    description="AI Evaluation Platform API - 路由聚合器",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# =====================================================================
# 注册中间件
# =====================================================================

# CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Prometheus指标收集中间件
from src.infra.monitoring.prometheus_middleware import register_metrics_middleware

register_metrics_middleware(app)

# 安全中间件
from src.api.security_middleware import SecurityMiddleware

app.add_middleware(SecurityMiddleware)

# =====================================================================
# 注册异常处理器
# =====================================================================


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
        errors.append(
            {
                "field": ".".join(str(loc) for loc in error["loc"]),
                "message": error["msg"],
                "type": error["type"],
            }
        )
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
    """全局异常处理"""
    logger.exception(f"Unexpected error on {request.url.path}: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "code": "INTERNAL_ERROR",
            "message": "系统内部发生不可预知的错误，请稍后重试",
            "data": None,
        },
    )


# =====================================================================
# 注册路由模块
# =====================================================================

from src.api.routes import (
    auth_router,
    calibration_router,
    dashboard_router,
    dataset_router,
    evaluation_router,
    evaluator_router,
    finetune_router,
    health_router,
    model_router,
    records_router,
    report_router,
    statistics_router,
)

# 注册所有路由模块
app.include_router(auth_router)
app.include_router(health_router)
app.include_router(evaluation_router)
app.include_router(records_router)
app.include_router(evaluator_router)
app.include_router(model_router)
app.include_router(report_router)
app.include_router(dataset_router)
app.include_router(calibration_router)
app.include_router(finetune_router)
app.include_router(statistics_router)
app.include_router(dashboard_router)


# =====================================================================
# 根路径端点（保留）
# =====================================================================


@app.get("/")
async def root():
    """根路径 - 返回API信息"""
    return success_response(
        {
            "name": "AI Eval Platform",
            "version": "2.0.0",
            "docs": "/docs",
            "health": "/health",
        }
    )
