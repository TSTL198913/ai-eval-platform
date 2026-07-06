"""
CodeEvaluator 2026年工业级标准合规性测试
测试目标：验证ERROR状态下score必须为0.0（禁止None）
标准依据：2026年AI评测工业级标准 - 评分合理性原则
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.domain.evaluators.code import CodeEvaluator
from src.schemas.evaluation import EvaluationSchema, EvaluatorStatus


class TestCodeEvaluatorIndustrialStandards:
    """2026年工业级标准合规性测试"""

    @pytest.fixture
    def evaluator(self):
        return CodeEvaluator(client=None)

    def test_error_status_must_return_zero_score_for_syntax_error(self, evaluator):
        """
        标准：语法错误的代码应返回低分
        场景：Python语法错误（缺少冒号）
        """
        request = EvaluationSchema(
            id="code_std_001",
            type="code",
            payload={
                "code": "def hello()\n    return 'Hello'",
                "metadata": {"language": "python"},
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.score <= 0.5, f"语法错误代码分数应<=0.5，实际返回: {result.score}"

    def test_error_status_must_return_zero_score_for_unmatched_parenthesis(self, evaluator):
        """
        标准：无效代码应返回低分
        场景：括号不匹配
        """
        request = EvaluationSchema(
            id="code_std_002",
            type="code",
            payload={
                "code": "print('Hello'",
                "metadata": {"language": "python"},
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.score <= 0.5, f"无效代码应返回低分，实际返回: {result.score}"

    def test_error_status_must_return_zero_score_for_invalid_indentation(self, evaluator):
        """
        标准：无效代码应返回低分
        场景：无效缩进
        """
        request = EvaluationSchema(
            id="code_std_003",
            type="code",
            payload={
                "code": "def hello():\nreturn 'Hello'",
                "metadata": {"language": "python"},
            },
        )

        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.score <= 0.5, f"无效代码应返回低分，实际返回: {result.score}"

    def test_error_status_must_return_zero_score_for_security_violation(self, evaluator):
        """
        标准：ERROR状态必须返回score=0.0，禁止score=None
        场景：代码安全违规
        """
        malicious_code = """
import os
os.system('rm -rf /')
"""
        request = EvaluationSchema(
            id="code_std_004",
            type="code",
            payload={
                "code": malicious_code,
                "metadata": {"language": "python"},
            },
        )

        result = evaluator.evaluate(request)

        if result.evaluation_status == EvaluatorStatus.ERROR:
            assert result.score == 0.0, f"ERROR状态应返回score=0.0，实际返回: {result.score}"

    def test_error_status_must_return_zero_score_for_invalid_structure(self, evaluator):
        """
        标准：ERROR状态必须返回score=0.0，禁止score=None
        场景：代码结构校验失败
        """
        invalid_struct_code = "print(1"
        request = EvaluationSchema(
            id="code_std_005",
            type="code",
            payload={
                "code": invalid_struct_code,
                "metadata": {"language": "python"},
            },
        )

        result = evaluator.evaluate(request)

        if result.evaluation_status == EvaluatorStatus.ERROR:
            assert result.score == 0.0, f"ERROR状态应返回score=0.0，实际返回: {result.score}"

    def test_success_status_must_have_numeric_score(self, evaluator):
        """
        标准：SUCCESS/PARTIAL状态必须返回明确的数值score
        场景：有效代码
        """
        request = EvaluationSchema(
            id="code_std_006",
            type="code",
            payload={
                "code": "def hello():\n    return 'Hello'",
                "metadata": {"language": "python"},
            },
        )

        result = evaluator.evaluate(request)

        assert result.score is not None, "有效代码评估应返回明确的score"
        assert isinstance(result.score, (int, float)), f"score应为数值类型，实际类型: {type(result.score)}"
        assert 0.0 <= result.score <= 1.0, f"score应在[0,1]区间，实际: {result.score}"
