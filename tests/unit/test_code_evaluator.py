"""
代码评估器专项测试 - 覆盖语法检查、代码审查评分逻辑
测试目标：验证CodeEvaluator的语法检查、语义评分、多语言支持
"""
import os
import sys
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.domain.evaluators.code import CodeEvaluator
from src.schemas.evaluation import EvaluationSchema


class TestCodeEvaluatorSyntaxCheck:
    """语法检查测试"""

    @pytest.fixture
    def evaluator(self):
        return CodeEvaluator()

    # ============================================================
    # Part 1: Python 语法检查
    # ============================================================
    def test_valid_python_code(self, evaluator):
        """有效Python代码应通过语法检查"""
        request = EvaluationSchema(
            id="code_001",
            type="code",
            payload={
                "code": "def hello():\n    return 'world'",
                "metadata": {"language": "python"},
            },
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is True
        assert result.score >= 0.0

    def test_invalid_python_syntax(self, evaluator):
        """无效Python语法应返回错误"""
        request = EvaluationSchema(
            id="code_002",
            type="code",
            payload={
                "code": "def hello(\n    return 'world'",  # 缺少右括号
                "metadata": {"language": "python"},
            },
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is False
        assert "语法错误" in result.error

    def test_empty_code_returns_error(self, evaluator):
        """空代码应返回错误"""
        request = EvaluationSchema(
            id="code_003",
            type="code",
            payload={"code": ""},
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is False
        assert "不能为空" in result.error

    def test_python_syntax_error_line_number(self, evaluator):
        """语法错误应包含行号"""
        request = EvaluationSchema(
            id="code_004",
            type="code",
            payload={
                "code": "x = 1\nif x > 0\n    print(x)",  # if语句缺少冒号
                "metadata": {"language": "python"},
            },
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is False
        assert "line" in result.error

    # ============================================================
    # Part 2: 代码审查评分（无LLM客户端）
    # ============================================================
    def test_no_llm_client_uses_default_score(self, evaluator):
        """无LLM客户端时使用默认评分"""
        request = EvaluationSchema(
            id="code_005",
            type="code",
            payload={
                "code": "def add(a, b):\n    return a + b",
                "metadata": {"language": "python"},
            },
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is True
        assert result.score == 0.8  # 语法正确，默认0.8

    # ============================================================
    # Part 3: 代码审查评分（有LLM客户端）
    # ============================================================
    @pytest.fixture
    def mock_llm_client(self):
        """Mock LLM客户端"""
        client = MagicMock()
        client.config = MagicMock()
        client.config.model_name = "gpt-4"
        client.chat = MagicMock(return_value="代码审查通过，逻辑清晰")
        return client

    @pytest.fixture
    def evaluator_with_client(self, mock_llm_client):
        return CodeEvaluator(client=mock_llm_client)

    def test_code_review_with_llm_client(self, evaluator_with_client):
        """使用LLM客户端进行代码审查"""
        request = EvaluationSchema(
            id="code_006",
            type="code",
            payload={
                "code": "def multiply(a, b):\n    return a * b",
                "metadata": {"language": "python"},
            },
        )
        result = evaluator_with_client.evaluate(request)
        assert result.is_valid is True
        assert result.text == "代码审查通过，逻辑清晰"
        assert result.score <= 1.0

    def test_code_review_with_expected_output(self, evaluator_with_client):
        """有期望输出时的评分"""
        mock_client = evaluator_with_client.client
        mock_client.chat = MagicMock(return_value="代码实现正确，包含边界条件处理")

        request = EvaluationSchema(
            id="code_007",
            type="code",
            payload={
                "code": "def safe_divide(a, b):\n    if b == 0:\n        return 0\n    return a / b",
                "expected_output": "代码实现正确，包含边界条件处理",
                "metadata": {"language": "python"},
            },
        )
        result = evaluator_with_client.evaluate(request)
        assert result.is_valid is True
        assert result.score >= 0.0

    def test_code_review_different_language(self, evaluator_with_client):
        """不同编程语言的审查（当前仅支持Python语法检查）"""
        mock_client = evaluator_with_client.client
        mock_client.chat = MagicMock(return_value="Python代码审查通过")

        request = EvaluationSchema(
            id="code_008",
            type="code",
            payload={
                "code": "def greet(name):\n    return f'Hello, {name}'",
                "metadata": {"language": "python"},
            },
        )
        result = evaluator_with_client.evaluate(request)
        assert result.is_valid is True
        assert "Python代码审查通过" in result.text


class TestCodeEvaluatorScoring:
    """评分逻辑测试"""

    @pytest.fixture
    def evaluator(self):
        return CodeEvaluator()

    def test_syntax_error_returns_zero_score(self, evaluator):
        """语法错误返回0分"""
        request = EvaluationSchema(
            id="score_001",
            type="code",
            payload={
                "code": "def broken(\n    pass",
                "metadata": {"language": "python"},
            },
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is False
        assert result.score == 0.0

    def test_valid_syntax_default_score(self, evaluator):
        """语法正确无LLM时默认0.8"""
        request = EvaluationSchema(
            id="score_002",
            type="code",
            payload={
                "code": "x = 1\ny = 2\nprint(x + y)",
                "metadata": {"language": "python"},
            },
        )
        result = evaluator.evaluate(request)
        assert result.score == 0.8

    def test_score_with_syntax_and_semantic_weights(self):
        """验证评分权重计算"""
        from src.domain.evaluators.code import SEMANTIC_WEIGHT, SYNTAX_WEIGHT

        assert SYNTAX_WEIGHT == 0.3
        assert SEMANTIC_WEIGHT == 0.7
        assert SYNTAX_WEIGHT + SEMANTIC_WEIGHT == 1.0


class TestCodeEvaluatorMetadata:
    """元数据测试"""

    @pytest.fixture
    def evaluator(self):
        return CodeEvaluator()

    def test_metadata_language_stored(self, evaluator):
        """语言元数据应被存储"""
        request = EvaluationSchema(
            id="meta_001",
            type="code",
            payload={
                "code": "print('hello')",
                "metadata": {"language": "python", "style_guide": "PEP8"},
            },
        )
        result = evaluator.evaluate(request)
        assert result.metadata["language"] == "python"
        assert result.metadata["style_guide"].lower() == "pep8"

    def test_default_language_python(self, evaluator):
        """默认语言应为python"""
        request = EvaluationSchema(
            id="meta_002",
            type="code",
            payload={"code": "print('hello')"},
        )
        result = evaluator.evaluate(request)
        # 即使不提供metadata，也应有language字段
        assert "language" in result.metadata

    def test_syntax_valid_flag(self, evaluator):
        """语法验证标志应正确设置"""
        # 有效代码
        request_valid = EvaluationSchema(
            id="meta_003",
            type="code",
            payload={"code": "x = 1"},
        )
        result_valid = evaluator.evaluate(request_valid)
        assert result_valid.metadata["syntax_valid"] is True

        # 无效代码
        request_invalid = EvaluationSchema(
            id="meta_004",
            type="code",
            payload={"code": "x ="},
        )
        result_invalid = evaluator.evaluate(request_invalid)
        assert result_invalid.is_valid is False
        assert result_invalid.score == 0.0


class TestCodeEvaluatorEdgeCases:
    """边界场景测试"""

    @pytest.fixture
    def evaluator(self):
        return CodeEvaluator()

    def test_code_with_unicode_characters(self, evaluator):
        """包含Unicode字符的代码"""
        request = EvaluationSchema(
            id="edge_001",
            type="code",
            payload={
                "code": "# 中文注释\nname = '测试'\nprint(name)",
                "metadata": {"language": "python"},
            },
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is True

    def test_very_long_code(self, evaluator):
        """超长代码"""
        long_code = "a = 1\n" * 100
        request = EvaluationSchema(
            id="edge_002",
            type="code",
            payload={
                "code": long_code,
                "metadata": {"language": "python"},
            },
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is True

    def test_only_comments(self, evaluator):
        """仅注释代码"""
        request = EvaluationSchema(
            id="edge_003",
            type="code",
            payload={
                "code": "# 这是一个空函数\n# 等待实现",
                "metadata": {"language": "python"},
            },
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is True

    def test_empty_lines_only(self, evaluator):
        """仅空行"""
        request = EvaluationSchema(
            id="edge_004",
            type="code",
            payload={
                "code": "\n\n\n",
                "metadata": {"language": "python"},
            },
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is True  # 空代码语法上是有效的

    def test_malicious_code_detection(self, evaluator):
        """恶意代码模式检测"""
        request = EvaluationSchema(
            id="edge_005",
            type="code",
            payload={
                "code": "import os\nos.system('rm -rf /')",
                "metadata": {"language": "python"},
            },
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is True  # 语法正确，但实际应在安全评估器中检测
