"""
摘要(Summary)评估器 - 2026 工业级标准重构版

用于评估摘要生成系统的输出质量，包括：
- 完整性评估：是否覆盖原文关键信息
- 准确性评估：是否与原文事实一致
- 简洁性评估：是否去除冗余信息
- 连贯性评估：是否逻辑通顺

工业级特性：
- LLM-as-a-Judge 多维评估
- SemanticTaskPolicy 降级策略
- 完整类型注解
- 结构化异常处理
"""

import logging

from src.domain.evaluators.base import BaseEvaluator
from src.domain.evaluators.evaluator_factory import EvaluatorFactory
from src.domain.evaluators.fallback_policy import SemanticTaskPolicy
from src.domain.evaluators.scoring import is_passing, score_text_similarity
from src.schemas.evaluation import DomainResponse, EvaluationSchema

logger = logging.getLogger(__name__)


@EvaluatorFactory.register("summary")
class SummaryEvaluator(BaseEvaluator):
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

        context = self.get_input_text(request)

        if self.client:
            return self._evaluate_with_llm(actual_output, expected_output, context)
        else:
            return self._evaluate_with_similarity(actual_output, expected_output)

    def _evaluate_with_llm(
        self, actual_output: str, expected_output: str, context: str
    ) -> DomainResponse:
        """使用 LLM-as-a-Judge 进行多维摘要评估"""
        try:
            prompt = self._build_evaluation_prompt(actual_output, expected_output, context)
            llm_output = self.client.chat(prompt)

            score, dimensions = self._parse_multi_dimension_score(llm_output)

            if score is None:
                logger.error(f"摘要评估响应解析失败: '{llm_output}'")
                raise ValueError(f"无法解析评分: {llm_output}")

            return self.create_success_response(
                text=actual_output,
                score=score,
                data={
                    "actual_output": actual_output,
                    "expected_output": expected_output,
                    "context": context[:200] + "..." if len(context) > 200 else context,
                    "raw_output": llm_output,
                    "dimensions": dimensions,
                    "evaluator": "summary",
                },
                metadata={
                    "match_mode": "llm_as_judge",
                    "passed": is_passing(score),
                },
            )

        except Exception as e:
            logger.exception(f"摘要评估器 LLM 调用失败: {e}")
            return self._evaluate_with_similarity(actual_output, expected_output)

    def _evaluate_with_similarity(self, actual_output: str, expected_output: str) -> DomainResponse:
        """使用文本相似度进行降级评估"""
        score = score_text_similarity(actual_output, expected_output)

        return self.create_success_response(
            text=actual_output,
            score=score,
            data={
                "actual_output": actual_output,
                "expected_output": expected_output,
                "evaluator": "summary",
                "warning": "使用文本相似度降级策略，结果可能不准确",
            },
            metadata={
                "match_mode": "text_similarity",
                "passed": is_passing(score),
            },
        )

    def _build_evaluation_prompt(
        self, actual_output: str, expected_output: str, context: str
    ) -> str:
        """构建摘要评估 Prompt"""
        context_display = context[:500] + "..." if len(context) > 500 else context

        return (
            "你是一个资深的摘要质量评测专家。请从以下维度评估摘要质量：\n"
            "1. 完整性：是否覆盖原文关键信息（权重0.3）\n"
            "2. 准确性：是否与原文事实一致（权重0.4）\n"
            "3. 简洁性：是否去除冗余信息（权重0.2）\n"
            "4. 连贯性：是否逻辑通顺（权重0.1）\n"
            "请分别给出每个维度的分数（0.0-1.0），然后给出加权总分。\n"
            "输出格式：完整性=X.XX,准确性=X.XX,简洁性=X.XX,连贯性=X.XX,总分=X.XX\n\n"
            f"【原文】：{context_display}\n"
            f"【期望摘要】：{expected_output}\n"
            f"【实际摘要】：{actual_output}\n\n"
            "评估结果："
        )

    def _parse_multi_dimension_score(self, llm_output: str) -> tuple[float | None, dict | None]:
        """解析多维评分"""
        try:
            dimensions = {}
            total_score = None

            import re

            pattern = r"(完整性|准确性|简洁性|连贯性|总分)=([\d.]+)"
            matches = re.findall(pattern, llm_output)

            for key, value in matches:
                try:
                    score = float(value)
                    dimensions[key] = score
                    if key == "总分":
                        total_score = score
                except ValueError:
                    continue

            if total_score is None and dimensions:
                weights = {"完整性": 0.3, "准确性": 0.4, "简洁性": 0.2, "连贯性": 0.1}
                total_score = sum(
                    dimensions.get(key, 0) * weights.get(key, 0)
                    for key in ["完整性", "准确性", "简洁性", "连贯性"]
                )

            return total_score, dimensions

        except Exception as e:
            logger.error(f"多维评分解析失败: {e}")
            return None, None
