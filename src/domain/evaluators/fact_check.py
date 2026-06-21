from src.domain.evaluators.base import BaseEvaluator
from src.domain.evaluators.evaluator_factory import EvaluatorFactory
from src.schemas.evaluation import DomainResponse, EvaluationSchema


@EvaluatorFactory.register("fact_check")
class FactCheckEvaluator(BaseEvaluator):
    def evaluate(self, request: EvaluationSchema) -> DomainResponse:
        if error := self.validate_input(request):
            return error
        user_input = self.get_input_text(request)

        prompt = f"""请验证以下陈述的真实性，返回 true（真实）或 false（虚假），并给出理由：
陈述：{user_input}
格式：结果: true/false\n理由: ..."""
        llm_output = self.client.chat(prompt) if self.client else "结果: true\n理由: 无法验证"

        is_true = "true" in llm_output.lower()
        score = 1.0 if is_true else 0.0

        return DomainResponse(
            is_valid=True,
            text=llm_output,
            score=score,
            data=f"事实核查: 结果={is_true}",
        )
