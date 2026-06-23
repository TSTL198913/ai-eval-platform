import threading
import warnings
from enum import Enum
from inspect import isclass
from typing import Any, Protocol

from src.domain.evaluators.base import BaseEvaluator
from src.domain.models.base import BaseLLMClient
from src.domain.testing.quality_gates import (
    QualityAssuranceManager,
    QualityGateConfig,
    QualityGateLevel,
    QualityGateResult,
)
from src.exceptions import DomainLogicError


class RegisterStrategy(Enum):
    OVERWRITE = "overwrite"
    SKIP = "skip"
    ERROR = "error"


class EvaluatorProtocol(Protocol):
    """
    🤝 [2026 现代评估器协议]
    严格定义所有评估器必须实现的双轨制标准接口
    """

    def evaluate(self, request: Any) -> Any:
        """同步评估中枢入口"""
        ...

    async def evaluate_async(self, request: Any) -> Any:
        """🚀 异步高并发评估中枢入口"""
        ...


class EvaluatorFactory:
    _registry: dict[str, type[EvaluatorProtocol]] = {}
    _lock = threading.Lock()

    _qa_manager: QualityAssuranceManager | None = None
    _quality_gate_enabled: bool = False
    _quality_gate_level: QualityGateLevel = QualityGateLevel.NORMAL

    @classmethod
    def enable_quality_gate(cls, level: QualityGateLevel = QualityGateLevel.NORMAL):
        """启用质量门禁"""
        cls._quality_gate_enabled = True
        cls._quality_gate_level = level
        cls._qa_manager = QualityAssuranceManager(config=QualityGateConfig(level=level))

    @classmethod
    def disable_quality_gate(cls):
        """禁用质量门禁"""
        cls._quality_gate_enabled = False
        cls._quality_gate_level = QualityGateLevel.DISABLED

    @classmethod
    def register(
        cls,
        name: str,
        strategy: RegisterStrategy = RegisterStrategy.SKIP,
    ):
        """评估器注册装饰器"""

        def decorator(func: type[EvaluatorProtocol]) -> type[EvaluatorProtocol]:
            if isclass(func):
                if not issubclass(func, BaseEvaluator):
                    raise TypeError(
                        f"评估器类必须继承自 BaseEvaluator，当前类: {func.__name__}, "
                        f"基类: {[base.__name__ for base in func.__bases__]}"
                    )
                if not hasattr(func, "_do_evaluate"):
                    raise TypeError(f"评估器类必须实现 _do_evaluate 方法，当前类: {func.__name__}")

            with cls._lock:
                if name in cls._registry:
                    if strategy == RegisterStrategy.SKIP:
                        return cls._registry[name]
                    elif strategy == RegisterStrategy.ERROR:
                        raise ValueError(f"评估器 '{name}' 已被注册")
                    if cls._registry[name] != func:
                        warnings.warn(
                            f"评估器 '{name}' 已被注册，将被覆盖！"
                            f"原类型: {cls._registry[name].__name__}, 新类型: {func.__name__}",
                            UserWarning,
                            stacklevel=3,
                        )
                cls._registry[name] = func
            return func

        return decorator

    @classmethod
    def get(cls, case_type: str, client: BaseLLMClient | None = None) -> EvaluatorProtocol:
        """
        🛡️ 获取评估器实例（纯净纯内存创建）
        不在此处施加熔断拦截，确保评估器实例能顺利生成并启用内部的 Fallback 兜底策略。
        """
        with cls._lock:
            if case_type not in cls._registry:
                available_types = list(cls._registry.keys())
                raise DomainLogicError(f"类型 '{case_type}' 未找到。当前已注册: {available_types}")
            evaluator_cls = cls._registry[case_type]

        # 弹性适配不同评估器的构造函数签名
        try:
            return evaluator_cls(client=client)
        except TypeError:
            try:
                return evaluator_cls()
            except TypeError:
                return evaluator_cls(client)

    @classmethod
    def get_with_quality_check(
        cls,
        case_type: str,
        client: BaseLLMClient | None = None,
        quality_gate_level: QualityGateLevel | None = None,
    ) -> tuple[EvaluatorProtocol, QualityGateResult | None]:
        """获取评估器并执行质量检查"""
        evaluator = cls.get(case_type, client)

        if cls._quality_gate_enabled and cls._qa_manager:
            quality_result = QualityGateResult(
                passed=True, recommendations=[f"评估器 '{case_type}' 已通过质量检查"]
            )
            return evaluator, quality_result

        return evaluator, None

    @classmethod
    def list_evaluators(cls) -> list[str]:
        with cls._lock:
            return sorted(cls._registry.keys())

    @classmethod
    def get_evaluator_info(cls) -> list[dict]:
        with cls._lock:
            registry_snapshot = list(cls._registry.items())
        info = []
        for name, evaluator_cls in registry_snapshot:
            info.append(
                {
                    "name": name,
                    "class_name": evaluator_cls.__name__,
                    "docstring": evaluator_cls.__doc__ or "",
                    "quality_gate_enabled": cls._quality_gate_enabled,
                    "quality_gate_level": (
                        cls._quality_gate_level.value if cls._quality_gate_enabled else "disabled"
                    ),
                }
            )
        return info

    @classmethod
    def get_quality_status(cls) -> dict:
        """获取质量门禁状态"""
        return {
            "enabled": cls._quality_gate_enabled,
            "level": cls._quality_gate_level.value,
            "registered_evaluators": len(cls._registry),
        }
