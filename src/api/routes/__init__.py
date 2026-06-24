"""
路由模块包
包含所有拆分的API路由
"""

from src.api.routes.ab_test_routes import router as ab_test_router
from src.api.routes.admin_routes import router as admin_router
from src.api.routes.annotation_routes import router as annotation_router
from src.api.routes.auth_routes import router as auth_router
from src.api.routes.benchmark_routes import router as benchmark_router
from src.api.routes.calibration_routes import router as calibration_router
from src.api.routes.cost_routes import router as cost_router
from src.api.routes.dashboard_routes import router as dashboard_router
from src.api.routes.dataset_routes import router as dataset_router
from src.api.routes.eval_config_routes import router as eval_config_router
from src.api.routes.evaluation_routes import router as evaluation_router
from src.api.routes.evaluator_routes import router as evaluator_router
from src.api.routes.evaluator_version_routes import router as evaluator_version_router
from src.api.routes.finetune_routes import router as finetune_router
from src.api.routes.health_routes import router as health_router
from src.api.routes.meta_evaluation_routes import router as meta_evaluation_router
from src.api.routes.model_comparison import router as model_comparison_router
from src.api.routes.model_routes import router as model_router
from src.api.routes.mutation_test_routes import router as mutation_test_router
from src.api.routes.online_evaluation_routes import router as online_evaluation_router
from src.api.routes.performance_routes import router as performance_router
from src.api.routes.quality_gates_routes import router as quality_gates_router
from src.api.routes.records_routes import router as records_router
from src.api.routes.report_routes import router as report_router
from src.api.routes.security_routes import router as security_router
from src.api.routes.statistics_routes import router as statistics_router

__all__ = [
    "ab_test_router",
    "admin_router",
    "annotation_router",
    "auth_router",
    "benchmark_router",
    "calibration_router",
    "cost_router",
    "dashboard_router",
    "dataset_router",
    "eval_config_router",
    "evaluation_router",
    "evaluator_router",
    "evaluator_version_router",
    "finetune_router",
    "health_router",
    "meta_evaluation_router",
    "model_comparison_router",
    "model_router",
    "mutation_test_router",
    "online_evaluation_router",
    "performance_router",
    "quality_gates_router",
    "records_router",
    "report_router",
    "security_router",
    "statistics_router",
]
