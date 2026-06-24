"""
文本匹配(Text)评估器 - 2026 工业级标准重构版

用于评估文本匹配系统的输出质量，包括：
- 语义相似度评估
- 事实一致性检查
- 关键信息完整性验证

工业级特性：
- LLM-as-a-Judge 语义评估
- SemanticTaskPolicy 降级策略（LLM失败时走本地相似度）
- 完整类型注解
- 结构化异常处理
"""

import logging

from src.domain.evaluators.base import BaseEvaluator
from src.domain.evaluators.evaluator_factory import EvaluatorFactory
from src.domain.evaluators.fallback_policy import SemanticTaskPolicy
from src.domain.evaluators.metadata import TextMetadata
from src.domain.evaluators.scoring import is_passing, score_text_similarity
from src.schemas.evaluation import DomainResponse, EvaluationSchema

logger = logging.getLogger(__name__)


@EvaluatorFactory.register("text")
def create_text_evaluator(client=None):
    return TextMatchEvaluator(client=client)


class TextMatchEvaluator(BaseEvaluator):
    def __init__(self, client=None):
        super().__init__(client, fallback_policy=SemanticTaskPolicy())

    def _do_evaluate(self, request: EvaluationSchema) -> DomainResponse:
        actual_output = self.get_payload_data(request, "actual_output")
        if not actual_output:
            return self.create_error_response(
                error_message="actual_output 不能为空",
                error_code="MISSING_ACTUAL_OUTPUT",
            )
        expected_output = self.get_payload_data(request, "expected_output")
        if not expected_output:
            return self.create_error_response(
                error_message="expected_output 不能为空",
                error_code="MISSING_EXPECTED_OUTPUT",
            )

        meta = TextMetadata.model_validate(request.metadata or {})

        if self.client:
            return self._evaluate_with_llm(actual_output, expected_output, meta)
        else:
            return self._evaluate_with_similarity(actual_output, expected_output, meta)

    def _evaluate_with_llm(
        self, actual_output: str, expected_output: str, meta: TextMetadata
    ) -> DomainResponse:
        """使用 LLM-as-a-Judge 进行语义评估"""
        try:
            prompt = self._build_evaluation_prompt(actual_output, expected_output, meta)
            llm_output = self.client.chat(prompt)
            score = self.safe_parse_score(llm_output)

            if score is None:
                logger.error(f"文本评估响应数字提取失败: '{llm_output}'")
                raise ValueError(f"无法解析评分: {llm_output}")

            return self.create_success_response(
                text=actual_output,
                score=score,
                data={
                    "actual_output": actual_output,
                    "expected_output": expected_output,
                    "raw_output": llm_output,
                    "evaluator": "text",
                },
                metadata={
                    "tone": meta.tone,
                    "match_mode": "llm_as_judge",
                    "passed": is_passing(score),
                },
            )

        except Exception as e:
            logger.exception(f"文本评估器 LLM 调用失败: {e}")
            return self._evaluate_with_similarity(actual_output, expected_output, meta)

    def _evaluate_with_similarity(
        self, actual_output: str, expected_output: str, meta: TextMetadata
    ) -> DomainResponse:
        """使用文本相似度进行降级评估"""
        score = score_text_similarity(actual_output, expected_output)

        return self.create_success_response(
            text=actual_output,
            score=score,
            data={
                "actual_output": actual_output,
                "expected_output": expected_output,
                "evaluator": "text",
                "warning": "使用文本相似度降级策略，结果可能不准确",
            },
            metadata={
                "tone": meta.tone,
                "match_mode": "text_similarity",
                "passed": is_passing(score),
            },
        )

    def _build_evaluation_prompt(
        self, actual_output: str, expected_output: str, meta: TextMetadata
    ) -> str:
        """构建文本匹配评估 Prompt"""
        tone_context = f"【语气要求】：{meta.tone}\n" if meta.tone else ""

        return (
            "你是一个严谨的语义匹配评测专家。请评估以下‘实际输出’与‘期望输出’的语义相似度。\n"
            "评估标准：\n"
            "- 语义完全等价（忽略表达方式差异）：1.0分\n"
            "- 核心含义一致但表述不同：0.7-0.9分\n"
            "- 部分信息重叠：0.3-0.6分\n"
            "- 完全无关：0.0分\n"
            "输出一个 0.0 到 1.0 的分数。\n\n"
            f"{tone_context}"
            f"【期望输出】：{expected_output}\n"
            f"【实际输出】：{actual_output}\n\n"
            "最终评分（仅输出数字）："
        )
