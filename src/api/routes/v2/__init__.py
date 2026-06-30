"""
v2路由聚合模块 - 将26个路由聚合为8个功能域
"""

from .analytics import router as analytics_v2_router
from .config import router as config_v2_router
from .data import router as data_v2_router
from .evaluation import router as evaluation_v2_router
from .models import router as models_v2_router

__all__ = [
    "evaluation_v2_router",
    "models_v2_router",
    "data_v2_router",
    "analytics_v2_router",
    "config_v2_router",
]
