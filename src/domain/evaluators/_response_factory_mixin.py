from typing import Any, Optional

from loguru import logger

from src.schemas.evaluation import DomainResponse
from src.schemas.evaluation import EvaluatorStatus


class ResponseFactoryMixin:
    def create_error_response(
        self,
        error_message: str,
        error_code: str | None = None,
        metadata: dict | None = None,
        confidence: float | None = None,
        data: dict | None = None,
    ) -> DomainResponse:
        response_metadata = metadata or {}
        if error_code:
            response_metadata["error_code"] = error_code
        final_confidence = confidence if confidence is not None else 0.05

        final_data = data or {}
        if "confidence_components" not in final_data:
            final_data["confidence_components"] = {
                "evaluation_method": "error",
                "reason": error_message,
                "confidence_breakdown": {},
                "base": 0.0,
                "score_bonus": 0.0,
                "time_penalty": 0.0,
            }
        if "confidence_auto_computed" not in final_data:
            final_data["confidence_auto_computed"] = True
        if "is_valid" not in final_data:
            final_data["is_valid"] = False
        if "error" not in final_data:
            final_data["error"] = error_message

        final_score = final_data.get("overall_score", 0.0)
        if final_score > 0:
            final_score = 0.0

        response = DomainResponse(
            error=error_message,
            metadata=response_metadata,
            evaluation_status=EvaluatorStatus.ERROR,
            confidence=final_confidence,
            score=final_score,
            data=final_data,
        )
        response.status_code = 400
        return response

    def create_success_response(
        self,
        text: str = "评估完成",
        score: float = 1.0,
        data: dict | None = None,
        metadata: dict | None = None,
        confidence: float | None = None,
        is_full_evaluation: bool = True,
    ) -> DomainResponse:
        default_confidence = 0.95 if is_full_evaluation else 0.85
        final_confidence = confidence if confidence is not None else default_confidence

        if confidence is None and score == 0.0:
            final_confidence = 0.3

        if confidence is None and score < 0.3:
            final_confidence = min(final_confidence, 0.5)

        final_data = data or {}
        if "is_valid" not in final_data:
            final_data["is_valid"] = True

        return DomainResponse(
            text=text,
            score=score,
            data=final_data,
            metadata=metadata or {},
            evaluation_status=EvaluatorStatus.SUCCESS,
            confidence=final_confidence,
        )

    def create_cannot_evaluate_response(
        self,
        reason: str,
        dimensions_skipped: list[str] | None = None,
        metadata: dict | None = None,
        confidence: float | None = None,
    ) -> DomainResponse:
        response_data = {
            "dimensions_skipped": dimensions_skipped or [],
            "skip_reason": reason,
        }
        return DomainResponse(
            score=0.0,
            text=f"无法评估: {reason}",
            data=response_data,
            metadata=metadata or {},
            evaluation_status=EvaluatorStatus.CANNOT_EVALUATE,
            confidence=confidence if confidence is not None else 0.2,
        )

    def create_partial_response(
        self,
        text: str,
        score: float,
        dimensions_evaluated: list[str],
        dimensions_skipped: list[str],
        skip_reasons: dict[str, str] | None = None,
        data: dict | None = None,
        metadata: dict | None = None,
        confidence: float | None = None,
        evaluation_method: str = "llm",
    ) -> DomainResponse:
        response_data = (data or {}).copy()
        response_data.update({
            "dimensions_evaluated": dimensions_evaluated,
            "dimensions_skipped": dimensions_skipped,
            "skip_reasons": skip_reasons or {},
            "evaluation_method": evaluation_method,
            "confidence_components": {
                "evaluation_method": evaluation_method,
                "coverage_ratio": len(dimensions_evaluated) / max(len(dimensions_evaluated) + len(dimensions_skipped), 1),
                "confidence_breakdown": {},
                "skipped_dimensions": dimensions_skipped,
            },
        })

        if confidence is None:
            total_dims = len(dimensions_evaluated) + len(dimensions_skipped)
            coverage_ratio = len(dimensions_evaluated) / max(total_dims, 1)

            if evaluation_method == "llm":
                final_confidence = 0.7 * coverage_ratio + 0.25
            elif evaluation_method == "embedding":
                final_confidence = 0.5 * coverage_ratio + 0.3
            else:
                final_confidence = 0.3 * coverage_ratio + 0.2

            confidence = round(final_confidence, 2)

        return DomainResponse(
            text=text,
            score=score,
            data=response_data,
            metadata=metadata or {},
            evaluation_status=EvaluatorStatus.PARTIAL,
            confidence=confidence,
        )
