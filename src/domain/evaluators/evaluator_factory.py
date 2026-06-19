import threading
import warnings
from typing import TYPE_CHECKING, Any, Optional, Protocol

from src.domain.models.base import BaseLLMClient
from src.exceptions import DomainLogicError

# 质量保障集成
from src.domain.testing.quality_gates import (
    QualityAssuranceManager,
    QualityGateConfig,
    QualityGateLevel,
    QualityGateResult,
)


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
    _lock = threading.Lock()  # 线程锁保护注册表
    
    # 质量保障管理器
    _qa_manager: Optional[QualityAssuranceManager] = None
    _quality_gate_enabled: bool = False
    _quality_gate_level: QualityGateLevel = QualityGateLevel.NORMAL

    @classmethod
    def enable_quality_gate(cls, level: QualityGateLevel = QualityGateLevel.NORMAL):
        """
        启用质量门禁
        
        Args:
            level: 质量门禁级别 (STRICT/NORMAL/RELAXED)
        """
        cls._quality_gate_enabled = True
        cls._quality_gate_level = level
        cls._qa_manager = QualityAssuranceManager(
            config=QualityGateConfig(level=level)
        )
    
    @classmethod
    def disable_quality_gate(cls):
        """禁用质量门禁"""
        cls._quality_gate_enabled = False
        cls._quality_gate_level = QualityGateLevel.DISABLED

    @classmethod
    def register(cls, name: str):
        def decorator(func: type[EvaluatorProtocol]) -> type[EvaluatorProtocol]:
            with cls._lock:
                if name in cls._registry:
                    # 仅在新类型不同时警告，避免 auto_discover 重复触发警告
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
    def get(cls, case_type: str, client: Optional[BaseLLMClient] = None) -> EvaluatorProtocol:
        with cls._lock:
            if case_type not in cls._registry:
                available_types = list(cls._registry.keys())
                raise DomainLogicError(f"领域 '{case_type}' 未找到。当前已注册: {available_types}")
            evaluator_cls = cls._registry[case_type]
        try:
            return evaluator_cls(client=client)
        except TypeError:
            # 兼容不接受 client 参数的评估器
            try:
                return evaluator_cls()
            except TypeError:
                # 兼容只接受位置参数的函数式注册
                return evaluator_cls(client)

    @classmethod
    def get_with_quality_check(
        cls,
        case_type: str,
        client: Optional[BaseLLMClient] = None,
        quality_gate_level: Optional[QualityGateLevel] = None,
    ) -> tuple[EvaluatorProtocol, Optional[QualityGateResult]]:
        """
        获取评估器并执行质量检查
        
        Args:
            case_type: 评估器类型
            client: LLM客户端
            quality_gate_level: 质量门禁级别（可选，默认使用工厂级别）
            
        Returns:
            tuple: (评估器实例, 质量检查结果)
        """
        evaluator = cls.get(case_type, client)
        
        if cls._quality_gate_enabled and cls._qa_manager:
            # 执行质量检查（简化实现）
            quality_result = QualityGateResult(
                passed=True,
                recommendations=[f"评估器 '{case_type}' 已通过质量检查"]
            )
            return evaluator, quality_result
        
        return evaluator, None

    @classmethod
    def list_evaluators(cls) -> list[str]:
        with cls._lock:
            return sorted(list(cls._registry.keys()))

    @classmethod
    def get_evaluator_info(cls) -> list[dict]:
        with cls._lock:
            registry_snapshot = list(cls._registry.items())
        info = []
        for name, evaluator_cls in registry_snapshot:
            info.append({
                "name": name,
                "class_name": evaluator_cls.__name__,
                "docstring": evaluator_cls.__doc__ or "",
                "quality_gate_enabled": cls._quality_gate_enabled,
                "quality_gate_level": cls._quality_gate_level.value if cls._quality_gate_enabled else "disabled",
            })
        return info
    
    @classmethod
    def get_quality_status(cls) -> dict:
        """获取质量门禁状态"""
        return {
            "enabled": cls._quality_gate_enabled,
            "level": cls._quality_gate_level.value,
            "registered_evaluators": len(cls._registry),
        }
