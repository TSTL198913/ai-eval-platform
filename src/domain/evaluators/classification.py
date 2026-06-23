import logging

from src.domain.evaluators.base import BaseEvaluator
from src.domain.evaluators.evaluator_factory import EvaluatorFactory
from src.schemas.evaluation import DomainResponse, EvaluationSchema

logger = logging.getLogger(__name__)


@EvaluatorFactory.register("classification")
class ClassificationEvaluator(BaseEvaluator):
    def _do_evaluate(self, request: EvaluationSchema) -> DomainResponse:
        if error := self.validate_input(request):
            return error
        user_input = self.get_input_text(request)
        expected_label = self.get_payload_data(request, "expected_label")
        labels = self.get_payload_data(request, "labels", [])
        if not expected_label:
            return DomainResponse(is_valid=False, error="expected_label 不能为空")

        labels_str = ", ".join(labels) if labels else "正类, 负类"
        prompt = f"""将以下文本分类到以下类别之一：{labels_str}
文本：{user_input}
请只返回类别名称。"""

        # 优先使用 LLM 进行分类
        if self.client:
            return self._evaluate_with_llm(user_input, expected_label, labels, prompt)

        # 无 LLM 时使用关键词匹配降级策略
        logger.warning("ClassificationEvaluator: 无 LLM client，降级使用关键词匹配策略")
        return self._evaluate_with_keyword_match(user_input, expected_label, labels)

    def _evaluate_with_llm(
        self, user_input: str, expected_label: str, labels: list, prompt: str
    ) -> DomainResponse:
        """使用 LLM 进行分类评估"""
        try:
            llm_output = self.client.chat(prompt).strip()
            score = 1.0 if llm_output == expected_label else 0.0

            return DomainResponse(
                is_valid=True,
                text=llm_output,
                score=score,
                data=f"分类结果(LLM): 预测={llm_output}, 预期={expected_label}",
                metadata={"mode": "llm", "predicted_label": llm_output},
            )
        except Exception as e:
            logger.error(f"ClassificationEvaluator LLM 调用失败: {e}")
            # LLM 调用失败时降级到关键词匹配
            return self._evaluate_with_keyword_match(user_input, expected_label, labels, str(e))

    def _evaluate_with_keyword_match(
        self, user_input: str, expected_label: str, labels: list, error: str = None
    ) -> DomainResponse:
        """使用关键词匹配进行降级分类评估"""
        user_input_lower = user_input.lower()
        expected_label_lower = expected_label.lower()

        # 检查输入文本中是否包含期望标签的关键词
        if expected_label_lower in user_input_lower:
            # 输入文本包含期望标签，可能是正确的分类
            return DomainResponse(
                is_valid=True,
                text=expected_label,
                score=0.7,  # 降级模式的置信度较低
                data=f"分类结果(降级模式-关键词匹配): 预测={expected_label}, 预期={expected_label}",
                metadata={
                    "mode": "fallback",
                    "warning": "使用关键词匹配降级策略，结果可能不准确",
                    "error": error,
                },
            )

        # 检查其他标签是否出现在输入中
        for label in labels:
            if label.lower() in user_input_lower and label.lower() != expected_label_lower:
                # 输入包含其他标签关键词，分类错误
                return DomainResponse(
                    is_valid=True,
                    text=label,
                    score=0.0,
                    data=f"分类结果(降级模式-关键词匹配): 预测={label}, 预期={expected_label}",
                    metadata={
                        "mode": "fallback",
                        "warning": "使用关键词匹配降级策略，结果可能不准确",
                        "predicted_label": label,
                    },
                )

        # 无法通过关键词判断，返回无效结果
        return DomainResponse(
            is_valid=False,
            text="",
            score=0.0,
            data="分类结果(降级模式): 无法判断，缺少 LLM client",
            metadata={
                "mode": "fallback",
                "warning": "无 LLM client 且关键词匹配失败，无法进行分类评估",
                "error": error,
            },
        )
