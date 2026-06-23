"""
Repository 工具方法测试
验证 _map_row_to_dict 等公共方法
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from datetime import datetime

from src.infra.db.repository import EvaluationRepository, _format_datetime


class TestFormatDatetime:
    """_format_datetime 工具函数测试"""

    def test_format_datetime_object(self):
        """格式化datetime对象"""
        dt = datetime(2024, 1, 15, 10, 30, 0)
        result = _format_datetime(dt)

        assert result == "2024-01-15T10:30:00"

    def test_format_none(self):
        """格式化None值"""
        result = _format_datetime(None)
        assert result is None

    def test_format_non_datetime(self):
        """格式化非datetime值"""
        result = _format_datetime("not a datetime")
        assert result == "not a datetime"


class TestMapRowToDict:
    """_map_row_to_dict 方法测试"""

    def test_map_basic_row(self):
        """映射基本行"""
        row = (1, "case-001", "gpt-4", "security", "completed", 150.5, 0.85, datetime(2024, 1, 15))
        result = EvaluationRepository._map_row_to_dict(row)

        assert result["id"] == 1
        assert result["case_id"] == "case-001"
        assert result["model_name"] == "gpt-4"
        assert result["adapter_name"] == "security"
        assert result["status"] == "completed"
        assert result["latency_ms"] == 150.5
        assert result["score"] == 0.85
        assert result["created_at"] == "2024-01-15T00:00:00"

    def test_map_row_with_response(self):
        """映射包含response_data的行"""
        # 字段顺序: id, case_id, model_name, adapter_name, status, latency_ms, score, response_data, created_at
        row = (
            1,
            "case-001",
            "gpt-4",
            "security",
            "completed",
            150.5,
            0.85,
            {"key": "value"},
            datetime(2024, 1, 15),
        )
        result = EvaluationRepository._map_row_to_dict(row, include_response=True)

        assert result["response_data"] == {"key": "value"}
        assert result["created_at"] == "2024-01-15T00:00:00"
        assert result["id"] == 1

    def test_map_row_without_response(self):
        """映射不包含response_data的行"""
        # 传入9个字段，response_data位置是None
        row = (
            1,
            "case-001",
            "gpt-4",
            "security",
            "completed",
            150.5,
            0.85,
            None,
            datetime(2024, 1, 15),
        )
        result = EvaluationRepository._map_row_to_dict(row, include_response=True)

        assert "response_data" in result
        assert result["response_data"] is None
        assert result["created_at"] == "2024-01-15T00:00:00"

    def test_map_row_empty_values(self):
        """映射包含空值的行"""
        row = (0, "", None, None, None, 0.0, None, None)
        result = EvaluationRepository._map_row_to_dict(row)

        assert result["id"] == 0
        assert result["case_id"] == ""
        assert result["model_name"] is None
        assert result["created_at"] is None

    def test_map_row_preserves_types(self):
        """映射保持原始类型"""
        row = (42, "test-case", "model", "adapter", "status", 3.14, 0.95, datetime(2024, 6, 21))
        result = EvaluationRepository._map_row_to_dict(row)

        assert isinstance(result["id"], int)
        assert isinstance(result["case_id"], str)
        assert isinstance(result["latency_ms"], float)
        assert isinstance(result["created_at"], str)
