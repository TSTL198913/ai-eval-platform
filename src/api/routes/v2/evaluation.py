"""
评估聚合路由 - 统一评估入口
整合 evaluation_routes + online_evaluation_routes + evaluator_routes
"""

from fastapi import APIRouter

from src.api.routes.evaluation_routes import router as evaluation_router
from src.api.routes.evaluator_routes import router as evaluator_router
from src.api.routes.online_evaluation_routes import router as online_evaluation_router

router = APIRouter(prefix="/evaluation", tags=["evaluation"])

router.include_router(evaluation_router, prefix="")
router.include_router(online_evaluation_router, prefix="/online")
router.include_router(evaluator_router, prefix="/evaluators")
