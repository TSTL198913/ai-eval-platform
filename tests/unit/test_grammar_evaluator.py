import pytest
from unittest.mock import MagicMock
from src.schemas.evaluation import EvaluationSchema
from src.domain.evaluators.grammar import GrammarEvaluator


class TestGrammarEvaluator:
    """语法检查评估器测试"""

    def setup_method(self):
        self.mock_client = MagicMock()

    def test_evaluate_grammatically_correct(self):
        """测试语法正确"""
        self.mock_client.chat.return_value = "The cat is on the mat."

        evaluator = GrammarEvaluator(self.mock_client)
        request = EvaluationSchema(
            id="test_grammar_001",
            type="grammar",
            payload={
                "user_input": "猫在垫子上。",
                "expected_output": "The cat is on the mat."
            }
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.score is not None

    def test_evaluate_grammatically_incorrect(self):
        """测试语法错误"""
        self.mock_client.chat.return_value = "I goes to school."

        evaluator = GrammarEvaluator(self.mock_client)
        request = EvaluationSchema(
            id="test_001",
            type="grammar",
            payload={"user_input": "我走去学校", "expected_output": "I go to school."}
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.score is not None

    def test_evaluate_missing_user_input(self):
        """测试缺少输入"""
        evaluator = GrammarEvaluator(self.mock_client)
        request = EvaluationSchema(
            id="test_001",
            type="grammar",
            payload={}
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is False

    def test_evaluate_without_client(self):
        """测试无客户端"""
        evaluator = GrammarEvaluator(None)
        request = EvaluationSchema(
            id="test_001",
            type="grammar",
            payload={"user_input": "测试语法", "expected_output": "test"}
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True

    def test_evaluate_score_range(self):
        """测试分数范围"""
        self.mock_client.chat.return_value = "Correct sentence."

        evaluator = GrammarEvaluator(self.mock_client)
        request = EvaluationSchema(
            id="test_001",
            type="grammar",
            payload={"user_input": "正确句子", "expected_output": "Correct"}
        )

        result = evaluator.evaluate(request)

        assert 0 <= result.score <= 1

    def test_evaluate_with_corrections(self):
        """测试包含修正"""
        self.mock_client.chat.return_value = "She goes to school every day."

        evaluator = GrammarEvaluator(self.mock_client)
        request = EvaluationSchema(
            id="test_001",
            type="grammar",
            payload={"user_input": "她每天去学校", "expected_output": "She goes to school every day."}
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
