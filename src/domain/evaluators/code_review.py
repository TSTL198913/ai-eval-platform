"""
代码审查评估器

综合评估代码的安全漏洞和质量。
"""

import asyncio

from src.domain.evaluators.base import BaseEvaluator
from src.domain.evaluators.code import CodeEvaluator
from src.domain.evaluators.evaluator_factory import EvaluatorFactory
from src.domain.evaluators.security_rules import (
    detect_security_vulnerabilities,
    format_security_report,
)
from src.schemas.evaluation import DomainResponse

DEFAULT_SECURITY_WEIGHT = 0.40
DEFAULT_QUALITY_WEIGHT = 0.60


@EvaluatorFactory.register("code_review")
class CodeReviewEvaluator(BaseEvaluator):
    """综合代码审查评估器"""

    def __init__(self, client=None):
        super().__init__(client=client)
        self._delegate = CodeEvaluator(client=client)

    def _do_evaluate(self, request) -> DomainResponse:
        """执行安全扫描与代码质量评估"""
        code = self.get_payload_data(request, "code") or self.get_input_text(request)
        if not code:
            return self.create_error_response(
                error_message="评测代码不能为空",
                error_code="MISSING_CODE",
            )

        security_result = detect_security_vulnerabilities(code)
        quality_response = self._delegate._do_evaluate(request)

        security_score = security_result["score"]
        quality_score = quality_response.score

        request_meta = request.metadata or {}
        w_security = request_meta.get("weight_security", DEFAULT_SECURITY_WEIGHT)
        w_quality = request_meta.get("weight_quality", DEFAULT_QUALITY_WEIGHT)

        has_critical = any(v["severity"] == "critical" for v in security_result["vulnerabilities"])
        if has_critical:
            w_security, w_quality = 0.65, 0.35
        else:
            total_w = w_security + w_quality
            if total_w > 0:
                w_security, w_quality = w_security / total_w, w_quality / total_w

        total_score = (security_score * w_security) + (quality_score * w_quality)
        total_score = round(min(max(total_score, 0.0), 1.0), 4)

        response_parts = []
        if security_result["vulnerabilities"]:
            response_parts.append(format_security_report(security_result))
        if quality_response.text:
            response_parts.append(quality_response.text)

        return self.create_success_response(
            text=" | ".join(response_parts) if response_parts else "代码综合审查安全通过",
            score=total_score,
            data={
                **(quality_response.data or {}),
                "security_score": security_score,
                "security_summary": security_result["summary"],
                "security_vulnerabilities": security_result["vulnerabilities"],
                "weights_applied": {
                    "security": round(w_security, 2),
                    "quality": round(w_quality, 2),
                },
            },
        )

    async def evaluate_async(self, request) -> DomainResponse:
        """异步评估入口"""
        return await asyncio.to_thread(self.evaluate, request)
