"""
CodeReviewEvaluator 专项测试
测试目标：验证 CodeReviewEvaluator 的委托机制、工厂注册和边界处理
关键发现：CodeReviewEvaluator 是 CodeEvaluator 的包装器，所有逻辑委托给 CodeEvaluator
"""

import os
import sys
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.domain.evaluators.code import CodeEvaluator
from src.domain.evaluators.code_review import CodeReviewEvaluator, create_code_review_evaluator
from src.domain.evaluators.evaluator_factory import EvaluatorFactory
from src.schemas.evaluation import DomainResponse, EvaluationSchema


@pytest.fixture(autouse=True)
def reset_evaluators_each_test():
    """
    自动在每个测试前重置 EvaluatorFactory 并重新触发自动发现。
    """
    from src.domain.evaluators import auto_discover
    from src.domain.evaluators.evaluator_factory import EvaluatorFactory as EF

    EF._registry = {}
    auto_discover(force=True)
    yield
    EF._registry = {}


# ============================================================
# Part 1: 正向测试 - 正常输入
# ============================================================
class TestCodeReviewEvaluatorPositiveCases:
    """正向测试 - 验证正常代码审查流程"""

    @pytest.fixture
    def evaluator(self):
        """创建无 LLM client 的评估器"""
        return CodeReviewEvaluator()

    @pytest.fixture
    def evaluator_with_client(self):
        """创建有 LLM client 的评估器"""
        client = MagicMock()
        client.chat.return_value = "代码审查通过，无明显问题"
        return CodeReviewEvaluator(client=client)

    def test_valid_python_code_without_client_returns_success(self, evaluator):
        """合法 Python 代码（无 LLM client）应返回成功"""
        # Arrange
        request = EvaluationSchema(
            id="case_001", type="code_review", payload={"code": "def hello():\n    print('hello')"}
        )

        # Act
        result = evaluator.evaluate(request)

        # Assert - 强断言
        assert result.is_valid is True
        assert result.score == 0.8  # 语法正确，无 LLM 审查时默认 0.8
        assert result.metadata is not None
        assert result.metadata["syntax_valid"] is True
        assert result.metadata["language"] == "python"

    def test_valid_python_code_with_client_uses_llm_review(self, evaluator_with_client):
        """合法 Python 代码（有 LLM client）应调用 LLM 进行审查"""
        # Arrange
        request = EvaluationSchema(
            id="case_002",
            type="code_review",
            payload={"code": "def add(a, b):\n    return a + b", "system_prompt": "请审查代码质量"},
        )

        # Act
        result = evaluator_with_client.evaluate(request)

        # Assert - 强断言
        assert result.is_valid is True
        assert result.score >= 0.0
        assert result.text is not None
        assert "代码审查" in result.text
        # 验证 LLM client 被调用
        evaluator_with_client.client.chat.assert_called_once()

    def test_evaluate_with_expected_output_calculates_score(self, evaluator_with_client):
        """有期望输出时应计算相似度分数"""
        # Arrange
        evaluator_with_client.client.chat.return_value = "代码质量良好，符合规范"
        request = EvaluationSchema(
            id="case_003",
            type="code_review",
            payload={"code": "x = 1", "expected_output": "代码质量良好"},
        )

        # Act
        result = evaluator_with_client.evaluate(request)

        # Assert - 强断言
        assert result.is_valid is True
        assert result.score > 0.0
        assert result.metadata is not None
        assert result.metadata["expected_output"] == "代码质量良好"

    def test_evaluate_with_custom_metadata(self, evaluator):
        """自定义 metadata 应正确传递"""
        # Arrange
        request = EvaluationSchema(
            id="case_004",
            type="code_review",
            payload={"code": "print('hello')"},
            metadata={"language": "python", "style_guide": "google"},
        )

        # Act
        result = evaluator.evaluate(request)

        # Assert - 强断言
        assert result.is_valid is True
        assert result.metadata["language"] == "python"
        assert result.metadata["style_guide"] == "google"

    def test_evaluate_with_text_field_as_code_input(self, evaluator):
        """使用 text 字段作为代码输入应正常工作"""
        # Arrange
        request = EvaluationSchema(id="case_005", type="code_review", payload={"text": "x = 1 + 2"})

        # Act
        result = evaluator.evaluate(request)

        # Assert - 强断言
        assert result.is_valid is True
        assert result.score == 0.8


