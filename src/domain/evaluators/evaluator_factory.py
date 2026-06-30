import logging
import threading
import warnings
from enum import Enum
from inspect import isclass
from queue import Queue
from typing import Any, Protocol

logger = logging.getLogger(__name__)

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

    _instance_pool: dict[str, Queue] = {}
    _pool_lock = threading.Lock()
    _max_pool_size = 10
    _pool_enabled = True

    _qa_manager: QualityAssuranceManager | None = None
    _quality_gate_enabled: bool = False
    _quality_gate_level: QualityGateLevel = QualityGateLevel.NORMAL

    @classmethod
    def set_pool_size(cls, size: int):
        """设置对象池最大容量"""
        cls._max_pool_size = max(1, size)

    @classmethod
    def enable_pool(cls):
        """启用对象池"""
        cls._pool_enabled = True

    @classmethod
    def disable_pool(cls):
        """禁用对象池（每次创建新实例）"""
        cls._pool_enabled = False

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
        force: bool = False,
    ):
        """评估器注册装饰器

        Args:
            name: 评估器名称
            strategy: 注册策略（SKIP/ERROR/OVERWRITE）
            force: 是否强制注册（绕过黑名单）
        """
        from src.domain.evaluators import _EVALUATOR_BLACKLIST

        def decorator(func: type[EvaluatorProtocol]) -> type[EvaluatorProtocol]:
            if name in _EVALUATOR_BLACKLIST and not force:
                logger.debug(f"评估器 '{name}' 在黑名单中，跳过注册")
                return func

            if isclass(func):
                if not issubclass(func, BaseEvaluator):
                    raise TypeError(
                        f"评估器类必须继承自 BaseEvaluator，当前类: {func.__name__}, "
                        f"基类: {[base.__name__ for base in func.__bases__]}"
                    )
                if (
                    hasattr(func, "__abstractmethods__")
                    and "_do_evaluate" in func.__abstractmethods__
                ):
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
    def _create_evaluator(
        cls, case_type: str, client: BaseLLMClient | None = None
    ) -> EvaluatorProtocol:
        """创建新的评估器实例"""
        with cls._lock:
            if case_type not in cls._registry:
                available_types = list(cls._registry.keys())
                raise DomainLogicError(f"类型 '{case_type}' 未找到。当前已注册: {available_types}")
            evaluator_cls = cls._registry[case_type]

        try:
            return evaluator_cls(client=client)
        except TypeError:
            try:
                return evaluator_cls()
            except TypeError:
                return evaluator_cls(client)

    @classmethod
    def get(cls, case_type: str, client: BaseLLMClient | None = None) -> EvaluatorProtocol:
        """
        🛡️ 获取评估器实例（支持对象池复用）
        不在此处施加熔断拦截，确保评估器实例能顺利生成并启用内部的 Fallback 兜底策略。
        """
        if not cls._pool_enabled:
            return cls._create_evaluator(case_type, client)

        with cls._pool_lock:
            if case_type not in cls._instance_pool:
                cls._instance_pool[case_type] = Queue(maxsize=cls._max_pool_size)

        pool = cls._instance_pool[case_type]

        try:
            evaluator = pool.get_nowait()
            logger.debug(f"从对象池获取评估器: {case_type}")
            return evaluator
        except Exception:
            evaluator = cls._create_evaluator(case_type, client)
            logger.debug(f"创建新评估器实例: {case_type}")
            return evaluator

    @classmethod
    def release(cls, case_type: str, evaluator: EvaluatorProtocol):
        """
        释放评估器实例回对象池
        """
        if not cls._pool_enabled:
            return

        pool = cls._instance_pool.get(case_type)
        if pool:
            try:
                pool.put_nowait(evaluator)
                logger.debug(f"评估器已归还对象池: {case_type}")
            except Exception:
                pass

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
            level = quality_gate_level or cls._quality_gate_level
            try:
                quality_result = cls._qa_manager.run_quality_gate(
                    module_name=case_type,
                    target_function=evaluator._do_evaluate,
                    source_code=cls._get_evaluator_source(case_type),
                    config=QualityGateConfig(level=level),
                )
                return evaluator, quality_result
            except Exception as e:
                logger.warning(f"质量门禁检查失败: {e}")
                return evaluator, None

        return evaluator, None

    @classmethod
    def _get_evaluator_source(cls, case_type: str) -> str | None:
        """获取评估器源代码（用于变异测试）"""
        import inspect

        with cls._lock:
            if case_type in cls._registry:
                evaluator_cls = cls._registry[case_type]
                try:
                    return inspect.getsource(evaluator_cls)
                except Exception:
                    return None
        return None

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
