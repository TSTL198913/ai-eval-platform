from src.domain.evaluators.base import BaseEvaluator
from src.domain.evaluators.evaluator_factory import EvaluatorFactory
from src.domain.evaluators.metadata import TextMetadata
from src.domain.evaluators.scoring import is_passing, score_text_similarity
from src.schemas.evaluation import DomainResponse

DEFAULT_TEXT_PROMPT = "你是一个文本评测助手。请准确、简洁地回答用户问题，回答应与预期语义一致。"


@EvaluatorFactory.register("text")
def create_text_evaluator(client=None):
    return TextMatchEvaluator(client=client)


class TextMatchEvaluator(BaseEvaluator):
    def evaluate(self, request) -> DomainResponse:
        user_input = self.get_input_text(request)
        expected_output = self.get_payload_data(request, "expected_output")
        system_prompt = self.get_payload_data(request, "system_prompt") or DEFAULT_TEXT_PROMPT
        meta = TextMetadata.model_validate(request.metadata or {})

        if not user_input:
            return DomainResponse(is_valid=False, error="user_input/text 不能为空")

        client_error = self.require_client()
        if client_error:
            return client_error

        llm_output = self.client.chat(user_input, system_prompt=system_prompt)
        score = score_text_similarity(llm_output, expected_output)

        return DomainResponse(
            is_valid=is_passing(score),
            text=llm_output,
            score=score,
            metadata={
                "expected_output": expected_output,
                "tone": meta.tone,
                "match_mode": "text_similarity",
            },
        )
