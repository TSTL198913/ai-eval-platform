from loguru import logger

from src.schemas.evaluation import DomainResponse
from src.schemas.evaluation import EvaluationSchema


class FallbackInfrastructureMixin:
    def _execute_fallback_infrastructure(
        self, request: EvaluationSchema, error: Exception
    ) -> DomainResponse:
        evaluator_name = type(self).__name__

        fallback_policy = self.fallback_policy
        if fallback_policy is None:
            has_rule_based = (
                hasattr(self, '_rule_based_qa') and callable(getattr(self, '_rule_based_qa'))
            ) or (
                hasattr(self, '_rule_based_factuality') and callable(getattr(self, '_rule_based_factuality'))
            )
            if has_rule_based:
                from src.domain.evaluators.fallback_policy import RuleBasedFallbackPolicy
                fallback_policy = RuleBasedFallbackPolicy()
            else:
                return self.create_error_response(
                    error_message=f"评估器 {evaluator_name} 失败且未配置降级策略。原始错误: {error}",
                    error_code="NO_FALLBACK_POLICY",
                )

        if not fallback_policy.should_fallback(error):
            return self.create_error_response(
                error_message=f"评估器 {evaluator_name} 失败，严格策略禁止降级。原始错误: {error}",
                error_code="FALLBACK_DISABLED",
            )

        try:
            from src.domain.evaluators.base import BaseEvaluator
            BaseEvaluator.set_current_evaluator(self)
            actual_output = self.get_payload_data(request, "actual_output", "")
            expected_output = self.get_payload_data(request, "expected_output", "")
            question = self.get_payload_data(request, "question", "")

            score = fallback_policy.get_fallback_score(actual_output, expected_output, question)
            metadata = self._build_fallback_metadata(error)

            result = self.create_partial_response(
                text=f"降级评估结果（基于 Embedding 相似度）：{actual_output}",
                score=score,
                dimensions_evaluated=["fallback_similarity"],
                dimensions_skipped=["llm_semantic"],
                skip_reasons={"llm_semantic": f"LLM 评估失败: {str(error)}"},
                data={"notice": "Derived from backup pipeline (Embedding fallback)"},
                metadata=metadata,
                evaluation_method="embedding",
            )
            result = self._auto_compute_confidence(result)
            return result
        except Exception as fallback_err:
            return self._handle_cascading_failure(evaluator_name, error, fallback_err)

    async def _execute_fallback_infrastructure_async(
        self, request: EvaluationSchema, error: Exception
    ) -> DomainResponse:
        evaluator_name = type(self).__name__

        fallback_policy = self.fallback_policy
        if fallback_policy is None:
            has_rule_based = (
                hasattr(self, '_rule_based_qa') and callable(getattr(self, '_rule_based_qa'))
            ) or (
                hasattr(self, '_rule_based_factuality') and callable(getattr(self, '_rule_based_factuality'))
            )
            if has_rule_based:
                from src.domain.evaluators.fallback_policy import RuleBasedFallbackPolicy
                fallback_policy = RuleBasedFallbackPolicy()
            else:
                return self.create_error_response(
                    error_message=f"评估器 {evaluator_name} 失败且未配置降级策略。原始错误: {error}",
                    error_code="NO_FALLBACK_POLICY",
                )

        if not fallback_policy.should_fallback(error):
            return self.create_error_response(
                error_message=f"评估器 {evaluator_name} 失败，严格策略禁止降级。原始错误: {error}",
                error_code="FALLBACK_DISABLED",
            )

        try:
            from src.domain.evaluators.base import BaseEvaluator
            BaseEvaluator.set_current_evaluator(self)
            actual_output = self.get_payload_data(request, "actual_output", "")
            expected_output = self.get_payload_data(request, "expected_output", "")
            question = self.get_payload_data(request, "question", "")

            score = await fallback_policy.get_fallback_score_async(actual_output, expected_output, question)
            metadata = self._build_fallback_metadata(error)

            result = self.create_partial_response(
                text=f"降级评估结果（基于 Embedding 相似度）：{actual_output}",
                score=score,
                dimensions_evaluated=["fallback_similarity"],
                dimensions_skipped=["llm_semantic"],
                skip_reasons={"llm_semantic": f"LLM 评估失败: {str(error)}"},
                data={"notice": "Derived from async backup pipeline (Embedding fallback)"},
                metadata=metadata,
                evaluation_method="embedding",
            )
            result = self._auto_compute_confidence(result)
            return result
        except Exception as fallback_err:
            return self._handle_cascading_failure(evaluator_name, error, fallback_err)

    def _build_fallback_metadata(self, error: Exception) -> dict:
        metadata = self.fallback_policy.get_fallback_metadata()
        metadata["confidence"] = self.fallback_policy.get_confidence()
        metadata["fallback_reason"] = str(error)
        return metadata

    def _handle_cascading_failure(
        self, evaluator_name: str, original_err: Exception, fallback_err: Exception
    ) -> DomainResponse:
        combined_msg = f"原始错误: {original_err} | 降级策略执行失败: {fallback_err}"
        logger.critical(f"评估器 {evaluator_name} 陷入灾难性双重崩溃: {combined_msg}")
        return self.create_error_response(
            error_message=f"评估器全面崩溃，拒绝不安全静默降级: {combined_msg}",
            error_code="CASCADING_FALLBACK_FAILURE",
        )
