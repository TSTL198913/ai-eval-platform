"""
📊 src/api/routes/visualization_routes.py
可视化数据 API 路由 - 2026 工业级实现

端点：
- GET /api/v1/visualization/radar - 雷达图数据
- GET /api/v1/visualization/trend - 趋势图数据
- GET /api/v1/visualization/distribution - 分布图数据
- GET /api/v1/visualization/boxplot - 箱线图数据
- GET /api/v1/visualization/heatmap - 热力图数据
- GET /api/v1/visualization/dashboard - 综合仪表盘数据
- GET /api/v1/visualization/report/html - HTML 报告
- GET /api/v1/visualization/report/markdown - Markdown 报告
"""

import logging
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse

from src.api.common import success_response
from src.infra.analytics.report_generator import ReportGenerator
from src.infra.analytics.visualization_service import VisualizationService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/visualization", tags=["可视化"])


# ==================== 辅助：模拟数据生成 ====================


def _generate_demo_evaluations(
    evaluator_types: list[str] | None = None,
    days: int = 30,
    samples_per_day: int = 10,
) -> list[dict[str, Any]]:
    """生成演示数据（生产环境应替换为真实 DB 查询）"""
    import random

    if evaluator_types is None:
        evaluator_types = ["standard_metric", "ragas", "deepeval", "security", "semantic"]

    evaluations: list[dict[str, Any]] = []
    now = datetime.utcnow()

    for d in range(days):
        day = now - timedelta(days=days - d)
        for _ in range(samples_per_day):
            for etype in evaluator_types:
                # 模拟一个带漂移的分数序列
                base = 0.7 + 0.1 * (d / days) + random.uniform(-0.1, 0.1)
                score = max(0.0, min(1.0, base))
                evaluations.append(
                    {
                        "evaluator_type": etype,
                        "score": round(score, 4),
                        "status": "success" if score >= 0.8 else "failed",
                        "latency_ms": random.randint(50, 500),
                        "created_at": day.isoformat(),
                    }
                )
    return evaluations


# ==================== 数据端点 ====================


@router.get("/radar", response_model=None)
async def get_radar_data(
    evaluator_types: str | None = Query(default=None, description="逗号分隔的评估器类型"),
):
    """获取雷达图数据"""
    try:
        types = evaluator_types.split(",") if evaluator_types else None
        evals = _generate_demo_evaluations(evaluator_types=types)
        data = VisualizationService.radar_from_evaluator_results(evals)
        return success_response(data=data, message="雷达图数据获取成功")
    except Exception as e:
        logger.exception(f"雷达图数据获取失败: {e}")
        raise HTTPException(status_code=500, detail={"code": 500, "message": str(e), "data": None})


@router.get("/trend", response_model=None)
async def get_trend_data(
    bucket: str = Query(default="day", pattern="^(day|hour|minute)$"),
    evaluator_types: str | None = None,
    days: int = Query(default=30, ge=1, le=365),
):
    """获取趋势图数据"""
    try:
        types = evaluator_types.split(",") if evaluator_types else None
        evals = _generate_demo_evaluations(evaluator_types=types, days=days)
        data = VisualizationService.trend_from_evaluations(
            evals, evaluator_types=types, bucket=bucket
        )
        return success_response(data=data, message="趋势图数据获取成功")
    except Exception as e:
        logger.exception(f"趋势图数据获取失败: {e}")
        raise HTTPException(status_code=500, detail={"code": 500, "message": str(e), "data": None})


@router.get("/distribution", response_model=None)
async def get_distribution_data(bin_count: int = Query(default=10, ge=3, le=50)):
    """获取分数分布直方图数据"""
    try:
        evals = _generate_demo_evaluations()
        scores = [e["score"] for e in evals]
        data = VisualizationService.generate_distribution_chart(scores, bin_count=bin_count)
        return success_response(data=data, message="分布图数据获取成功")
    except Exception as e:
        logger.exception(f"分布图数据获取失败: {e}")
        raise HTTPException(status_code=500, detail={"code": 500, "message": str(e), "data": None})


@router.get("/boxplot", response_model=None)
async def get_boxplot_data():
    """获取箱线图数据"""
    try:
        evals = _generate_demo_evaluations()
        by_evaluator: dict[str, list[float]] = {}
        for e in evals:
            by_evaluator.setdefault(e["evaluator_type"], []).append(e["score"])
        groups = [{"name": k, "values": v} for k, v in by_evaluator.items()]
        data = VisualizationService.generate_boxplot(groups)
        return success_response(data=data, message="箱线图数据获取成功")
    except Exception as e:
        logger.exception(f"箱线图数据获取失败: {e}")
        raise HTTPException(status_code=500, detail={"code": 500, "message": str(e), "data": None})


@router.get("/heatmap", response_model=None)
async def get_heatmap_data():
    """获取评估器相关性热力图数据"""
    try:
        evals = _generate_demo_evaluations()
        data = VisualizationService.heatmap_from_evaluations(evals)
        return success_response(data=data, message="热力图数据获取成功")
    except Exception as e:
        logger.exception(f"热力图数据获取失败: {e}")
        raise HTTPException(status_code=500, detail={"code": 500, "message": str(e), "data": None})


@router.get("/dashboard", response_model=None)
async def get_dashboard_data(
    evaluator_types: str | None = None,
    days: int = Query(default=30, ge=1, le=365),
):
    """获取综合仪表盘数据（一次性返回所有图表）"""
    try:
        types = evaluator_types.split(",") if evaluator_types else None
        evals = _generate_demo_evaluations(evaluator_types=types, days=days)
        data = VisualizationService.generate_dashboard(evals)
        return success_response(data=data, message="仪表盘数据获取成功")
    except Exception as e:
        logger.exception(f"仪表盘数据获取失败: {e}")
        raise HTTPException(status_code=500, detail={"code": 500, "message": str(e), "data": None})


# ==================== 报告端点 ====================


@router.get("/report/html", response_class=HTMLResponse)
async def get_html_report(
    title: str = "AI 评测报告",
    days: int = Query(default=30, ge=1, le=365),
):
    """获取自包含 HTML 报告"""
    try:
        evals = _generate_demo_evaluations(days=days)
        generator = ReportGenerator(title=title)
        html = generator.generate_html_report(evals)
        return HTMLResponse(content=html)
    except Exception as e:
        logger.exception(f"HTML 报告生成失败: {e}")
        raise HTTPException(status_code=500, detail=f"HTML 报告生成失败: {e}")


@router.get("/report/markdown", response_class=JSONResponse)
async def get_markdown_report(
    title: str = "AI 评测报告",
    days: int = Query(default=30, ge=1, le=365),
):
    """获取 Markdown 报告"""
    try:
        evals = _generate_demo_evaluations(days=days)
        generator = ReportGenerator(title=title)
        md = generator.generate_markdown_report(evals)
        return success_response(
            data={"title": title, "content": md}, message="Markdown 报告生成成功"
        )
    except Exception as e:
        logger.exception(f"Markdown 报告生成失败: {e}")
        raise HTTPException(status_code=500, detail={"code": 500, "message": str(e), "data": None})
