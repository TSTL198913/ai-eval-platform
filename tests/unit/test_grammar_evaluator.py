from unittest.mock import MagicMock

from src.domain.evaluators.grammar import GrammarEvaluator
from src.schemas.evaluation import EvaluationSchema


class TestGrammarEvaluator:
    """语法检查评估器测试"""

    def setup_method(self):
        self.mock_client = MagicMock()

    def test_evaluate_no_errors(self):
        """测试无语法错误"""
        self.mock_client.chat.return_value = "错误数: 0\n修正后: The cat is on the mat."

        evaluator = GrammarEvaluator(self.mock_client)
        request = EvaluationSchema(
            id="test_grammar_001", type="grammar", payload={"user_input": "The cat is on the mat."}
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.score == 1.0

    def test_evaluate_with_errors(self):
        """测试有语法错误"""
        self.mock_client.chat.return_value = "错误数: 2\n修正后: I go to school."

        evaluator = GrammarEvaluator(self.mock_client)
        request = EvaluationSchema(
            id="test_001", type="grammar", payload={"user_input": "I goes to school."}
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.score == 0.6

    def test_evaluate_missing_user_input(self):
        """测试缺少输入"""
        evaluator = GrammarEvaluator(self.mock_client)
        request = EvaluationSchema(id="test_001", type="grammar", payload={})

        result = evaluator.evaluate(request)

        assert result.is_valid is False

    def test_evaluate_without_client(self):
        """测试无客户端"""
        evaluator = GrammarEvaluator(None)
        request = EvaluationSchema(
            id="test_001", type="grammar", payload={"user_input": "测试语法"}
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.score == 1.0
