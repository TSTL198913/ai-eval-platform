import re

from src.domain.evaluators.base import BaseEvaluator
from src.domain.evaluators.evaluator_factory import EvaluatorFactory
from src.domain.evaluators.scoring import is_passing
from src.schemas.evaluation import DomainResponse, EvaluationSchema


@EvaluatorFactory.register("general")
def create_general_evaluator(client=None):
    return GeneralEvaluator(client=client)


class GeneralEvaluator(BaseEvaluator):
    @staticmethod
    def _sanitize_input(text: str) -> str:
        """脱敏处理：过滤敏感信息避免泄露给LLM厂商"""
        text = re.sub(r"sk-[a-zA-Z0-9]{20,}", "[REDACTED_API_KEY]", text)
        text = re.sub(r"AKIA[A-Z0-9]{16}", "[REDACTED_AWS_KEY]", text)
        text = re.sub(r"AIza[0-9A-Za-z\\-_]{35}", "[REDACTED_GCP_KEY]", text)
        text = re.sub(r"mongodb\+srv://[^\s]+", "[REDACTED_MONGO_URI]", text)
        text = re.sub(r"postgres(ql)?://[^\s]+", "[REDACTED_PG_URI]", text)
        text = re.sub(r"mysql://[^\s]+", "[REDACTED_MYSQL_URI]", text)
        return text

    def _do_evaluate(self, request: EvaluationSchema) -> DomainResponse:
        if error := self.validate_input(request):
            return error
        user_input = self.get_input_text(request)
        expected_output = self.get_payload_data(request, "expected_output")
        system_prompt = self.get_payload_data(request, "system_prompt")

        if not self.client:
            return DomainResponse(
                is_valid=True,
                data=f"通用评估: {user_input}",
                score=1.0,
            )

        sanitized_input = self._sanitize_input(user_input)
        if system_prompt:
            llm_output = self.client.chat(sanitized_input, system_prompt=system_prompt)
        else:
            llm_output = self.client.chat(sanitized_input)

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
