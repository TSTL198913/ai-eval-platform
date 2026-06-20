"""
评估器版本管理模块测试
测试目标：验证EvaluatorVersionManager的核心功能
核心功能：
1. 评估器版本注册
2. 版本追踪和获取
3. 校准状态检查
4. 版本废弃和历史

关键发现：（测试过程中记录）
"""

import os
import shutil
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.domain.evaluator_version import (
    EvaluatorVersion,
    EvaluatorVersionManager,
    VersionStatus,
)


class TestEvaluatorVersionCreation:
    """评估器版本创建测试"""

    def test_version_creation(self):
        """创建评估器版本"""
        version = EvaluatorVersion(
            version_id="v001",
            evaluator_name="llm_as_judge",
            version="1.0.0",
            changelog="Initial release",
            code_hash="abc123",
            config_snapshot={"threshold": 0.8},
        )

        assert version.version_id == "v001"
        assert version.evaluator_name == "llm_as_judge"
        assert version.version == "1.0.0"
        assert version.status == VersionStatus.ACTIVE

    def test_version_to_dict(self):
        """版本转字典"""
        version = EvaluatorVersion(
            version_id="v001",
            evaluator_name="llm_as_judge",
            version="1.0.0",
            changelog="Initial release",
            code_hash="abc123",
            config_snapshot={},
        )

        result = version.to_dict()

        assert result["version_id"] == "v001"
        assert result["evaluator_name"] == "llm_as_judge"
        assert result["status"] == "active"


class TestEvaluatorVersionManager:
    """版本管理器测试"""

    @pytest.fixture
    def manager(self):
        """创建测试用版本管理器"""
        temp_dir = tempfile.mkdtemp()
        manager = EvaluatorVersionManager(storage_path=temp_dir)
        manager._versions = {}  # 清空
        manager._current_codes = {}
        yield manager
        shutil.rmtree(temp_dir, ignore_errors=True)

    def test_register_version(self, manager):
        """注册新版本"""
        version = manager.register_version(
            evaluator_name="test_evaluator",
            version="1.0.0",
            code_hash="hash123",
            config={"setting": "value"},
            changelog="First version",
        )

        assert version is not None
        assert version.evaluator_name == "test_evaluator"
        assert version.version == "1.0.0"
        assert version.status == VersionStatus.ACTIVE

    def test_register_duplicate_version_raises(self, manager):
        """重复注册版本应抛出异常"""
        manager.register_version(
            evaluator_name="test_evaluator", version="1.0.0", code_hash="hash1", config={}
        )

        with pytest.raises(ValueError, match="already exists"):
            manager.register_version(
                evaluator_name="test_evaluator",
                version="1.0.0",  # 相同版本
                code_hash="hash2",
                config={},
            )

    def test_register_multiple_versions_same_evaluator(self, manager):
        """同一评估器可注册多个版本"""
        v1 = manager.register_version(
            evaluator_name="test_evaluator", version="1.0.0", code_hash="hash1", config={}
        )
        v2 = manager.register_version(
            evaluator_name="test_evaluator", version="1.1.0", code_hash="hash2", config={}
        )

        assert v1.version != v2.version
        assert v1.version_id != v2.version_id

    def test_get_current_version(self, manager):
        """获取当前版本"""
        manager.register_version(
            evaluator_name="test_evaluator", version="1.0.0", code_hash="hash1", config={}
        )
        manager.register_version(
            evaluator_name="test_evaluator", version="1.1.0", code_hash="hash2", config={}
        )

        current = manager.get_current_version("test_evaluator")

        assert current is not None
        assert current.version == "1.1.0"  # 最新版本

    def test_get_current_version_not_registered(self, manager):
        """未注册的评估器返回None"""
        current = manager.get_current_version("nonexistent_evaluator")
        assert current is None

    def test_get_all_versions(self, manager):
        """获取所有版本"""
        manager.register_version("eval1", "1.0.0", "hash1", {})
        manager.register_version("eval1", "1.1.0", "hash2", {})
        manager.register_version("eval2", "1.0.0", "hash3", {})

        versions = manager.get_all_versions("eval1")

        assert len(versions) == 2
        assert all(v.evaluator_name == "eval1" for v in versions)


