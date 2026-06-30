"""
CodeEvaluator专项测试
测试目标：验证CodeEvaluator的代码审查功能
核心功能：
1. Python语法检查
2. 代码语义评分（基于LLM）
3. 期望输出对比

关键发现：
1. DEFAULT_SYNTAX_WEIGHT=0.2, DEFAULT_SEMANTIC_WEIGHT=0.3
2. 无LLM client时score=0.8（仅语法）
3. 语法错误返回(is_valid=False, error包含"语法错误")
4. 有效代码返回(is_valid=True, score>=0.8)
"""

import os
import sys
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.domain.evaluators.code import DEFAULT_SEMANTIC_WEIGHT, DEFAULT_SYNTAX_WEIGHT, CodeEvaluator
from src.domain.evaluators.scoring import is_passing
from src.schemas.evaluation import EvaluationSchema


class TestCodeEvaluatorPositiveCases:
    """正向测试 - 有效代码应通过语法检查"""

    @pytest.fixture
    def evaluator_without_client(self):
        """无LLM客户端的评估器"""
        return CodeEvaluator(client=None)

    @pytest.fixture
    def evaluator_with_client(self):
        """带LLM客户端的评估器"""
        mock_client = MagicMock()
        mock_client.chat.return_value = "代码审查完成，发现一些可改进的地方。"
        return CodeEvaluator(client=mock_client)

    def test_valid_python_code_passes_syntax(self, evaluator_without_client):
        """有效Python代码应通过语法检查"""
        request = EvaluationSchema(
            id="code_001",
            type="code",
            payload={
                "code": "def hello():\n    return 'Hello, World!'",
                "metadata": {"language": "python"},
            },
        )

        result = evaluator_without_client.evaluate(request)

        assert result.is_valid is True
        assert result.score >= 0.8
        assert "语法" in result.text or "通过" in result.text

    def test_valid_code_with_expected_output_similarity(self, evaluator_with_client):
        """有expected_output时评分基于文本相似度"""
        mock_client = evaluator_with_client.client
        mock_client.chat.return_value = "代码审查：良好，符合最佳实践"

        request = EvaluationSchema(
            id="code_002",
            type="code",
            payload={
                "code": "def add(a, b):\n    return a + b",
                "expected_output": "代码审查：良好，符合最佳实践",
                "metadata": {"language": "python"},
            },
        )

        result = evaluator_with_client.evaluate(request)

        assert result.is_valid is True
        assert result.score >= DEFAULT_SYNTAX_WEIGHT
        mock_client.chat.assert_called_once()

    def test_valid_code_in_payload(self, evaluator_without_client):
        """代码在payload中应正常处理"""
        request = EvaluationSchema(
            id="code_003",
            type="code",
            payload={
                "code": "print('Hello')",
                "metadata": {"language": "python"},
            },
        )

        result = evaluator_without_client.evaluate(request)

        assert result.is_valid is True

    def test_valid_code_in_user_input(self, evaluator_without_client):
        """代码在user_input中应正常处理"""
        request = EvaluationSchema(
            id="code_004",
            type="code",
            payload={
                "text": "x = 1 + 2",
                "metadata": {"language": "python"},
            },
        )

        result = evaluator_without_client.evaluate(request)

        assert result.is_valid is True


