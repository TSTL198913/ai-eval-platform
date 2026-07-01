"""
ClassificationEvaluator - 分类评估器专项测试
测试目标：验证ClassificationEvaluator的validate_input、expected_label不能为空、置信度评分等核心功能
"""

import os
import sys
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.domain.evaluators.classification import ClassificationEvaluator
from src.schemas.evaluation import EvaluationSchema


class TestClassificationEvaluatorPositiveCases:
    """正向测试 - 正常输入"""

    @pytest.fixture
    def mock_client(self):
        client = MagicMock()
        client.config = MagicMock()
        client.config.model_name = "gpt-4"
        client.chat.return_value = "1.0"
        return client

    @pytest.fixture
    def target(self, mock_client):
        return ClassificationEvaluator(client=mock_client)

    def test_llm_output_matches_expected_label_score_is_one(self, target, mock_client):
        """实际输出匹配expected_label应返回高分"""
        mock_client.chat.return_value = "1.0"
        request = EvaluationSchema(
            id="cls_001",
            type="classification",
            payload={
                "user_input": "积极的评论",
                "actual_output": "正类",
                "expected_label": "正类",
            },
        )
        result = target.evaluate(request)

        assert result.is_valid is True
        assert result.score == 1.0
        assert result.text == "正类"
        
        # 强断言：验证置信度和状态
        assert result.confidence is not None, "confidence不应为None"
        assert 0.0 <= result.confidence <= 1.0, f"confidence应在0-1之间，实际为{result.confidence}"
        assert result.evaluation_status.value == "success", f"evaluation_status应为success"

    def test_valid_input_with_labels_returns_valid(self, target, mock_client):
        """带labels的合法输入应返回有效响应"""
        mock_client.chat.return_value = "0.9"
        request = EvaluationSchema(
            id="cls_002",
            type="classification",
            payload={
                "user_input": "这个产品很好用",
                "actual_output": "正面",
                "expected_label": "正面",
                "labels": ["正面", "负面", "中立"],
            },
        )
        result = target.evaluate(request)

        assert result.is_valid is True
        assert result.score is not None
        
        # 强断言：验证评分范围和置信度
        assert 0.0 <= result.score <= 1.0, f"score应在0-1之间，实际为{result.score}"
        assert result.score == pytest.approx(0.9, abs=0.01), f"score应接近0.9，实际为{result.score}"
        assert result.confidence is not None, "confidence不应为None"

    def test_text_field_instead_of_user_input_works(self, target, mock_client):
        """使用text字段代替user_input也应正常工作"""
        mock_client.chat.return_value = "0.85"
        request = EvaluationSchema(
            id="cls_003",
            type="classification",
            payload={
                "text": "另一个文本",
                "actual_output": "分类结果",
                "expected_label": "分类结果",
            },
        )
        result = target.evaluate(request)

        assert result.is_valid is True
        assert result.score == 0.85


class TestClassificationEvaluatorNegativeCases:
    """负向测试 - 错误输入"""

    @pytest.fixture
    def target(self):
        return ClassificationEvaluator(client=None)

    def test_empty_expected_label_returns_error(self, target):
        """空expected_label应返回错误"""
        request = EvaluationSchema(
            id="cls_neg_001",
            type="classification",
            payload={"user_input": "测试", "actual_output": "正类", "expected_label": ""},
        )
        result = target.evaluate(request)

        assert result.is_valid is False
        assert "expected_label" in result.error

    def test_missing_expected_label_returns_error(self, target):
        """缺少expected_label字段应返回错误"""
        request = EvaluationSchema(
            id="cls_neg_002",
            type="classification",
            payload={"user_input": "测试", "actual_output": "正类"},
        )
        result = target.evaluate(request)

        assert result.is_valid is False
        assert "expected_label" in result.error

    def test_missing_actual_output_returns_error(self, target):
        """缺少actual_output字段应返回错误"""
        request = EvaluationSchema(
            id="cls_neg_003",
            type="classification",
            payload={"user_input": "测试", "expected_label": "正类"},
        )
        result = target.evaluate(request)

        assert result.is_valid is False
        assert "actual_output" in result.error

    def test_empty_actual_output_returns_error(self, target):
        """空actual_output应返回错误"""
        request = EvaluationSchema(
            id="cls_neg_004",
            type="classification",
            payload={"user_input": "测试", "actual_output": "", "expected_label": "正类"},
        )
        result = target.evaluate(request)

        assert result.is_valid is False
        assert "actual_output" in result.error

    def test_none_expected_label_returns_error(self, target):
        """None expected_label应返回错误"""
        request = EvaluationSchema(
            id="cls_neg_005",
            type="classification",
            payload={"user_input": "测试", "actual_output": "正类", "expected_label": None},
        )
        result = target.evaluate(request)

        assert result.is_valid is False

    def test_no_client_returns_error(self, target):
        """无LLM client应返回错误"""
        request = EvaluationSchema(
            id="cls_neg_006",
            type="classification",
            payload={"user_input": "测试", "actual_output": "正类", "expected_label": "正类"},
        )
        result = target.evaluate(request)

        assert result.is_valid is False
        assert "LLM" in result.error


class TestClassificationEvaluatorBoundaryCases:
    """边界测试 - 边界值"""

    @pytest.fixture
    def mock_client(self):
        client = MagicMock()
        client.config = MagicMock()
        client.config.model_name = "gpt-4"
        client.chat.return_value = "0.5"
        return client

    @pytest.fixture
    def target(self, mock_client):
        return ClassificationEvaluator(client=mock_client)

    def test_very_long_input(self, target, mock_client):
        """超长输入"""
        mock_client.chat.return_value = "0.7"
        long_text = "测试" * 1000
        request = EvaluationSchema(
            id="cls_bound_002",
            type="classification",
            payload={"user_input": long_text, "actual_output": "分类", "expected_label": "分类"},
        )
        result = target.evaluate(request)

        assert result.is_valid is True

    def test_unicode_chinese_labels(self, target, mock_client):
        """中文标签"""
        mock_client.chat.return_value = "0.95"
        request = EvaluationSchema(
            id="cls_bound_003",
            type="classification",
            payload={"user_input": "测试文本", "actual_output": "科技", "expected_label": "科技"},
        )
        result = target.evaluate(request)

        assert result.is_valid is True

    def test_empty_labels_list(self, target, mock_client):
        """空labels列表"""
        mock_client.chat.return_value = "0.8"
        request = EvaluationSchema(
            id="cls_bound_004",
            type="classification",
            payload={
                "user_input": "测试",
                "actual_output": "正类",
                "expected_label": "正类",
                "labels": [],
            },
        )
        result = target.evaluate(request)

        assert result.is_valid is True
