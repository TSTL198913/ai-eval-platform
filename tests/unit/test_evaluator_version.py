"""
评估器版本控制模块测试
"""

import pytest
import os
import tempfile
import shutil
from datetime import datetime
from src.domain.evaluator_version import (
    EvaluatorVersionManager,
    EvaluatorVersion,
    VersionStatus
)


class TestEvaluatorVersionManager:
    """评估器版本管理器测试"""

    def setup_method(self):
        """测试前准备"""
        self.temp_dir = tempfile.mkdtemp()
        self.manager = EvaluatorVersionManager(storage_path=self.temp_dir)

    def teardown_method(self):
        """测试后清理"""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_register_version(self):
        """测试注册新版本"""
        version = self.manager.register_version(
            evaluator_name="test_evaluator",
            version="1.0.0",
            code_hash="abc123",
            config={"threshold": 0.8},
            changelog="Initial version"
        )

        assert isinstance(version, EvaluatorVersion)
        assert version.evaluator_name == "test_evaluator"
        assert version.version == "1.0.0"
        assert version.code_hash == "abc123"
        assert version.status == VersionStatus.ACTIVE

    def test_register_duplicate_version_raises(self):
        """测试重复注册版本"""
        self.manager.register_version(
            evaluator_name="test_evaluator",
            version="1.0.0",
            code_hash="abc123",
            config={}
        )

        with pytest.raises(ValueError, match="already exists"):
            self.manager.register_version(
                evaluator_name="test_evaluator",
                version="1.0.0",
                code_hash="def456",
                config={}
            )

    def test_get_current_version(self):
        """测试获取当前版本"""
        self.manager.register_version(
            evaluator_name="test_evaluator",
            version="1.0.0",
            code_hash="abc123",
            config={}
        )

        current = self.manager.get_current_version("test_evaluator")
        assert current is not None
        assert current.version == "1.0.0"

    def test_get_current_version_not_exists(self):
        """测试获取不存在的版本"""
        current = self.manager.get_current_version("nonexistent")
        assert current is None

    def test_get_version_by_id(self):
        """测试通过ID获取版本"""
        version = self.manager.register_version(
            evaluator_name="test_evaluator",
            version="1.0.0",
            code_hash="abc123",
            config={}
        )

        retrieved = self.manager.get_version_by_id(version.version_id)
        assert retrieved is not None
        assert retrieved.version_id == version.version_id

    def test_get_all_versions(self):
        """测试获取所有版本"""
        self.manager.register_version("eval1", "1.0.0", "hash1", {})
        self.manager.register_version("eval1", "1.1.0", "hash2", {})
        self.manager.register_version("eval2", "1.0.0", "hash3", {})

        versions_eval1 = self.manager.get_all_versions("eval1")
        assert len(versions_eval1) == 2

        all_versions = self.manager.get_all_versions()
        assert len(all_versions) == 3

    def test_update_calibration(self):
        """测试更新校准分数"""
        self.manager.register_version(
            evaluator_name="test_evaluator",
            version="1.0.0",
            code_hash="abc123",
            config={}
        )

        updated = self.manager.update_calibration(
            evaluator_name="test_evaluator",
            calibration_score=0.85
        )

        assert updated is not None
        assert updated.calibration_score == 0.85

    def test_check_calibration_status_no_version(self):
        """测试检查校准状态 - 无版本"""
        status = self.manager.check_calibration_status("nonexistent")
        assert status["status"] == "no_version"

    def test_check_calibration_status_not_calibrated(self):
        """测试检查校准状态 - 未校准"""
        self.manager.register_version(
            evaluator_name="test_evaluator",
            version="1.0.0",
            code_hash="abc123",
            config={}
        )

        status = self.manager.check_calibration_status("test_evaluator")
        assert status["status"] == "not_calibrated"
        assert status["can_proceed"] == True  # 允许执行但会提示

    def test_check_calibration_status_calibrated(self):
        """测试检查校准状态 - 已校准"""
        self.manager.register_version(
            evaluator_name="test_evaluator",
            version="1.0.0",
            code_hash="abc123",
            config={}
        )
        self.manager.update_calibration(
            evaluator_name="test_evaluator",
            calibration_score=94.0  # 接近基准95
        )

        status = self.manager.check_calibration_status("test_evaluator")
        assert status["status"] == "calibrated"
        assert status["can_proceed"] == True

    def test_check_calibration_status_drifted(self):
        """测试检查校准状态 - 已偏离"""
        self.manager.register_version(
            evaluator_name="test_evaluator",
            version="1.0.0",
            code_hash="abc123",
            config={}
        )
        self.manager.update_calibration(
            evaluator_name="test_evaluator",
            calibration_score=70.0  # 远离基准95
        )

        status = self.manager.check_calibration_status("test_evaluator")
        assert status["status"] == "drifted"
        assert status["can_proceed"] == False

    def test_deprecate_version(self):
        """测试废弃版本"""
        version = self.manager.register_version(
            evaluator_name="test_evaluator",
            version="1.0.0",
            code_hash="abc123",
            config={}
        )

        result = self.manager.deprecate_version(version.version_id)
        assert result == True

        deprecated = self.manager.get_version_by_id(version.version_id)
        assert deprecated.status == VersionStatus.DEPRECATED

    def test_get_version_history(self):
        """测试获取版本历史"""
        self.manager.register_version("eval1", "1.0.0", "hash1", {})
        self.manager.register_version("eval1", "1.1.0", "hash2", {})
        self.manager.register_version("eval1", "2.0.0", "hash3", {})

        history = self.manager.get_version_history("eval1", limit=2)
        assert len(history) == 2
        assert history[0]["version"] == "2.0.0"  # 最新在前

    def test_version_to_dict(self):
        """测试版本序列化"""
        version = self.manager.register_version(
            evaluator_name="test_evaluator",
            version="1.0.0",
            code_hash="abc123",
            config={"key": "value"}
        )

        version_dict = version.to_dict()
        assert isinstance(version_dict, dict)
        assert version_dict["evaluator_name"] == "test_evaluator"
        assert version_dict["version"] == "1.0.0"
        assert version_dict["code_hash"] == "abc123"
        assert version_dict["config_snapshot"] == {"key": "value"}
        assert "created_at" in version_dict


class TestEvaluatorVersion:
    """评估器版本测试"""

    def test_version_creation(self):
        """测试版本创建"""
        version = EvaluatorVersion(
            version_id="v001",
            evaluator_name="test",
            version="1.0.0",
            changelog="Initial",
            code_hash="hash123",
            config_snapshot={}
        )

        assert version.version_id == "v001"
        assert version.status == VersionStatus.ACTIVE

    def test_version_with_calibration(self):
        """测试带校准分数的版本"""
        version = EvaluatorVersion(
            version_id="v001",
            evaluator_name="test",
            version="1.0.0",
            changelog="",
            code_hash="hash",
            config_snapshot={},
            calibration_score=92.5,
            calibration_threshold=5.0
        )

        assert version.calibration_score == 92.5
        assert version.calibration_threshold == 5.0
