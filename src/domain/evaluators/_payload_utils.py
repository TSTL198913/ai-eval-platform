from typing import Any, Optional

from loguru import logger

from src.schemas.evaluation import DomainResponse
from src.schemas.evaluation import EvaluationSchema


class PayloadUtilsMixin:
    FIELD_ALIASES = {
        "actual_output": ["answer", "output", "text", "response"],
        "expected_output": ["expected_answer", "target", "ground_truth"],
        "user_input": ["text", "input", "question", "query", "prompt"],
        "question": ["user_input", "text", "query"],
        "evidence": ["context", "reference", "retrieved_context"],
        "context": ["evidence", "reference", "retrieved_context"],
        "code": ["actual_output", "text"],
        "ground_truth": ["expected_output", "expected_context"],
        "retrieved_context": ["context", "evidence"],
        "expected_context": ["ground_truth", "expected_output"],
        "expected_label": ["target_label", "label"],
    }

    def get_payload_data(self, request: Any, key: str, default: Any = None) -> Any:
        value = request.payload.get(key)
        if value is not None:
            return value

        aliases = self.FIELD_ALIASES.get(key, [])
        for alias in aliases:
            value = request.payload.get(alias)
            if value is not None:
                logger.debug(f"字段别名映射: {alias} -> {key}")
                return value

        return default

    def get_input_text(self, request: EvaluationSchema, default: str = "") -> str:
        return (
            self.get_payload_data(request, "user_input")
            or self.get_payload_data(request, "text")
            or self.get_payload_data(request, "question")
            or default
        )

    def validate_input(self, request: EvaluationSchema) -> DomainResponse | None:
        if not self._require_input:
            return None

        user_input = self.get_input_text(request)
        if not user_input or not user_input.strip():
            return self.create_error_response(
                error_message="user_input/text 不能为空", error_code="INVALID_INPUT"
            )
        return None

    def validate_expected(self, request: EvaluationSchema) -> DomainResponse | None:
        if not self._require_expected:
            return None

        expected_output = self.get_payload_data(request, "expected_output") or self.get_payload_data(request, "expected_answer")
        if not expected_output or (
            isinstance(expected_output, str) and not expected_output.strip()
        ):
            return self.create_error_response(
                error_message="expected_output 不能为空", error_code="INVALID_EXPECTED"
            )
        return None

    def require_client_with_error(self) -> DomainResponse | None:
        if not self.client:
            return self.create_error_response(
                error_message="此评估器需要 LLM 客户端，但未提供", error_code="CLIENT_REQUIRED"
            )
        if not hasattr(self.client, "chat"):
            return self.create_error_response(
                error_message="LLM 客户端缺少 chat 方法", error_code="INVALID_CLIENT"
            )
        return None

    def _tokenize_chinese(self, text: str) -> set[str]:
        from src.domain.services.text_analysis_service import text_analysis_service
        return text_analysis_service.tokenize_chinese(text)

    def _calculate_text_similarity(self, actual: str, expected: str) -> float:
        from src.domain.services.text_analysis_service import text_analysis_service
        return text_analysis_service.calculate_text_similarity(actual, expected)

    def _detect_entity_replacement(self, evidence: str, actual_output: str) -> float:
        from src.domain.services.text_analysis_service import text_analysis_service
        return text_analysis_service.detect_entity_replacement(evidence, actual_output)

    def _detect_over_inference(self, evidence: str, actual_output: str) -> float:
        from src.domain.services.text_analysis_service import text_analysis_service
        return text_analysis_service.detect_over_inference(evidence, actual_output)
