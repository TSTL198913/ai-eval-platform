"""
评估配置路由模块
提供评估配置的CRUD操作API端点
"""

import logging
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Response
from pydantic import BaseModel, Field
from starlette import status as status_module

from src.api.common import error_response, success_response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/eval-configs", tags=["评估配置"])

# 内存存储（生产环境应替换为数据库）
_eval_configs: dict[str, dict[str, Any]] = {}


class EvalConfigCreate(BaseModel):
    """创建评估配置请求"""

    name: str = Field(..., min_length=1, max_length=100, description="配置名称")
    evaluator_type: str = Field(..., min_length=1, description="评估器类型")
    config: dict[str, Any] = Field(default_factory=dict, description="配置参数")
    enabled: bool = Field(default=True, description="是否启用")


class EvalConfigUpdate(BaseModel):
    """更新评估配置请求"""

    name: str | None = Field(None, max_length=100, description="配置名称")
    evaluator_type: str | None = Field(None, description="评估器类型")
    config: dict[str, Any] | None = Field(None, description="配置参数")
    enabled: bool | None = Field(None, description="是否启用")


@router.get("")
async def get_all_configs():
    """获取所有评估配置"""
    configs = [
        {
            "id": config_id,
            "name": config["name"],
            "evaluator_type": config["evaluator_type"],
            "config": config["config"],
            "enabled": config["enabled"],
            "created_at": config["created_at"],
            "updated_at": config.get("updated_at"),
        }
        for config_id, config in _eval_configs.items()
    ]
    return success_response(configs)


@router.post("")
async def create_config(data: EvalConfigCreate, response: Response):
    """创建评估配置"""
    config_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()

    _eval_configs[config_id] = {
        "name": data.name,
        "evaluator_type": data.evaluator_type,
        "config": data.config,
        "enabled": data.enabled,
        "created_at": now,
    }

    return success_response(
        {
            "id": config_id,
            "name": data.name,
            "evaluator_type": data.evaluator_type,
            "config": data.config,
            "enabled": data.enabled,
            "created_at": now,
        }
    )


@router.get("/{config_id}")
async def get_config(config_id: str, response: Response):
    """获取单个评估配置"""
    if config_id not in _eval_configs:
        response.status_code = status_module.HTTP_404_NOT_FOUND
        return error_response(404, "配置不存在")

    config = _eval_configs[config_id]
    return success_response(
        {
            "id": config_id,
            "name": config["name"],
            "evaluator_type": config["evaluator_type"],
            "config": config["config"],
            "enabled": config["enabled"],
            "created_at": config["created_at"],
            "updated_at": config.get("updated_at"),
        }
    )


@router.put("/{config_id}")
async def update_config(config_id: str, data: EvalConfigUpdate, response: Response):
    """更新评估配置"""
    if config_id not in _eval_configs:
        response.status_code = status_module.HTTP_404_NOT_FOUND
        return error_response(404, "配置不存在")

    config = _eval_configs[config_id]
    update_data = data.model_dump(exclude_none=True)

    for key, value in update_data.items():
        if value is not None:
            config[key] = value

    config["updated_at"] = datetime.utcnow().isoformat()

    return success_response(
        {
            "id": config_id,
            "name": config["name"],
            "evaluator_type": config["evaluator_type"],
            "config": config["config"],
            "enabled": config["enabled"],
            "created_at": config["created_at"],
            "updated_at": config["updated_at"],
        }
    )


@router.delete("/{config_id}")
async def delete_config(config_id: str, response: Response):
    """删除评估配置"""
    if config_id not in _eval_configs:
        response.status_code = status_module.HTTP_404_NOT_FOUND
        return error_response(404, "配置不存在")

    del _eval_configs[config_id]
    return success_response({"message": "配置已删除"})
