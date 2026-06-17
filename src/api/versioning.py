"""
API版本迁移管理

支持多版本API共存：
- /api/v1/* - 旧版API（保持兼容）
- /api/v2/* - 新版API（推荐使用）

提供版本适配器，处理字段映射和默认值。
"""

from typing import Any, Dict
from fastapi import APIRouter


def create_versioned_router(prefix: str, tags: list[str]) -> APIRouter:
    """创建版本化路由"""
    return APIRouter(prefix=prefix, tags=tags)


def migrate_v1_to_v2(data: Dict[str, Any]) -> Dict[str, Any]:
    """V1字段映射到V2"""
    if "user_input" in data:
        data["input"] = data.pop("user_input")
    if "expected_output" in data:
        data["expected"] = data.pop("expected_output")
    return data


def migrate_v2_to_v1(data: Dict[str, Any]) -> Dict[str, Any]:
    """V2字段映射到V1"""
    if "input" in data:
        data["user_input"] = data.pop("input")
    if "expected" in data:
        data["expected_output"] = data.pop("expected")
    return data
