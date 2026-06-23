"""
Domain模块专项测试
测试目标：验证calibration_service、evaluator_version、model_versioning等模块
"""

import json
import os
import sys
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.domain.calibration_service import CalibrationService
from src.domain.evaluator_version import EvaluatorVersion, VersionStatus
from src.domain.model_versioning import ModelVersion, ModelVersionRegistry


class TestEvaluatorVersion:
    """EvaluatorVersion评估器版本测试"""

    def test_version_construction(self):
        """应能正确构造EvaluatorVersion"""
        version = EvaluatorVersion(
            version_id="v1",
            evaluator_name="test_evaluator",
            version="1.0.0",
            changelog="Initial version",
            code_hash="abc123",
            config_snapshot={"key": "value"},
        )

        assert version.version_id == "v1"
        assert version.evaluator_name == "test_evaluator"
        assert version.version == "1.0.0"
        assert version.changelog == "Initial version"
        assert version.code_hash == "abc123"
        assert version.config_snapshot == {"key": "value"}
        assert version.status == VersionStatus.ACTIVE

    def test_version_with_optional_fields(self):
        """应能正确设置可选字段"""
        version = EvaluatorVersion(
            version_id="v2",
            evaluator_name="test",
            version="2.0.0",
            changelog="Update",
            code_hash="def456",
            config_snapshot={},
            calibration_score=0.95,
            calibration_threshold=10.0,
            status=VersionStatus.DEPRECATED,
            created_by="admin",
        )

        assert version.calibration_score == 0.95
        assert version.calibration_threshold == 10.0
        assert version.status == VersionStatus.DEPRECATED
        assert version.created_by == "admin"

    def test_to_dict(self):
        """to_dict应返回正确的字典表示"""
        version = EvaluatorVersion(
            version_id="v3",
            evaluator_name="test",
            version="1.0.0",
            changelog="test",
            code_hash="hash",
            config_snapshot={"key": "value"},
            calibration_score=0.8,
            status=VersionStatus.RECALIBRATING,
        )

        result = version.to_dict()
        assert result["version_id"] == "v3"
        assert result["version"] == "1.0.0"
        assert result["calibration_score"] == 0.8
        assert result["status"] == "recalibrating"

    def test_version_status_enum(self):
        """VersionStatus枚举值"""
        assert VersionStatus.ACTIVE.value == "active"
        assert VersionStatus.DEPRECATED.value == "deprecated"
        assert VersionStatus.RECALIBRATING.value == "recalibrating"


class TestModelVersion:
    """ModelVersion模型版本测试"""

    def test_model_version_construction(self):
        """应能正确构造ModelVersion"""
        version = ModelVersion(
            version_id="mv1",
            model_name="test_model",
            version="1.0.0",
        )

        assert version.version_id == "mv1"
        assert version.model_name == "test_model"
        assert version.version == "1.0.0"
        assert version.base_model is None
        assert version.training_data is None
        assert isinstance(version.created_at, datetime)
        assert version.metadata == {}

    def test_model_version_with_optional_fields(self):
        """应能正确设置可选字段"""
        version = ModelVersion(
            version_id="mv2",
            model_name="test_model",
            version="2.0.0",
            base_model="base_v1",
            training_data="dataset_v2",
            metadata={"accuracy": 0.95},
        )

        assert version.base_model == "base_v1"
        assert version.training_data == "dataset_v2"
        assert version.metadata == {"accuracy": 0.95}


