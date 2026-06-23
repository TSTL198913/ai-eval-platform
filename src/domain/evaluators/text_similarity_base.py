"""
基于文本相似度评估的抽象基类
用于 TranslationEvaluator 等子类继承
"""

from abc import abstractmethod

from src.domain.evaluators.base import BaseEvaluator
from src.domain.evaluators.evaluator_factory import EvaluatorFactory
from src.domain.evaluators.scoring import score_text_similarity
from src.schemas.evaluation import DomainResponse, EvaluationSchema


@EvaluatorFactory.register("text_similarity_base")
class TextSimilarityBasedEvaluator(BaseEvaluator):
    """基于文本相似度评估的抽象基类

    子类需要实现：
    - build_prompt(): 构建评估Prompt
    - get_evaluator_name(): 获取评估器名称
    """

    def _do_evaluate(self, request: EvaluationSchema) -> DomainResponse:
        """统一的评估流程"""
        user_input = self.get_input_text(request)
        expected_output = self.get_payload_data(request, "expected_output")

        prompt = self.build_prompt(user_input, request)

        llm_output = self._call_llm(prompt)

        score = self._calculate_score(llm_output, expected_output)

        return DomainResponse(
            is_valid=True,
            text=llm_output,
            score=score,
            data={
                "user_input": user_input,
                "expected_output": expected_output,
                "llm_output": llm_output,
            },
        )

    def _call_llm(self, prompt: str) -> str:
        """调用LLM获取评估结果"""
        if self.client:
            try:
                return self.client.chat(prompt)
            except Exception:
                return prompt
        return prompt

    def _calculate_score(self, llm_output: str, expected_output: str | None) -> float:
        """计算相似度分数"""
        if expected_output is None:
            return 1.0
        return score_text_similarity(llm_output, expected_output)

    @abstractmethod
    def build_prompt(self, user_input: str, request: EvaluationSchema) -> str:
        """构建评估Prompt - 子类必须实现"""
        pass

    def get_evaluator_name(self) -> str:
        """获取评估器名称 - 子类应重写"""
        return "text_similarity"
