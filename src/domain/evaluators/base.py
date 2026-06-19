from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Optional

from src.domain.evaluators.evaluator_factory import EvaluatorFactory
from src.exceptions import BasePlatformError
from src.schemas.evaluation import DomainResponse, EvaluationSchema

if TYPE_CHECKING:
    from src.domain.models.base import BaseLLMClient


class BaseEvaluator(ABC):
    def __init__(self, client: Optional["BaseLLMClient"] = None):
        self.client = client

    @abstractmethod
    def evaluate(self, request: EvaluationSchema) -> DomainResponse:
        """子类实现评测逻辑，禁止返回 None。"""
        pass

    def get_payload_data(self, request: Any, key: str, default: Any = None) -> Any:
        return request.payload.get(key, default)

    def get_input_text(self, request: EvaluationSchema, default: str = "") -> str:
        """兼容 user_input / text 两种字段命名。"""
        return (
            self.get_payload_data(request, "user_input")
            or self.get_payload_data(request, "text")
            or default
        )

    def require_client(self) -> DomainResponse | None:
        if not self.client:
            return DomainResponse(is_valid=False, error="LLM client 未配置")
        return None

    def safe_evaluate(self, request: EvaluationSchema) -> DomainResponse:
        try:
            response = self.evaluate(request)
            if response is None:
                return DomainResponse(is_valid=False, error="EVALUATION_ERROR: Evaluator returned None unexpectedly.")
            return response
        except BasePlatformError:
            raise
        except Exception as e:
            logger = __import__('logging').getLogger(__name__)
            logger.error(f"Evaluation execution error for {request.type}: {e}", exc_info=True)
            return DomainResponse(is_valid=False, error=f"EVALUATION_ERROR: {str(e)}")
