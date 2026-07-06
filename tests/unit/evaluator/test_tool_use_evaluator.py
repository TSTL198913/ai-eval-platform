"""ToolUseEvaluator 单元测试"""

import pytest
from unittest.mock import MagicMock

from src.domain.evaluators.tool_use import ToolUseEvaluator
from src.schemas.evaluation import EvaluationSchema
from src.schemas.evaluation import EvaluatorStatus


class TestToolUseEvaluatorPositiveCases:
    """正向测试用例"""

    def test_all_correct_tool_calls(self):
        """所有工具调用都正确"""
        evaluator = ToolUseEvaluator()
        request = EvaluationSchema(
            id="test_case_001",
            type="tool_use",
            payload={
                "tool_calls": [
                    {"tool_name": "search"},
                    {"tool_name": "calculator"},
                    {"tool_name": "analyzer"},
                ],
                "expected_tool_calls": ["search", "calculator", "analyzer"],
            },
        )
        response = evaluator.safe_evaluate(request)

        assert response.evaluation_status == EvaluatorStatus.SUCCESS
        assert response.score == 1.0
        assert response.data["correct_calls"] == 3
        assert response.data["total_expected"] == 3

    def test_partial_correct_tool_calls(self):
        """部分工具调用正确"""
        evaluator = ToolUseEvaluator()
        request = EvaluationSchema(
            id="test_case_002",
            type="tool_use",
            payload={
                "tool_calls": [
                    {"tool_name": "search"},
                    {"tool_name": "wrong_tool"},
                    {"tool_name": "analyzer"},
                ],
                "expected_tool_calls": ["search", "calculator", "analyzer"],
            },
        )
        response = evaluator.safe_evaluate(request)

        assert response.evaluation_status == EvaluatorStatus.SUCCESS
        assert response.score == 2 / 3
        assert response.data["correct_calls"] == 2

    def test_single_tool_call(self):
        """单工具调用"""
        evaluator = ToolUseEvaluator()
        request = EvaluationSchema(
            id="test_case_003",
            type="tool_use",
            payload={
                "tool_calls": [{"tool_name": "search"}],
                "expected_tool_calls": ["search"],
            },
        )
        response = evaluator.safe_evaluate(request)

        assert response.evaluation_status == EvaluatorStatus.SUCCESS
        assert response.score == 1.0

    def test_no_tool_calls_made(self):
        """未调用任何工具"""
        evaluator = ToolUseEvaluator()
        request = EvaluationSchema(
            id="test_case_004",
            type="tool_use",
            payload={
                "tool_calls": [],
                "expected_tool_calls": ["search"],
            },
        )
        response = evaluator.safe_evaluate(request)

        assert response.evaluation_status == EvaluatorStatus.SUCCESS
        assert response.score == 0.0
        assert "reason" in response.data

    def test_exact_expected_calls(self):
        """精确匹配期望工具调用"""
        evaluator = ToolUseEvaluator()
        request = EvaluationSchema(
            id="test_case_005",
            type="tool_use",
            payload={
                "tool_calls": [
                    {"tool_name": "tool_a", "args": {"query": "test"}},
                    {"tool_name": "tool_b"},
                ],
                "expected_tool_calls": ["tool_a", "tool_b"],
            },
        )
        response = evaluator.safe_evaluate(request)

        assert response.evaluation_status == EvaluatorStatus.SUCCESS
        assert response.score == 1.0


class TestToolUseEvaluatorNegativeCases:
    """负向测试用例"""

    def test_no_expected_tool_calls(self):
        """缺少期望工具列表"""
        evaluator = ToolUseEvaluator()
        request = EvaluationSchema(
            id="test_case_006",
            type="tool_use",
            payload={
                "tool_calls": [{"tool_name": "search"}],
                "expected_tool_calls": [],
            },
        )
        response = evaluator.safe_evaluate(request)

        assert response.evaluation_status == EvaluatorStatus.ERROR
        assert "expected_tool_calls" in response.error

    def test_empty_expected_tool_calls(self):
        """空期望工具列表"""
        evaluator = ToolUseEvaluator()
        request = EvaluationSchema(
            id="test_case_007",
            type="tool_use",
            payload={
                "tool_calls": [{"tool_name": "search"}],
                "expected_tool_calls": None,
            },
        )
        response = evaluator.safe_evaluate(request)

        assert response.evaluation_status == EvaluatorStatus.ERROR

    def test_tool_calls_without_tool_name(self):
        """工具调用缺少工具名"""
        evaluator = ToolUseEvaluator()
        request = EvaluationSchema(
            id="test_case_008",
            type="tool_use",
            payload={
                "tool_calls": [{"args": {"query": "test"}}],
                "expected_tool_calls": ["search"],
            },
        )
        response = evaluator.safe_evaluate(request)

        assert response.evaluation_status == EvaluatorStatus.SUCCESS
        assert response.score == 0.0

    def test_no_tool_calls_and_no_expected(self):
        """无工具调用且无期望"""
        evaluator = ToolUseEvaluator()
        request = EvaluationSchema(
            id="test_case_009",
            type="tool_use",
            payload={
                "tool_calls": [],
                "expected_tool_calls": [],
            },
        )
        response = evaluator.safe_evaluate(request)

        assert response.evaluation_status == EvaluatorStatus.ERROR


