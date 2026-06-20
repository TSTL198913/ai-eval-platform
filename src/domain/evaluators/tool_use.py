"""
工具使用评估器
"""

from src.domain.evaluators.base import BaseEvaluator
from src.domain.evaluators.evaluator_factory import EvaluatorFactory
from src.schemas.evaluation import DomainResponse, EvaluationSchema


@EvaluatorFactory.register("tool_use")
class ToolUseEvaluator(BaseEvaluator):
    """工具使用评估器"""

    def evaluate(self, request: EvaluationSchema) -> DomainResponse:
        """评估工具调用"""
        tool_calls = self.get_payload_data(request, "tool_calls", [])
        expected_tool_calls = self.get_payload_data(request, "expected_tool_calls", [])

        if not tool_calls:
            return DomainResponse(
                is_valid=True,
                score=0.0,
                text="No tool calls made",
                data={"reason": "No tool calls made", "correct_calls": 0, "total_expected": len(expected_tool_calls)},
            )

        correct_calls = 0
        for call in tool_calls:
            tool_name = call.get("tool_name", "")
            if tool_name in expected_tool_calls:
                correct_calls += 1

        score = correct_calls / len(expected_tool_calls) if expected_tool_calls else 1.0

        # 如果调用次数过多，扣分
        if len(tool_calls) > len(expected_tool_calls) * 2:
            score *= 0.5

        return DomainResponse(
            is_valid=True,
            score=score,
            text=f"Tool use evaluation: {correct_calls}/{len(expected_tool_calls)} correct",
            data={
                "score": score,
                "correct_calls": correct_calls,
                "total_expected": len(expected_tool_calls),
                "tool_calls": tool_calls,
            },
        )
