from src.domain.evaluators.base import BaseEvaluator
from src.domain.evaluators.evaluator_factory import EvaluatorFactory
from src.schemas.evaluation import DomainResponse, EvaluationSchema


@EvaluatorFactory.register("sentiment")
class SentimentEvaluator(BaseEvaluator):
    """情感分析评估器"""

    POSITIVE_WORDS = [
        "好",
        "喜欢",
        "爱",
        "棒",
        "优秀",
        "满意",
        "开心",
        "高兴",
        "happy",
        "love",
        "good",
        "great",
        "excellent",
        "wonderful",
    ]
    NEGATIVE_WORDS = [
        "坏",
        "讨厌",
        "恨",
        "差",
        "糟糕",
        "不满",
        "伤心",
        "难过",
        "sad",
        "hate",
        "bad",
        "terrible",
        "awful",
        "poor",
    ]

    def evaluate(self, request: EvaluationSchema) -> DomainResponse:
        if error := self.validate_input(request):
            return error
        user_input = self.get_input_text(request)
        expected_sentiment = self.get_payload_data(request, "expected_sentiment")

        # 如果有LLM client，使用LLM分析
        if self.client:
            prompt = f"""分析以下文本的情感倾向，返回 positive、negative 或 neutral：
文本：{user_input}"""
            llm_output = self.client.chat(prompt)
            sentiment = llm_output.strip().lower()
        else:
            # 无LLM client时，使用关键词匹配
            sentiment = self._simple_sentiment_analysis(user_input)

        # 计算分数
        if expected_sentiment:
            score = 1.0 if sentiment == expected_sentiment.lower() else 0.5
        else:
            score = 1.0

        return DomainResponse(
            is_valid=True,
            text=sentiment,
            score=score,
            data={"predicted_sentiment": sentiment, "expected_sentiment": expected_sentiment},
        )

    def _simple_sentiment_analysis(self, text: str) -> str:
        """简单的关键词情感分析"""
        text_lower = text.lower()

        positive_count = sum(1 for word in self.POSITIVE_WORDS if word in text_lower)
        negative_count = sum(1 for word in self.NEGATIVE_WORDS if word in text_lower)

        if positive_count > negative_count:
            return "positive"
        elif negative_count > positive_count:
            return "negative"
        else:
            return "neutral"
