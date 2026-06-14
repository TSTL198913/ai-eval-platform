from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Optional

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
                return DomainResponse(is_valid=False, error="Evaluator returned None unexpectedly.")
            return response
        except Exception as e:
            return DomainResponse(is_valid=False, error=f"Evaluation execution error: {str(e)}")


class EvaluatorFactory:
    _registry = {}

    @classmethod
    def register(cls, name):
        def decorator(func):
            cls._registry[name] = func
            return func

        return decorator

    @classmethod
    def get(cls, case_type: str, client: Optional["BaseLLMClient"] = None) -> Any:
        if case_type not in cls._registry:
            available_types = list(cls._registry.keys())
            raise ValueError(f"领域 '{case_type}' 未找到。当前已注册: {available_types}")
        return cls._registry[case_type](client=client)
