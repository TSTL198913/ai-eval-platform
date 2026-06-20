"""
模型版本管理

支持：
- 多模型版本注册
- 版本对比评测
- 模型血缘追踪
"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class ModelVersion(BaseModel):
    """模型版本"""

    version_id: str
    model_name: str
    version: str
    base_model: str | None = None
    training_data: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ModelVersionRegistry:
    """模型版本注册表"""

    _instance: Optional["ModelVersionRegistry"] = None
    _models: dict[str, list[ModelVersion]] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def register(self, model_version: ModelVersion) -> None:
        """注册模型版本"""
        if model_version.model_name not in self._models:
            self._models[model_version.model_name] = []
        self._models[model_version.model_name].append(model_version)

    def get_versions(self, model_name: str) -> list[ModelVersion]:
        """获取模型所有版本"""
        return self._models.get(model_name, [])

    def get_latest(self, model_name: str) -> ModelVersion | None:
        """获取最新版本"""
        versions = self.get_versions(model_name)
        if not versions:
            return None
        return max(versions, key=lambda v: v.created_at)

    def compare_versions(self, model_name: str, v1: str, v2: str) -> dict[str, Any]:
        """对比两个版本"""
        versions = {v.version: v for v in self.get_versions(model_name)}
        if v1 not in versions or v2 not in versions:
            return {}
        return {
            "model_name": model_name,
            "v1": versions[v1].model_dump(),
            "v2": versions[v2].model_dump(),
            "differences": self._compute_diff(versions[v1], versions[v2]),
        }

    def _compute_diff(self, v1: ModelVersion, v2: ModelVersion) -> dict[str, Any]:
        """计算版本差异"""
        return {
            "version_changed": v1.version != v2.version,
            "base_model_changed": v1.base_model != v2.base_model,
            "training_data_changed": v1.training_data != v2.training_data,
            "metadata_diff": {
                k: (v1.metadata.get(k), v2.metadata.get(k))
                for k in set(v1.metadata.keys()) | set(v2.metadata.keys())
                if v1.metadata.get(k) != v2.metadata.get(k)
            },
        }


model_version_registry = ModelVersionRegistry()