# ============================================================
# Part 2: 负向测试 - 错误输入
# ============================================================
class TestCodeReviewEvaluatorNegativeCases:
    """负向测试 - 验证错误输入的处理"""

    @pytest.fixture
    def evaluator(self):
        return CodeReviewEvaluator()

    def test_empty_code_returns_error(self, evaluator):
        """空代码应返回错误"""
        # Arrange
        request = EvaluationSchema(id="case_006", type="code_review", payload={"code": ""})

        # Act
        result = evaluator.evaluate(request)

        # Assert - 强断言
        assert result.is_valid is False
        assert "不能为空" in result.error
        assert result.score == 0.0 or result.score is None

    def test_syntax_error_code_returns_error(self, evaluator):
        """语法错误的代码应返回错误"""
        # Arrange
        request = EvaluationSchema(
            id="case_007", type="code_review", payload={"code": "def broken(\n    # 缺少右括号"}
        )

        # Act
        result = evaluator.evaluate(request)

        # Assert - 强断言
        assert result.is_valid is False
        assert "语法错误" in result.error
        assert result.score == 0.0
        assert result.metadata is not None
        # 语法错误时 metadata 包含 language 字段
        assert "language" in result.metadata

    def test_missing_code_and_text_fields_returns_error(self, evaluator):
        """缺少 code 和 text 字段应返回错误"""
        # Arrange
        request = EvaluationSchema(
            id="case_008", type="code_review", payload={"other_field": "value"}
        )

        # Act
        result = evaluator.evaluate(request)

        # Assert - 强断言
        assert result.is_valid is False
        assert "不能为空" in result.error

    def test_invalid_python_syntax_returns_detailed_error(self, evaluator):
        """无效 Python 语法应返回详细错误信息"""
        # Arrange
        request = EvaluationSchema(
            id="case_009",
            type="code_review",
            payload={"code": "if True\n    print('missing colon')"},
        )

        # Act
        result = evaluator.evaluate(request)

        # Assert - 强断言
        assert result.is_valid is False
        assert "语法错误" in result.error
        # 错误信息应包含行号
        assert "line" in result.error.lower()


# ============================================================
# Part 3: 边界测试 - 边界值
# ============================================================
class TestCodeReviewEvaluatorBoundaryCases:
    """边界测试 - 验证边界值处理"""

    @pytest.fixture
    def evaluator(self):
        return CodeReviewEvaluator()

    @pytest.fixture
    def evaluator_with_client(self):
        client = MagicMock()
        client.chat.return_value = "审查完成"
        return CodeReviewEvaluator(client=client)

    def test_none_code_value_returns_error(self, evaluator):
        """code 为 None 应返回错误"""
        # Arrange
        request = EvaluationSchema(id="case_010", type="code_review", payload={"code": None})

        # Act
        result = evaluator.evaluate(request)

        # Assert - 强断言
        assert result.is_valid is False
        assert "不能为空" in result.error

    def test_whitespace_only_code_passes_syntax_check(self, evaluator):
        """仅包含空白的代码通过语法检查（Python 允许空白代码）"""
        # Arrange
        request = EvaluationSchema(
            id="case_011", type="code_review", payload={"code": "   \n\t   "}
        )

        # Act
        result = evaluator.evaluate(request)

        # Assert - 强断言
        # 空白代码在 Python 中是有效的语法，ast.parse 可以解析
        assert result.is_valid is True
        assert result.score == 0.8  # 语法正确，无 LLM 审查时默认 0.8
        assert "语法检查通过" in result.text

    def test_very_long_code_processes_correctly(self, evaluator_with_client):
        """超长代码应正常处理"""
        # Arrange
        long_code = "x = 1\n" * 10000
        request = EvaluationSchema(id="case_012", type="code_review", payload={"code": long_code})

        # Act
        result = evaluator_with_client.evaluate(request)

        # Assert - 强断言
        assert result.is_valid is True
        assert result.score >= 0.0

    def test_score_boundary_at_threshold(self, evaluator_with_client):
        """分数边界值测试（0.8 为通过阈值）"""
        # Arrange - 模拟 LLM 返回与期望完全匹配
        evaluator_with_client.client.chat.return_value = "完美匹配期望输出"
        request = EvaluationSchema(
            id="case_013",
            type="code_review",
            payload={"code": "x = 1", "expected_output": "完美匹配期望输出"},
        )

        # Act
        result = evaluator_with_client.evaluate(request)

        # Assert - 强断言
        assert result.score >= 0.0
        assert result.score <= 1.0
        # 语法正确至少有 0.3 分
        assert result.score >= 0.3


# ============================================================
# Part 4: 异常测试 - 异常情况处理
# ============================================================
class TestCodeReviewEvaluatorExceptionCases:
    """异常测试 - 验证异常情况的处理"""

    def test_llm_client_raises_exception_returns_error(self):
        """LLM client 抛出异常时应返回错误（使用 safe_evaluate）"""
        # Arrange
        client = MagicMock()
        client.chat.side_effect = Exception("LLM service unavailable")
        evaluator = CodeReviewEvaluator(client=client)
        request = EvaluationSchema(id="case_014", type="code_review", payload={"code": "x = 1"})

        # Act - 使用 safe_evaluate 捕获异常
        result = evaluator.safe_evaluate(request)

        # Assert - 强断言
        assert result.is_valid is False
        assert "EVALUATION_ERROR" in result.error or "unavailable" in result.error

    def test_safe_evaluate_catches_unexpected_exception(self):
        """safe_evaluate 应捕获未预期的异常"""
        # Arrange
        client = MagicMock()
        client.chat.side_effect = RuntimeError("Unexpected error")
        evaluator = CodeReviewEvaluator(client=client)
        request = EvaluationSchema(id="case_015", type="code_review", payload={"code": "x = 1"})

        # Act
        result = evaluator.safe_evaluate(request)

        # Assert - 强断言
        assert result.is_valid is False
        assert "EVALUATION_ERROR" in result.error


