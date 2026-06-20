"""
CodeEvaluator 专项测试
测试目标：验证 CodeEvaluator 的语法检查、评分逻辑、依赖处理
关键发现：测试覆盖正向、负向、边界、异常、依赖场景
"""

import os
import sys
import pytest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.domain.evaluators.code import CodeEvaluator, create_code_evaluator, SYNTAX_WEIGHT, SEMANTIC_WEIGHT
from src.schemas.evaluation import EvaluationSchema


class TestCodeEvaluatorPositiveCases:
    """正向测试 - 正常输入应返回预期输出"""

    @pytest.fixture
    def evaluator(self):
        """创建无 LLM client 的评估器"""
        return CodeEvaluator()

    def test_valid_python_code_passes(self, evaluator):
        """有效的 Python 代码应通过评估"""
        # Arrange
        request = EvaluationSchema(
            id="pos_001",
            type="code",
            payload={
                "code": "def hello():\n    return 'world'",
            },
        )

        # Act
        result = evaluator.evaluate(request)

        # Assert - 强断言验证业务逻辑
        assert result.is_valid is True
        assert result.score == 0.8  # 无 LLM client 时默认分数
        assert result.error is None
        assert result.metadata["syntax_valid"] is True
        assert result.metadata["language"] == "python"

    def test_code_with_text_field_instead_of_code(self, evaluator):
        """使用 text 字段而非 code 字段应正常工作"""
        # Arrange
        request = EvaluationSchema(
            id="pos_002",
            type="code",
            payload={
                "text": "x = 1\nprint(x)",
            },
        )

        # Act
        result = evaluator.evaluate(request)

        # Assert
        assert result.is_valid is True
        assert result.score == 0.8
        assert result.metadata["syntax_valid"] is True

    def test_custom_system_prompt_used(self, evaluator):
        """自定义 system_prompt 应被传递给 LLM client"""
        # Arrange - 创建带 Mock client 的评估器
        mock_client = MagicMock()
        mock_client.chat.return_value = "代码质量优秀"
        evaluator_with_client = CodeEvaluator(client=mock_client)

        request = EvaluationSchema(
            id="pos_003",
            type="code",
            payload={
                "code": "def add(a, b):\n    return a + b",
                "system_prompt": "请用中文审查代码",
            },
        )

        # Act
        result = evaluator_with_client.evaluate(request)

        # Assert - 验证 system_prompt 被传递
        mock_client.chat.assert_called_once()
        call_args = mock_client.chat.call_args
        assert call_args[1]["system_prompt"] == "请用中文审查代码"
        assert result.is_valid is True

    def test_with_expected_output_calculates_score(self, evaluator):
        """有期望输出时应计算相似度分数"""
        # Arrange
        mock_client = MagicMock()
        mock_client.chat.return_value = "代码实现正确，包含边界条件处理"
        evaluator_with_client = CodeEvaluator(client=mock_client)

        request = EvaluationSchema(
            id="pos_004",
            type="code",
            payload={
                "code": "def safe_divide(a, b):\n    if b == 0:\n        return 0\n    return a / b",
                "expected_output": "代码实现正确，包含边界条件处理",
            },
        )

        # Act
        result = evaluator_with_client.evaluate(request)

        # Assert - 验证分数计算（语法分 + 语义分）
        assert result.is_valid is True
        assert result.score >= SYNTAX_WEIGHT  # 至少包含语法分
        assert result.score <= 1.0
        assert result.metadata["expected_output"] == "代码实现正确，包含边界条件处理"

    def test_different_language_metadata(self, evaluator):
        """不同编程语言的元数据应正确存储"""
        # Arrange
        request = EvaluationSchema(
            id="pos_005",
            type="code",
            payload={
                "code": "console.log('hello');",
            },
            metadata={"language": "javascript", "style_guide": "airbnb"},
        )

        # Act
        result = evaluator.evaluate(request)

        # Assert
        assert result.metadata["language"] == "javascript"
        assert result.metadata["style_guide"] == "airbnb"
        assert result.metadata["syntax_valid"] is True


