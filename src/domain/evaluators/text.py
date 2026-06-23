from src.domain.evaluators.base import BaseEvaluator
from src.domain.evaluators.evaluator_factory import EvaluatorFactory
from src.domain.evaluators.metadata import TextMetadata
from src.domain.evaluators.scoring import is_passing, score_text_similarity
from src.schemas.evaluation import DomainResponse, EvaluationSchema


@EvaluatorFactory.register("text")
def create_text_evaluator(client=None):
    return TextMatchEvaluator(client=client)


class TextMatchEvaluator(BaseEvaluator):
    def _do_evaluate(self, request: EvaluationSchema) -> DomainResponse:
        actual_output = self.get_payload_data(request, "actual_output")
        if not actual_output:
            return DomainResponse(is_valid=False, error="actual_output 不能为空")
        expected_output = self.get_payload_data(request, "expected_output")
        if not expected_output:
            return DomainResponse(is_valid=False, error="expected_output 不能为空")

        score = score_text_similarity(actual_output, expected_output)
        meta = TextMetadata.model_validate(request.metadata or {})

        return DomainResponse(
            is_valid=True,
            text=actual_output,
            score=score,
            metadata={
                "expected_output": expected_output,
                "tone": meta.tone,
                "match_mode": "text_similarity",
                "passed": is_passing(score),
            },
        )
