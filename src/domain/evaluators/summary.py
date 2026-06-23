from src.domain.evaluators.base import BaseEvaluator
from src.domain.evaluators.evaluator_factory import EvaluatorFactory
from src.domain.evaluators.scoring import score_text_similarity
from src.schemas.evaluation import DomainResponse, EvaluationSchema


@EvaluatorFactory.register("summary")
class SummaryEvaluator(BaseEvaluator):
    def _do_evaluate(self, request: EvaluationSchema) -> DomainResponse:
        actual_output = self.get_payload_data(request, "actual_output")
        if not actual_output:
            return DomainResponse(is_valid=False, error="actual_output 不能为空")
        expected_output = self.get_payload_data(request, "expected_output")
        if not expected_output:
            return DomainResponse(is_valid=False, error="expected_output 不能为空")

        score = score_text_similarity(actual_output, expected_output)

        return DomainResponse(
            is_valid=True,
            text=actual_output,
            score=score,
            data=f"摘要质量评估: 相似度={score:.2f}",
        )
