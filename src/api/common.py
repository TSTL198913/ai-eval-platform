"""
API公共模块
包含响应函数、验证函数、资源获取函数
解决server.py与routes模块的循环依赖问题
"""

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# =====================================================================
# 输入验证函数
# =====================================================================


def validate_evaluator_name(name: str) -> bool:
    """验证评估器名称，防止SQL注入和特殊字符攻击"""
    if not name or not name.strip():
        return False
    if name.strip() == "/":
        return False
    pattern = r"^[a-zA-Z0-9_-]+$"
    return bool(re.match(pattern, name))


def validate_dataset_name(name: str) -> bool:
    """验证数据集名称"""
    if not name or not name.strip():
        return False
    pattern = r"^[a-zA-Z0-9_-]+$"
    return bool(re.match(pattern, name))


# =====================================================================
# 响应辅助函数
# =====================================================================


def success_response(data: Any = None, message: str = "success") -> dict[str, Any]:
    """统一成功响应格式"""
    return {"code": 0, "message": message, "data": data}


def error_response(code: int, message: str) -> dict[str, Any]:
    """统一错误响应格式"""
    return {"code": code, "message": message, "data": None}


# =====================================================================
# 资源获取函数（延迟加载）
# =====================================================================


def _get_data_service():
    """获取数据服务实例（延迟加载）"""
    from src.services.data_svc import get_data_service

    return get_data_service()


# 保留 _get_repository 作为向后兼容别名
def _get_repository():
    """获取数据库仓库实例（延迟加载）- 已弃用，请使用 _get_data_service"""
    from src.infra.db.repository import EvaluationRepository

    return EvaluationRepository()


def _get_celery_app():
    """获取Celery应用实例（延迟加载）"""
    from src.workers.celery_app import celery_app

    return celery_app


def _get_eval_case_task():
    """获取评估任务函数（延迟加载）"""
    from src.workers.tasks import eval_case_task

    return eval_case_task
