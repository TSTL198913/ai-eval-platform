from typing import TYPE_CHECKING, Any, Optional, Protocol

from src.domain.models.base import BaseLLMClient


class EvaluatorProtocol(Protocol):
    """评估器协议 - 定义评估器必须实现的接口"""
    
    def evaluate(self, request: Any) -> Any:
        """评估方法"""
        ...
    
    def safe_evaluate(self, request: Any) -> Any:
        """安全评估方法"""
        ...


class EvaluatorFactory:
    _registry: dict[str, type[EvaluatorProtocol]] = {}

    @classmethod
    def register(cls, name: str):
        def decorator(func: type[EvaluatorProtocol]) -> type[EvaluatorProtocol]:
            cls._registry[name] = func
            return func

        return decorator

    @classmethod
    def get(cls, case_type: str, client: Optional[BaseLLMClient] = None) -> EvaluatorProtocol:
        if case_type not in cls._registry:
            available_types = list(cls._registry.keys())
            raise ValueError(f"领域 '{case_type}' 未找到。当前已注册: {available_types}")
        return cls._registry[case_type](client=client)

    @classmethod
    def list_evaluators(cls) -> list[str]:
        return sorted(list(cls._registry.keys()))

    @classmethod
    def get_evaluator_info(cls) -> list[dict]:
        info = []
        for name, evaluator_cls in cls._registry.items():
            info.append({
                "name": name,
                "class_name": evaluator_cls.__name__,
                "docstring": evaluator_cls.__doc__ or "",
            })
        return info
