"""Rubric版本控制模块（Rubric Versioning）

2026工业级标准实现：
1. 版本标识 - {rubric_type}-v{major}.{minor}.{patch}-{hash}
2. 变更日志规范 - version/date/author/type/description/impact/rollback_to
3. 自动回滚机制 - 漂移>15%触发回滚
4. 版本存储和管理 - 保存每个版本的完整配置和校准数据

版本标识格式：
    {rubric_type}-v{major}.{minor}.{patch}-{hash}

示例：
    customer_service-v1.0.0-a3f2c1
    code_review-v2.1.0-b7d4e9
"""

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class ChangeType(Enum):
    """变更类型枚举"""

    ADD = "ADD"
    MODIFY = "MODIFY"
    DELETE = "DELETE"
    FIX = "FIX"


@dataclass
class ChangeLogEntry:
    """变更日志条目"""

    version: str
    date: str
    author: str
    type: ChangeType
    description: str
    impact: str = ""
    rollback_to: str | None = None


@dataclass
class RubricVersion:
    """Rubric版本"""

    rubric_type: str
    major: int
    minor: int
    patch: int
    hash: str
    config: dict[str, Any]
    changelog: list[ChangeLogEntry] = field(default_factory=list)
    calibration_data: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    is_active: bool = False


class RubricVersionManager:
    """Rubric版本管理器"""

    ROLLBACK_THRESHOLD = 0.15

    def __init__(self):
        """初始化版本管理器"""
        self.versions: dict[str, list[RubricVersion]] = {}
        self._load_default_rubrics()

    def _generate_hash(self, config: dict[str, Any]) -> str:
        """生成配置的哈希值"""
        config_str = json.dumps(config, sort_keys=True, ensure_ascii=False)
        return hashlib.md5(config_str.encode()).hexdigest()[:6]

    def _format_version(
        self, rubric_type: str, major: int, minor: int, patch: int, hash_str: str
    ) -> str:
        """格式化版本标识"""
        return f"{rubric_type}-v{major}.{minor}.{patch}-{hash_str}"

    def _parse_version(self, version_str: str) -> dict[str, Any] | None:
        """解析版本标识"""
        import re

        match = re.match(r"^([^-]+)-v(\d+)\.(\d+)\.(\d+)-([a-f0-9]+)$", version_str)
        if not match:
            return None

        return {
            "rubric_type": match.group(1),
            "major": int(match.group(2)),
            "minor": int(match.group(3)),
            "patch": int(match.group(4)),
            "hash": match.group(5),
        }

    def _load_default_rubrics(self):
        """加载默认Rubrics"""

        default_configs = {
            "customer_service": {
                "dimensions": ["accuracy", "relevance", "safety", "coherence", "completeness"],
                "weights": {
                    "accuracy": 0.25,
                    "relevance": 0.25,
                    "safety": 0.20,
                    "coherence": 0.15,
                    "completeness": 0.15,
                },
                "score_levels": {
                    "excellent": (90, 100),
                    "good": (75, 89),
                    "acceptable": (60, 74),
                    "poor": (40, 59),
                    "very_poor": (0, 39),
                },
            },
            "code_review": {
                "dimensions": ["accuracy", "safety", "coherence", "completeness", "conciseness"],
                "weights": {
                    "accuracy": 0.30,
                    "safety": 0.25,
                    "coherence": 0.20,
                    "completeness": 0.15,
                    "conciseness": 0.10,
                },
                "score_levels": {
                    "excellent": (90, 100),
                    "good": (75, 89),
                    "acceptable": (60, 74),
                    "poor": (40, 59),
                    "very_poor": (0, 39),
                },
            },
            "content_safety": {
                "dimensions": ["safety", "relevance"],
                "weights": {
                    "safety": 0.70,
                    "relevance": 0.30,
                },
                "risk_levels": {
                    "critical": (0.0, 0.2),
                    "high": (0.2, 0.4),
                    "medium": (0.4, 0.6),
                    "low": (0.6, 0.8),
                    "safe": (0.8, 1.0),
                },
            },
        }

        for rubric_type, config in default_configs.items():
            hash_str = self._generate_hash(config)
            version = RubricVersion(
                rubric_type=rubric_type,
                major=1,
                minor=0,
                patch=0,
                hash=hash_str,
                config=config,
                changelog=[
                    ChangeLogEntry(
                        version=self._format_version(rubric_type, 1, 0, 0, hash_str),
                        date=datetime.now().isoformat(),
                        author="AI评测专家组",
                        type=ChangeType.ADD,
                        description=f"初始化{rubric_type} Rubric配置",
                    )
                ],
                created_at=datetime.now().isoformat(),
                is_active=True,
            )

            if rubric_type not in self.versions:
                self.versions[rubric_type] = []
            self.versions[rubric_type].append(version)

    def create_version(
        self,
        rubric_type: str,
        config: dict[str, Any],
        author: str,
        description: str,
        change_type: ChangeType = ChangeType.MODIFY,
        impact: str = "",
    ) -> str:
        """创建新版本

        Args:
            rubric_type: Rubric类型
            config: 配置内容
            author: 变更人
            description: 变更描述
            change_type: 变更类型
            impact: 影响范围

        Returns:
            新版本标识
        """
        existing_versions = self.versions.get(rubric_type, [])

        if existing_versions:
            latest = existing_versions[-1]
            major, minor, patch = latest.major, latest.minor, latest.patch

            if change_type in (ChangeType.ADD, ChangeType.FIX):
                patch += 1
            elif change_type == ChangeType.MODIFY:
                minor += 1
            elif change_type == ChangeType.DELETE:
                major += 1
        else:
            major, minor, patch = 1, 0, 0

        hash_str = self._generate_hash(config)
        version_str = self._format_version(rubric_type, major, minor, patch, hash_str)

        rollback_to = existing_versions[-1].version if existing_versions else None

        new_version = RubricVersion(
            rubric_type=rubric_type,
            major=major,
            minor=minor,
            patch=patch,
            hash=hash_str,
            config=config,
            changelog=[
                ChangeLogEntry(
                    version=version_str,
                    date=datetime.now().isoformat(),
                    author=author,
                    type=change_type,
                    description=description,
                    impact=impact,
                    rollback_to=rollback_to,
                )
            ]
            + (existing_versions[-1].changelog if existing_versions else []),
            created_at=datetime.now().isoformat(),
            is_active=True,
        )

        if rubric_type not in self.versions:
            self.versions[rubric_type] = []

        for v in self.versions[rubric_type]:
            v.is_active = False

        self.versions[rubric_type].append(new_version)

        logger.info(f"创建新Rubric版本: {version_str}")
        return version_str

    def get_version(self, rubric_type: str, version_str: str | None = None) -> RubricVersion | None:
        """获取指定版本

        Args:
            rubric_type: Rubric类型
            version_str: 版本标识，默认为最新版本

        Returns:
            RubricVersion对象
        """
        versions = self.versions.get(rubric_type, [])
        if not versions:
            return None

        if version_str:
            for v in versions:
                if (
                    self._format_version(v.rubric_type, v.major, v.minor, v.patch, v.hash)
                    == version_str
                ):
                    return v
            return None

        return versions[-1]

    def get_active_version(self, rubric_type: str) -> RubricVersion | None:
        """获取当前激活版本"""
        versions = self.versions.get(rubric_type, [])
        for v in reversed(versions):
            if v.is_active:
                return v
        return versions[-1] if versions else None

    def rollback(self, rubric_type: str, target_version_str: str | None = None) -> bool:
        """回滚到指定版本

        Args:
            rubric_type: Rubric类型
            target_version_str: 目标版本标识，默认为上一个版本

        Returns:
            是否回滚成功
        """
        versions = self.versions.get(rubric_type, [])
        if len(versions) < 2:
            logger.warning(f"没有可回滚的版本: {rubric_type}")
            return False

        if target_version_str:
            target_index = None
            for i, v in enumerate(versions):
                if (
                    self._format_version(v.rubric_type, v.major, v.minor, v.patch, v.hash)
                    == target_version_str
                ):
                    target_index = i
                    break

            if target_index is None:
                logger.warning(f"目标版本不存在: {target_version_str}")
                return False
        else:
            target_index = len(versions) - 2

        for v in versions:
            v.is_active = False

        versions[target_index].is_active = True

        target_version = versions[target_index]
        version_str = self._format_version(
            target_version.rubric_type,
            target_version.major,
            target_version.minor,
            target_version.patch,
            target_version.hash,
        )

        logger.info(f"回滚Rubric版本: {rubric_type} -> {version_str}")
        return True

    def auto_rollback_if_needed(self, rubric_type: str, drift_score: float) -> bool:
        """根据漂移分数自动回滚

        Args:
            rubric_type: Rubric类型
            drift_score: 漂移分数（0-1）

        Returns:
            是否触发回滚
        """
        if drift_score > self.ROLLBACK_THRESHOLD:
            logger.warning(
                f"检测到评分漂移 {drift_score:.2f} > 阈值 {self.ROLLBACK_THRESHOLD}，自动回滚"
            )
            return self.rollback(rubric_type)
        return False

    def save_calibration_data(
        self, rubric_type: str, version_str: str, calibration_data: dict[str, Any]
    ):
        """保存校准数据"""
        version = self.get_version(rubric_type, version_str)
        if version:
            version.calibration_data = calibration_data
            logger.info(f"保存校准数据: {version_str}")

    def get_changelog(self, rubric_type: str) -> list[dict[str, Any]]:
        """获取变更日志"""
        versions = self.versions.get(rubric_type, [])
        changelog = []

        for v in reversed(versions):
            if v.changelog:
                changelog.append(
                    {
                        "version": self._format_version(
                            v.rubric_type, v.major, v.minor, v.patch, v.hash
                        ),
                        "date": v.changelog[0].date,
                        "author": v.changelog[0].author,
                        "type": v.changelog[0].type.value,
                        "description": v.changelog[0].description,
                        "impact": v.changelog[0].impact,
                        "rollback_to": v.changelog[0].rollback_to,
                        "is_active": v.is_active,
                    }
                )

        return changelog

    def list_versions(self, rubric_type: str) -> list[str]:
        """列出所有版本"""
        versions = self.versions.get(rubric_type, [])
        return [
            self._format_version(v.rubric_type, v.major, v.minor, v.patch, v.hash) for v in versions
        ]


rubric_version_manager = RubricVersionManager()
