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
"""

import logging
import re

from src.domain.evaluators.base import BaseEvaluator
from src.domain.evaluators.evaluator_factory import EvaluatorFactory
from src.domain.evaluators.fallback_policy import StrictSemanticPolicy
from src.schemas.evaluation import DomainResponse, EvaluationSchema

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
        if error := self.require_client_with_error():
            return error

        user_input = self.get_input_text(request)
        expected_output = self.get_payload_data(request, "expected_output")
        system_prompt = self.get_payload_data(request, "system_prompt")

        sanitized_input = self._sanitize_input(user_input)

        prompt = self._build_evaluation_prompt(sanitized_input, expected_output, system_prompt)

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
            logger.exception(f"通用评估器 LLM 调用失败: {e}")
            return self.create_error_response(
                error_message=f"LLM 调用异常: {str(e)}", error_code="LLM_CALL_ERROR"
            )

    def _build_evaluation_prompt(
        self, user_input: str, expected_output: str, system_prompt: str | None
    ) -> str:
        """构建通用评估 Prompt"""
        system_context = f"【系统指令】：{system_prompt}\n\n" if system_prompt else ""

        return (
            "你是一个资深的AI输出质量评测专家。请评估以下回答的质量。\n"
            "评估维度包括：准确性、完整性、逻辑性、表达清晰度。\n"
            "输出一个 0.0 到 1.0 的分数，其中 1.0 表示完美，0.0 表示完全错误。\n\n"
            f"{system_context}"
            f"【输入问题/指令】：{user_input}\n"
            f"【期望输出】：{expected_output}\n"
            f"【实际输出】：需要你基于上述信息进行评估\n\n"
            "最终评分（仅输出数字）："
        )
