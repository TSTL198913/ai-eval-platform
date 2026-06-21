"""
ClassificationEvaluator - 分类评估器专项测试
测试目标：验证ClassificationEvaluator的validate_input、expected_label不能为空、score = 1.0 if llm_output == expected_label else 0.0等核心功能
关键发现：（测试过程中记录）
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
        """Mock LLM客户端"""
        client = MagicMock()
        client.config = MagicMock()
        client.config.model_name = "gpt-4"
        client.chat.return_value = "正类"
        return client

    @pytest.fixture
    def target(self, mock_client):
        return ClassificationEvaluator(client=mock_client)

    def test_llm_output_matches_expected_label_score_is_one(self, target, mock_client):
        """LLM输出匹配expected_label应返回score=1.0"""
        mock_client.chat.return_value = "正类"
        request = EvaluationSchema(
            id="cls_001",
            type="classification",
            payload={
                "user_input": "积极的评论",
                "expected_label": "正类",
            },
        )
        result = target.evaluate(request)

        assert result.is_valid is True
        assert result.score == 1.0
        assert result.text == "正类"

    def test_valid_input_with_labels_returns_valid(self, target, mock_client):
        """带labels的合法输入应返回有效响应"""
        mock_client.chat.return_value = "正面"
        request = EvaluationSchema(
            id="cls_002",
            type="classification",
            payload={
                "user_input": "这个产品很好用",
                "expected_label": "正面",
                "labels": ["正面", "负面", "中立"],
            },
        )
        result = target.evaluate(request)

        assert result.is_valid is True
        assert result.score is not None

    def test_text_field_instead_of_user_input_works(self, target, mock_client):
        """使用text字段代替user_input也应正常工作"""
        mock_client.chat.return_value = "分类结果"
        request = EvaluationSchema(
            id="cls_003",
            type="classification",
            payload={
                "text": "另一个文本",
                "expected_label": "分类结果",
            },
        )
        result = target.evaluate(request)

        assert result.is_valid is True


class TestClassificationEvaluatorNegativeCases:
    """负向测试 - 错误输入"""

    @pytest.fixture
    def mock_client(self):
        client = MagicMock()
        client.config = MagicMock()
        client.config.model_name = "gpt-4"
        client.chat.return_value = "负类"
        return client

    @pytest.fixture
    def target(self, mock_client):
        return ClassificationEvaluator(client=mock_client)

    def test_llm_output_does_not_match_expected_label_score_is_zero(self, target, mock_client):
        """LLM输出不匹配expected_label应返回score=0.0"""
        mock_client.chat.return_value = "负类"
        request = EvaluationSchema(
            id="cls_neg_001",
            type="classification",
            payload={
                "user_input": "消极的评论",
                "expected_label": "正类",
            },
        )
        result = target.evaluate(request)

        assert result.is_valid is True
        assert result.score == 0.0

    def test_empty_user_input_returns_error(self, target, mock_client):
        """空user_input应返回is_valid=False"""
        request = EvaluationSchema(
            id="cls_neg_002",
            type="classification",
            payload={"user_input": ""},
        )
        result = target.evaluate(request)

        assert result.is_valid is False
        assert result.error is not None
        assert "不能为空" in result.error

    def test_empty_text_returns_error(self, target, mock_client):
        """空text字段应返回is_valid=False"""
        request = EvaluationSchema(
            id="cls_neg_003",
            type="classification",
            payload={"text": ""},
        )
        result = target.evaluate(request)

        assert result.is_valid is False

    def test_missing_expected_label_returns_error(self, target, mock_client):
        """无expected_label应返回is_valid=False, error='expected_label 不能为空'"""
        request = EvaluationSchema(
            id="cls_neg_004",
            type="classification",
            payload={"user_input": "测试文本"},
        )
        result = target.evaluate(request)

        assert result.is_valid is False
        assert "expected_label" in result.error
        assert "不能为空" in result.error

    def test_empty_expected_label_returns_error(self, target, mock_client):
        """expected_label为空应返回is_valid=False"""
        request = EvaluationSchema(
            id="cls_neg_005",
            type="classification",
            payload={
                "user_input": "测试文本",
                "expected_label": "",
            },
        )
        result = target.evaluate(request)

        assert result.is_valid is False


class TestClassificationEvaluatorBoundaryCases:
    """边界测试 - 边界值"""

    @pytest.fixture
    def mock_client(self):
        client = MagicMock()
        client.config = MagicMock()
        client.config.model_name = "gpt-4"
        return client

    def test_without_client_uses_expected_label_directly(self, mock_client):
        """无client时应使用expected_label作为llm_output"""
        target = ClassificationEvaluator(client=None)
        request = EvaluationSchema(
            id="cls_bound_001",
            type="classification",
            payload={
                "user_input": "测试文本",
                "expected_label": "正面",
            },
        )
        result = target.evaluate(request)

        assert result.is_valid is True
        assert result.score == 1.0  # expected_label == expected_label

    def test_whitespace_in_output_is_stripped(self, mock_client):
        """输出包含空白字符时应被strip后再比较"""
        mock_client.chat.return_value = "  正面  "  # 带空格
        target = ClassificationEvaluator(client=mock_client)
        request = EvaluationSchema(
            id="cls_bound_002",
            type="classification",
            payload={
                "user_input": "测试",
                "expected_label": "正面",
            },
        )
        result = target.evaluate(request)

        assert result.is_valid is True
        assert result.text == "正面"  # strip后
        assert result.score == 1.0  # strip后 "正面" == "正面"

    def test_empty_labels_uses_default(self, mock_client):
        """labels为空时应使用默认标签"""
        mock_client.chat.return_value = "正类"
        target = ClassificationEvaluator(client=mock_client)
        request = EvaluationSchema(
            id="cls_bound_003",
            type="classification",
            payload={
                "user_input": "测试",
                "expected_label": "正类",
                "labels": [],
            },
        )
        result = target.evaluate(request)

        assert result.is_valid is True

    def test_none_input_returns_error(self, mock_client):
        """None输入应被正确处理"""
        target = ClassificationEvaluator(client=mock_client)
        request = EvaluationSchema(
            id="cls_bound_004",
            type="classification",
            payload={"user_input": None},
        )
        result = target.evaluate(request)

        assert result.is_valid is False


class TestClassificationEvaluatorDependencyHandling:
    """依赖测试 - 外部依赖Mock"""

    @pytest.fixture
    def mock_client(self):
        client = MagicMock()
        client.config = MagicMock()
        client.config.model_name = "gpt-4"
        client.chat.return_value = "正面"
        return client

    def test_with_client_calls_llm(self, mock_client):
        """有client时应调用LLM"""
        target = ClassificationEvaluator(client=mock_client)
        request = EvaluationSchema(
            id="cls_dep_001",
            type="classification",
            payload={
                "user_input": "测试文本",
                "expected_label": "正面",
            },
        )
        result = target.evaluate(request)

        mock_client.chat.assert_called_once()
        assert result.is_valid is True

    def test_without_client_returns_expected_label_match(self):
        """无client时应直接比较expected_label与自身"""
        target = ClassificationEvaluator(client=None)
        request = EvaluationSchema(
            id="cls_dep_002",
            type="classification",
            payload={
                "user_input": "测试文本",
                "expected_label": "分类标签",
            },
        )
        result = target.evaluate(request)

        assert result.score == 1.0


class TestClassificationEvaluatorScoringLogic:
    """评分逻辑测试"""

    @pytest.fixture
    def mock_client(self):
        client = MagicMock()
        client.config = MagicMock()
        client.config.model_name = "gpt-4"
        return client

    def test_exact_match_case_sensitive(self, mock_client):
        """精确匹配（大小写敏感）"""
        mock_client.chat.return_value = "Positive"
        target = ClassificationEvaluator(client=mock_client)
        request = EvaluationSchema(
            id="cls_score_001",
            type="classification",
            payload={
                "user_input": "测试",
                "expected_label": "positive",  # 小写
            },
        )
        result = target.evaluate(request)

        assert result.score == 0.0  # "Positive" != "positive"

    def test_partial_match_not_counted(self, mock_client):
        """部分匹配不应得分"""
        mock_client.chat.return_value = "正面评价"
        target = ClassificationEvaluator(client=mock_client)
        request = EvaluationSchema(
            id="cls_score_002",
            type="classification",
            payload={
                "user_input": "测试",
                "expected_label": "正面",
            },
        )
        result = target.evaluate(request)

        assert result.score == 0.0  # "正面评价" != "正面"

    def test_data_contains_prediction_and_expected(self, mock_client):
        """result.data应包含预测值和期望值"""
        mock_client.chat.return_value = "正面"
        target = ClassificationEvaluator(client=mock_client)
        request = EvaluationSchema(
            id="cls_score_003",
            type="classification",
            payload={
                "user_input": "测试",
                "expected_label": "正面",
            },
        )
        result = target.evaluate(request)

        assert result.data is not None
        assert "预测" in result.data or "预测" in str(result.data)
        assert "预期" in result.data or "预期" in str(result.data)
