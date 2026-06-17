from unittest.mock import MagicMock

from src.domain.evaluators.code import CodeEvaluator
from src.schemas.evaluation import EvaluationSchema


class TestCodeEvaluator:
    """代码评估器测试"""

    def setup_method(self):
        self.mock_client = MagicMock()

    def test_evaluate_valid_syntax(self):
        """测试有效语法"""
        self.mock_client.chat.return_value = "代码审查结果"

        evaluator = CodeEvaluator(self.mock_client)
        request = EvaluationSchema(
            id="test_code_valid",
            type="code",
            payload={"code": "def hello():\n    print('Hello')"},
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True

    def test_evaluate_invalid_syntax(self):
        """测试无效语法"""
        evaluator = CodeEvaluator(self.mock_client)
        request = EvaluationSchema(
            id="test_code_invalid",
            type="code",
            payload={"code": "def hello():\n    print('Hello'"},
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is False
        assert "语法错误" in result.error

    def test_evaluate_with_expected_output(self):
        """测试包含期望输出"""
        self.mock_client.chat.return_value = "代码质量良好"

        evaluator = CodeEvaluator(self.mock_client)
        request = EvaluationSchema(
            id="test_expected",
            type="code",
            payload={
                "code": "def add(a, b):\n    return a + b",
                "expected_output": "代码质量良好",
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True

    def test_evaluate_missing_code(self):
        """测试缺少代码"""
        evaluator = CodeEvaluator(self.mock_client)
        request = EvaluationSchema(
            id="test_missing",
            type="code",
            payload={},
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is False
        assert "不能为空" in result.error

    def test_evaluate_without_client(self):
        """测试无客户端模式"""
        evaluator = CodeEvaluator(None)
        request = EvaluationSchema(
            id="test_no_client",
            type="code",
            payload={"code": "def hello():\n    pass"},
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is False

    def test_check_syntax_valid(self):
        """测试语法检查有效"""
        evaluator = CodeEvaluator(self.mock_client)
        syntax_ok, error = evaluator._check_syntax("def test():\n    pass")

        assert syntax_ok is True
        assert error == ""

    def test_check_syntax_invalid(self):
        """测试语法检查无效"""
        evaluator = CodeEvaluator(self.mock_client)
        syntax_ok, error = evaluator._check_syntax("def test(")

        assert syntax_ok is False
        assert "语法错误" in error

    def test_score_review_no_expected(self):
        """测试评分无期望输出"""
        evaluator = CodeEvaluator(self.mock_client)
        score = evaluator._score_review("审查结果", None, True)

        assert score > 0.0

    def test_score_review_with_expected(self):
        """测试评分有期望输出"""
        evaluator = CodeEvaluator(self.mock_client)
        score = evaluator._score_review("代码审查", "代码审查", True)

        assert score == 1.0