# ============================================================
# Part 5: 依赖测试 - 外部依赖 Mock
# ============================================================
class TestCodeReviewEvaluatorDependencyHandling:
    """依赖测试 - 验证委托机制和依赖注入"""

    def test_delegates_to_code_evaluator(self):
        """验证 CodeReviewEvaluator 正确委托给 CodeEvaluator"""
        # Arrange
        mock_code_evaluator = MagicMock()
        mock_code_evaluator.evaluate.return_value = DomainResponse(
            is_valid=True, score=0.9, text="审查通过"
        )

        evaluator = CodeReviewEvaluator()
        evaluator._delegate = mock_code_evaluator

        request = EvaluationSchema(id="case_016", type="code_review", payload={"code": "x = 1"})

        # Act
        result = evaluator.evaluate(request)

        # Assert - 强断言
        assert result.is_valid is True
        assert result.score == 0.9
        mock_code_evaluator.evaluate.assert_called_once_with(request)

    def test_with_mock_llm_client_works_correctly(self):
        """使用 Mock LLM client 应正常工作"""
        # Arrange
        mock_client = MagicMock()
        mock_client.chat.return_value = "代码质量优秀"

        evaluator = CodeReviewEvaluator(client=mock_client)
        request = EvaluationSchema(
            id="case_017",
            type="code_review",
            payload={"code": "def hello():\n    return 'world'", "system_prompt": "请审查代码"},
        )

        # Act
        result = evaluator.evaluate(request)

        # Assert - 强断言
        assert result.is_valid is True
        assert result.text == "代码质量优秀"
        mock_client.chat.assert_called_once()

    def test_without_llm_client_uses_syntax_only_scoring(self):
        """无 LLM client 时应仅使用语法检查评分"""
        # Arrange
        evaluator = CodeReviewEvaluator(client=None)
        request = EvaluationSchema(id="case_018", type="code_review", payload={"code": "x = 1 + 2"})

        # Act
        result = evaluator.evaluate(request)

        # Assert - 强断言
        assert result.is_valid is True
        assert result.score == 0.8  # 语法正确默认分数
        assert "语法检查通过" in result.text

    def test_factory_creates_evaluator_with_client(self):
        """工厂方法应正确注入 client"""
        # Arrange
        mock_client = MagicMock()

        # Act
        evaluator = create_code_review_evaluator(client=mock_client)

        # Assert - 强断言
        assert evaluator.client is mock_client
        assert evaluator._delegate is not None
        assert isinstance(evaluator._delegate, CodeEvaluator)

    def test_factory_creates_evaluator_without_client(self):
        """工厂方法应支持无 client 创建"""
        # Act
        evaluator = create_code_review_evaluator()

        # Assert - 强断言
        assert evaluator.client is None
        assert evaluator._delegate is not None


# ============================================================
# Part 6: 工厂注册测试
# ============================================================
class TestCodeReviewEvaluatorFactoryRegistration:
    """工厂注册测试 - 验证评估器正确注册到工厂"""

    def test_evaluator_registered_in_factory(self):
        """验证 code_review 评估器已注册到工厂"""
        # Act
        evaluators = EvaluatorFactory.list_evaluators()

        # Assert - 强断言
        assert "code_review" in evaluators

    def test_factory_get_returns_code_review_evaluator(self):
        """工厂应返回 CodeReviewEvaluator 实例"""
        # Act
        evaluator = EvaluatorFactory.get("code_review")

        # Assert - 强断言
        # 验证评估器有 evaluate 方法
        assert hasattr(evaluator, "evaluate")
        assert hasattr(evaluator, "safe_evaluate")
        # 验证评估器有 _delegate 属性（CodeReviewEvaluator 的特征）
        assert hasattr(evaluator, "_delegate")

    def test_factory_get_with_client_injects_client(self):
        """工厂应正确注入 client"""
        # Arrange
        mock_client = MagicMock()

        # Act
        evaluator = EvaluatorFactory.get("code_review", client=mock_client)

        # Assert - 强断言
        assert evaluator.client is mock_client
        assert evaluator._delegate.client is mock_client

    def test_evaluator_info_contains_correct_metadata(self):
        """评估器信息应包含正确的元数据"""
        # Act
        info = EvaluatorFactory.get_evaluator_info()
        code_review_info = next((e for e in info if e["name"] == "code_review"), None)

        # Assert - 强断言
        assert code_review_info is not None
        # 工厂注册的是函数名 create_code_review_evaluator
        assert code_review_info["class_name"] == "create_code_review_evaluator"
        # docstring 应包含相关描述
        assert code_review_info["docstring"] is not None
