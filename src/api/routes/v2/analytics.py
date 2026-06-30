"""
分析聚合路由 - 统一分析入口
整合 statistics_routes + report_routes + visualization_routes + dashboard_routes
"""

from fastapi import APIRouter

from src.api.routes.dashboard_routes import router as dashboard_router
from src.api.routes.report_routes import router as report_router
from src.api.routes.statistics_routes import router as statistics_router
from src.api.routes.visualization_routes import router as visualization_router

router = APIRouter(prefix="/analytics", tags=["analytics"])

router.include_router(statistics_router, prefix="/statistics")
router.include_router(report_router, prefix="/reports")
router.include_router(visualization_router, prefix="/visualization")
router.include_router(dashboard_router, prefix="/dashboard")