class TestModelVersionRegistry:
    """ModelVersionRegistry模型版本注册表测试"""

    @pytest.fixture(autouse=True)
    def reset_registry(self):
        """每个测试前重置注册表状态"""
        ModelVersionRegistry._instance = None
        ModelVersionRegistry._models = {}

    def test_singleton(self):
        """应是单例模式"""
        r1 = ModelVersionRegistry()
        r2 = ModelVersionRegistry()
        assert r1 is r2

    def test_register_and_get_versions(self):
        """注册和获取模型版本"""
        registry = ModelVersionRegistry()
        version1 = ModelVersion(version_id="mv1", model_name="test_model", version="1.0.0")
        version2 = ModelVersion(version_id="mv2", model_name="test_model", version="2.0.0")

        registry.register(version1)
        registry.register(version2)

        versions = registry.get_versions("test_model")
        assert len(versions) == 2

    def test_get_versions_empty(self):
        """获取不存在模型的版本应返回空列表"""
        registry = ModelVersionRegistry()
        versions = registry.get_versions("unknown_model")
        assert versions == []

    def test_get_latest(self):
        """获取最新版本"""
        import time

        registry = ModelVersionRegistry()
        version1 = ModelVersion(version_id="mv1", model_name="test_model", version="1.0.0")
        time.sleep(0.001)
        version2 = ModelVersion(version_id="mv2", model_name="test_model", version="2.0.0")

        registry.register(version1)
        registry.register(version2)

        latest = registry.get_latest("test_model")
        assert latest.version == "2.0.0"

    def test_get_latest_empty(self):
        """获取不存在模型的最新版本应返回None"""
        registry = ModelVersionRegistry()
        latest = registry.get_latest("unknown_model")
        assert latest is None

    def test_compare_versions(self):
        """对比两个版本"""
        registry = ModelVersionRegistry()
        version1 = ModelVersion(
            version_id="mv1",
            model_name="test_model",
            version="1.0.0",
            base_model="base_v1",
            metadata={"accuracy": 0.9},
        )
        version2 = ModelVersion(
            version_id="mv2",
            model_name="test_model",
            version="2.0.0",
            base_model="base_v2",
            metadata={"accuracy": 0.95, "speed": "fast"},
        )

        registry.register(version1)
        registry.register(version2)

        diff = registry.compare_versions("test_model", "1.0.0", "2.0.0")
        assert diff["model_name"] == "test_model"
        assert "differences" in diff

    def test_compare_versions_invalid(self):
        """对比不存在的版本应返回空字典"""
        registry = ModelVersionRegistry()
        diff = registry.compare_versions("test_model", "1.0.0", "99.0.0")
        assert diff == {}


