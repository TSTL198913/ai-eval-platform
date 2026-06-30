"""
FactCheckEvaluator - 事实核查评估器专项测试
"""

import os
import sys
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.domain.evaluators.fact_check import FactCheckEvaluator
from src.schemas.evaluation import EvaluationSchema


class TestFactCheckEvaluatorPositiveCases:
    """正向测试 - 正常输入"""

    @pytest.fixture
    def mock_client(self):
        """Mock LLM客户端"""
        client = MagicMock()
        client.config = MagicMock()
        client.config.model_name = "gpt-4"
        client.chat.return_value = "结果: true\n理由: 这是一个真实的事实"
        return client

    @pytest.fixture
    def target(self, mock_client):
        return FactCheckEvaluator(client=mock_client)

    def test_llm_returns_true_score_is_one(self, target, mock_client):
        """LLM返回包含'true'应返回score=1.0"""
        mock_client.chat.return_value = "结果: true\n理由: 这是一个真实的事实"
        request = EvaluationSchema(
            id="fact_001",
            type="fact_check",
            payload={"user_input": "太阳从东方升起", "actual_output": "太阳从东方升起"},
        )
        result = target.evaluate(request)

        assert result.is_valid is True
        assert result.score == 1.0
        assert "true" in result.data.get("fact_check_label", "")

    def test_valid_input_returns_valid_response(self, target, mock_client):
        """合法输入应返回is_valid=True"""
        request = EvaluationSchema(
            id="fact_002",
            type="fact_check",
            payload={"user_input": "水的化学式是H2O", "actual_output": "水的化学式是H2O"},
        )
        result = target.evaluate(request)

        assert result.is_valid is True
        assert result.score is not None

    def test_true_case_insensitive(self, target, mock_client):
        """'true'判断应不区分大小写"""
        mock_client.chat.return_value = "结果: TRUE\n理由: 验证"
        request = EvaluationSchema(
            id="fact_003",
            type="fact_check",
            payload={"user_input": "事实陈述", "actual_output": "事实陈述"},
        )
        result = target.evaluate(request)

        assert result.score == 1.0


class TestFactCheckEvaluatorNegativeCases:
    """负向测试 - 错误输入"""

    @pytest.fixture
    def mock_client(self):
        client = MagicMock()
        client.config = MagicMock()
        client.config.model_name = "gpt-4"
        client.chat.return_value = "结果: false\n理由: 这是一个虚假的事实"
        return client

    @pytest.fixture
    def target(self, mock_client):
        return FactCheckEvaluator(client=mock_client)

    def test_llm_returns_false_score_is_zero(self, target, mock_client):
        """LLM返回包含'false'应返回score=0.0"""
        mock_client.chat.return_value = "结果: false\n理由: 这是一个虚假的事实"
        request = EvaluationSchema(
            id="fact_neg_001",
            type="fact_check",
            payload={"user_input": "太阳从西方升起", "actual_output": "太阳从西方升起"},
        )
        result = target.evaluate(request)

        assert result.is_valid is True
        assert result.score == 0.0

    def test_false_case_insensitive(self, target, mock_client):
        """'false'判断应不区分大小写"""
        mock_client.chat.return_value = "结果: FALSE\n理由: 验证"
        request = EvaluationSchema(
            id="fact_neg_002",
            type="fact_check",
            payload={"user_input": "事实陈述", "actual_output": "事实陈述"},
        )
        result = target.evaluate(request)

        assert result.score == 0.0