class TestToolUseEvaluatorBoundaryCases:
    """边界测试用例"""

    def test_tool_calls_exceed_expected_twice(self):
        """工具调用次数超过期望的两倍"""
        evaluator = ToolUseEvaluator()
        request = EvaluationSchema(
            id="test_case_010",
            type="tool_use",
            payload={
                "tool_calls": [
                    {"tool_name": "search"},
                    {"tool_name": "search"},
                    {"tool_name": "search"},
                    {"tool_name": "search"},
                    {"tool_name": "search"},
                ],
                "expected_tool_calls": ["search", "calculator"],
            },
        )
        response = evaluator.safe_evaluate(request)

        assert response.evaluation_status == EvaluatorStatus.SUCCESS
        assert "correct_calls" in response.data

    def test_all_wrong_tool_calls(self):
        """所有工具调用都错误"""
        evaluator = ToolUseEvaluator()
        request = EvaluationSchema(
            id="test_case_011",
            type="tool_use",
            payload={
                "tool_calls": [
                    {"tool_name": "wrong_a"},
                    {"tool_name": "wrong_b"},
                ],
                "expected_tool_calls": ["correct_a", "correct_b"],
            },
        )
        response = evaluator.safe_evaluate(request)

        assert response.evaluation_status == EvaluatorStatus.SUCCESS
        assert response.score == 0.0

    def test_large_number_of_tool_calls(self):
        """大量工具调用"""
        evaluator = ToolUseEvaluator()
        tool_calls = [{"tool_name": f"tool_{i}"} for i in range(10)]
        expected_tools = [f"tool_{i}" for i in range(10)]
        request = EvaluationSchema(
            id="test_case_012",
            type="tool_use",
            payload={
                "tool_calls": tool_calls,
                "expected_tool_calls": expected_tools,
            },
        )
        response = evaluator.safe_evaluate(request)

        assert response.evaluation_status == EvaluatorStatus.SUCCESS
        assert response.score == 1.0

    def test_tool_calls_exactly_twice_expected(self):
        """工具调用正好是期望的两倍"""
        evaluator = ToolUseEvaluator()
        request = EvaluationSchema(
            id="test_case_013",
            type="tool_use",
            payload={
                "tool_calls": [
                    {"tool_name": "a"},
                    {"tool_name": "b"},
                    {"tool_name": "a"},
                    {"tool_name": "b"},
                ],
                "expected_tool_calls": ["a", "b"],
            },
        )
        response = evaluator.safe_evaluate(request)

        assert response.evaluation_status == EvaluatorStatus.SUCCESS
        assert response.data["correct_calls"] == 4

    def test_tool_calls_exactly_twice_plus_one_expected(self):
        """工具调用正好是期望的两倍加一"""
        evaluator = ToolUseEvaluator()
        request = EvaluationSchema(
            id="test_case_014",
            type="tool_use",
            payload={
                "tool_calls": [
                    {"tool_name": "a"},
                    {"tool_name": "b"},
                    {"tool_name": "a"},
                    {"tool_name": "b"},
                    {"tool_name": "c"},
                ],
                "expected_tool_calls": ["a", "b"],
            },
        )
        response = evaluator.safe_evaluate(request)

        assert response.evaluation_status == EvaluatorStatus.SUCCESS
        assert "correct_calls" in response.data


class TestToolUseEvaluatorIntegration:
    """集成测试用例"""

    def test_evaluator_registered_in_factory(self):
        """评估器应在工厂中注册"""
        from src.domain.evaluators.evaluator_factory import EvaluatorFactory

        assert "tool_use" in EvaluatorFactory._registry

    def test_evaluate_with_metadata(self):
        """带元数据的评估"""
        evaluator = ToolUseEvaluator()
        request = EvaluationSchema(
            id="test_case_015",
            type="tool_use",
            payload={
                "tool_calls": [{"tool_name": "search"}],
                "expected_tool_calls": ["search"],
            },
            metadata={"test_key": "test_value"},
        )
        response = evaluator.safe_evaluate(request)

        assert response.evaluation_status == EvaluatorStatus.SUCCESS
        assert response.score == 1.0

    def test_tool_calls_with_complex_args(self):
        """带复杂参数的工具调用"""
        evaluator = ToolUseEvaluator()
        request = EvaluationSchema(
            id="test_case_016",
            type="tool_use",
            payload={
                "tool_calls": [
                    {
                        "tool_name": "search",
                        "args": {
                            "query": "test",
                            "filters": ["a", "b", "c"],
                            "options": {"limit": 10, "timeout": 5},
                        },
                    }
                ],
                "expected_tool_calls": ["search"],
            },
        )
        response = evaluator.safe_evaluate(request)

        assert response.evaluation_status == EvaluatorStatus.SUCCESS
        assert response.score == 1.0
        assert "tool_calls" in response.data