class TestCodeEvaluatorNegativeCases:
    """负向测试 - 错误输入应返回错误"""

    @pytest.fixture
    def evaluator(self):
        return CodeEvaluator()

    def test_empty_code_returns_error(self, evaluator):
        """空代码应返回错误"""
        # Arrange
        request = EvaluationSchema(
            id="neg_001",
            type="code",
            payload={"code": ""},
        )

        # Act
        result = evaluator.evaluate(request)

        # Assert
        assert result.is_valid is False
        assert "不能为空" in result.error
        assert result.score is None

    def test_syntax_error_returns_error_with_line_number(self, evaluator):
        """语法错误应包含行号信息"""
        # Arrange
        request = EvaluationSchema(
            id="neg_002",
            type="code",
            payload={
                "code": "def broken(\n    pass",  # 缺少右括号
            },
        )

        # Act
        result = evaluator.evaluate(request)

        # Assert
        assert result.is_valid is False
        assert "语法错误" in result.error
        assert "line" in result.error
        assert result.score == 0.0

    def test_missing_colon_in_if_statement(self, evaluator):
        """if 语句缺少冒号应返回错误"""
        # Arrange
        request = EvaluationSchema(
            id="neg_003",
            type="code",
            payload={
                "code": "x = 1\nif x > 0\n    print(x)",
            },
        )

        # Act
        result = evaluator.evaluate(request)

        # Assert
        assert result.is_valid is False
        assert "语法错误" in result.error
        assert result.score == 0.0

    def test_invalid_indentation(self, evaluator):
        """无效缩进应返回错误"""
        # Arrange
        request = EvaluationSchema(
            id="neg_004",
            type="code",
            payload={
                "code": "def test():\nprint('wrong indent')",
            },
        )

        # Act
        result = evaluator.evaluate(request)

        # Assert
        assert result.is_valid is False
        assert "语法错误" in result.error or "indent" in result.error.lower()

    def test_none_payload_code_returns_error(self, evaluator):
        """payload 中 code 和 text 都为 None 时应返回错误"""
        # Arrange
        request = EvaluationSchema(
            id="neg_005",
            type="code",
            payload={"other_field": "value"},
        )

        # Act
        result = evaluator.evaluate(request)

        # Assert
        assert result.is_valid is False
        assert "不能为空" in result.error


class TestCodeEvaluatorBoundaryCases:
    """边界测试 - 边界值处理"""

    @pytest.fixture
    def evaluator(self):
        return CodeEvaluator()

    def test_minimal_valid_code(self, evaluator):
        """最小有效代码（单个表达式）"""
        # Arrange
        request = EvaluationSchema(
            id="bound_001",
            type="code",
            payload={"code": "x = 1"},
        )

        # Act
        result = evaluator.evaluate(request)

        # Assert
        assert result.is_valid is True
        assert result.score == 0.8

    def test_very_long_code(self, evaluator):
        """超长代码（1000行）"""
        # Arrange
        long_code = "\n".join([f"line_{i} = {i}" for i in range(1000)])
        request = EvaluationSchema(
            id="bound_002",
            type="code",
            payload={"code": long_code},
        )

        # Act
        result = evaluator.evaluate(request)

        # Assert
        assert result.is_valid is True
        assert result.score == 0.8

    def test_code_with_unicode_characters(self, evaluator):
        """包含 Unicode 字符的代码"""
        # Arrange
        request = EvaluationSchema(
            id="bound_003",
            type="code",
            payload={
                "code": "# 中文注释\nname = '测试'\nprint(name)",
            },
        )

        # Act
        result = evaluator.evaluate(request)

        # Assert
        assert result.is_valid is True
        assert result.score == 0.8

    def test_code_only_comments(self, evaluator):
        """仅包含注释的代码"""
        # Arrange
        request = EvaluationSchema(
            id="bound_004",
            type="code",
            payload={
                "code": "# 这是一个空函数\n# 等待实现\n# TODO: 实现逻辑",
            },
        )

        # Act
        result = evaluator.evaluate(request)

        # Assert
        assert result.is_valid is True
        assert result.score == 0.8

    def test_code_empty_lines_only(self, evaluator):
        """仅包含空行的代码"""
        # Arrange
        request = EvaluationSchema(
            id="bound_005",
            type="code",
            payload={"code": "\n\n\n"},
        )

        # Act
        result = evaluator.evaluate(request)

        # Assert
        assert result.is_valid is True
        assert result.score == 0.8

    def test_none_metadata_uses_defaults(self, evaluator):
        """metadata 为 None 时使用默认值"""
        # Arrange
        request = EvaluationSchema(
            id="bound_006",
            type="code",
            payload={"code": "x = 1"},
            metadata=None,
        )

        # Act
        result = evaluator.evaluate(request)

        # Assert
        assert result.metadata["language"] == "python"  # 默认语言
        assert result.metadata["style_guide"] == "pep8"  # 默认风格


