"""
Prometheus 中间件 - FastAPI 请求自动采集

功能：
1. 自动记录请求延迟、状态码、路径
2. 按评估器类型统计调用次数
3. 记录错误类型分布
"""

import time
from collections.abc import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from src.infra.monitoring.metrics import (
    EVALUATION_COUNTER,
    EVALUATION_LATENCY,
)


class PrometheusMiddleware(BaseHTTPMiddleware):
    """Prometheus 指标收集中间件"""

    def __init__(self, app: ASGIApp):
        super().__init__(app)
        # 路径模式：/api/v1/evaluate/{evaluator_type}
        self.eval_pattern = "/api/v1/evaluate/"

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # 跳过metrics端点自身，避免递归
        if request.url.path == "/metrics":
            return await call_next(request)

        start_time = time.time()

        # 执行请求
        response = await call_next(request)

        # 计算延迟
        latency = time.time() - start_time

        # 提取路径标签
        path = request.url.path
        status_code = response.status_code

        # 判断是否为评估请求
        if path.startswith(self.eval_pattern):
            evaluator_type = path[len(self.eval_pattern):].split("/")[0] or "unknown"
        else:
            evaluator_type = "other"

        # 记录指标
        status = "success" if status_code < 400 else "error"

        # 延迟直方图
        EVALUATION_LATENCY.labels(
            domain=evaluator_type,
            status=status
        ).observe(latency)

        # 计数器
        EVALUATION_COUNTER.labels(
            domain=evaluator_type,
            status=status
        ).inc()

        return response


def register_metrics_middleware(app: ASGIApp):
    """注册中间件到FastAPI应用"""
    app.add_middleware(PrometheusMiddleware)