class TestCalibrationStatusCheck:
    """校准状态检查测试"""

    @pytest.fixture
    def manager(self):
        """创建测试用版本管理器"""
        temp_dir = tempfile.mkdtemp()
        manager = EvaluatorVersionManager(storage_path=temp_dir)
        manager._versions = {}
        manager._current_codes = {}
        yield manager
        shutil.rmtree(temp_dir, ignore_errors=True)

    def test_check_calibration_status_no_version(self, manager):
        """无版本时应返回no_version"""
        status = manager.check_calibration_status("nonexistent")

        assert status["status"] == "no_version"

    def test_check_calibration_status_not_calibrated(self, manager):
        """未校准时应返回not_calibrated"""
        manager.register_version(
            evaluator_name="test_evaluator", version="1.0.0", code_hash="hash1", config={}
        )

        status = manager.check_calibration_status("test_evaluator")

        assert status["status"] == "not_calibrated"
        assert status["can_proceed"] is True  # 未校准但允许执行

    def test_check_calibration_status_calibrated(self, manager):
        """校准通过时应返回calibrated"""
        manager.register_version(
            evaluator_name="test_evaluator", version="1.0.0", code_hash="hash1", config={}
        )
        manager.update_calibration("test_evaluator", 94.0)  # 接近基线95

        status = manager.check_calibration_status("test_evaluator")

        assert status["status"] == "calibrated"
        assert status["can_proceed"] is True

    def test_check_calibration_status_drifted(self, manager):
        """漂移时应返回drifted"""
        manager.register_version(
            evaluator_name="test_evaluator", version="1.0.0", code_hash="hash1", config={}
        )
        manager.update_calibration("test_evaluator", 80.0)  # 偏离基线95

        status = manager.check_calibration_status("test_evaluator")

        assert status["status"] == "drifted"
        assert status["can_proceed"] is False  # 漂移拒绝执行

    def test_check_calibration_status_threshold_calculation(self, manager):
        """校准阈值计算 - 使用默认阈值"""
        manager.register_version(
            evaluator_name="test_evaluator",
            version="1.0.0",
            code_hash="hash1",
            config={},  # 使用默认阈值（5%）
        )
        # 基线95，评估器85，偏差10.5%
        manager.update_calibration("test_evaluator", 85.0)

        status = manager.check_calibration_status("test_evaluator")

        # 默认阈值为5%
        assert status["threshold"] == 5.0  # 使用默认阈值
        assert status["deviation_pct"] == pytest.approx(10.53, 0.1)
        assert status["status"] == "drifted"


class TestVersionDeprecation:
    """版本废弃测试"""

    @pytest.fixture
    def manager(self):
        """创建测试用版本管理器"""
        temp_dir = tempfile.mkdtemp()
        manager = EvaluatorVersionManager(storage_path=temp_dir)
        manager._versions = {}
        manager._current_codes = {}
        yield manager
        shutil.rmtree(temp_dir, ignore_errors=True)

    def test_deprecate_version(self, manager):
        """废弃版本"""
        version = manager.register_version(
            evaluator_name="test_evaluator", version="1.0.0", code_hash="hash1", config={}
        )

        result = manager.deprecate_version(version.version_id)

        assert result is True
        assert manager._versions[version.version_id].status == VersionStatus.DEPRECATED

    def test_deprecate_nonexistent_version(self, manager):
        """废弃不存在的版本应返回False"""
        result = manager.deprecate_version("nonexistent_id")
        assert result is False


class TestVersionHistory:
    """版本历史测试"""

    @pytest.fixture
    def manager(self):
        """创建测试用版本管理器"""
        temp_dir = tempfile.mkdtemp()
        manager = EvaluatorVersionManager(storage_path=temp_dir)
        manager._versions = {}
        manager._current_codes = {}
        yield manager
        shutil.rmtree(temp_dir, ignore_errors=True)

    def test_get_version_history(self, manager):
        """获取版本历史"""
        manager.register_version("test_evaluator", "1.0.0", "hash1", {}, "v1 changelog")
        manager.register_version("test_evaluator", "1.1.0", "hash2", {}, "v2 changelog")
        manager.register_version("test_evaluator", "1.2.0", "hash3", {}, "v3 changelog")

        history = manager.get_version_history("test_evaluator")

        assert len(history) == 3
        assert history[0]["version"] == "1.2.0"  # 最新在前
        assert history[1]["version"] == "1.1.0"

    def test_get_version_history_with_limit(self, manager):
        """获取版本历史（限制数量）"""
        for i in range(5):
            manager.register_version("test_evaluator", f"1.{i}.0", f"hash{i}", {})

        history = manager.get_version_history("test_evaluator", limit=3)

        assert len(history) == 3


class TestCalibrationUpdate:
    """校准更新测试"""

    @pytest.fixture
    def manager(self):
        """创建测试用版本管理器"""
        temp_dir = tempfile.mkdtemp()
        manager = EvaluatorVersionManager(storage_path=temp_dir)
        manager._versions = {}
        manager._current_codes = {}
        yield manager
        shutil.rmtree(temp_dir, ignore_errors=True)

    def test_update_calibration(self, manager):
        """更新校准分数"""
        manager.register_version(
            evaluator_name="test_evaluator", version="1.0.0", code_hash="hash1", config={}
        )

        updated = manager.update_calibration("test_evaluator", 90.0)

        assert updated is not None
        assert updated.calibration_score == 90.0

    def test_update_calibration_by_code_hash(self, manager):
        """通过code_hash更新校准"""
        manager.register_version(
            evaluator_name="test_evaluator", version="1.0.0", code_hash="hash1", config={}
        )

        updated = manager.update_calibration("test_evaluator", 92.0, code_hash="hash1")

        assert updated.calibration_score == 92.0

    def test_update_calibration_nonexistent(self, manager):
        """更新不存在的评估器应返回None"""
        result = manager.update_calibration("nonexistent", 90.0)
        assert result is None


class TestVersionStatus:
    """版本状态枚举测试"""

    def test_version_status_values(self):
        """版本状态枚举值"""
        assert VersionStatus.ACTIVE.value == "active"
        assert VersionStatus.DEPRECATED.value == "deprecated"
        assert VersionStatus.RECALIBRATING.value == "recalibrating"


# 关键发现：
# 1. 版本管理器支持同一评估器的多个版本
# 2. get_current_version返回最新版本
# 3. 校准基准分数为95，阈值默认5%
# 4. 漂移时can_proceed=False，拒绝执行
# 5. 版本可被废弃（deprecated）
