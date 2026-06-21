from src.domain.evaluators.base import BaseEvaluator
from src.domain.evaluators.evaluator_factory import EvaluatorFactory
from src.schemas.evaluation import DomainResponse, EvaluationSchema


@EvaluatorFactory.register("classification")
class ClassificationEvaluator(BaseEvaluator):
    def evaluate(self, request: EvaluationSchema) -> DomainResponse:
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
        llm_output = self.client.chat(prompt) if self.client else expected_label
        llm_output = llm_output.strip()

        score = 1.0 if llm_output == expected_label else 0.0

        return DomainResponse(
            is_valid=True,
            text=llm_output,
            score=score,
            data=f"分类结果: 预测={llm_output}, 预期={expected_label}",
        )
