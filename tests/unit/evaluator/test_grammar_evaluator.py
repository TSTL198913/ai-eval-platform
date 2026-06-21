"""
GrammarEvaluator - 语法检查评估器专项测试
测试目标：验证GrammarEvaluator的validate_input、解析LLM输出的错误数量、score = max(0, 1.0 - error_count * 0.2)等核心功能
关键发现：（测试过程中记录）
"""

import os
import sys
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.domain.evaluators.grammar import GrammarEvaluator
from src.schemas.evaluation import EvaluationSchema


class TestGrammarEvaluatorPositiveCases:
    """正向测试 - 正常输入"""

    @pytest.fixture
    def mock_client(self):
        """Mock LLM客户端"""
        client = MagicMock()
        client.config = MagicMock()
        client.config.model_name = "gpt-4"
        client.chat.return_value = "错误数: 0\n修正后: 正确的文本"
        return client

    @pytest.fixture
    def target(self, mock_client):
        return GrammarEvaluator(client=mock_client)

    def test_valid_input_returns_valid_response(self, target, mock_client):
        """合法输入应返回is_valid=True"""
        request = EvaluationSchema(
            id="gram_001",
            type="grammar",
            payload={"user_input": "这是一个正确的句子"},
        )
        result = target.evaluate(request)

        assert result.is_valid is True
        assert result.score is not None
        assert result.error is None

    def test_no_errors_returns_full_score(self, target, mock_client):
        """无错误时应返回score=1.0"""
        mock_client.chat.return_value = "错误数: 0\n修正后: 正确的句子"
        request = EvaluationSchema(
            id="gram_002",
            type="grammar",
            payload={"user_input": "正确的句子"},
        )
        result = target.evaluate(request)

        assert result.is_valid is True
        assert result.score == 1.0

    def test_one_error_returns_reduced_score(self, target, mock_client):
        """1个错误应返回score=0.8"""
        mock_client.chat.return_value = "错误数: 1\n修正后: 正确的句子"
        request = EvaluationSchema(
            id="gram_003",
            type="grammar",
            payload={"user_input": "有错误的句子"},
        )
        result = target.evaluate(request)

        assert result.is_valid is True
        assert result.score == 0.8

    def test_multiple_errors_calculated_correctly(self, target, mock_client):
        """多个错误应按公式计算: score = max(0, 1.0 - error_count * 0.2)"""
        mock_client.chat.return_value = "错误数: 3\n修正后: 正确的句子"
        request = EvaluationSchema(
            id="gram_004",
            type="grammar",
            payload={"user_input": "有多个错误的句子"},
        )
        result = target.evaluate(request)

        assert result.is_valid is True
        assert abs(result.score - 0.4) < 0.001  # 允许浮点数误差


class TestGrammarEvaluatorNegativeCases:
    """负向测试 - 错误输入"""

    @pytest.fixture
    def target(self):
        return GrammarEvaluator(client=None)

    def test_empty_user_input_returns_error(self, target):
        """空user_input应返回is_valid=False"""
        request = EvaluationSchema(
            id="gram_neg_001",
            type="grammar",
            payload={"user_input": ""},
        )
        result = target.evaluate(request)

        assert result.is_valid is False
        assert result.error is not None
        assert "不能为空" in result.error

    def test_empty_text_returns_error(self, target):
        """空text字段应返回is_valid=False"""
        request = EvaluationSchema(
            id="gram_neg_002",
            type="grammar",
            payload={"text": ""},
        )
        result = target.evaluate(request)

        assert result.is_valid is False

    def test_missing_input_returns_error(self, target):
        """缺少输入字段应返回错误"""
        request = EvaluationSchema(
            id="gram_neg_003",
            type="grammar",
            payload={},
        )
        result = target.evaluate(request)

        assert result.is_valid is False


