from src.domain.evaluators.base import BaseEvaluator, EvaluatorFactory
from src.domain.evaluators.scoring import is_passing
from src.schemas.evaluation import DomainResponse


@EvaluatorFactory.register("general")
def create_general_evaluator(client=None):
    return GeneralEvaluator(client=client)


class GeneralEvaluator(BaseEvaluator):
    def evaluate(self, request):
        user_input = self.get_input_text(request)
        expected_output = self.get_payload_data(request, "expected_output")

        if not user_input:
            return DomainResponse(is_valid=False, error="user_input/text 不能为空")

        # 如果没有 LLM client，使用简单的模拟响应（保持向后兼容）
        if not self.client:
            return DomainResponse(
                is_valid=True,
                data=f"通用评估: {user_input}",
                score=1.0,
            )

        llm_output = self.client.chat(user_input)

        if expected_output:
            from src.domain.evaluators.scoring import score_text_similarity
            score = score_text_similarity(llm_output, expected_output)
        else:
            score = 1.0

        return DomainResponse(
            is_valid=is_passing(score),
            text=llm_output,
            score=score,
            data=f"通用评估: {user_input}",
        )
