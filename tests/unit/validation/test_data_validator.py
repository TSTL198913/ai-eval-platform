"""
Golden Dataset Validator Tests
测试目标：验证数据验证层的 Schema 验证功能
"""

import json
import os
import pytest

from src.infra.validation.data_validator import GoldenDatasetValidator


class TestDataValidatorPositiveCases:
    """正向测试 - 有效数据"""

    @pytest.fixture
    def validator(self):
        return GoldenDatasetValidator()

    def test_valid_data_passes_validation(self, validator):
        """有效数据应通过验证"""
        valid_data = [
            {
                "id": "test-001",
                "type": "qa",
                "user_input": "什么是 AI？",
                "actual_output": "AI 是人工智能",
                "expected_output": "AI 是人工智能",
                "expected_score": 1.0,
                "tags": ["ai", "basic"],
            },
            {
                "id": "test-002",
                "type": "code",
                "user_input": "写一个加法函数",
                "actual_output": "def add(a, b): return a + b",
                "expected_output": "def add(a, b): return a + b",
                "expected_score": 0.9,
                "tags": ["python", "function"],
            },
        ]

        result = validator.validate(valid_data)

        assert result["success"] is True
        assert "validation_results" in result
        assert result["validation_results"]["success_count"] > 0

    def test_empty_list_returns_error(self, validator):
        """空列表应返回错误"""
        result = validator.validate([])

        assert result["success"] is False
        assert "数据集为空" in result["errors"]


class TestDataValidatorNegativeCases:
    """负向测试 - 无效数据"""

    @pytest.fixture
    def validator(self):
        return GoldenDatasetValidator()

    def test_missing_required_field_fails(self, validator):
        """缺少必需字段应失败"""
        invalid_data = [
            {
                "id": "test-invalid-001",
                "type": "qa",
                "user_input": "测试",
                "actual_output": "输出",
                "expected_output": "期望",
                "expected_score": 0.5,
            },
        ]

        result = validator.validate(invalid_data)

        assert result["success"] is False
        assert len(result["errors"]) > 0

    def test_invalid_score_range_fails(self, validator):
        """分数超出范围应失败"""
        invalid_data = [
            {
                "id": "test-invalid-002",
                "type": "qa",
                "user_input": "测试",
                "actual_output": "输出",
                "expected_output": "期望",
                "expected_score": 1.5,
                "tags": [],
            },
        ]
        
        result = validator.validate(invalid_data)

        assert result["success"] is False

    def test_invalid_type_fails(self, validator):
        """无效类型应失败"""
        invalid_data = [
            {
                "id": "test-invalid-003",
                "type": "invalid_type",
                "user_input": "测试",
                "actual_output": "输出",
                "expected_output": "期望",
                "expected_score": 0.5,
                "tags": [],
            },
        ]

        result = validator.validate(invalid_data)

        assert result["success"] is False

    def test_null_required_field_fails(self, validator):
        """必需字段为 null 应失败"""
        invalid_data = [
            {
                "id": "test-invalid-004",
                "type": "qa",
                "user_input": None,
                "actual_output": "输出",
                "expected_output": "期望",
                "expected_score": 0.5,
                "tags": [],
            },
        ]

        result = validator.validate(invalid_data)

        assert result["success"] is False

    def test_duplicate_id_fails(self, validator):
        """重复 ID 应失败"""
        invalid_data = [
            {
                "id": "duplicate-001",
                "type": "qa",
                "user_input": "测试1",
                "actual_output": "输出1",
                "expected_output": "期望1",
                "expected_score": 0.5,
                "tags": [],
            },
            {
                "id": "duplicate-001",
                "type": "qa",
                "user_input": "测试2",
                "actual_output": "输出2",
                "expected_output": "期望2",
                "expected_score": 0.6,
                "tags": [],
            },
        ]

        result = validator.validate(invalid_data)

        assert result["success"] is False


class TestDataValidatorBoundaryCases:
    """边界测试 - 边界值"""

    @pytest.fixture
    def validator(self):
        return GoldenDatasetValidator()

    def test_score_at_boundary_0_0_passes(self, validator):
        """分数为 0.0 应通过"""
        data = [
            {
                "id": "boundary-001",
                "type": "qa",
                "user_input": "测试",
                "actual_output": "输出",
                "expected_output": "期望",
                "expected_score": 0.0,
                "tags": [],
            },
        ]

        result = validator.validate(data)

        assert result["success"] is True

    def test_score_at_boundary_1_0_passes(self, validator):
        """分数为 1.0 应通过"""
        data = [
            {
                "id": "boundary-002",
                "type": "qa",
                "user_input": "测试",
                "actual_output": "输出",
                "expected_output": "期望",
                "expected_score": 1.0,
                "tags": [],
            },
        ]

        result = validator.validate(data)

        assert result["success"] is True

    def test_id_with_special_chars_fails(self, validator):
        """ID 包含特殊字符应失败"""
        data = [
            {
                "id": "test@#$",
                "type": "qa",
                "user_input": "测试",
                "actual_output": "输出",
                "expected_output": "期望",
                "expected_score": 0.5,
                "tags": [],
            },
        ]

        result = validator.validate(data)

        assert result["success"] is False


class TestDataValidatorContract:
    """契约测试 - 验证验证器契约"""

    @pytest.fixture
    def validator(self):
        return GoldenDatasetValidator()

    def test_validation_report_generated(self, validator):
        """应能生成验证报告"""
        valid_data = [
            {
                "id": "contract-001",
                "type": "qa",
                "user_input": "测试",
                "actual_output": "输出",
                "expected_output": "期望",
                "expected_score": 0.5,
                "tags": [],
            },
        ]

        validator.validate(valid_data)
        report = validator.get_validation_report()

        assert isinstance(report, str)
        assert "验证报告" in report
        assert "状态:" in report

    def test_validate_golden_dataset_file(self, validator):
        """应能验证 Golden Dataset 文件"""
        result = validator.validate_golden_dataset()
        
        assert "success" in result
        assert "errors" in result
        assert "warnings" in result