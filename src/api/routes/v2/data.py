"""
数据聚合路由 - 统一数据管理入口
整合 dataset_routes + annotation_routes + records_routes
"""

from fastapi import APIRouter

from src.api.routes.annotation_routes import router as annotation_router
from src.api.routes.dataset_routes import router as dataset_router
from src.api.routes.records_routes import router as records_router

router = APIRouter(prefix="/data", tags=["data"])

router.include_router(dataset_router, prefix="/datasets")
router.include_router(annotation_router, prefix="/annotations")
router.include_router(records_router, prefix="/records")