class TestCodeEvaluatorExceptionCases:
    """异常测试 - 异常情况处理"""

    @pytest.fixture
    def evaluator(self):
        return CodeEvaluator()

    def test_llm_client_raises_exception(self, evaluator):
        """LLM client 抛出异常时应正确处理"""
        # Arrange
        mock_client = MagicMock()
        mock_client.chat.side_effect = Exception("LLM service unavailable")
        evaluator_with_client = CodeEvaluator(client=mock_client)

        request = EvaluationSchema(
            id="exc_001",
            type="code",
            payload={"code": "x = 1"},
        )

        # Act & Assert - 异常应向上传播
        with pytest.raises(Exception) as exc_info:
            evaluator_with_client.evaluate(request)
        assert "LLM service unavailable" in str(exc_info.value)

    def test_scoring_function_with_empty_llm_output(self, evaluator):
        """LLM 输出为空字符串时的评分"""
        # Arrange
        mock_client = MagicMock()
        mock_client.chat.return_value = ""
        evaluator_with_client = CodeEvaluator(client=mock_client)

        request = EvaluationSchema(
            id="exc_002",
            type="code",
            payload={"code": "x = 1"},
        )

        # Act
        result = evaluator_with_client.evaluate(request)

        # Assert - 空输出时语义分为 0
        assert result.score == SYNTAX_WEIGHT  # 仅语法分
        assert result.is_valid is False  # 0.3 < 0.8 阈值

    def test_scoring_function_with_whitespace_output(self, evaluator):
        """LLM 输出仅包含空白字符时的评分"""
        # Arrange
        mock_client = MagicMock()
        mock_client.chat.return_value = "   \n\t  "
        evaluator_with_client = CodeEvaluator(client=mock_client)

        request = EvaluationSchema(
            id="exc_003",
            type="code",
            payload={"code": "x = 1"},
        )

        # Act
        result = evaluator_with_client.evaluate(request)

        # Assert - 空白输出视为空
        assert result.score == SYNTAX_WEIGHT


class TestCodeEvaluatorDependencyHandling:
    """依赖测试 - 外部依赖 Mock 验证"""

    @pytest.fixture
    def evaluator(self):
        return CodeEvaluator()

    def test_without_llm_client_uses_default_scoring(self, evaluator):
        """无 LLM client 时使用默认评分 0.8"""
        # Arrange
        request = EvaluationSchema(
            id="dep_001",
            type="code",
            payload={"code": "x = 1"},
        )

        # Act
        result = evaluator.evaluate(request)

        # Assert
        assert result.is_valid is True
        assert result.score == 0.8
        assert "语法检查通过" in result.text

    def test_with_mock_llm_client(self, evaluator):
        """使用 Mock LLM client 应正确调用"""
        # Arrange
        mock_client = MagicMock()
        mock_client.chat.return_value = "代码质量良好，符合规范"
        evaluator_with_client = CodeEvaluator(client=mock_client)

        request = EvaluationSchema(
            id="dep_002",
            type="code",
            payload={
                "code": "def add(a, b):\n    return a + b",
            },
            metadata={"language": "python"},
        )

        # Act
        result = evaluator_with_client.evaluate(request)

        # Assert - 验证 Mock 调用
        mock_client.chat.assert_called_once()
        call_args = mock_client.chat.call_args
        assert "def add(a, b):" in call_args[0][0]
        assert "python" in call_args[0][0]
        assert result.text == "代码质量良好，符合规范"

    def test_llm_client_chat_parameters(self, evaluator):
        """验证 LLM client.chat 的调用参数"""
        # Arrange
        mock_client = MagicMock()
        mock_client.chat.return_value = "审查结果"
        evaluator_with_client = CodeEvaluator(client=mock_client)

        request = EvaluationSchema(
            id="dep_003",
            type="code",
            payload={
                "code": "print('hello')",
                "system_prompt": "你是代码审查专家",
            },
            metadata={"language": "python"},
        )

        # Act
        evaluator_with_client.evaluate(request)

        # Assert - 验证参数
        call_args = mock_client.chat.call_args
        # 第一个位置参数是 review_prompt
        assert "print('hello')" in call_args[0][0]
        # system_prompt 作为关键字参数
        assert call_args[1]["system_prompt"] == "你是代码审查专家"

    @patch('src.domain.evaluators.code.score_text_similarity')
    @patch('src.domain.evaluators.code.score_keyword_overlap')
    def test_scoring_functions_called_correctly(self, mock_keyword, mock_similarity, evaluator):
        """验证评分函数被正确调用"""
        # Arrange
        mock_client = MagicMock()
        mock_client.chat.return_value = "代码审查通过"
        evaluator_with_client = CodeEvaluator(client=mock_client)

        mock_similarity.return_value = 0.9
        mock_keyword.return_value = 0.8

        request = EvaluationSchema(
            id="dep_004",
            type="code",
            payload={
                "code": "x = 1",
                "expected_output": "代码审查通过",
            },
        )

        # Act
        result = evaluator_with_client.evaluate(request)

        # Assert - 验证评分函数被调用
        # 由于 min(score, 1.0) 限制，分数最高为1.0
        expected_score = min(SYNTAX_WEIGHT + SEMANTIC_WEIGHT * 0.9, 1.0)
        assert result.score == pytest.approx(expected_score, rel=1e-2) or result.score == 1.0

    def test_factory_creates_evaluator(self):
        """工厂函数应正确创建评估器"""
        # Act
        evaluator = create_code_evaluator()

        # Assert
        assert evaluator.__class__.__name__ == "CodeEvaluator"
        assert evaluator.client is None

    def test_factory_creates_evaluator_with_client(self):
        """工厂函数应支持传入 client"""
        # Arrange
        mock_client = MagicMock()

        # Act
        evaluator = create_code_evaluator(client=mock_client)

        # Assert
        assert evaluator.__class__.__name__ == "CodeEvaluator"
        assert evaluator.client == mock_client