class TestFactCheckEvaluatorBoundaryCases:
    """边界测试 - 边界值"""

    def test_without_llm_client_returns_false(self):
        """无LLM client时应返回is_valid=False"""
        target = FactCheckEvaluator(client=None)
        request = EvaluationSchema(
            id="fact_bound_001",
            type="fact_check",
            payload={"user_input": "无法验证的陈述"},
        )
        result = target.evaluate(request)

        assert result.is_valid is False
        assert result.score is None
        assert "LLM" in result.error or "client" in result.error.lower()

    def test_empty_user_input_returns_error(self):
        """空user_input应返回is_valid=False"""
        target = FactCheckEvaluator(client=None)
        request = EvaluationSchema(
            id="fact_bound_002",
            type="fact_check",
            payload={"user_input": ""},
        )
        result = target.evaluate(request)

        assert result.is_valid is False
        assert "不能为空" in result.error

    def test_empty_text_returns_error(self):
        """空text字段应返回is_valid=False"""
        target = FactCheckEvaluator(client=None)
        request = EvaluationSchema(
            id="fact_bound_003",
            type="fact_check",
            payload={"text": ""},
        )
        result = target.evaluate(request)

        assert result.is_valid is False

    def test_missing_input_returns_error(self):
        """缺少输入字段应返回错误"""
        target = FactCheckEvaluator(client=None)
        request = EvaluationSchema(
            id="fact_bound_004",
            type="fact_check",
            payload={},
        )
        result = target.evaluate(request)

        assert result.is_valid is False

    def test_none_input_returns_error(self):
        """None输入应被正确处理"""
        target = FactCheckEvaluator(client=None)
        request = EvaluationSchema(
            id="fact_bound_005",
            type="fact_check",
            payload={"user_input": None},
        )
        result = target.evaluate(request)

        assert result.is_valid is False

    def test_no_true_or_false_returns_error(self):
        """不包含true也不包含false应返回错误"""
        mock_client = MagicMock()
        mock_client.config = MagicMock()
        mock_client.config.model_name = "gpt-4"
        mock_client.chat.return_value = "无法确定"
        target = FactCheckEvaluator(client=mock_client)

        request = EvaluationSchema(
            id="fact_bound_006",
            type="fact_check",
            payload={"user_input": "模糊的陈述", "actual_output": "模糊的陈述"},
        )
        result = target.evaluate(request)

        assert result.is_valid is False
        assert "无法解析" in result.error


class TestFactCheckEvaluatorDependencyHandling:
    """依赖测试 - 外部依赖Mock"""

    @pytest.fixture
    def mock_client(self):
        client = MagicMock()
        client.config = MagicMock()
        client.config.model_name = "gpt-4"
        client.chat.return_value = "结果: true\n理由: 验证通过"
        return client

    def test_with_client_calls_llm(self, mock_client):
        """有client时应调用LLM"""
        target = FactCheckEvaluator(client=mock_client)
        request = EvaluationSchema(
            id="fact_dep_001",
            type="fact_check",
            payload={"user_input": "测试陈述", "actual_output": "测试陈述"},
        )
        result = target.evaluate(request)

        mock_client.chat.assert_called_once()
        assert result.is_valid is True

    def test_without_client_returns_error(self):
        """无LLM client时应返回is_valid=False"""
        target = FactCheckEvaluator(client=None)
        request = EvaluationSchema(
            id="fact_dep_002",
            type="fact_check",
            payload={"user_input": "测试陈述"},
        )
        result = target.evaluate(request)

        assert result.is_valid is False
        assert result.score is None
        assert "LLM" in result.error or "client" in result.error.lower()


class TestFactCheckEvaluatorParsingLogic:
    """解析逻辑测试"""

    @pytest.fixture
    def mock_client(self):
        client = MagicMock()
        client.config = MagicMock()
        client.config.model_name = "gpt-4"
        return client

    def test_result_prefix_extraction(self, mock_client):
        """应正确提取'结果:'后的值"""
        mock_client.chat.return_value = "结果: true\n理由: 测试"
        target = FactCheckEvaluator(client=mock_client)
        request = EvaluationSchema(
            id="fact_parse_002",
            type="fact_check",
            payload={"user_input": "测试", "actual_output": "测试"},
        )
        result = target.evaluate(request)

        assert result.score == 1.0

    def test_multiline_output_handled(self, mock_client):
        """多行输出应正确处理"""
        mock_client.chat.return_value = "分析：第一行\n结果：true\n结论：验证通过"
        target = FactCheckEvaluator(client=mock_client)
        request = EvaluationSchema(
            id="fact_parse_003",
            type="fact_check",
            payload={"user_input": "测试", "actual_output": "测试"},
        )
        result = target.evaluate(request)

        assert result.score == 1.0
