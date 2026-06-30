"""
分类(Classification)评估器 - 2026 工业级标准重构版

用于评估分类系统的输出质量，包括：
- 标签准确性评估
- 置信度量化
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


@EvaluatorFactory.register("classification")
class ClassificationEvaluator(BaseEvaluator):
    def __init__(self, client=None):
        super().__init__(client, fallback_policy=StrictSemanticPolicy(), require_input=True)

    def _do_evaluate(self, request: EvaluationSchema) -> DomainResponse:
        if error := self.validate_input(request):
            return error

        user_input = self.get_input_text(request)
        actual_output = self.get_payload_data(request, "actual_output")
        expected_label = self.get_payload_data(request, "expected_label")
        labels = self.get_payload_data(request, "labels", [])

        if not expected_label:
            return self.create_error_response(
                error_message="expected_label 不能为空",
                error_code="MISSING_EXPECTED_LABEL",
            )

        if not actual_output:
            return self.create_error_response(
                error_message="actual_output 不能为空",
                error_code="MISSING_ACTUAL_OUTPUT",
            )

        if error := self.require_client_with_error():
            return error

        labels_str = ", ".join(labels) if labels else "正类, 负类"

        prompt = self._build_evaluation_prompt(
            user_input, actual_output, expected_label, labels_str
        )

        try:
            llm_output = self.client.chat(prompt)
            score = self.safe_parse_score(llm_output)

            if score is None:
                logger.error(f"分类评估响应数字提取失败: '{llm_output}'")
                score = self._calculate_fallback_score(actual_output, expected_label, labels)

            return self.create_success_response(
                text=actual_output,
                score=score,
                data={
                    "user_input": user_input,
                    "actual_output": actual_output,
                    "expected_label": expected_label,
                    "predicted_label": actual_output,
                    "all_labels": labels,
                    "raw_output": llm_output,
                    "evaluator": "classification",
                },
                metadata={"mode": "llm_as_judge"},
            )

        except Exception as e:
            logger.exception(f"分类评估器 LLM 调用失败: {e}")
            score = self._calculate_fallback_score(actual_output, expected_label, labels)
            return self.create_success_response(
                text=actual_output,
                score=score,
                data={
                    "user_input": user_input,
                    "actual_output": actual_output,
                    "expected_label": expected_label,
                    "warning": "LLM调用失败，使用语义相似度降级评分",
                },
                metadata={"mode": "fallback"},
            )

    def _build_evaluation_prompt(
        self, user_input: str, actual_output: str, expected_label: str, labels_str: str
    ) -> str:
        """构建分类评估 Prompt"""
        return (
            "你是一个严谨的分类评测专家。请评估以下分类结果的质量。\n"
            "评估标准：\n"
            "- 完全匹配期望标签：1.0分\n"
            "- 语义相近（如'汽车'与'轿车'）：0.7-0.9分\n"
            "- 部分相关（如'电子产品'与'手机'）：0.3-0.6分\n"
            "- 完全无关：0.0分\n"
            "输出一个 0.0 到 1.0 的分数。\n\n"
            f"【分类标签】：{labels_str}\n"
            f"【输入文本】：{user_input}\n"
            f"【期望标签】：{expected_label}\n"
            f"【实际分类】：{actual_output}\n\n"
            "最终评分（仅输出数字）："
        )

    def _calculate_fallback_score(
        self, actual_output: str, expected_label: str, labels: list
    ) -> float:
        """降级评分：基于语义相似度"""
        actual_lower = actual_output.lower()
        expected_lower = expected_label.lower()

        if actual_lower == expected_lower:
            return 1.0

        if expected_lower in actual_lower or actual_lower in expected_lower:
            return 0.8

        for label in labels:
            label_lower = label.lower()
            if actual_lower == label_lower:
                if label_lower == expected_lower:
                    return 1.0
                else:
                    return 0.1

        return 0.0