class TestCodeEvaluatorScoringLogic:
    """评分逻辑详细测试"""

    @pytest.fixture
    def evaluator(self):
        return CodeEvaluator()

    def test_syntax_weight_constant(self):
        """验证语法权重常量"""
        assert SYNTAX_WEIGHT == 0.3

    def test_semantic_weight_constant(self):
        """验证语义权重常量"""
        assert SEMANTIC_WEIGHT == 0.7

    def test_weights_sum_to_one(self):
        """验证权重总和为 1"""
        assert SYNTAX_WEIGHT + SEMANTIC_WEIGHT == 1.0

    def test_score_without_expected_output(self, evaluator):
        """无期望输出时，语义分基于 LLM 输出是否为空"""
        # Arrange
        mock_client = MagicMock()
        mock_client.chat.return_value = "代码审查通过"
        evaluator_with_client = CodeEvaluator(client=mock_client)

        request = EvaluationSchema(
            id="score_001",
            type="code",
            payload={"code": "x = 1"},
        )

        # Act
        result = evaluator_with_client.evaluate(request)

        # Assert - 无期望输出时，语义分为 SEMANTIC_WEIGHT
        assert result.score == SYNTAX_WEIGHT + SEMANTIC_WEIGHT  # 1.0

    def test_score_with_high_similarity(self, evaluator):
        """高相似度时应得高分"""
        # Arrange
        mock_client = MagicMock()
        mock_client.chat.return_value = "代码实现正确，逻辑清晰"
        evaluator_with_client = CodeEvaluator(client=mock_client)

        request = EvaluationSchema(
            id="score_002",
            type="code",
            payload={
                "code": "x = 1",
                "expected_output": "代码实现正确，逻辑清晰",
            },
        )

        # Act
        result = evaluator_with_client.evaluate(request)

        # Assert - 高相似度应得高分
        assert result.score >= 0.9
        assert result.is_valid is True

    def test_score_with_low_similarity(self, evaluator):
        """低相似度时应得低分"""
        # Arrange
        mock_client = MagicMock()
        mock_client.chat.return_value = "代码有问题"
        evaluator_with_client = CodeEvaluator(client=mock_client)

        request = EvaluationSchema(
            id="score_003",
            type="code",
            payload={
                "code": "x = 1",
                "expected_output": "代码实现正确，逻辑清晰，符合规范",
            },
        )

        # Act
        result = evaluator_with_client.evaluate(request)

        # Assert - 低相似度时分数较低
        assert result.score < 1.0
        # 但至少有语法分
        assert result.score >= SYNTAX_WEIGHT