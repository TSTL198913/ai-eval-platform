"""
通用(General)评估器 - 2026 工业级标准重构版

用于通用文本质量评估，包括：
- 回答质量评估
- 事实一致性检查
- 语义完整性验证

工业级特性：
- 严格语义策略（禁止静默降级）
- LLM-as-a-Judge 核心评估
- 完整类型注解
- 结构化异常处理
- 真正异步评估（支持 achat）
"""

import asyncio
import logging
import re

from src.domain.evaluators.base import BaseEvaluator
from src.domain.evaluators.evaluator_factory import EvaluatorFactory
from src.domain.evaluators.fallback_policy import StrictSemanticPolicy
from src.domain.services.fallback_scoring_service import fallback_scoring_service
from src.domain.services.text_analysis_service import text_analysis_service
from src.schemas.evaluation import DomainResponse
from src.schemas.evaluation import EvaluationSchema

logger = logging.getLogger(__name__)


@EvaluatorFactory.register("general")
def create_general_evaluator(client=None):
    return GeneralEvaluator(client=client)


class GeneralEvaluator(BaseEvaluator):
    def __init__(self, client=None):
        super().__init__(
            client,
            fallback_policy=StrictSemanticPolicy(),
            require_input=True,
            require_expected=True,
        )

    @staticmethod
    def _sanitize_input(text: str) -> str:
        """脱敏处理：过滤敏感信息避免泄露给LLM厂商"""
        text = re.sub(r"sk-[a-zA-Z0-9]{20,}", "[REDACTED_API_KEY]", text)
        text = re.sub(r"AKIA[A-Z0-9]{16}", "[REDACTED_AWS_KEY]", text)
        text = re.sub(r"AIza[0-9A-Za-z\-_]{35}", "[REDACTED_GCP_KEY]", text)
        text = re.sub(r"mongodb\+srv://[^\s]+", "[REDACTED_MONGO_URI]", text)
        text = re.sub(r"postgres(ql)?://[^\s]+", "[REDACTED_PG_URI]", text)
        text = re.sub(r"mysql://[^\s]+", "[REDACTED_MYSQL_URI]", text)
        return text

    def _do_evaluate(self, request: EvaluationSchema) -> DomainResponse:
        if error := self.validate_input(request):
            return error
        if error := self.validate_expected(request):
            return error

        user_input = self.get_input_text(request)
        expected_output = self.get_payload_data(request, "expected_output")
        actual_output = self.get_payload_data(request, "actual_output", "") or self.get_payload_data(request, "text", "")
        system_prompt = self.get_payload_data(request, "system_prompt")

        sanitized_input = self._sanitize_input(user_input)
        sanitized_expected_output = self._sanitize_input(expected_output) if expected_output else None
        sanitized_actual_output = self._sanitize_input(actual_output) if actual_output else None

        prompt = self._build_evaluation_prompt(sanitized_input, sanitized_expected_output, sanitized_actual_output, system_prompt)

        try:
            llm_output = self.client.chat(prompt)
            score = self.safe_parse_score(llm_output)

            if score is None:
                logger.error(f"通用评估响应数字提取失败: '{llm_output}'")
                return self.create_error_response(
                    error_message=f"无法解析评分: {llm_output[:100]}",
                    error_code="SCORE_PARSE_ERROR",
                )

            return self.create_success_response(
                text=llm_output,
                score=score,
                data={
                    "user_input": user_input,
                    "expected_output": expected_output,
                    "raw_output": llm_output,
                    "evaluator": "general",
                },
            )

        except Exception as e:
            logger.exception(f"通用评估器 LLM 调用失败，降级至规则评估: {e}")

        rule_score = self._rule_based_general(user_input, expected_output, actual_output)
        if rule_score is not None:
            return self.create_partial_response(
                text=actual_output,
                score=rule_score,
                dimensions_evaluated=["rule_based_general"],
                dimensions_skipped=["llm_judgment"],
                skip_reasons={"llm_judgment": "LLM unavailable"},
                data={
                    "user_input": user_input,
                    "expected_output": expected_output,
                    "evaluator": "general",
                    "fallback_reason": "LLM unavailable, using rule-based evaluation",
                },
                confidence=0.4,
                evaluation_method="rule_based",
            )

        return self.create_error_response(
            error_message=f"LLM 调用异常且规则降级失败: {str(e)}", error_code="LLM_CALL_ERROR"
        )

    def _rule_based_general(self, user_input: str, expected_output: str, actual_output: str) -> float | None:
        """基于规则的通用评估（降级策略）- 使用统一的 FallbackScoringService"""
        return fallback_scoring_service.calculate_fallback_score(
            user_input=user_input,
            expected_output=expected_output,
            actual_output=actual_output,
            evaluator_type="general",
        )

    def _calculate_answer_coverage(self, actual: str, expected: str) -> float:
        """计算答案覆盖率"""
        return text_analysis_service.calculate_answer_coverage(actual, expected)

    def _calculate_question_relevance(self, question: str, answer: str) -> float:
        """计算问题相关性"""
        return text_analysis_service.calculate_question_relevance(question, answer)

    def _detect_opposite_meaning(self, actual: str, expected: str) -> bool:
        """检测反义词"""
        return text_analysis_service.detect_opposite_meaning(actual, expected)

    def _build_evaluation_prompt(
        self, user_input: str, expected_output: str, actual_output: str, system_prompt: str | None
    ) -> str:
        """构建通用评估 Prompt"""
        system_context = f"【系统指令】：{system_prompt}\n\n" if system_prompt else ""

        return (
            "你是一个资深的AI输出质量评测专家。请评估以下回答的质量。\n"
            "评估维度包括：准确性、完整性、逻辑性、表达清晰度。\n"
            "请以JSON格式输出评估结果，包含 score（0.0-1.0）和 confidence（0.0-1.0）字段。\n"
            "其中 score=1.0 表示完美，score=0.0 表示完全错误。\n\n"
            f"{system_context}"
            f"【输入问题/指令】：{user_input}\n"
            f"【期望输出】：{expected_output}\n"
            f"【实际输出】：{actual_output}\n\n"
            "请输出JSON格式结果：\n"
        )

    async def _do_evaluate_async(self, request: EvaluationSchema) -> DomainResponse:
        """
        🚀 真正异步评估核心逻辑：使用 achat 方法而非线程池

        设计原则：
        - 如果 client 支持 achat，则直接 await 异步调用
        - 否则回退到线程池执行同步评估
        - 熔断保护由 evaluate_async 上层提供
        """
        if error := self.validate_input(request):
            return error
        if error := self.validate_expected(request):
            return error

        user_input = self.get_input_text(request)
        expected_output = self.get_payload_data(request, "expected_output")
        actual_output = self.get_payload_data(request, "actual_output", "") or self.get_payload_data(request, "text", "")
        system_prompt = self.get_payload_data(request, "system_prompt")

        sanitized_input = self._sanitize_input(user_input)
        sanitized_expected_output = self._sanitize_input(expected_output) if expected_output else None
        sanitized_actual_output = self._sanitize_input(actual_output) if actual_output else None

        prompt = self._build_evaluation_prompt(sanitized_input, sanitized_expected_output, sanitized_actual_output, system_prompt)

        try:
            if hasattr(self.client, "achat"):
                llm_output = await self.client.achat(prompt)
            else:
                llm_output = await asyncio.to_thread(self.client.chat, prompt)

            score = self.safe_parse_score(llm_output)

            if score is None:
                logger.error(f"通用评估响应数字提取失败: '{llm_output}'")
                return self.create_error_response(
                    error_message=f"无法解析评分: {llm_output[:100]}",
                    error_code="SCORE_PARSE_ERROR",
                )

            return self.create_success_response(
                text=llm_output,
                score=score,
                data={
                    "user_input": user_input,
                    "expected_output": expected_output,
                    "raw_output": llm_output,
                    "evaluator": "general",
                    "async_mode": "true",
                },
            )

        except Exception as e:
            logger.exception(f"通用评估器 LLM 异步调用失败，降级至规则评估: {e}")

        rule_score = self._rule_based_general(user_input, expected_output, actual_output)
        if rule_score is not None:
            return self.create_partial_response(
                text=actual_output,
                score=rule_score,
                dimensions_evaluated=["rule_based_general"],
                dimensions_skipped=["llm_judgment"],
                skip_reasons={"llm_judgment": "LLM unavailable"},
                data={
                    "user_input": user_input,
                    "expected_output": expected_output,
                    "evaluator": "general",
                    "fallback_reason": "LLM unavailable, using rule-based evaluation",
                    "async_mode": "true",
                },
                confidence=0.4,
                evaluation_method="rule_based",
            )

        return self.create_error_response(
            error_message=f"LLM 调用异常且规则降级失败: {str(e)}", error_code="LLM_CALL_ERROR"
        )
