"""
路由模块包
包含所有拆分的API路由
"""

from src.api.routes.annotation_routes import router as annotation_router
from src.api.routes.auth_routes import router as auth_router
from src.api.routes.calibration_routes import router as calibration_router
from src.api.routes.dashboard_routes import router as dashboard_router
from src.api.routes.dataset_routes import router as dataset_router
from src.api.routes.eval_config_routes import router as eval_config_router
from src.api.routes.evaluation_routes import router as evaluation_router
from src.api.routes.evaluator_routes import router as evaluator_router
from src.api.routes.finetune_routes import router as finetune_router
from src.api.routes.health_routes import router as health_router
from src.api.routes.model_comparison import router as model_comparison_router
from src.api.routes.model_routes import router as model_router
from src.api.routes.records_routes import router as records_router
from src.api.routes.report_routes import router as report_router
from src.api.routes.statistics_routes import router as statistics_router

__all__ = [
    "annotation_router",
    "auth_router",
    "health_router",
    "evaluation_router",
    "records_router",
    "evaluator_router",
    "model_router",
    "model_comparison_router",
    "report_router",
    "dataset_router",
    "calibration_router",
    "finetune_router",
    "statistics_router",
    "dashboard_router",
    "eval_config_router",
]
