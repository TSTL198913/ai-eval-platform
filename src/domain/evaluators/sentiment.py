from src.domain.evaluators.base import BaseEvaluator, EvaluatorFactory
from src.schemas.evaluation import DomainResponse, EvaluationSchema


@EvaluatorFactory.register("sentiment")
class SentimentEvaluator(BaseEvaluator):
    def evaluate(self, request: EvaluationSchema) -> DomainResponse:
        user_input = self.get_input_text(request)
        expected_sentiment = self.get_payload_data(request, "expected_sentiment")
        if not user_input:
            return DomainResponse(is_valid=False, error="user_input/text 不能为空")

        prompt = f"""分析以下文本的情感倾向，返回 positive、negative 或 neutral：
文本：{user_input}"""
        llm_output = self.client.chat(prompt) if self.client else "neutral"
        llm_output = llm_output.strip().lower()

        score = 1.0 if llm_output == expected_sentiment.lower() else 0.0

        return DomainResponse(
            is_valid=True,
            text=llm_output,
            score=score,
            data=f"情感分析: 预测={llm_output}, 预期={expected_sentiment}",
        )
