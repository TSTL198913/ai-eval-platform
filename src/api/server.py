"""
AI Eval Platform - 主应用入口（路由聚合器）
所有API端点已拆分到独立的路由模块中
"""

import logging
import os
import time
from contextlib import asynccontextmanager

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from src.api.common import success_response
from src.domain.evaluators import EVALUATOR_REGISTRY
from src.exceptions import BasePlatformError
from src.infra.db.session import init_tables
from src.infra.security.fastapi_rbac import RBACMiddleware

logger = logging.getLogger(__name__)

# =====================================================================
# Lifespan事件处理器 - 启动预热
# =====================================================================


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan事件处理器 - 启动时预热关键资源"""
    logger.info("=" * 60)
    logger.info("开始预热...")
    warmup_start = time.time()

    # 1. 初始化数据库表
    logger.info("[1/5] 初始化数据库表...")
    t0 = time.time()
    init_tables()
    logger.info(f"[1/5] 数据库表初始化完成: {time.time() - t0:.0f}s")

    # 2. 预热数据库连接池
    logger.info("[2/5] 预热数据库连接池...")
    t0 = time.time()
    try:
        from sqlalchemy import text

        from src.infra.db.session import get_db

        db_gen = get_db()
        db = next(db_gen)
        _ = db.execute(text("SELECT 1"))
        db.commit()
        next(db_gen, None)
        logger.info(f"[2/5] 连接池预热完成: {time.time() - t0:.0f}s")
    except Exception as e:
        logger.warning(f"[2/5] 连接池预热失败: {e}")

    # 3. 预热评估器注册表
    logger.info("[3/5] 预热评估器注册表...")
    t0 = time.time()
    try:
        evaluators = list(EVALUATOR_REGISTRY.keys())
        logger.info(f"[3/5] 已注册评估器: {evaluators}")
        logger.info(f"[3/5] 评估器预热完成: {time.time() - t0:.0f}s")
    except Exception as e:
        logger.warning(f"[3/5] 评估器预热失败: {e}")

    # 4. 预热模型工厂
    logger.info("[4/5] 预热模型工厂...")
    t0 = time.time()
    try:
        from src.domain.models.llm_factory import ModelRegistry

        providers = ModelRegistry.list_providers()
        logger.info(f"[4/5] 可用模型供应商: {providers}")
        logger.info(f"[4/5] 模型工厂预热完成: {time.time() - t0:.0f}s")
    except Exception as e:
        logger.warning(f"[4/5] 模型工厂预热失败: {e}")

    # 5. 预热报告生成器
    logger.info("[5/5] 预热报告生成器...")
    t0 = time.time()
    try:
        from src.domain.reports.report_generator import ReportGenerator

        _ = ReportGenerator()
        logger.info(f"[5/5] 报告生成器预热完成: {time.time() - t0:.0f}s")
    except Exception as e:
        logger.warning(f"[5/5] 报告生成器预热失败: {e}")

    logger.info("=" * 60)
    logger.info(f"预热完成! 总耗时: {time.time() - warmup_start:.1f}s")
    logger.info("=" * 60)

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

# CORS中间件 - 支持环境变量配置的白名单
_cors_origins = os.environ.get("CORS_ALLOWED_ORIGINS", "").split(",")
if not _cors_origins or _cors_origins == [""]:
    _cors_origins = ["http://localhost:3000", "http://localhost:5173", "http://127.0.0.1:3000"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)

# Prometheus指标收集中间件
from src.infra.monitoring.prometheus_middleware import register_metrics_middleware

register_metrics_middleware(app)

# 安全中间件
from src.api.security_middleware import SecurityMiddleware

app.add_middleware(SecurityMiddleware)
app.add_middleware(RBACMiddleware)

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
    ab_test_router,
    admin_router,
    annotation_router,
    auth_router,
    benchmark_router,
    calibration_router,
    cost_router,
    dashboard_router,
    dataset_router,
    eval_config_router,
    evaluation_router,
    evaluator_router,
    evaluator_version_router,
    finetune_router,
    health_router,
    meta_evaluation_router,
    model_comparison_router,
    model_router,
    mutation_test_router,
    online_evaluation_router,
    performance_router,
    quality_gates_router,
    records_router,
    report_router,
    security_router,
    statistics_router,
)

# 注册所有路由模块
app.include_router(auth_router)
app.include_router(health_router)
app.include_router(admin_router)
app.include_router(ab_test_router)
app.include_router(benchmark_router)
app.include_router(security_router)
app.include_router(meta_evaluation_router)
app.include_router(quality_gates_router)
app.include_router(cost_router)
app.include_router(evaluator_version_router)
app.include_router(mutation_test_router)
app.include_router(performance_router)
app.include_router(online_evaluation_router)
app.include_router(evaluation_router)
app.include_router(records_router)
app.include_router(evaluator_router)
app.include_router(model_router)
app.include_router(model_comparison_router)
app.include_router(report_router)
app.include_router(dataset_router)
app.include_router(calibration_router)
app.include_router(finetune_router)
app.include_router(statistics_router)
app.include_router(dashboard_router)
app.include_router(annotation_router)
app.include_router(eval_config_router)

# =====================================================================
# v2 API 路由聚合（精简后：8个功能域）
# =====================================================================
from src.api.routes.v2 import (
    analytics_v2_router,
    config_v2_router,
    data_v2_router,
    evaluation_v2_router,
    models_v2_router,
)

app.include_router(evaluation_v2_router, prefix="/v2")
app.include_router(models_v2_router, prefix="/v2")
app.include_router(data_v2_router, prefix="/v2")
app.include_router(analytics_v2_router, prefix="/v2")
app.include_router(config_v2_router, prefix="/v2")


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
