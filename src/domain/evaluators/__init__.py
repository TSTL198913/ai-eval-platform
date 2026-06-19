import importlib
import os
import pkgutil
import sys
from typing import Any, Dict

from .evaluator_factory import EvaluatorFactory

_EVALUATOR_REGISTRY: Dict[str, Any] | None = None

IS_TESTING = os.environ.get("TESTING", "0") == "1"

# 不应自动发现的子模块
_SKIP_MODULES = {"base", "metadata", "evaluator_factory"}


def auto_discover(force: bool = False):
    """自动发现并注册所有评估器

    Args:
        force: 强制重新发现（清除 sys.modules 缓存后重新 import）
    """
    global _EVALUATOR_REGISTRY
    if force:
        # 清除已加载的评估器模块，强制重新 import
        to_remove = [
            name
            for name in list(sys.modules.keys())
            if name.startswith("src.domain.evaluators.")
            and name != "src.domain.evaluators"
            and name.split(".")[-1] not in _SKIP_MODULES
        ]
        for name in to_remove:
            del sys.modules[name]
        _EVALUATOR_REGISTRY = None

    if _EVALUATOR_REGISTRY is None:
        for _, name, _is_pkg in pkgutil.iter_modules(__path__):
            if name not in _SKIP_MODULES:
                importlib.import_module(f".{name}", package=__name__)
        _EVALUATOR_REGISTRY = EvaluatorFactory._registry
    return _EVALUATOR_REGISTRY


def lazy_discover():
    """延迟发现评估器，确保在测试环境下也能正常工作"""
    return auto_discover()


# 始终调用 auto_discover 以确保评估器已注册
EVALUATOR_REGISTRY = auto_discover()
