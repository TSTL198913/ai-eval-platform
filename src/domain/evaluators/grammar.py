import re

from src.domain.evaluators.base import BaseEvaluator
from src.domain.evaluators.evaluator_factory import EvaluatorFactory
from src.schemas.evaluation import DomainResponse, EvaluationSchema


def _count_grammar_errors(text: str) -> tuple[int, list[str]]:
    errors = []
    if not text:
        return 0, []

    first_char = text[0]
    if first_char.isalpha() and not first_char.isupper():
        if "\u4e00" <= first_char <= "\u9fff":
            pass
        else:
            errors.append("首字母应大写")

    if not text.endswith((".", "?", "!", "。", "？", "！")):
        errors.append("缺少句末标点")

    consecutive_spaces = re.findall(r" {2,}", text)
    if consecutive_spaces:
        errors.append(f"存在连续空格({len(consecutive_spaces)}处)")

    return len(errors), errors


@EvaluatorFactory.register("grammar")
class GrammarEvaluator(BaseEvaluator):
    def _do_evaluate(self, request: EvaluationSchema) -> DomainResponse:
        actual_output = self.get_payload_data(request, "actual_output")
        if not actual_output:
            return DomainResponse(is_valid=False, error="actual_output 不能为空")

        error_count, error_details = _count_grammar_errors(actual_output)
        score = max(0, 1.0 - error_count * 0.2)

        return DomainResponse(
            is_valid=True,
            text=actual_output,
            score=score,
            data=f"语法检查: 错误数={error_count}, 详情={', '.join(error_details) if error_details else '无'}",
        )
