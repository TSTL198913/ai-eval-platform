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
from src.domain.evaluators.scoring import is_passing
from src.domain.evaluators.scoring import score_text_similarity
from src.schemas.evaluation import DomainResponse
from src.schemas.evaluation import EvaluationSchema

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
            prompt = self._build_evaluation_prompt(actual_output, expected_output, meta)

            def data_builder(score: float, llm_output: str) -> dict:
                return {
                    "actual_output": actual_output,
                    "expected_output": expected_output,
                    "raw_output": llm_output,
                    "evaluator": "text",
                }

            def fallback_fn(error_msg: str) -> DomainResponse:
                return self._evaluate_with_similarity(actual_output, expected_output, meta)

            result = self._evaluate_with_llm(
                prompt=prompt,
                fallback_fn=fallback_fn,
                data_builder=data_builder,
                evaluator_name="TextEvaluator",
                text=actual_output,
            )
            result.metadata.update({
                "tone": getattr(meta, "tone", None),
                "match_mode": "llm_as_judge",
                "passed": is_passing(result.score) if result.score is not None else False,
            })
            return result
        else:
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
                "tone": getattr(meta, "tone", None),
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