class TestGrammarEvaluatorBoundaryCases:
    """边界测试 - 边界值"""

    @pytest.fixture
    def mock_client(self):
        client = MagicMock()
        client.config = MagicMock()
        client.config.model_name = "gpt-4"
        return client

    def test_without_llm_client_returns_default_output(self, mock_client):
        """无LLM client时应返回默认输出，错误数为0"""
        target = GrammarEvaluator(client=None)
        request = EvaluationSchema(
            id="gram_bound_001",
            type="grammar",
            payload={"user_input": "原始文本"},
        )
        result = target.evaluate(request)

        assert result.is_valid is True
        assert result.score == 1.0  # 错误数为0时，score = 1.0 - 0 = 1.0

    def test_more_than_five_errors_returns_zero_score(self, mock_client):
        """超过5个错误应返回score=0（最低分数）"""
        target = GrammarEvaluator(client=mock_client)
        mock_client.chat.return_value = "错误数: 6\n修正后: 正确"
        request = EvaluationSchema(
            id="gram_bound_002",
            type="grammar",
            payload={"user_input": "错误太多"},
        )
        result = target.evaluate(request)

        assert result.score == 0.0  # max(0, 1.0 - 6*0.2) = max(0, -0.2) = 0

    def test_exactly_five_errors_returns_zero_score(self, mock_client):
        """正好5个错误应返回score=0"""
        target = GrammarEvaluator(client=mock_client)
        mock_client.chat.return_value = "错误数: 5\n修正后: 正确"
        request = EvaluationSchema(
            id="gram_bound_003",
            type="grammar",
            payload={"user_input": "五个错误"},
        )
        result = target.evaluate(request)

        assert result.score == 0.0  # max(0, 1.0 - 5*0.2) = max(0, 0) = 0

    def test_none_input_returns_error(self, mock_client):
        """None输入应被正确处理"""
        target = GrammarEvaluator(client=mock_client)
        request = EvaluationSchema(
            id="gram_bound_004",
            type="grammar",
            payload={"user_input": None},
        )
        result = target.evaluate(request)

        assert result.is_valid is False

    def test_very_long_text_handled(self, mock_client):
        """超长文本应被正确处理"""
        mock_client.chat.return_value = "错误数: 0\n修正后: 文本"
        target = GrammarEvaluator(client=mock_client)
        long_text = "测试" * 1000
        request = EvaluationSchema(
            id="gram_bound_005",
            type="grammar",
            payload={"user_input": long_text},
        )
        result = target.evaluate(request)

        assert result.is_valid is True


class TestGrammarEvaluatorParsingLogic:
    """解析逻辑测试"""

    @pytest.fixture
    def mock_client(self):
        client = MagicMock()
        client.config = MagicMock()
        client.config.model_name = "gpt-4"
        return client

    @pytest.fixture
    def target(self, mock_client):
        return GrammarEvaluator(client=mock_client)

    def test_invalid_error_count_format_handled(self, target, mock_client):
        """错误数格式无效时应默认为0"""
        mock_client.chat.return_value = "错误数: 不是数字\n修正后: 文本"
        request = EvaluationSchema(
            id="gram_parse_001",
            type="grammar",
            payload={"user_input": "测试"},
        )
        result = target.evaluate(request)

        assert result.score == 1.0  # 解析失败默认为0

    def test_missing_error_count_line_handled(self, target, mock_client):
        """缺少错误数行时应正常处理"""
        mock_client.chat.return_value = "修正后: 正确的文本"
        request = EvaluationSchema(
            id="gram_parse_002",
            type="grammar",
            payload={"user_input": "测试"},
        )
        result = target.evaluate(request)

        assert result.is_valid is True
        assert result.score == 1.0

    def test_corrected_text_extracted(self, target, mock_client):
        """应正确提取修正后的文本"""
        mock_client.chat.return_value = "错误数: 1\n修正后: 这是修正后的文本"
        request = EvaluationSchema(
            id="gram_parse_003",
            type="grammar",
            payload={"user_input": "原始"},
        )
        result = target.evaluate(request)

        assert result.data is not None
        assert "这是修正后的文本" in result.data

    def test_multiline_output_parsed_correctly(self, target, mock_client):
        """多行输出应正确解析"""
        mock_client.chat.return_value = "第一行\n错误数: 2\n第二行\n修正后: 最终文本\n第三行"
        request = EvaluationSchema(
            id="gram_parse_004",
            type="grammar",
            payload={"user_input": "原始"},
        )
        result = target.evaluate(request)

        assert abs(result.score - 0.6) < 0.001  # 允许浮点数误差
        assert "最终文本" in result.data
