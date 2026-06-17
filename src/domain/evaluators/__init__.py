import importlib
import os
import pkgutil
from typing import Any, Dict

from .evaluator_factory import EvaluatorFactory

_EVALUATOR_REGISTRY: Dict[str, Any] | None = None

IS_TESTING = os.environ.get("TESTING", "0") == "1"


def auto_discover():
    """自动发现并注册所有评估器"""
    global _EVALUATOR_REGISTRY
    if _EVALUATOR_REGISTRY is None:
        for _, name, _is_pkg in pkgutil.iter_modules(__path__):
            if name not in ["base", "metadata", "evaluator_factory"]:
                importlib.import_module(f".{name}", package=__name__)
        _EVALUATOR_REGISTRY = EvaluatorFactory._registry
    return _EVALUATOR_REGISTRY


def lazy_discover():
    """延迟发现评估器，确保在测试环境下也能正常工作"""
    return auto_discover()


# 始终调用 auto_discover 以确保评估器已注册
EVALUATOR_REGISTRY = auto_discover()
