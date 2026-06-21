from src.domain.evaluators.base import BaseEvaluator
from src.domain.evaluators.evaluator_factory import EvaluatorFactory
from src.domain.evaluators.scoring import score_text_similarity
from src.schemas.evaluation import DomainResponse, EvaluationSchema


@EvaluatorFactory.register("semantic")
class SemanticEvaluator(BaseEvaluator):
    def evaluate(self, request: EvaluationSchema) -> DomainResponse:
        if error := self.validate_input(request):
            return error
        user_input = self.get_input_text(request)
        expected_output = self.get_payload_data(request, "expected_output")
        if not expected_output:
            return DomainResponse(is_valid=False, error="expected_output 不能为空")

        llm_output = self.client.chat(user_input) if self.client else user_input
        score = score_text_similarity(llm_output, expected_output)

        return DomainResponse(
            is_valid=True,
            text=llm_output,
            score=score,
            data=f"语义相似度评估: {llm_output}",
        )
