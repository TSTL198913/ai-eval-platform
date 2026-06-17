from unittest.mock import MagicMock

from src.domain.evaluators.code_review import CodeReviewEvaluator
from src.schemas.evaluation import EvaluationSchema


class TestCodeReviewEvaluator:
    """代码审查评估器测试"""

    def setup_method(self):
        self.mock_client = MagicMock()

    def test_evaluate_delegates_to_code_evaluator(self):
        """测试评估委托给代码评估器"""
        self.mock_client.chat.return_value = "代码审查结果"

        evaluator = CodeReviewEvaluator(self.mock_client)
        request = EvaluationSchema(
            id="test_code_review",
            type="code_review",
            payload={"code": "def hello():\n    print('Hello')"},
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True

    def test_evaluate_invalid_syntax(self):
        """测试无效语法"""
        evaluator = CodeReviewEvaluator(self.mock_client)
        request = EvaluationSchema(
            id="test_invalid",
            type="code_review",
            payload={"code": "def hello():\n    print('Hello'"},
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is False

    def test_evaluate_missing_code(self):
        """测试缺少代码"""
        evaluator = CodeReviewEvaluator(self.mock_client)
        request = EvaluationSchema(
            id="test_missing",
            type="code_review",
            payload={},
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is False