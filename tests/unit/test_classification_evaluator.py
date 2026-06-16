from unittest.mock import MagicMock

from src.domain.evaluators.classification import ClassificationEvaluator
from src.schemas.evaluation import EvaluationSchema


class TestClassificationEvaluator:
    """文本分类评估器测试"""

    def setup_method(self):
        self.mock_client = MagicMock()

    def test_evaluate_exact_match(self):
        """测试完全匹配"""
        self.mock_client.chat.return_value = "科技"

        evaluator = ClassificationEvaluator(self.mock_client)
        request = EvaluationSchema(
            id="test_class_001",
            type="classification",
            payload={"user_input": "AI技术", "expected_label": "科技"},
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.score == 1.0

    def test_evaluate_no_match(self):
        """测试完全不匹配"""
        self.mock_client.chat.return_value = "娱乐"

        evaluator = ClassificationEvaluator(self.mock_client)
        request = EvaluationSchema(
            id="test_001",
            type="classification",
            payload={"user_input": "足球", "expected_label": "科技"},
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.score == 0.0

    def test_evaluate_missing_user_input(self):
        """测试缺少输入"""
        evaluator = ClassificationEvaluator(self.mock_client)
        request = EvaluationSchema(
            id="test_001", type="classification", payload={"expected_label": "科技"}
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is False
        assert "不能为空" in result.error

    def test_evaluate_missing_expected_label(self):
        """测试缺少期望类别"""
        evaluator = ClassificationEvaluator(self.mock_client)
        request = EvaluationSchema(
            id="test_001", type="classification", payload={"user_input": "新闻内容"}
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is False

    def test_evaluate_without_client(self):
        """测试无客户端"""
        evaluator = ClassificationEvaluator(None)
        request = EvaluationSchema(
            id="test_001",
            type="classification",
            payload={"user_input": "测试", "expected_label": "测试"},
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
