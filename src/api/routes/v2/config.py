"""
配置聚合路由 - 统一配置管理入口
整合 eval_config_routes + evaluator_version_routes + calibration_routes + quality_gates_routes
"""

from fastapi import APIRouter

from src.api.routes.calibration_routes import router as calibration_router
from src.api.routes.eval_config_routes import router as eval_config_router
from src.api.routes.evaluator_version_routes import router as evaluator_version_router
from src.api.routes.quality_gates_routes import router as quality_gates_router

router = APIRouter(prefix="/config", tags=["config"])

router.include_router(eval_config_router, prefix="/evaluators")
router.include_router(evaluator_version_router, prefix="/versions")
router.include_router(calibration_router, prefix="/calibration")
router.include_router(quality_gates_router, prefix="/quality-gates")
