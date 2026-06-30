"""
模型聚合路由 - 统一模型管理入口
整合 model_routes + model_comparison + finetune_routes
"""

from fastapi import APIRouter

from src.api.routes.finetune_routes import router as finetune_router
from src.api.routes.model_comparison import router as model_comparison_router
from src.api.routes.model_routes import router as model_router

router = APIRouter(prefix="/models", tags=["models"])

router.include_router(model_router, prefix="")
router.include_router(model_comparison_router, prefix="/comparison")
router.include_router(finetune_router, prefix="/finetune")
