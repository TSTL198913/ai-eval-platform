from src.domain.evaluators.base import BaseEvaluator, EvaluatorFactory
from src.schemas.evaluation import DomainResponse, EvaluationSchema


@EvaluatorFactory.register("grammar")
class GrammarEvaluator(BaseEvaluator):
    def evaluate(self, request: EvaluationSchema) -> DomainResponse:
        user_input = self.get_input_text(request)
        if not user_input:
            return DomainResponse(is_valid=False, error="user_input/text 不能为空")

        prompt = f"""检查以下文本的语法错误，返回修正后的文本和错误数量：
文本：{user_input}
格式：错误数: X\n修正后: ..."""
        llm_output = self.client.chat(prompt) if self.client else "错误数: 0\n修正后: " + user_input

        error_count = 0
        corrected_text = user_input
        lines = llm_output.strip().split("\n")
        for line in lines:
            if line.startswith("错误数"):
                try:
                    error_count = int(line.split(":")[1].strip())
                except ValueError:
                    error_count = 0
            elif line.startswith("修正后"):
                corrected_text = line.split(":", 1)[1].strip()

        score = max(0, 1.0 - error_count * 0.2)

        return DomainResponse(
            is_valid=True,
            text=llm_output,
            score=score,
            data=f"语法检查: 错误数={error_count}, 修正后={corrected_text}",
        )