class TestCalibrationService:
    """CalibrationService校准服务测试"""

    def test_create_golden_dataset(self):
        """创建黄金数据集"""
        with patch("src.domain.calibration_service.golden_dataset_manager") as mock_manager:
            mock_dataset = MagicMock()
            mock_dataset.to_dict.return_value = {"id": "ds1", "name": "test"}
            mock_manager.create_dataset.return_value = mock_dataset

            service = CalibrationService()
            result = service.create_golden_dataset("test", "desc", "category")

            assert result == {"id": "ds1", "name": "test"}
            mock_manager.create_dataset.assert_called_with("test", "desc", "category")

    def test_add_golden_sample(self):
        """添加黄金样本"""
        with patch("src.domain.calibration_service.golden_dataset_manager") as mock_manager:
            mock_sample = MagicMock()
            mock_sample.to_dict.return_value = {"id": "s1"}
            mock_manager.add_sample.return_value = mock_sample

            service = CalibrationService()
            result = service.add_golden_sample("ds1", {"data": "test"})

            assert result == {"id": "s1"}

    def test_add_golden_sample_none(self):
        """添加样本失败应返回None"""
        with patch("src.domain.calibration_service.golden_dataset_manager") as mock_manager:
            mock_manager.add_sample.return_value = None

            service = CalibrationService()
            result = service.add_golden_sample("ds1", {})

            assert result is None

    def test_correct_evaluation(self):
        """修正评估结果"""
        with patch("src.domain.calibration_service.golden_dataset_manager") as mock_manager:
            mock_sample = MagicMock()
            mock_sample.to_dict.return_value = {"id": "s1", "corrected": True}
            mock_manager.correct_sample.return_value = mock_sample

            service = CalibrationService()
            result = service.correct_evaluation("s1", {"score": 0.9}, "user")

            assert result == {"id": "s1", "corrected": True}

    def test_get_few_shot_examples(self):
        """获取少样本示例"""
        with patch("src.domain.calibration_service.golden_dataset_manager") as mock_manager:
            mock_manager.get_few_shot_examples.return_value = ["example1", "example2"]

            service = CalibrationService()
            result = service.get_few_shot_examples("ds1", 2)

            assert result == ["example1", "example2"]

    def test_get_calibration_stats(self):
        """获取校准统计"""
        with patch("src.domain.calibration_service.golden_dataset_manager") as mock_manager:
            mock_dataset = MagicMock()
            mock_dataset.id = "ds1"
            mock_dataset.name = "test"
            mock_dataset.samples = [1, 2, 3]
            mock_dataset.corrected_count = 1
            mock_manager.get_dataset.return_value = mock_dataset

            service = CalibrationService()
            result = service.get_calibration_stats("ds1")

            assert result["total_samples"] == 3
            assert result["corrected_samples"] == 1

    def test_get_calibration_stats_none(self):
        """获取不存在数据集的统计应返回None"""
        with patch("src.domain.calibration_service.golden_dataset_manager") as mock_manager:
            mock_manager.get_dataset.return_value = None

            service = CalibrationService()
            result = service.get_calibration_stats("ds1")

            assert result is None

    def test_list_golden_datasets(self):
        """列出黄金数据集"""
        with patch("src.domain.calibration_service.golden_dataset_manager") as mock_manager:
            mock_ds1, mock_ds2 = MagicMock(), MagicMock()
            mock_ds1.to_dict.return_value = {"id": "ds1"}
            mock_ds2.to_dict.return_value = {"id": "ds2"}
            mock_manager.list_datasets.return_value = [mock_ds1, mock_ds2]

            service = CalibrationService()
            result = service.list_golden_datasets()

            assert len(result) == 2

    def test_export_calibration_data(self):
        """导出校准数据"""
        with patch("src.domain.calibration_service.golden_dataset_manager") as mock_manager:
            mock_dataset = MagicMock()
            mock_dataset.id = "ds1"
            mock_dataset.name = "test"
            mock_dataset.description = "desc"
            mock_dataset.category = "cat"
            mock_sample = MagicMock()
            mock_sample.to_dict.return_value = {"id": "s1"}
            mock_dataset.samples = [mock_sample]
            mock_manager.get_dataset.return_value = mock_dataset

            with patch("builtins.open", MagicMock()):
                service = CalibrationService()
                filepath = service.export_calibration_data("ds1")

                assert isinstance(filepath, str)
                assert "ds1" in filepath

    def test_export_calibration_data_none(self):
        """导出不存在数据集应返回空字符串"""
        with patch("src.domain.calibration_service.golden_dataset_manager") as mock_manager:
            mock_manager.get_dataset.return_value = None

            service = CalibrationService()
            result = service.export_calibration_data("ds1")

            assert result == ""

    def test_import_calibration_data(self):
        """导入校准数据"""
        test_data = {
            "name": "imported",
            "description": "imported desc",
            "category": "general",
            "samples": [{"id": "s1"}],
        }

        with patch("os.path.exists", return_value=True):
            with patch("builtins.open", MagicMock()) as mock_open:
                mock_file = MagicMock()
                mock_file.__enter__.return_value = mock_file
                mock_file.read.return_value = json.dumps(test_data)
                mock_open.return_value = mock_file

                with patch("src.domain.calibration_service.golden_dataset_manager") as mock_manager:
                    mock_dataset = MagicMock()
                    mock_dataset.id = "imported_ds"
                    mock_manager.create_dataset.return_value = mock_dataset

                    service = CalibrationService()
                    result = service.import_calibration_data("test.json")

                    assert result is True

    def test_import_calibration_data_not_exists(self):
        """导入不存在的文件应返回False"""
        with patch("os.path.exists", return_value=False):
            service = CalibrationService()
            result = service.import_calibration_data("non_existent.json")

            assert result is False

    def test_import_calibration_data_error(self):
        """导入文件出错应返回False"""
        with patch("os.path.exists", return_value=True):
            with patch("builtins.open", MagicMock(side_effect=Exception)):
                service = CalibrationService()
                result = service.import_calibration_data("test.json")

                assert result is False
