from src.domain.evaluators.base import BaseEvaluator, EvaluatorFactory
from src.domain.evaluators.metadata import FinanceMetadata
from src.domain.evaluators.scoring import is_passing, score_numeric_match
from src.schemas.evaluation import DomainResponse

DEFAULT_FINANCE_PROMPT = (
    "你是一个专业的金融分析师。请准确回答用户的金融问题，"
    "回答需包含具体金额、币种和简要计算过程。"
)


@EvaluatorFactory.register("finance")
def create_finance_evaluator(client=None):
    return FinanceEvaluator(client=client)


class FinanceEvaluator(BaseEvaluator):
    def evaluate(self, request) -> DomainResponse:
        user_input = self.get_input_text(request)
        expected_output = self.get_payload_data(request, "expected_output")
        system_prompt = (
            self.get_payload_data(request, "system_prompt") or DEFAULT_FINANCE_PROMPT
        )

        meta = FinanceMetadata.model_validate(request.metadata or {})

        if not user_input:
            return DomainResponse(is_valid=False, error="user_input/text 不能为空")

        if not self.client:
            return DomainResponse(is_valid=False, error="LLM client 未配置")

        llm_output = self.client.chat(user_input, system_prompt=system_prompt)
        score = score_numeric_match(llm_output, expected_output)

        return DomainResponse(
            is_valid=is_passing(score),
            text=llm_output,
            score=score,
            metadata={
                "expected_output": expected_output,
                "rate": meta.rate,
                "target": meta.target,
            },
        )
