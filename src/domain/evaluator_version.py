"""
评估器版本控制模块
为每个评估器记录赋予版本号，确保历史评测记录的可追溯性
"""

import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from enum import Enum

from src.infra.db.repository import EvaluationRepository


class VersionStatus(Enum):
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    RECALIBRATING = "recalibrating"


@dataclass
class EvaluatorVersion:
    """评估器版本"""
    version_id: str
    evaluator_name: str
    version: str  # 语义化版本，如 "1.0.0"
    changelog: str
    code_hash: str  # 代码哈希，用于唯一标识
    config_snapshot: Dict[str, Any]  # 配置快照
    calibration_score: Optional[float] = None  # 最后校准分数
    calibration_threshold: float = 5.0  # 校准偏差阈值(%)
    status: VersionStatus = VersionStatus.ACTIVE
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    created_by: str = "system"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version_id": self.version_id,
            "evaluator_name": self.evaluator_name,
            "version": self.version,
            "changelog": self.changelog,
            "code_hash": self.code_hash,
            "config_snapshot": self.config_snapshot,
            "calibration_score": self.calibration_score,
            "calibration_threshold": self.calibration_threshold,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "created_by": self.created_by
        }


class EvaluatorVersionManager:
    """评估器版本管理器"""

    def __init__(self, storage_path: str = "data/evaluator_versions"):
        self._versions: Dict[str, EvaluatorVersion] = {}
        self._storage_path = storage_path
        self._current_codes: Dict[str, str] = {}  # evaluator_name -> code_hash
        os.makedirs(storage_path, exist_ok=True)
        self._load_versions()

    def _load_versions(self):
        """从文件加载版本数据"""
        index_file = os.path.join(self._storage_path, "index.json")
        if os.path.exists(index_file):
            try:
                with open(index_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for vid, vdata in data.items():
                        vdata["created_at"] = datetime.fromisoformat(vdata["created_at"])
                        vdata["updated_at"] = datetime.fromisoformat(vdata["updated_at"])
                        vdata["status"] = VersionStatus(vdata["status"])
                        self._versions[vid] = EvaluatorVersion(**vdata)

                # 加载当前代码哈希
                hash_file = os.path.join(self._storage_path, "codes.json")
                if os.path.exists(hash_file):
                    with open(hash_file, "r", encoding="utf-8") as f:
                        self._current_codes = json.load(f)
            except Exception as e:
                print(f"Failed to load versions: {e}")

    def _save_versions(self):
        """保存版本数据"""
        index_file = os.path.join(self._storage_path, "index.json")
        data = {vid: v.to_dict() for vid, v in self._versions.items()}
        with open(index_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        hash_file = os.path.join(self._storage_path, "codes.json")
        with open(hash_file, "w", encoding="utf-8") as f:
            json.dump(self._current_codes, f)

    def register_version(
        self,
        evaluator_name: str,
        version: str,
        code_hash: str,
        config: Dict[str, Any],
        changelog: str = "",
        created_by: str = "system"
    ) -> EvaluatorVersion:
        """注册新的评估器版本"""
        import uuid
        version_id = str(uuid.uuid4())[:8]

        # 检查是否已存在相同版本
        for v in self._versions.values():
            if v.evaluator_name == evaluator_name and v.version == version:
                raise ValueError(f"Version {version} already exists for {evaluator_name}")

        evaluator_version = EvaluatorVersion(
            version_id=version_id,
            evaluator_name=evaluator_name,
            version=version,
            changelog=changelog,
            code_hash=code_hash,
            config_snapshot=config,
            created_by=created_by
        )

        self._versions[version_id] = evaluator_version
        self._current_codes[evaluator_name] = code_hash
        self._save_versions()

        return evaluator_version

    def get_current_version(self, evaluator_name: str) -> Optional[EvaluatorVersion]:
        """获取评估器当前版本"""
        code_hash = self._current_codes.get(evaluator_name)
        if not code_hash:
            # 返回该评估器的最新版本
            versions = [v for v in self._versions.values() if v.evaluator_name == evaluator_name]
            if versions:
                return max(versions, key=lambda x: x.created_at)
            return None

        for v in self._versions.values():
            if v.evaluator_name == evaluator_name and v.code_hash == code_hash:
                return v
        return None

    def get_version_by_id(self, version_id: str) -> Optional[EvaluatorVersion]:
        """通过ID获取版本"""
        return self._versions.get(version_id)

    def get_all_versions(self, evaluator_name: str = None) -> List[EvaluatorVersion]:
        """获取所有版本"""
        versions = list(self._versions.values())
        if evaluator_name:
            versions = [v for v in versions if v.evaluator_name == evaluator_name]
        return sorted(versions, key=lambda x: x.created_at, reverse=True)

    def update_calibration(
        self,
        evaluator_name: str,
        calibration_score: float,
        code_hash: str = None
    ) -> Optional[EvaluatorVersion]:
        """更新校准分数"""
        if code_hash:
            for v in self._versions.values():
                if v.evaluator_name == evaluator_name and v.code_hash == code_hash:
                    v.calibration_score = calibration_score
                    v.updated_at = datetime.utcnow()
                    self._save_versions()
                    return v
        else:
            current = self.get_current_version(evaluator_name)
            if current:
                current.calibration_score = calibration_score
                current.updated_at = datetime.utcnow()
                self._save_versions()
                return current
        return None

    def check_calibration_status(self, evaluator_name: str) -> Dict[str, Any]:
        """检查校准状态"""
        current = self.get_current_version(evaluator_name)
        if not current:
            return {"status": "no_version", "message": "未注册版本"}

        if current.calibration_score is None:
            return {
                "status": "not_calibrated",
                "message": "尚未校准",
                "version_id": current.version_id,
                "can_proceed": True  # 未校准但允许执行
            }

        # 计算与基准的偏差
        baseline_score = 95.0  # 默认基准分数
        deviation = abs(current.calibration_score - baseline_score)
        deviation_pct = (deviation / baseline_score) * 100

        is_calibrated = deviation_pct <= current.calibration_threshold

        return {
            "status": "calibrated" if is_calibrated else "drifted",
            "message": "校准正常" if is_calibrated else "评估器偏离校准区间",
            "version_id": current.version_id,
            "calibration_score": current.calibration_score,
            "baseline_score": baseline_score,
            "deviation_pct": round(deviation_pct, 2),
            "threshold": current.calibration_threshold,
            "can_proceed": is_calibrated
        }

    def deprecate_version(self, version_id: str, reason: str = "") -> bool:
        """废弃版本"""
        version = self._versions.get(version_id)
        if version:
            version.status = VersionStatus.DEPRECATED
            version.updated_at = datetime.utcnow()
            self._save_versions()
            return True
        return False

    def get_version_history(self, evaluator_name: str, limit: int = 10) -> List[Dict[str, Any]]:
        """获取版本历史"""
        versions = self.get_all_versions(evaluator_name)[:limit]
        return [
            {
                "version": v.version,
                "version_id": v.version_id,
                "changelog": v.changelog,
                "calibration_score": v.calibration_score,
                "status": v.status.value,
                "created_at": v.created_at.isoformat()
            }
            for v in versions
        ]


# 全局实例
evaluator_version_manager = EvaluatorVersionManager()
