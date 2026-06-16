from src.domain.evaluators.base import BaseEvaluator, EvaluatorFactory
from src.domain.evaluators.scoring import score_text_similarity
from src.schemas.evaluation import DomainResponse, EvaluationSchema


@EvaluatorFactory.register("qa")
class QAEvaluator(BaseEvaluator):
    def evaluate(self, request: EvaluationSchema) -> DomainResponse:
        user_input = self.get_input_text(request)
        expected_output = self.get_payload_data(request, "expected_output")
        context = self.get_payload_data(request, "context", "")
        if not user_input:
            return DomainResponse(is_valid=False, error="user_input/text 不能为空")

        prompt = f"""{context}

基于以上上下文回答问题：
问题：{user_input}"""
        llm_output = self.client.chat(prompt) if self.client else user_input

        score = score_text_similarity(llm_output, expected_output) if expected_output else 1.0

        return DomainResponse(
            is_valid=True,
            text=llm_output,
            score=score,
            data=f"问答结果: {llm_output}",
        )
