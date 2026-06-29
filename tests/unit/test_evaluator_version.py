"""
评估器版本管理单元测试
测试目标：验证 EvaluatorVersionManager 的版本注册、查询、校准、废弃功能
关键发现：
- 版本注册支持语义化版本号和代码哈希
- 校准状态自动计算偏差百分比
- 废弃版本标记为 DEPRECATED 状态
- 支持版本历史查询，按创建时间倒序
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


class TestEvaluatorVersion:
    """EvaluatorVersion 数据类测试"""

    def test_version_creation_minimal(self):
        """最小化版本创建应正常"""
        v = EvaluatorVersion(
            version_id="v001",
            evaluator_name="security",
            version="1.0.0",
            changelog="Initial release",
            code_hash="abc123",
            config_snapshot={"threshold": 0.5},
        )
        assert v.version_id == "v001"
        assert v.evaluator_name == "security"
        assert v.version == "1.0.0"
        assert v.code_hash == "abc123"
        assert v.calibration_score is None
        assert v.calibration_threshold == 5.0
        assert v.status == VersionStatus.ACTIVE
        assert v.created_by == "system"

    def test_version_creation_full(self):
        """完整版创建应正常"""
        v = EvaluatorVersion(
            version_id="v002",
            evaluator_name="llm_as_judge",
            version="2.1.0",
            changelog="Added new dimensions",
            code_hash="def456",
            config_snapshot={"model": "gpt-4", "temperature": 0.7},
            calibration_score=92.5,
            calibration_threshold=3.0,
            status=VersionStatus.DEPRECATED,
            created_by="alice",
        )
        assert v.calibration_score == 92.5
        assert v.calibration_threshold == 3.0
        assert v.status == VersionStatus.DEPRECATED
        assert v.created_by == "alice"

    def test_to_dict_returns_all_fields(self):
        """to_dict 应返回所有字段"""
        v = EvaluatorVersion(
            version_id="v003",
            evaluator_name="security",
            version="1.0.0",
            changelog="Test",
            code_hash="hash1",
            config_snapshot={"key": "value"},
            calibration_score=90.0,
        )
        d = v.to_dict()
        assert isinstance(d, dict)
        assert d["version_id"] == "v003"
        assert d["evaluator_name"] == "security"
        assert d["version"] == "1.0.0"
        assert d["code_hash"] == "hash1"
        assert d["calibration_score"] == 90.0
        assert d["status"] == "active"
        assert "created_at" in d
        assert "updated_at" in d


class TestEvaluatorVersionManagerPositive:
    """正向测试 - 版本管理正常操作"""

    @pytest.fixture
    def temp_dir(self):
        tmpdir = tempfile.mkdtemp()
        yield tmpdir
        shutil.rmtree(tmpdir, ignore_errors=True)

    @pytest.fixture
    def manager(self, temp_dir):
        return EvaluatorVersionManager(storage_path=temp_dir)

    def test_register_version(self, manager):
        """注册版本应成功"""
        version = manager.register_version(
            evaluator_name="security",
            version="1.0.0",
            code_hash="abc123",
            config={"threshold": 0.5},
            changelog="Initial release",
            created_by="admin",
        )
        assert version is not None
        assert version.version_id is not None
        assert len(version.version_id) == 8
        assert version.evaluator_name == "security"
        assert version.version == "1.0.0"
        assert version.changelog == "Initial release"
        assert version.code_hash == "abc123"
        assert version.config_snapshot == {"threshold": 0.5}
        assert version.created_by == "admin"
        assert version.status == VersionStatus.ACTIVE

    def test_get_current_version(self, manager):
        """获取当前版本应返回最新注册的版本"""
        manager.register_version(
            evaluator_name="security",
            version="1.0.0",
            code_hash="hash1",
            config={},
        )
        current = manager.get_current_version("security")
        assert current is not None
        assert current.version == "1.0.0"
        assert current.code_hash == "hash1"

    def test_get_version_by_id(self, manager):
        """通过ID获取版本应正确"""
        v = manager.register_version(
            evaluator_name="security",
            version="1.0.0",
            code_hash="hash1",
            config={},
        )
        retrieved = manager.get_version_by_id(v.version_id)
        assert retrieved is not None
        assert retrieved.version_id == v.version_id
        assert retrieved.version == "1.0.0"

    def test_get_all_versions(self, manager):
        """获取所有版本应返回列表"""
        manager.register_version("eval_a", "1.0.0", "hash1", {})
        manager.register_version("eval_a", "2.0.0", "hash2", {})
        manager.register_version("eval_b", "1.0.0", "hash3", {})

        all_versions = manager.get_all_versions()
        assert len(all_versions) == 3

        eval_a_versions = manager.get_all_versions("eval_a")
        assert len(eval_a_versions) == 2
        # 按创建时间倒序
        assert eval_a_versions[0].version == "2.0.0"
        assert eval_a_versions[1].version == "1.0.0"

    def test_update_calibration(self, manager):
        """更新校准分数应正确"""
        v = manager.register_version(
            evaluator_name="security",
            version="1.0.0",
            code_hash="hash1",
            config={},
        )
        assert v.calibration_score is None

        updated = manager.update_calibration("security", 93.5)
        assert updated is not None
        assert updated.calibration_score == 93.5
        # updated_at 应该晚于或等于 created_at
        assert updated.updated_at >= updated.created_at

    def test_update_calibration_with_code_hash(self, manager):
        """通过代码哈希更新校准分数应正确"""
        manager.register_version(
            evaluator_name="security",
            version="1.0.0",
            code_hash="hash1",
            config={},
        )
        manager.register_version(
            evaluator_name="security",
            version="2.0.0",
            code_hash="hash2",
            config={},
        )

        updated = manager.update_calibration("security", 90.0, code_hash="hash1")
        assert updated is not None
        assert updated.code_hash == "hash1"
        assert updated.calibration_score == 90.0

    def test_check_calibration_status_not_calibrated(self, manager):
        """未校准版本应返回 not_calibrated 状态"""
        manager.register_version(
            evaluator_name="security",
            version="1.0.0",
            code_hash="hash1",
            config={},
        )
        status = manager.check_calibration_status("security")
        assert status["status"] == "not_calibrated"
        assert status["can_proceed"] is True
        assert status["version_id"] is not None

    def test_check_calibration_status_calibrated(self, manager):
        """校准通过的版本应返回 calibrated 状态"""
        manager.register_version(
            evaluator_name="security",
            version="1.0.0",
            code_hash="hash1",
            config={},
        )
        manager.update_calibration("security", 94.0)  # 94 离 95 偏差 1.05%，在 5% 阈值内

        status = manager.check_calibration_status("security")
        assert status["status"] == "calibrated"
        assert status["can_proceed"] is True
        assert status["calibration_score"] == 94.0
        assert status["baseline_score"] == 95.0
        assert status["deviation_pct"] < 5.0

    def test_check_calibration_status_drifted(self, manager):
        """偏离校准区间应返回 drifted 状态"""
        manager.register_version(
            evaluator_name="security",
            version="1.0.0",
            code_hash="hash1",
            config={},
        )
        # 注意：EvaluatorVersion 默认 calibration_threshold=5.0
        # 80 离 95 偏差 15.8%，超出 5% 阈值
        manager.update_calibration("security", 80.0)

        status = manager.check_calibration_status("security")
        assert status["status"] == "drifted"
        assert status["can_proceed"] is False
        assert status["deviation_pct"] > 5.0

    def test_deprecate_version(self, manager):
        """废弃版本应正确标记"""
        v = manager.register_version(
            evaluator_name="security",
            version="1.0.0",
            code_hash="hash1",
            config={},
        )
        assert v.status == VersionStatus.ACTIVE

        result = manager.deprecate_version(v.version_id, "outdated")
        assert result is True

        deprecated = manager.get_version_by_id(v.version_id)
        assert deprecated.status == VersionStatus.DEPRECATED

    def test_register_with_custom_calibration_threshold(self, manager):
        """Bug 已修复：注册时可以指定自定义校准阈值"""
        v = manager.register_version(
            evaluator_name="security",
            version="1.0.0",
            code_hash="hash1",
            config={},
            calibration_threshold=3.0,  # 使用自定义阈值
        )
        assert v.calibration_threshold == 3.0

    def test_register_default_calibration_threshold(self, manager):
        """默认校准阈值应为 5.0"""
        v = manager.register_version(
            evaluator_name="security",
            version="1.0.0",
            code_hash="hash1",
            config={},
        )
        assert v.calibration_threshold == 5.0

    def test_get_version_history(self, manager):
        """获取版本历史应返回格式化列表"""
        manager.register_version("eval", "1.0.0", "hash1", {})
        manager.register_version("eval", "2.0.0", "hash2", {})

        history = manager.get_version_history("eval")
        assert len(history) == 2
        assert history[0]["version"] == "2.0.0"  # 最新的在前
        assert history[1]["version"] == "1.0.0"
        assert all("version_id" in h for h in history)
        assert all("changelog" in h for h in history)
        assert all("status" in h for h in history)
        assert all("created_at" in h for h in history)


class TestEvaluatorVersionManagerNegative:
    """负向测试 - 错误场景处理"""

    @pytest.fixture
    def temp_dir(self):
        tmpdir = tempfile.mkdtemp()
        yield tmpdir
        shutil.rmtree(tmpdir, ignore_errors=True)

    @pytest.fixture
    def manager(self, temp_dir):
        return EvaluatorVersionManager(storage_path=temp_dir)

    def test_duplicate_version_raises_error(self, manager):
        """重复版本号应抛出 ValueError"""
        manager.register_version("security", "1.0.0", "hash1", {})

        with pytest.raises(ValueError, match="already exists"):
            manager.register_version("security", "1.0.0", "hash2", {})

    def test_get_current_version_nonexistent(self, manager):
        """获取不存在评估器的当前版本应返回 None"""
        assert manager.get_current_version("nonexistent") is None

    def test_get_version_by_id_nonexistent(self, manager):
        """获取不存在的版本ID应返回 None"""
        assert manager.get_version_by_id("nonexistent_id") is None

    def test_check_calibration_no_version(self, manager):
        """无版本时校准状态应返回 no_version"""
        status = manager.check_calibration_status("nonexistent")
        assert status["status"] == "no_version"
        assert "message" in status

    def test_deprecate_nonexistent_version(self, manager):
        """废弃不存在的版本应返回 False"""
        result = manager.deprecate_version("nonexistent")
        assert result is False

    def test_get_all_versions_filter_nonexistent(self, manager):
        """过滤不存在的评估器应返回空列表"""
        manager.register_version("eval_a", "1.0.0", "hash1", {})
        versions = manager.get_all_versions("nonexistent")
        assert versions == []

    def test_update_calibration_nonexistent(self, manager):
        """更新不存在评估器的校准分数应返回 None"""
        result = manager.update_calibration("nonexistent", 90.0)
        assert result is None


class TestEvaluatorVersionManagerBoundary:
    """边界测试"""

    @pytest.fixture
    def temp_dir(self):
        tmpdir = tempfile.mkdtemp()
        yield tmpdir
        shutil.rmtree(tmpdir, ignore_errors=True)

    @pytest.fixture
    def manager(self, temp_dir):
        return EvaluatorVersionManager(storage_path=temp_dir)

    def test_many_versions(self, manager):
        """大量版本应正常工作"""
        for i in range(50):
            manager.register_version(
                evaluator_name="eval",
                version=f"1.{i}.0",
                code_hash=f"hash_{i}",
                config={"version": i},
            )

        versions = manager.get_all_versions("eval")
        assert len(versions) == 50
        # 最新版本在前
        assert versions[0].version == "1.49.0"

    def test_version_history_limit(self, manager):
        """版本历史应受 limit 限制"""
        for i in range(20):
            manager.register_version(
                evaluator_name="eval",
                version=f"1.{i}.0",
                code_hash=f"hash_{i}",
                config={},
            )

        history = manager.get_version_history("eval", limit=5)
        assert len(history) == 5

    def test_empty_changelog(self, manager):
        """空 changelog 应正常"""
        v = manager.register_version(
            evaluator_name="eval",
            version="1.0.0",
            code_hash="hash1",
            config={},
            changelog="",
        )
        assert v.changelog == ""

    def test_large_config_snapshot(self, manager):
        """大配置快照应正常存储"""
        large_config = {f"key_{i}": f"value_{i}" for i in range(100)}
        v = manager.register_version(
            evaluator_name="eval",
            version="1.0.0",
            code_hash="hash1",
            config=large_config,
        )
        assert v.config_snapshot == large_config
        assert len(v.config_snapshot) == 100

    def test_special_characters_in_changelog(self, manager):
        """changelog 中的特殊字符应正常处理"""
        changelog = """
        # Release Notes
        - 新增功能: "安全检测"
        - 修复 bug: <注入攻击>
        - 性能提升: 50%
        """
        v = manager.register_version(
            evaluator_name="eval",
            version="1.0.0",
            code_hash="hash1",
            config={},
            changelog=changelog,
        )
        assert v.changelog == changelog


class TestVersionStatus:
    """VersionStatus 枚举测试"""

    def test_status_values(self):
        """枚举值应正确"""
        assert VersionStatus.ACTIVE.value == "active"
        assert VersionStatus.DEPRECATED.value == "deprecated"
        assert VersionStatus.RECALIBRATING.value == "recalibrating"
