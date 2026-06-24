"""
情感分析(Sentiment)评估器 - 2026 工业级标准重构版

用于评估情感分析系统的输出质量，包括：
- 情感准确性评估
- 强度量化
- 边界情况处理

工业级特性：
- LLM-as-a-Judge 置信度评分
- 语义相似度匹配（而非精确匹配）
- 完整类型注解
- 结构化异常处理
"""

import logging

from src.domain.evaluators.base import BaseEvaluator
from src.domain.evaluators.evaluator_factory import EvaluatorFactory
from src.domain.evaluators.fallback_policy import StrictSemanticPolicy
from src.schemas.evaluation import DomainResponse, EvaluationSchema

logger = logging.getLogger(__name__)

SENTIMENT_MAP = {
    "positive": {"积极", "正面", "好", "满意", "喜欢", "爱", "棒", "优秀"},
    "negative": {"消极", "负面", "坏", "不满", "讨厌", "恨", "差", "糟糕"},
    "neutral": {"中性", "中立", "一般", "普通"},
}


@EvaluatorFactory.register("sentiment")
class SentimentEvaluator(BaseEvaluator):
    def __init__(self, client=None):
        super().__init__(client, fallback_policy=StrictSemanticPolicy())

    def _do_evaluate(self, request: EvaluationSchema) -> DomainResponse:
        if error := self.validate_input(request):
            return error

        user_input = self.get_input_text(request)
        actual_output = self.get_payload_data(request, "actual_output")
        expected_sentiment = self.get_payload_data(request, "expected_sentiment")

        if not expected_sentiment:
            return self.create_error_response(
                error_message="expected_sentiment 不能为空",
                error_code="MISSING_EXPECTED_SENTIMENT",
            )

        if not actual_output:
            return self.create_error_response(
                error_message="actual_output 不能为空",
                error_code="MISSING_ACTUAL_OUTPUT",
            )

        if error := self.require_client_with_error():
            return error

        prompt = self._build_evaluation_prompt(user_input, actual_output, expected_sentiment)

        try:
            llm_output = self.client.chat(prompt)
            score = self.safe_parse_score(llm_output)

            if score is None:
                logger.error(f"情感评估响应数字提取失败: '{llm_output}'")
                score = self._calculate_fallback_score(actual_output, expected_sentiment)

            return self.create_success_response(
                text=actual_output,
                score=score,
                data={
                    "user_input": user_input,
                    "actual_output": actual_output,
                    "expected_sentiment": expected_sentiment,
                    "predicted_sentiment": actual_output,
                    "raw_output": llm_output,
                    "evaluator": "sentiment",
                },
                metadata={"mode": "llm_as_judge"},
            )

        except Exception as e:
            logger.exception(f"情感评估器 LLM 调用失败: {e}")
            score = self._calculate_fallback_score(actual_output, expected_sentiment)
            return self.create_success_response(
                text=actual_output,
                score=score,
                data={
                    "user_input": user_input,
                    "actual_output": actual_output,
                    "expected_sentiment": expected_sentiment,
                    "warning": "LLM调用失败，使用语义相似度降级评分",
                },
                metadata={"mode": "fallback"},
            )

    def _build_evaluation_prompt(
        self, user_input: str, actual_output: str, expected_sentiment: str
    ) -> str:
        """构建情感评估 Prompt"""
        return (
            "你是一个严谨的情感分析评测专家。请评估以下情感分析结果的质量。\n"
            "评估标准：\n"
            "- 完全匹配期望情感：1.0分\n"
            "- 语义相近（如'positive'与'积极'）：0.7-0.9分\n"
            "- 部分相关（如情感方向正确但强度不同）：0.3-0.6分\n"
            "- 完全相反（如期望positive实际negative）：0.0分\n"
            "- 中性与其他情感之间：0.2-0.4分\n"
            "输出一个 0.0 到 1.0 的分数。\n\n"
            f"【输入文本】：{user_input}\n"
            f"【期望情感】：{expected_sentiment}\n"
            f"【实际情感】：{actual_output}\n\n"
            "最终评分（仅输出数字）："
        )

    def _calculate_fallback_score(self, actual_output: str, expected_sentiment: str) -> float:
        """降级评分：基于语义相似度"""
        actual_lower = actual_output.lower().strip()
        expected_lower = expected_sentiment.lower().strip()

        if actual_lower == expected_lower:
            return 1.0

        actual_category = self._normalize_sentiment(actual_lower)
        expected_category = self._normalize_sentiment(expected_lower)

        if actual_category == expected_category:
            return 0.8

        opposite_map = {"positive": "negative", "negative": "positive"}
        if actual_category in opposite_map and opposite_map[actual_category] == expected_category:
            return 0.0

        if actual_category == "neutral" or expected_category == "neutral":
            return 0.3

        return 0.1

    def _normalize_sentiment(self, sentiment: str) -> str:
        """标准化情感标签"""
        for key, synonyms in SENTIMENT_MAP.items():
            if sentiment == key or sentiment in synonyms:
                return key
        return sentiment
