import logging

from src.domain.evaluators.base import BaseEvaluator
from src.domain.evaluators.evaluator_factory import EvaluatorFactory
from src.domain.evaluators.fallback_policy import SemanticTaskPolicy
from src.schemas.evaluation import DomainResponse, EvaluationSchema

logger = logging.getLogger(__name__)


@EvaluatorFactory.register("semantic")
class SemanticEvaluator(BaseEvaluator):
    def __init__(self, client=None):
        # 注入语义降级策略（LLM 挂了自动走本地 Embedding 相似度）
        super().__init__(
            client, fallback_policy=SemanticTaskPolicy(), require_input=True, require_expected=True
        )

    def _do_evaluate(self, request: EvaluationSchema) -> DomainResponse:
        # 1. 契约前置验证
        if error := self.validate_input(request):
            return error
        if error := self.validate_expected(request):
            return error
        if error := self.require_client_with_error():
            return error

        actual_output = self.get_payload_data(request, "actual_output")
        expected_output = self.get_payload_data(request, "expected_output")

        # 2. 裸奔构造 Prompt（无需考虑异常捕获）
        prompt = (
            "你是一个严谨的语义对齐裁判。请评估以下‘实际输出’与‘期望输出’的语义相似度。\n"
            "忽略字面表达差异，关注核心本质含义。最后必须输出一个 0.0 到 1.0 之间的浮点分数。\n\n"
            f"【期望输出】：{expected_output}\n"
            f"【实际输出】：{actual_output}\n\n"
            "评分（仅输出数字）："
        )

        # 3. 发射请求并调用基类防御盾牌
        llm_output = self.client.chat(prompt)
        score = self.safe_parse_score(llm_output)

        if score is None:
            # 显式抛出异常，基类熔断器会自动记录失败，并无缝触发 SemanticTaskPolicy 向量计算
            raise ValueError(f"LLM 响应无法解析为合法分数: '{llm_output}'")

        return self.create_success_response(
            text=actual_output, score=score, data={"raw_llm_judgment": llm_output}
        )
