"""
评估器配置路由模块
包含评估器列表查询、详情查询、配置管理等端点
"""

import json
import logging
import time

from fastapi import APIRouter, Response, status

from src.api.common import (
    _get_data_service,
    error_response,
    success_response,
    validate_evaluator_name,
)
from src.domain.evaluators import EVALUATOR_REGISTRY
from src.schemas.schemas import EvalConfigRequest

router = APIRouter(prefix="/api/v1", tags=["评估器"])

logger = logging.getLogger(__name__)


@router.get("/evaluators")
async def get_all_evaluators():
    """获取所有评估器列表"""
    evaluators = []
    for name, cls in EVALUATOR_REGISTRY.items():
        evaluators.append(
            {
                "name": name,
                "class_name": cls.__name__,
                "docstring": cls.__doc__ or "No description",
                "module": cls.__module__,
            }
        )
    return success_response(evaluators)


@router.get("/evaluators/{name}")
async def get_evaluator_detail(name: str, response: Response):
    """获取评估器详情"""
    # 输入验证：防止SQL注入和特殊字符攻击
    if not validate_evaluator_name(name):
        response.status_code = status.HTTP_404_NOT_FOUND
        return error_response(404, "Invalid evaluator name format")

    try:
        if name not in EVALUATOR_REGISTRY:
            response.status_code = status.HTTP_404_NOT_FOUND
            return error_response(404, f"Evaluator '{name}' not found")

        evaluator_cls = EVALUATOR_REGISTRY[name]
        return success_response(
            {
                "name": name,
                "class_name": evaluator_cls.__name__,
                "docstring": evaluator_cls.__doc__ or "No description",
                "module": evaluator_cls.__module__,
            }
        )
    except Exception as e:
        logger.error("Failed to get evaluator info: {0}", e)
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return error_response(500, "获取评估器信息失败")


# ==================== 评估配置管理 ====================
@router.post("/eval-configs")
async def save_eval_config(data: EvalConfigRequest):
    """保存评估配置"""
    try:
        config_id = data.id or f"config_{int(time.time())}"

        svc = _get_data_service()
        # 保存配置到数据库
        record = {
            "case_id": config_id,
            "adapter_name": f"config:{data.evaluator_type}",
            "model_name": "config",
            "status": "config",
            "latency_ms": 0,
            "response_data": {
                "name": data.name,
                "evaluator_type": data.evaluator_type,
                "config": data.config,
                "enabled": data.enabled,
            },
        }
        svc.create(record)

        return success_response(
            {
                "id": config_id,
                "name": data.name,
                "evaluator_type": data.evaluator_type,
                "enabled": data.enabled,
            }
        )
    except Exception as e:
        logger.error(f"Save eval config failed: {e}")
        return error_response(500, "保存配置失败")


@router.get("/eval-configs")
async def get_eval_configs():
    """获取所有评估配置"""
    try:
        svc = _get_data_service()
        records = svc.get_all(limit=100)
        # 过滤出配置记录
        configs = []
        for r in records:
            if r.get("adapter_name", "").startswith("config:"):
                response_data = r.get("response_data")
                if isinstance(response_data, str):
                    try:
                        response_data = json.loads(response_data)
                    except json.JSONDecodeError:
                        response_data = {}
                configs.append(
                    {
                        "id": r.get("case_id"),
                        "name": (
                            response_data.get("name", "未命名")
                            if isinstance(response_data, dict)
                            else "未命名"
                        ),
                        "evaluator_type": (
                            response_data.get("evaluator_type", "")
                            if isinstance(response_data, dict)
                            else ""
                        ),
                        "config": (
                            response_data.get("config", {})
                            if isinstance(response_data, dict)
                            else {}
                        ),
                        "enabled": (
                            response_data.get("enabled", True)
                            if isinstance(response_data, dict)
                            else True
                        ),
                    }
                )
        return success_response(configs)
    except Exception as e:
        logger.error(f"Get eval configs failed: {e}")
        return error_response(500, "获取配置列表失败")


@router.delete("/eval-configs/{config_id}")
async def delete_eval_config(config_id: str, response: Response):
    """删除评估配置"""
    try:
        svc = _get_data_service()
        # 根据case_id查找并删除
        records = svc.get_all(limit=1000)
        for r in records:
            if r.get("case_id") == config_id and r.get("adapter_name", "").startswith("config:"):
                svc.delete(r.get("id"))
                return success_response({"deleted": True})
        response.status_code = status.HTTP_404_NOT_FOUND
        return error_response(404, "配置不存在")
    except Exception as e:
        logger.error(f"Delete eval config failed: {e}")
        return error_response(500, "删除配置失败")