class TestCodeEvaluatorNegativeCases:
    """负向测试 - 语法错误应返回错误"""

    @pytest.fixture
    def evaluator(self):
        return CodeEvaluator(client=None)

    def test_syntax_error_returns_zero_score(self, evaluator):
        """语法错误应返回score=0.0"""
        request = EvaluationSchema(
            id="code_010",
            type="code",
            payload={
                "code": "def hello()\n    return 'Hello'",  # 缺少冒号
                "metadata": {"language": "python"},
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert "语法错误" in result.text
        assert result.score == 0.0

    def test_unmatched_parenthesis_error(self, evaluator):
        """括号不匹配应返回语法错误"""
        request = EvaluationSchema(
            id="code_011",
            type="code",
            payload={
                "code": "print('Hello'",  # 缺少右括号
                "metadata": {"language": "python"},
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert "语法错误" in result.text
        assert result.score == 0.0

    def test_invalid_indentation_error(self, evaluator):
        """无效缩进应返回语法错误"""
        request = EvaluationSchema(
            id="code_012",
            type="code",
            payload={
                "code": "def hello():\nreturn 'Hello'",  # 缩进错误
                "metadata": {"language": "python"},
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert "语法错误" in result.text
        assert result.score == 0.0


class TestCodeEvaluatorBoundaryCases:
    """边界测试"""

    @pytest.fixture
    def evaluator(self):
        return CodeEvaluator(client=None)

    def test_empty_code_returns_error(self, evaluator):
        """空代码应返回错误"""
        request = EvaluationSchema(
            id="code_020",
            type="code",
            payload={
                "code": "",
                "metadata": {"language": "python"},
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is False
        assert "不能为空" in result.error

    def test_no_code_no_text_returns_error(self, evaluator):
        """无code也无text应返回错误"""
        request = EvaluationSchema(
            id="code_021",
            type="code",
            payload={},
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is False
        assert "不能为空" in result.error

    def test_without_llm_client_syntax_only_score(self, evaluator):
        """无LLM client时应仅基于语法评分"""
        request = EvaluationSchema(
            id="code_022",
            type="code",
            payload={
                "code": "def hello():\n    print('Hello')",
                "metadata": {"language": "python"},
            },
        )

        result = evaluator.evaluate(request)

        # 无LLM client时，语法正确score=0.8
        assert result.score == 0.8
        assert result.is_valid is True


class TestCodeEvaluatorScoringLogic:
    """评分逻辑测试"""

    def test_syntax_weight_constant(self):
        """DEFAULT_SYNTAX_WEIGHT应为0.2"""
        assert DEFAULT_SYNTAX_WEIGHT == 0.2

    def test_semantic_weight_constant(self):
        """DEFAULT_SEMANTIC_WEIGHT应为0.3"""
        assert DEFAULT_SEMANTIC_WEIGHT == 0.3

    @pytest.fixture
    def mock_client(self):
        client = MagicMock()
        client.chat.return_value = "代码审查建议"
        return client

    def test_with_llm_client_combines_scores(self, mock_client):
        """有LLM client时应组合语法和语义分数"""
        evaluator = CodeEvaluator(client=mock_client)

        request = EvaluationSchema(
            id="code_030",
            type="code",
            payload={
                "code": "def add(a, b):\n    return a + b",
                "expected_output": "代码审查：良好实践",
                "metadata": {"language": "python"},
            },
        )

        result = evaluator.evaluate(request)

        # 语法正确(0.2) + 语义部分匹配(部分0.3)
        assert result.score >= DEFAULT_SYNTAX_WEIGHT
        assert result.score <= 1.0

    def test_without_expected_output_semantic_score(self, mock_client):
        """无expected_output时语义分数基于LLM输出"""
        mock_client.chat.return_value = "代码审查：发现一些问题"

        evaluator = CodeEvaluator(client=mock_client)

        request = EvaluationSchema(
            id="code_031",
            type="code",
            payload={
                "code": "def add(a, b):\n    return a + b",
                "metadata": {"language": "python"},
            },
        )

        result = evaluator.evaluate(request)

        # 有LLM输出，语义分数应为DEFAULT_SEMANTIC_WEIGHT
        assert result.score >= DEFAULT_SYNTAX_WEIGHT


class TestCodeEvaluatorDependencyHandling:
    """依赖测试"""

    @pytest.fixture
    def mock_client(self):
        client = MagicMock()
        client.chat.return_value = "代码审查完成"
        return client

    def test_llm_client_is_used(self, mock_client):
        """验证LLM客户端被使用"""
        evaluator = CodeEvaluator(client=mock_client)

        request = EvaluationSchema(
            id="code_040",
            type="code",
            payload={
                "code": "x = 1",
                "expected_output": "good",
                "metadata": {"language": "python"},
            },
        )

        evaluator.evaluate(request)

        mock_client.chat.assert_called_once()

    def test_llm_client_called_with_code_review_prompt(self, mock_client):
        """验证LLM客户端被用正确参数调用"""
        evaluator = CodeEvaluator(client=mock_client)

        request = EvaluationSchema(
            id="code_041",
            type="code",
            payload={
                "code": "def hello():\n    pass",
                "metadata": {"language": "python"},
            },
        )

        evaluator.evaluate(request)

        call_args = mock_client.chat.call_args
        assert "def hello" in call_args[0][0]
        assert "python" in call_args[0][0].lower()

    def test_without_llm_client_still_works(self):
        """无LLM客户端时应正常工作"""
        evaluator = CodeEvaluator(client=None)

        request = EvaluationSchema(
            id="code_042",
            type="code",
            payload={
                "code": "valid_code = True",
                "metadata": {"language": "python"},
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.score == 0.8


class TestCodeEvaluatorMetadata:
    """元数据处理测试"""

    @pytest.fixture
    def evaluator(self):
        return CodeEvaluator(client=None)

    def test_language_in_data(self, evaluator):
        """语言应在data中返回"""
        request = EvaluationSchema(
            id="code_050",
            type="code",
            payload={"code": "print(1)"},
            metadata={"language": "python", "style_guide": "pep8"},
        )

        result = evaluator.evaluate(request)

        assert result.data["language"] == "python"
        assert result.data["style_guide"] == "pep8"

    def test_default_metadata_values(self, evaluator):
        """默认metadata值"""
        request = EvaluationSchema(
            id="code_051",
            type="code",
            payload={"code": "print(1)"},
            metadata={},
        )

        result = evaluator.evaluate(request)

        assert result.data["language"] == "python"
        assert result.data["style_guide"] == ""

    def test_none_metadata_handled(self, evaluator):
        """None metadata应正常处理"""
        request = EvaluationSchema(
            id="code_052",
            type="code",
            payload={
                "code": "print(1)",
            },
        )

        result = evaluator.evaluate(request)

        assert result.data["language"] == "python"


class TestCodeEvaluatorSystemPrompt:
    """系统提示词测试"""

    @pytest.fixture
    def mock_client(self):
        client = MagicMock()
        client.chat.return_value = "审查完成"
        return client

    def test_custom_system_prompt_used(self, mock_client):
        """自定义system_prompt应被使用"""
        evaluator = CodeEvaluator(client=mock_client)

        request = EvaluationSchema(
            id="code_060",
            type="code",
            payload={
                "code": "x = 1",
                "system_prompt": "你是一个代码审查员",
                "metadata": {"language": "python"},
            },
        )

        evaluator.evaluate(request)

        call_args = mock_client.chat.call_args
        assert call_args[1]["system_prompt"] == "你是一个代码审查员"


class TestCodeEvaluatorSyntaxCheck:
    """语法检查专项测试"""

    @pytest.fixture
    def evaluator(self):
        return CodeEvaluator(client=None)

    def test_valid_function_definition(self, evaluator):
        """有效函数定义"""
        result = evaluator._check_syntax("def add(a, b):\n    return a + b")

        assert result[0] is True
        assert result[1] == ""

    def test_valid_class_definition(self, evaluator):
        """有效类定义"""
        result = evaluator._check_syntax("class MyClass:\n    def __init__(self):\n        pass")

        assert result[0] is True

    def test_valid_import(self, evaluator):
        """有效导入语句"""
        result = evaluator._check_syntax("import os\nfrom sys import path")

        assert result[0] is True

    def test_invalid_syntax_returns_error(self, evaluator):
        """无效语法返回错误"""
        result = evaluator._check_syntax("if x =\n    pass")

        assert result[0] is False
        assert "语法错误" in result[1]

    def test_syntax_error_includes_line_number(self, evaluator):
        """语法错误应包含行号"""
        result = evaluator._check_syntax("def hello()\n    pass")

        assert result[0] is False
        assert "第" in result[1] and "行" in result[1]


class TestIsPassingFunction:
    """is_passing函数测试"""

    def test_high_score_passes(self):
        """高分应通过"""
        assert is_passing(0.8) is True
        assert is_passing(1.0) is True

    def test_low_score_fails(self):
        """低分应失败"""
        assert is_passing(0.79) is False
        assert is_passing(0.0) is False

    def test_threshold_boundary(self):
        """阈值边界"""
        assert is_passing(0.8) is True
        assert is_passing(0.799) is False
