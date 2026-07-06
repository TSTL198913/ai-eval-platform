import os
import sys

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault(
    "HF_HOME",
    os.path.join(os.path.expanduser("~"), ".cache", "huggingface", "hub"),
)

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

import pytest

from src.domain.evaluators.evaluator_factory import EvaluatorFactory
from src.schemas.evaluation import EvaluationSchema


class TestCodeEvaluatorConfidenceLevel:
    """Code评估器confidence_level合规性测试 - 2026年工业级标准"""

    def test_code_error_status_has_confidence_level(self):
        """负向：语法错误代码应返回confidence_level"""
        evaluator = EvaluatorFactory.get("code")
        request = EvaluationSchema(
            type="code",
            payload={
                "user_input": "写一个Python函数",
                "actual_output": "def hello()\n    return 'Hello'",
                "language": "python"
            }
        )
        result = evaluator.evaluate(request)
        
        assert result.is_valid is True
        assert result.score <= 0.5, f"语法错误代码应返回低分，实际: {result.score}"
        assert result.confidence_level is not None, "结果必须包含confidence_level"
        assert hasattr(result, 'confidence_level'), "结果必须有confidence_level属性"

    def test_code_error_status_confidence_level_is_enum(self):
        """边界：confidence_level应为枚举类型"""
        evaluator = EvaluatorFactory.get("code")
        request = EvaluationSchema(
            type="code",
            payload={
                "user_input": "写一个Python函数",
                "actual_output": "def hello(): return 'Hello'",
                "language": "python"
            }
        )
        result = evaluator.evaluate(request)
        
        assert result.is_valid is True
        assert result.confidence_level is not None
        
        level_value = result.confidence_level.value if hasattr(result.confidence_level, 'value') else str(result.confidence_level)
        assert level_value in ["very_low", "low", "medium", "high", "very_high"], \
            f"confidence_level值应为枚举值，实际为: {level_value}"

    def test_code_success_status_has_confidence_level(self):
        """正向：有效代码应返回confidence_level"""
        evaluator = EvaluatorFactory.get("code")
        request = EvaluationSchema(
            type="code",
            payload={
                "user_input": "写一个Python函数计算斐波那契数列",
                "actual_output": "def fib(n):\n    if n <= 0:\n        return []\n    result = [0, 1]\n    for i in range(2, n):\n        result.append(result[-1] + result[-2])\n    return result",
                "language": "python"
            }
        )
        result = evaluator.evaluate(request)
        
        assert result.score is not None
        assert result.confidence_level is not None, "SUCCESS/PARTIAL状态必须包含confidence_level"
        assert hasattr(result, 'confidence_level')

    def test_code_security_violation_has_confidence_level(self):
        """负向：安全违规代码应返回低分和confidence_level"""
        evaluator = EvaluatorFactory.get("code")
        request = EvaluationSchema(
            type="code",
            payload={
                "user_input": "删除所有文件",
                "actual_output": "import os; os.system('rm -rf /')",
                "language": "python"
            }
        )
        result = evaluator.evaluate(request)
        
        assert result.is_valid is True
        assert result.score <= 0.5, f"安全违规代码应返回低分，实际: {result.score}"
        assert result.confidence_level is not None, "安全违规代码必须包含confidence_level"

    def test_code_confidence_auto_computed_flag(self):
        """验证：confidence_auto_computed标记必须为true"""
        evaluator = EvaluatorFactory.get("code")
        request = EvaluationSchema(
            type="code",
            payload={
                "user_input": "写一个Python函数",
                "actual_output": "def hello()\n    return 'Hello'",
                "language": "python"
            }
        )
        result = evaluator.evaluate(request)
        
        assert result.data is not None, "data字段不能为空"
        assert result.data.get("confidence_auto_computed") is True, \
            "confidence_auto_computed必须为true"

    def test_code_confidence_components_present(self):
        """验证：必须包含confidence相关字段"""
        evaluator = EvaluatorFactory.get("code")
        request = EvaluationSchema(
            type="code",
            payload={
                "user_input": "写一个Python函数",
                "actual_output": "def hello(): return 'Hello'",
                "language": "python"
            }
        )
        result = evaluator.evaluate(request)
        
        assert result.is_valid is True
        assert result.data is not None
        assert "confidence_components" in result.data, "必须包含confidence_components"